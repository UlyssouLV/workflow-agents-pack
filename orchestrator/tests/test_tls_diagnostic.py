"""TLS / domaine + diagnostic CLI (ADR 0011, #94)."""

import os
import re
from pathlib import Path

from helpers_pack import ecrire_cle, lire_config, passe


def test_avec_domaine_caddy_prend_le_chemin_https_lets_encrypt(home, depot_pack):
    instance = passe(home, depot_pack)
    ecrire_cle(instance, "exposition", True)
    ecrire_cle(instance, "domaine", "cockpit.exemple.test")
    passe(home, depot_pack)

    caddyfile = (instance / "Caddyfile").read_text()
    assert "cockpit.exemple.test" in caddyfile
    assert "reverse_proxy runtime:8787" in caddyfile
    # Pas de mode HTTP public clair : le site est nommé (TLS auto Caddy / Let’s Encrypt).
    assert not re.search(r"^:80\b", caddyfile, re.MULTILINE)
    compose = (instance / "compose.yaml").read_text()
    assert "./caddy-data:/data" in compose
    caddy = re.search(r"caddy:.*?(?=\n  \S|\Z)", compose, re.S)
    assert caddy is not None
    ports = caddy.group(0)
    assert '"80:80"' in ports
    assert '"443:443"' in ports
    assert "127.0.0.1" not in ports.split("ports:", 1)[1].split("volumes:", 1)[0]


def test_cli_domaine_regenerer_caddyfile_https(home, depot_pack, faux_docker, capsys):
    from wap_runtime.cli import main

    passe(home, depot_pack)
    assert main(["exposition", "on"]) == 0
    capsys.readouterr()

    assert main(["domaine", "cockpit.exemple.test"]) == 0
    assert "OK — domaine" in capsys.readouterr().out
    assert lire_config(home / ".wap-runtime")["domaine"] == "cockpit.exemple.test"
    caddyfile = (home / ".wap-runtime" / "Caddyfile").read_text()
    assert "cockpit.exemple.test {" in caddyfile
    assert not re.search(r"^:80\b", caddyfile, re.MULTILINE)


def test_cli_domaine_invalide_refuse_le_chemin(home, depot_pack, faux_docker, capsys):
    from wap_runtime.cli import main

    passe(home, depot_pack)
    assert main(["domaine", "../etc/passwd"]) == 1
    assert "domaine invalide" in capsys.readouterr().out
    assert lire_config(home / ".wap-runtime").get("domaine", "") in ("", None)


def test_diagnostic_separe_instance_et_operateur(home, depot_pack, faux_docker, capsys):
    from wap_runtime.cli import main
    from wap_runtime.identifiants_cockpit import definir as definir_identifiants

    instance = passe(home, depot_pack)
    definir_identifiants(instance, "ops", "mot-de-passe-assez-long")
    assert main(["exposition", "on"]) == 0
    assert main(["domaine", "cockpit.exemple.test"]) == 0
    capsys.readouterr()

    # Faux docker : `compose ps` → Caddy running (script enrichi pour ce test).
    bin_dir = Path(os.environ["PATH"].split(os.pathsep)[0])
    docker = bin_dir / "docker"
    journal = home.parent / "docker-diag.log"
    docker.write_text(
        f"""#!/bin/sh
echo "$*" >> "{journal}"
if echo "$*" | grep -q "compose.*ps"; then
  echo 'caddy running'
  exit 0
fi
exit 0
"""
    )
    docker.chmod(0o755)

    assert main(["diagnostic"]) == 0
    sortie = capsys.readouterr().out
    assert "Côté instance" in sortie
    assert "OK — Caddy" in sortie
    assert "OK — ports 80/443" in sortie
    assert "OK — identifiants cockpit" in sortie
    assert "Côté opérateur" in sortie
    assert "DNS" in sortie
    assert "NAT" in sortie
    assert "CGNAT" in sortie


def test_diagnostic_signale_reste_instance_sans_domaine(home, depot_pack, faux_docker, capsys):
    from wap_runtime.cli import main
    from wap_runtime.identifiants_cockpit import definir as definir_identifiants

    instance = passe(home, depot_pack)
    definir_identifiants(instance, "ops", "mot-de-passe-assez-long")
    assert main(["exposition", "on"]) == 0
    capsys.readouterr()

    code = main(["diagnostic"])
    sortie = capsys.readouterr().out
    assert code == 1
    assert "KO — aucun domaine" in sortie or "domaine" in sortie.lower()
    assert "HTTP public" in sortie or "non supporté" in sortie
    assert "Côté opérateur" in sortie


def _diagnostic_expo_caddy_ko(home, depot_pack, monkeypatch, capsys, occupes):
    """Expo + domaine, Caddy pas up (faux docker muet), ports sondés simulés."""
    from wap_runtime import diagnostic
    from wap_runtime.cli import main
    from wap_runtime.identifiants_cockpit import definir as definir_identifiants

    instance = passe(home, depot_pack)
    definir_identifiants(instance, "ops", "mot-de-passe-assez-long")
    assert main(["exposition", "on"]) == 0
    assert main(["domaine", "cockpit.exemple.test"]) == 0
    capsys.readouterr()
    monkeypatch.setattr(diagnostic, "_port_ecoute", lambda port: port in occupes)
    code = main(["diagnostic"])
    return code, capsys.readouterr().out


def test_diagnostic_signale_80_occupe_par_un_autre_processus(
    home, depot_pack, faux_docker, monkeypatch, capsys
):
    code, sortie = _diagnostic_expo_caddy_ko(home, depot_pack, monkeypatch, capsys, {80})
    assert code == 1
    assert "KO — port 80 occupé par un autre processus" in sortie
    assert "port 443 occupé" not in sortie
    assert "ss -ltnp" in sortie


def test_diagnostic_signale_443_occupe_par_un_autre_processus(
    home, depot_pack, faux_docker, monkeypatch, capsys
):
    code, sortie = _diagnostic_expo_caddy_ko(home, depot_pack, monkeypatch, capsys, {80, 443})
    assert code == 1
    assert "KO — port 80 occupé" in sortie
    assert "KO — port 443 occupé" in sortie


def test_diagnostic_caddy_up_ne_prend_pas_ses_ports_pour_un_conflit(
    home, depot_pack, faux_docker, monkeypatch, capsys
):
    from wap_runtime import diagnostic
    from wap_runtime.cli import main
    from wap_runtime.identifiants_cockpit import definir as definir_identifiants

    instance = passe(home, depot_pack)
    definir_identifiants(instance, "ops", "mot-de-passe-assez-long")
    assert main(["exposition", "on"]) == 0
    assert main(["domaine", "cockpit.exemple.test"]) == 0
    capsys.readouterr()
    monkeypatch.setattr(diagnostic, "_caddy_tourne", lambda instance: True)
    monkeypatch.setattr(diagnostic, "_port_ecoute", lambda port: True)

    assert main(["diagnostic"]) == 0
    assert "occupé" not in capsys.readouterr().out


# `/proc/net/tcp` : :80 en LISTEN (0A) sur l’IP publique, :443 en TIME_WAIT (06).
PROC_NET_TCP = """\
  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode
   0: 0A00000A:0050 00000000:0000 0A 00000000:00000000 00:00000000 00000000     0        0 1
   1: 0100007F:01BB 0100007F:9C40 06 00000000:00000000 00:00000000 00000000     0        0 0
"""


def test_port_ecoute_lit_les_sockets_en_ecoute_sur_toutes_les_adresses(tmp_path):
    from wap_runtime.diagnostic import _port_ecoute

    (tmp_path / "tcp").write_text(PROC_NET_TCP)

    assert _port_ecoute(80, tmp_path)
    assert not _port_ecoute(443, tmp_path)


def test_port_ecoute_lit_aussi_tcp6(tmp_path):
    from wap_runtime.diagnostic import _port_ecoute

    (tmp_path / "tcp").write_text(PROC_NET_TCP.splitlines()[0] + "\n")
    (tmp_path / "tcp6").write_text(
        PROC_NET_TCP.splitlines()[0] + "\n"
        "   0: 00000000000000000000000000000000:01BB 00000000000000000000000000000000:0000 0A"
        " 00000000:00000000 00:00000000 00000000     0        0 1\n"
    )

    assert _port_ecoute(443, tmp_path)
    assert not _port_ecoute(80, tmp_path)


def test_diagnostic_expo_off_pas_d_alerte_80_443(
    home, depot_pack, faux_docker, monkeypatch, capsys
):
    from wap_runtime import diagnostic
    from wap_runtime.cli import main
    from wap_runtime.identifiants_cockpit import definir as definir_identifiants

    instance = passe(home, depot_pack)
    definir_identifiants(instance, "ops", "mot-de-passe-assez-long")
    capsys.readouterr()
    monkeypatch.setattr(diagnostic, "_port_ecoute", lambda port: True)

    assert main(["diagnostic"]) == 0
    assert "occupé" not in capsys.readouterr().out
