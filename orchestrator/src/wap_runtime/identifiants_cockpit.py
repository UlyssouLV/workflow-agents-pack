"""Identifiants cockpit et sessions serveur de l’instance (ADR 0010).

Distinct de `wap-runtime auth` (GitHub / agents) : un seul login + hash par instance,
sessions serveur dans SQLite sous `~/.wap-runtime/`.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

from wap_runtime.fichiers import remplacer

FICHIER_IDENTIFIANTS = "cockpit-credentials.toml"
FICHIER_SESSIONS = "cockpit-sessions.sqlite"
DUREE_SESSION = timedelta(days=7)

# Paramètres scrypt raisonnables pour un mot de passe ops (stdlib, sans dépendance).
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 64
_MODE_SECRETS = 0o600


def chemin_identifiants(instance: Path) -> Path:
    return instance / FICHIER_IDENTIFIANTS


def chemin_sessions(instance: Path) -> Path:
    return instance / FICHIER_SESSIONS


def est_configure(instance: Path) -> bool:
    """Vrai seulement si un login et un hash sont présents et lisibles."""
    chemin = chemin_identifiants(instance)
    if not chemin.is_file():
        return False
    try:
        data = tomllib.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError, TypeError):
        return False
    login = data.get("login")
    password_hash = data.get("password_hash")
    return isinstance(login, str) and bool(login) and isinstance(password_hash, str) and bool(
        password_hash
    )


def definir(instance: Path, login: str, mot_de_passe: str) -> str:
    """Crée ou remplace les identifiants ; rend `"cree"` ou `"change"`.

    Un changement invalide toutes les sessions serveur de l’instance.
    """
    login = login.strip()
    if not login:
        raise ValueError("login vide")
    if not mot_de_passe:
        raise ValueError("mot de passe vide")
    deja = est_configure(instance)
    hash_ = _hasher(mot_de_passe)
    contenu = (
        f"login = {json.dumps(login)}\n"
        f"password_hash = {json.dumps(hash_)}\n"
    )
    remplacer(chemin_identifiants(instance), contenu, _MODE_SECRETS)
    if deja:
        invalider_toutes_les_sessions_serveur(instance)
        return "change"
    return "cree"


def verifier(instance: Path, login: str, mot_de_passe: str) -> bool:
    """Vrai si login + mot de passe correspondent aux identifiants stockés."""
    chemin = chemin_identifiants(instance)
    if not chemin.is_file():
        return False
    try:
        data = tomllib.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError, TypeError):
        return False
    if data.get("login") != login:
        return False
    stocke = data.get("password_hash")
    if not isinstance(stocke, str):
        return False
    return _verifier_hash(mot_de_passe, stocke)


def creer_session_serveur(
    instance: Path, *, maintenant: datetime | None = None
) -> str:
    """Enregistre une session serveur (~7 jours) ; rend son identifiant opaque."""
    maintenant = instant_utc(maintenant)
    id_ = secrets.token_urlsafe(32)
    expire = maintenant + DUREE_SESSION
    with _connexion(instance) as db:
        _schema(db)
        db.execute(
            "INSERT INTO sessions_serveur (id, created_at, expires_at) VALUES (?, ?, ?)",
            (id_, maintenant.isoformat(), expire.isoformat()),
        )
        db.commit()
    return id_


def session_serveur_valide(
    instance: Path, id_session: str, *, maintenant: datetime | None = None
) -> bool:
    """Vrai si la session serveur existe et n’a pas expiré."""
    if not id_session:
        return False
    maintenant = instant_utc(maintenant)
    with _connexion(instance) as db:
        _schema(db)
        ligne = db.execute(
            "SELECT expires_at FROM sessions_serveur WHERE id = ?", (id_session,)
        ).fetchone()
    if ligne is None:
        return False
    try:
        expire = datetime.fromisoformat(ligne[0])
    except (TypeError, ValueError):
        return False
    if expire.tzinfo is None:
        expire = expire.replace(tzinfo=timezone.utc)
    return maintenant < expire


def supprimer_session_serveur(instance: Path, id_session: str) -> None:
    with _connexion(instance) as db:
        _schema(db)
        db.execute("DELETE FROM sessions_serveur WHERE id = ?", (id_session,))
        db.commit()


def invalider_toutes_les_sessions_serveur(instance: Path) -> None:
    with _connexion(instance) as db:
        _schema(db)
        db.execute("DELETE FROM sessions_serveur")
        db.commit()


def instant_utc(quand: datetime | None = None) -> datetime:
    """Instant conscient du fuseau UTC (maintenant si `quand` est omis)."""
    if quand is None:
        return datetime.now(timezone.utc)
    if quand.tzinfo is None:
        return quand.replace(tzinfo=timezone.utc)
    return quand.astimezone(timezone.utc)


def _hasher(mot_de_passe: str) -> str:
    sel = secrets.token_bytes(16)
    derive = hashlib.scrypt(
        mot_de_passe.encode("utf-8"),
        salt=sel,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_SCRYPT_DKLEN,
    )
    return (
        f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}$"
        f"{sel.hex()}${derive.hex()}"
    )


def _verifier_hash(mot_de_passe: str, stocke: str) -> bool:
    parties = stocke.split("$")
    if len(parties) != 6 or parties[0] != "scrypt":
        return False
    try:
        n, r, p = int(parties[1]), int(parties[2]), int(parties[3])
        sel = bytes.fromhex(parties[4])
        attendu = bytes.fromhex(parties[5])
    except ValueError:
        return False
    try:
        derive = hashlib.scrypt(
            mot_de_passe.encode("utf-8"),
            salt=sel,
            n=n,
            r=r,
            p=p,
            dklen=len(attendu),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(derive, attendu)


def _connexion(instance: Path) -> sqlite3.Connection:
    chemin = chemin_sessions(instance)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(chemin)
    try:
        chemin.chmod(_MODE_SECRETS)
    except OSError:
        pass
    return db


def _schema(db: sqlite3.Connection) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions_serveur (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL
        )
        """
    )
