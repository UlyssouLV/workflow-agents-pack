"""Unité systemd `wap-runtime.service` : au démarrage du serveur, `update` puis Compose.

Calquée sur `argos.service` d’ArgOS : `oneshot` qui reste actif, après Docker et le
réseau. `ExecStartPre=-+` lance `wap-runtime update` en root, et son échec ou son
« rien à faire » (code 2) n’empêche pas le démarrage. Seuls `runtime` et `runner`
décident du succès ; Caddy démarre ensuite sans bloquer (80/443 pris sur un hôte
partagé). `setup` l’écrit et l’active sans la démarrer (Compose tourne déjà),
`update` la régénère depuis le nouveau paquet ; `uninstall` l’arrête et la retire.
"""

import os
import subprocess
from pathlib import Path
from typing import Mapping

from wap_runtime.instance import chemin_instance
from wap_runtime.socle import LIEN_COMMANDE, UTILISATEUR, resoudre

NOM_UNITE = "wap-runtime.service"
CHEMIN_UNITE = Path("/etc/systemd/system") / NOM_UNITE
# Chemin de l’unité pour `update --unite-seule` : par l’environnement, jamais par argv.
ENV_UNITE = "WAP_UNITE"
# Relances bornées : au plus 5 essais en 10 minutes, puis l’unité reste en échec.
RELANCES = 5
FENETRE_RELANCES_S = 600


def contenu_unite(instance: Path, utilisateur: str, commande: Path, docker: str) -> str:
    return f"""[Unit]
Description=wap-runtime : mise à jour puis démarrage de l’instance
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target
StartLimitBurst={RELANCES}
StartLimitIntervalSec={FENETRE_RELANCES_S}

[Service]
Type=oneshot
RemainAfterExit=yes
User={utilisateur}
WorkingDirectory={instance}
ExecStartPre=-+{commande} update
ExecStart={docker} compose up -d --wait runtime runner
ExecStartPost=-{docker} compose up -d
ExecStop={docker} compose down
TimeoutStartSec=infinity
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
"""


def ecrire_unite(
    home: Path,
    unite: Path = CHEMIN_UNITE,
    commande: Path = LIEN_COMMANDE,
    env: Mapping[str, str] = os.environ,
) -> None:
    """Unité de l’instance de `home`, avec le `docker` de l’hôte (`setup` et `update`)."""
    docker = resoudre("docker", env, home) or "docker"
    installer_unite(unite, contenu_unite(chemin_instance(home), UTILISATEUR, commande, docker), env)


def installer_unite(unite: Path, contenu: str, env: Mapping[str, str] = os.environ) -> None:
    """Écrit l’unité si elle diffère, recharge systemd et l’active ; idempotent."""
    if not (unite.exists() and unite.read_text() == contenu):
        unite.parent.mkdir(parents=True, exist_ok=True)
        unite.write_text(contenu)
    for arguments in (["daemon-reload"], ["enable", NOM_UNITE]):
        subprocess.run(["systemctl", *arguments], check=True, env=dict(env), stdin=subprocess.DEVNULL)


def retirer_unite(unite: Path) -> bool:
    """Arrête, désactive et supprime l’unité si elle existe ; rend `True` s’il l’a retirée."""
    if not unite.exists():
        return False
    subprocess.run(["systemctl", "disable", "--now", NOM_UNITE], check=True, stdin=subprocess.DEVNULL)
    unite.unlink()
    subprocess.run(["systemctl", "daemon-reload"], check=True, stdin=subprocess.DEVNULL)
    return True
