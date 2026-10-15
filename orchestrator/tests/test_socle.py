"""Socle de la machine hôte : plateforme, plan d’installation, exécution journalisée."""

import os
from pathlib import Path

import pytest

from wap_runtime.socle import (
    PlateformeNonSupportee,
    installer_socle,
    lire_plateforme,
    planifier,
)

DEBIAN_12 = 'PRETTY_NAME="Debian GNU/Linux 12 (bookworm)"\nID=debian\nVERSION_ID="12"\nVERSION_CODENAME=bookworm\n'
UBUNTU_2204 = 'NAME="Ubuntu"\nID=ubuntu\nID_LIKE=debian\nVERSION_ID="22.04"\nVERSION_CODENAME=jammy\n'

TOUT_PRESENT = ("git", "docker", "gh", "claude", "agent", "curl")


def os_release(tmp_path: Path, contenu: str) -> Path:
    chemin = tmp_path / "os-release"
    chemin.write_text(contenu)
    return chemin


class Machine:
    """PATH temporaire de faux binaires, `id` qui joue l’utilisateur `orchestrator`."""

    def __init__(self, tmp_path: Path):
        self.racine = tmp_path
        self.bin = tmp_path / "bin"
        self.bin.mkdir()
        self.appels = tmp_path / "appels.log"
        self.home_orchestrator = tmp_path / "home-orchestrator"
        self.env = {"PATH": str(self.bin)}

    def binaire(self, nom: str, script: str = "exit 0") -> None:
        chemin = self.bin / nom
        chemin.write_text(
            f'#!/bin/sh\necho "{nom} $* [DEBIAN_FRONTEND=$DEBIAN_FRONTEND]" >> "{self.appels}"\n{script}\n'
        )
        chemin.chmod(0o755)

    def binaires(self, *noms: str) -> None:
        for nom in noms:
            self.binaire(nom)

    def utilisateur(self, groupes: str = "orchestrator docker") -> None:
        self.binaire(
            "id",
            f'[ "$2" = orchestrator ] || exit 1\n[ "$1" = -nG ] && echo "{groupes}"\nexit 0',
        )

    def plan(self, contenu: str = DEBIAN_12):
        return planifier(
            os_release(self.racine, contenu),
            env=self.env,
            home_orchestrator=self.home_orchestrator,
        )

    def installer(self, contenu: str = DEBIAN_12, **env) -> int:
        return installer_socle(
            os_release(self.racine, contenu),
            journal=self.racine / "log" / "install.log",
            env={**self.env, **env},
            home_orchestrator=self.home_orchestrator,
        )

    @property
    def journal(self) -> str:
        return (self.racine / "log" / "install.log").read_text()


@pytest.fixture
def machine(tmp_path) -> Machine:
    return Machine(tmp_path)


def noms(plan) -> list[str]:
    return [etape.nom for etape in plan]


# — Plateforme —


@pytest.mark.parametrize("contenu", [DEBIAN_12, UBUNTU_2204])
def test_plateformes_supportees(tmp_path, contenu):
    plateforme = lire_plateforme(os_release(tmp_path, contenu))
    assert plateforme.id in ("debian", "ubuntu")
    assert plateforme.codename in ("bookworm", "jammy")


def test_debian_13_et_ubuntu_24_04_sont_supportees(tmp_path):
    lire_plateforme(os_release(tmp_path, "ID=debian\nVERSION_ID=13\nVERSION_CODENAME=trixie\n"))
    lire_plateforme(os_release(tmp_path, 'ID=ubuntu\nVERSION_ID="24.04"\nVERSION_CODENAME=noble\n'))


@pytest.mark.parametrize(
    "contenu",
    [
        "ID=debian\nVERSION_ID=11\nVERSION_CODENAME=bullseye\n",
        'ID=ubuntu\nVERSION_ID="20.04"\nVERSION_CODENAME=focal\n',
        'ID=fedora\nVERSION_ID="40"\n',
        "ID=debian\nVERSION_CODENAME=trixie\n",  # testing : pas de VERSION_ID
    ],
)
def test_plateforme_non_supportee(tmp_path, contenu):
    with pytest.raises(PlateformeNonSupportee, match="Debian 12\\+ / Ubuntu 22.04\\+"):
        lire_plateforme(os_release(tmp_path, contenu))


def test_os_release_absent(tmp_path):
    with pytest.raises(PlateformeNonSupportee):
        lire_plateforme(tmp_path / "absent")


def test_plateforme_non_supportee_arrete_sans_rien_executer(machine, capsys):
    machine.binaire("apt-get")

    assert machine.installer('ID=fedora\nVERSION_ID="40"\n') != 0

    assert "Debian 12+ / Ubuntu 22.04+" in capsys.readouterr().out
    assert not machine.appels.exists()


# — Plan —


def test_tout_present_plan_vide(machine):
    machine.binaires(*TOUT_PRESENT)
    machine.utilisateur()

    assert machine.plan() == []


def test_machine_nue_plan_complet_dans_l_ordre(machine):
    assert noms(machine.plan()) == [
        "git",
        "docker",
        "gh",
        "utilisateur orchestrator",
        "groupe docker",
        "curl",
        "claude",
        "agent",
    ]


@pytest.mark.parametrize(
    "absent, etape, attendu",
    [
        ("git", "git", "apt-get install -y git"),
        ("docker", "docker", "docker-compose-plugin"),
        ("gh", "gh", "https://cli.github.com/packages"),
        ("claude", "claude", "https://claude.ai/install.sh"),
        ("agent", "agent", "https://cursor.com/install"),
    ],
)
def test_chaque_binaire_absent_ajoute_exactement_son_etape(machine, absent, etape, attendu):
    machine.binaires(*(nom for nom in TOUT_PRESENT if nom != absent))
    machine.utilisateur()

    plan = machine.plan()

    assert noms(plan) == [etape]
    assert any(attendu in commande for commande in plan[0].commandes)


def test_docker_passe_par_le_depot_officiel_de_la_distribution(machine):
    machine.binaires(*(nom for nom in TOUT_PRESENT if nom != "docker"))
    machine.utilisateur()

    (docker,) = machine.plan(UBUNTU_2204)

    script = "\n".join(docker.commandes)
    assert "https://download.docker.com/linux/ubuntu jammy stable" in script
    assert "systemctl enable --now docker" in script
    assert docker.utilisateur is None


def test_plugin_compose_absent_ajoute_seulement_le_plugin(machine):
    machine.binaires(*(nom for nom in TOUT_PRESENT if nom != "docker"))
    machine.binaire("docker", '[ "$1" = compose ] && exit 1\nexit 0')
    machine.utilisateur()

    (etape,) = machine.plan()

    assert etape.nom == "plugin docker compose"
    script = "\n".join(etape.commandes)
    assert "apt-get install -y docker-compose-plugin" in script
    assert "docker-ce " not in script


def test_claude_et_agent_s_installent_pour_l_utilisateur_orchestrator(machine):
    machine.binaires("git", "docker", "gh", "curl")
    machine.utilisateur()

    plan = machine.plan()

    assert noms(plan) == ["claude", "agent"]
    assert all(etape.utilisateur == "orchestrator" for etape in plan)


def test_claude_et_agent_deja_installes_chez_orchestrator(machine):
    machine.binaires("git", "docker", "gh", "curl")
    machine.utilisateur()
    local_bin = machine.home_orchestrator / ".local" / "bin"
    local_bin.mkdir(parents=True)
    for nom in ("claude", "agent"):
        (local_bin / nom).write_text("#!/bin/sh\n")
        (local_bin / nom).chmod(0o755)

    assert machine.plan() == []


def test_utilisateur_absent_ajoute_creation_et_groupe_docker(machine):
    machine.binaires(*TOUT_PRESENT)

    plan = machine.plan()

    assert noms(plan) == ["utilisateur orchestrator", "groupe docker"]
    assert any("useradd" in c and "orchestrator" in c for c in plan[0].commandes)
    assert any("usermod -aG docker orchestrator" in c for c in plan[1].commandes)


def test_utilisateur_hors_du_groupe_docker(machine):
    machine.binaires(*TOUT_PRESENT)
    machine.utilisateur(groupes="orchestrator")

    assert noms(machine.plan()) == ["groupe docker"]


def test_curl_absent_n_est_installe_que_pour_les_installeurs_officiels(machine):
    machine.binaires("git", "docker", "gh", "claude", "agent")
    machine.utilisateur()

    assert machine.plan() == []


def test_aucune_etape_n_authentifie(machine):
    script = "\n".join(c for etape in machine.plan() for c in etape.commandes)
    assert "auth" not in script
    assert "login" not in script


# — Exécution —


def test_execution_installe_sans_interaction_et_journalise(machine, capsys):
    machine.binaires(*(nom for nom in TOUT_PRESENT if nom != "git"), "apt-get")
    machine.utilisateur()

    assert machine.installer() == 0

    assert "apt-get install -y git [DEBIAN_FRONTEND=noninteractive]" in machine.appels.read_text()
    assert "git" in machine.journal
    assert "OK" in capsys.readouterr().out


def test_plan_vide_ne_lance_rien(machine):
    machine.binaires(*TOUT_PRESENT, "apt-get")
    machine.utilisateur()

    assert machine.installer() == 0

    assert "apt-get" not in machine.appels.read_text()


def test_etape_utilisateur_passe_par_runuser(machine):
    machine.binaires("git", "docker", "gh", "curl", "agent", "bash")
    machine.utilisateur()
    machine.binaire("runuser", 'while [ "$1" != -- ]; do shift; done\nshift\nexec "$@"')

    assert machine.installer() == 0

    appels = machine.appels.read_text()
    assert "runuser -u orchestrator --" in appels
    assert "curl -fsSL https://claude.ai/install.sh" in appels


def test_echec_d_une_etape_nomme_l_etape_ecrit_le_log_et_sort_non_zero(machine, capsys):
    machine.binaires(*(nom for nom in TOUT_PRESENT if nom != "gh"), "apt-get", "install", "chmod", "dpkg", "mkdir", "tee")
    machine.utilisateur()
    machine.binaire("curl", 'echo "curl: (6) Could not resolve host" >&2\nexit 6')

    assert machine.installer() != 0

    sortie = capsys.readouterr().out
    assert "« gh »" in sortie
    assert str(machine.racine / "log" / "install.log") in sortie
    assert "Could not resolve host" in machine.journal
    assert "gh" in machine.journal and "échec" in machine.journal


def test_echec_arrete_les_etapes_suivantes(machine):
    machine.binaires("docker", "gh", "curl", "claude", "agent")
    machine.utilisateur()
    machine.binaire("apt-get", "exit 100")

    assert machine.installer() != 0

    assert machine.appels.read_text().count("apt-get") == 1


def test_wap_debug_rend_le_log_verbeux(machine):
    machine.binaires(*(nom for nom in TOUT_PRESENT if nom != "git"), "apt-get")
    machine.utilisateur()

    assert machine.installer() == 0
    normal = machine.journal
    (machine.racine / "log" / "install.log").unlink()

    assert machine.installer(WAP_DEBUG="1") == 0
    verbeux = machine.journal

    assert "+ apt-get install -y git" not in normal
    assert "+ apt-get install -y git" in verbeux
    assert "détecté" in verbeux and "détecté" not in normal
    assert len(verbeux) > len(normal)
