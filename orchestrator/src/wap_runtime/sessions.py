"""Sessions des agents : `jobs/<id>/session.json` (spec 0.4.0, « Enregistrement »).

Le runner les crée et les clôt ; le `runtime` les lit (l’instance lui est montée en lecture
seule). Rien n’est supprimé automatiquement.

`python -m wap_runtime.sessions <jobs> <id> <commande…>` : lancé dans la session tmux, exécute
l’agent puis clôt la session selon son code de sortie.
"""

import json
import re
import secrets
import signal
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from wap_runtime.fichiers import remplacer

OUVERTE, TERMINEE, ECHOUEE = "ouverte", "terminée", "échouée"
# Code de sortie d’un agent arrêté par **Terminer** (SIGHUP), comme le rend un shell.
CODE_ARRETEE = 128 + signal.SIGHUP
_ID = re.compile(r"[0-9]{8}-[0-9]{6}-[0-9a-f]{6}")


class Sessions:
    def __init__(
        self, jobs: Path, horloge: Callable[[], datetime] = lambda: datetime.now(timezone.utc)
    ):
        self.jobs = jobs
        self._horloge = horloge

    def creer(self, repo: str, ticket: int, agent: str, commande: str) -> dict:
        debut = self._horloge()
        session = {
            "id": f"{debut:%Y%m%d-%H%M%S}-{secrets.token_hex(3)}",
            "repo": repo,
            "ticket": ticket,
            "agent": agent,
            "commande": commande,
            "debut": debut.isoformat(),
            "fin": None,
            "etat": OUVERTE,
            "code_sortie": None,
        }
        (self.jobs / session["id"]).mkdir(parents=True)
        self._ecrire(session)
        return session

    def lire(self, id_: str) -> dict | None:
        """`None` si `id_` n’est pas un identifiant de session ou n’existe pas."""
        if not _ID.fullmatch(id_):
            return None
        try:
            return json.loads((self.jobs / id_ / "session.json").read_text())
        except (OSError, ValueError):
            return None

    def toutes(self) -> list[dict]:
        """De la plus récente à la plus ancienne (l’identifiant commence par le début)."""
        if not self.jobs.is_dir():
            return []
        lues = (self.lire(d.name) for d in sorted(self.jobs.iterdir(), reverse=True))
        return [s for s in lues if s is not None]

    def ouverte(self) -> dict | None:
        """La session ouverte de l’instance : une seule à la fois (ADR 0004)."""
        return next((s for s in self.toutes() if s["etat"] == OUVERTE), None)

    def clore(self, id_: str, code: int) -> dict:
        """Une session déjà close garde son état final."""
        if (lue := self.lire(id_))["etat"] != OUVERTE:
            return lue
        session = {
            **lue,
            "fin": self._horloge().isoformat(),
            "etat": TERMINEE if code == 0 else ECHOUEE,
            "code_sortie": code,
        }
        self._ecrire(session)
        return session

    def _ecrire(self, session: dict) -> None:
        # Le `runtime` lit ce fichier pendant que le runner le réécrit.
        contenu = json.dumps(session, ensure_ascii=False, indent=2) + "\n"
        remplacer(self.jobs / session["id"] / "session.json", contenu, 0o644)


def executer(jobs: Path, id_: str, commande: list[str]) -> int:
    """L’agent hérite du terminal (tmux) ; rend son code de sortie, une fois la session close.

    **Terminer** ferme la session tmux : SIGHUP arrête l’agent, et l’exécuteur, qui y survit,
    clôt la session (un agent tué par un signal sort en `128 + signal`).
    """
    agent: subprocess.Popen | None = None
    arretee = False

    def arreter(*_) -> None:
        nonlocal arretee
        arretee = True
        if agent is not None:
            agent.send_signal(signal.SIGHUP)

    # Un gestionnaire, pas SIG_IGN : l’agent, lui, garde le comportement par défaut.
    signal.signal(signal.SIGHUP, arreter)
    try:
        agent = subprocess.Popen(commande)
    except OSError as erreur:
        print(f"KO — {commande[0]} : {erreur}", file=sys.stderr)
        code = 127
    else:
        if arretee:
            # Terminé avant que l’agent ne démarre.
            agent.send_signal(signal.SIGHUP)
        code = agent.wait()
        code = 128 - code if code < 0 else code
    Sessions(jobs).clore(id_, code)
    return code


if __name__ == "__main__":
    sys.exit(executer(Path(sys.argv[1]), sys.argv[2], sys.argv[3:]))
