"""Écriture des fichiers de l’instance que le runtime lit pendant qu’on les modifie."""

import os
from pathlib import Path


def remplacer(chemin: Path, contenu: str, mode: int) -> None:
    """Remplace `chemin` d’un coup : aucun lecteur ne voit un fichier à moitié écrit.

    Le fichier provisoire naît en `mode` (quel que soit l’umask) ; en root, il revient au
    propriétaire du dossier de l’instance.
    """
    provisoire = chemin.with_name(f".{chemin.name}.tmp")
    provisoire.unlink(missing_ok=True)
    descripteur = os.open(provisoire, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(descripteur, "w") as fichier:
        os.fchmod(fichier.fileno(), mode)
        fichier.write(contenu)
    if os.geteuid() == 0:
        proprio = chemin.parent.stat()
        os.chown(provisoire, proprio.st_uid, proprio.st_gid)
    os.replace(provisoire, chemin)
