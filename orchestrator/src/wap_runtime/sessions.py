"""Sessions des agents : `jobs/<id>/session.json` (spec 0.4.0, « Enregistrement »).

Le runner les crée et les clôt ; le `runtime` les lit (l’instance lui est montée en lecture
seule). Rien n’est supprimé automatiquement.

`python -m wap_runtime.sessions <jobs> <id> [<clones>]` : lancé dans la session tmux, exécute l’agent
de la session sur son ticket en l’enregistrant (`wap_runtime.enregistrement`), copie sa transcription
puis clôt la session selon son code de sortie (avec son instantané si `<clones>` est donné).
"""

import fcntl
import json
import re
import secrets
import signal
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from wap_runtime.agents import agent_par_id, commande_agent
from wap_runtime.enregistrement import CAST, TRANSCRIPTION, copier_transcription, enregistrer
from wap_runtime.fichiers import remplacer

OUVERTE, TERMINEE, ECHOUEE, INTERROMPUE = "ouverte", "terminée", "échouée", "interrompue"
# Close par **Terminer** : un arrêt humain, pas un échec de l’agent.
ARRETEE = "arrêtée"
# Close par l’ouverture de la suivante (ADR 0006) : `suivante` la désigne.
ENCHAINEE = "enchaînée"
# Activité d’une session ouverte : hooks → `wap-runtime etat`.
INCONNUE, TRAVAILLE, ATTEND = "inconnue", "travaille", "attend"
# Code de sortie d’un agent arrêté par **Terminer** (SIGHUP), comme le rend un shell.
CODE_ARRETEE = 128 + signal.SIGHUP
ID_SESSION = re.compile(r"[0-9]{8}-[0-9]{6}-[0-9a-f]{6}")
# Verrou de `jobs/<id>/` : l’exécuteur (tmux) et le runner (**Terminer**) peuvent la clore ensemble.
VERROU = ".session.lock"


def publique(session: dict) -> dict:
    """Champs d’API : titre absent → nom de l’agent."""
    agent = agent_par_id(session["agent"])
    return {
        **session,
        "activite": session.get("activite") or INCONNUE,
        "skill": session.get("skill"),
        "titre": session.get("titre") or (agent.nom if agent else session["agent"]),
    }


class Sessions:
    def __init__(
        self,
        jobs: Path,
        horloge: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        clones: Path | None = None,
    ):
        """`clones` : le dossier des clones gérés (le runner) ; une session qui s’y ferme laisse
        son instantané (`wap_runtime.instantane`). Sans lui (le `runtime`, les lectures), aucun."""
        self.jobs = jobs
        self._horloge = horloge
        self._clones = clones

    def creer(
        self,
        repo: str,
        ticket: int | None,
        agent: str,
        commande: str,
        precedente: str | None = None,
        branche: str | None = None,
        modele: str | None = None,
    ) -> dict:
        """`ticket` nul : session libre. `precedente` : la session enchaînée qui ouvre celle-ci.

        `modele` : ID Cursor effectif, ou `None` (Auto / Claude).
        """
        debut = self._horloge()
        session = {
            "id": f"{debut:%Y%m%d-%H%M%S}-{secrets.token_hex(3)}",
            "repo": repo,
            "ticket": ticket,
            "branche": branche,
            "agent": agent,
            "commande": commande,
            "debut": debut.isoformat(),
            "fin": None,
            "etat": OUVERTE,
            "code_sortie": None,
            "precedente": precedente,
            "suivante": None,
            "activite": INCONNUE,
            "skill": None,
            "titre": None,
            "modele": modele,
        }
        (self.jobs / session["id"]).mkdir(parents=True)
        self._ecrire(session)
        return session

    def lire(self, id_: str) -> dict | None:
        """`None` si `id_` n’est pas un identifiant de session ou n’existe pas."""
        if not ID_SESSION.fullmatch(id_):
            return None
        try:
            lue = json.loads((self.jobs / id_ / "session.json").read_text())
        except (OSError, ValueError):
            return None
        # Écrite avant la 0.4.1 : hors de toute chaîne ; avant la 0.4.2 : pas de `branche` ni d’activité ;
        # avant la 0.5.1 : pas de modèle Cursor.
        return {
            "precedente": None,
            "suivante": None,
            "branche": None,
            "activite": INCONNUE,
            "skill": None,
            "titre": None,
            "modele": None,
            **lue,
        }

    def toutes(self) -> list[dict]:
        """De la plus récente à la plus ancienne (l’identifiant commence par le début)."""
        if not self.jobs.is_dir():
            return []
        lues = (self.lire(d.name) for d in sorted(self.jobs.iterdir(), reverse=True))
        return [s for s in lues if s is not None]

    def ouvertes(self) -> list[dict]:
        """Les sessions ouvertes, de la plus récente à la plus ancienne."""
        return [s for s in self.toutes() if s["etat"] == OUVERTE]

    def du_repo(self, slug: str) -> list[dict]:
        """Celles de `slug` (casse ignorée, comme GitHub), de la plus récente à la plus ancienne."""
        return [s for s in self.toutes() if s["repo"].lower() == slug.lower()]

    def ouverte(self, repo: str) -> dict | None:
        """La session ouverte de `repo` : au plus une par clone géré (ADR 0007)."""
        return next(
            (s for s in self.toutes() if s["etat"] == OUVERTE and s["repo"].lower() == repo.lower()),
            None,
        )

    def qui_travaille(self, sauf: str | None = None) -> dict | None:
        """Session ouverte d’activité *travaille*, hors `sauf` (lancement sur un autre repo)."""
        return next(
            (
                s
                for s in self.toutes()
                if s["etat"] == OUVERTE
                and s.get("activite") == TRAVAILLE
                and (sauf is None or s["repo"].lower() != sauf.lower())
            ),
            None,
        )

    def demander_arret(self, id_: str) -> None:
        """**Terminer**, avant de couper le terminal : la clôture qui suit rend la session `arrêtée`,
        quel que soit le code de sortie de l’agent. Une session close ne change pas."""
        with self._verrou(id_):
            if (lue := self.lire(id_)) is not None and lue["etat"] == OUVERTE:
                self._ecrire({**lue, "arret_demande": True})

    def clore(self, id_: str, code: int) -> dict:
        """Une session déjà close garde son état final ; une clôture en cours (l’instantané se prend)
        est attendue, puis rendue."""
        with self._verrou(id_):
            if (lue := self.lire(id_))["etat"] != OUVERTE:
                return lue
            fin = self._figer(lue)
            if lue.get("arret_demande"):
                etat = ARRETEE
            else:
                etat = TERMINEE if code == 0 else ECHOUEE
            session = {**lue, "fin": fin.isoformat(), "etat": etat, "code_sortie": code}
            self._ecrire(session)
            return session

    def enregistrer_etat(
        self,
        id_: str,
        activite: str | None = None,
        skill: str | None = None,
        prompt: str | None = None,
    ) -> dict:
        """Met à jour l’activité et/ou le skill d’une session ouverte.

        `activite` à `None` : ne change que le skill (outil `Skill` des hooks).
        Le premier `prompt` devient le titre.
        """
        if activite is not None and activite not in (TRAVAILLE, ATTEND):
            raise ValueError(f"activité inconnue : {activite}")
        if not ID_SESSION.fullmatch(id_) or not (self.jobs / id_).is_dir():
            raise ValueError(f"session {id_} close ou inconnue")
        with self._verrou(id_):
            session = self.lire(id_)
            if session is None or session["etat"] != OUVERTE:
                raise ValueError(f"session {id_} close ou inconnue")
            maj = {**session}
            if activite is not None:
                maj["activite"] = activite
            if skill:
                maj["skill"] = skill
            if prompt and session["titre"] is None:
                maj["titre"] = prompt
            self._ecrire(maj)
            return maj

    def enchainer(self, id_: str, suivante: str) -> dict:
        """La session ouverte `id_` passe `enchaînée` vers `suivante` ; l’exécuteur, en la clôturant
        ensuite, lui laisse cet état."""
        with self._verrou(id_):
            lue = self.lire(id_)
            fin = self._figer(lue)
            session = {**lue, "fin": fin.isoformat(), "etat": ENCHAINEE, "suivante": suivante}
            self._ecrire(session)
            return session

    def interrompre(self) -> list[dict]:
        """Au démarrage du runner : les sessions restées ouvertes n’ont plus d’agent (runner
        redémarré pendant la session) ; elles passent `interrompue`, ce qui libère leurs clones."""
        interrompues = []
        for session in self.toutes():
            if session["etat"] == OUVERTE:
                with self._verrou(session["id"]):
                    fin = self._figer(session)
                    session = {**session, "fin": fin.isoformat(), "etat": INTERROMPUE}
                    self._ecrire(session)
                interrompues.append(session)
        return interrompues

    @contextmanager
    def _verrou(self, id_: str):
        """Une lecture-écriture de `session.json` à la fois, entre processus : sans lui, **Terminer**
        clôt en parallèle de l’exécuteur (deux instantanés), ou un hook réécrit une session close."""
        with open(self.jobs / id_ / VERROU, "a") as verrou:
            fcntl.flock(verrou, fcntl.LOCK_EX)
            yield

    def _figer(self, session: dict) -> datetime:
        """L’instantané de la session qui se ferme, avant son état final : une session close a
        déjà le sien. Rend l’heure de fin."""
        fin = self._horloge()
        if self._clones is not None:
            from wap_runtime.instantane import prendre

            prendre(self._clones / session["repo"], self.jobs / session["id"], session["id"], fin)
        return fin

    def _ecrire(self, session: dict) -> None:
        # Le `runtime` lit ce fichier pendant que le runner le réécrit.
        contenu = json.dumps(session, ensure_ascii=False, indent=2) + "\n"
        remplacer(self.jobs / session["id"] / "session.json", contenu, 0o644)


def executer(jobs: Path, id_: str, clones: Path | None = None) -> int:
    """L’agent hérite de la taille et de la saisie du terminal (tmux) ; rend son code de sortie,
    une fois le terminal enregistré, la transcription copiée et la session close.

    La commande se déduit de la session (agent connu, ticket s’il y en a) : rien de la ligne
    de commande n’arrive aux arguments de l’agent."""
    if not ID_SESSION.fullmatch(id_):
        raise SystemExit(f"session invalide : {id_}")
    session = Sessions(jobs).lire(id_)
    if session is None or (agent := agent_par_id(session["agent"])) is None:
        raise SystemExit(f"session {id_} inconnue")
    ticket = None if session["ticket"] is None else int(session["ticket"])
    code = enregistrer(commande_agent(agent, ticket, session.get("modele")), jobs / id_ / CAST)
    depuis = datetime.fromisoformat(session["debut"]).timestamp()
    copier_transcription(session["agent"], Path.home(), depuis, jobs / id_ / TRANSCRIPTION)
    Sessions(jobs, clones=clones).clore(id_, code)
    return code


if __name__ == "__main__":
    sys.exit(executer(Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3]) if len(sys.argv) > 3 else None))
