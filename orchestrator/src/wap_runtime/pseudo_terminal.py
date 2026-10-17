"""Pseudo-terminal relié à celui de l’utilisateur : `auth claude` (`claude setup-token`) et
l’exécuteur d’une session (`wap_runtime.enregistrement`)."""

import fcntl
import os
import termios
import tty


def controler() -> None:
    """Dans l’enfant (`preexec_fn`) : le pseudo-terminal devient son terminal de contrôle
    (^C, SIGWINCH)."""
    os.setsid()
    fcntl.ioctl(0, termios.TIOCSCTTY, 0)


def brut(fd: int) -> list | None:
    """Le terminal `fd` en mode brut (les touches vont telles quelles à l’enfant, qui gère
    l’écho) ; rend ses réglages d’avant, `None` hors d’un terminal."""
    if not os.isatty(fd):
        return None
    avant = termios.tcgetattr(fd)
    tty.setraw(fd, termios.TCSANOW)
    return avant


def restaurer(fd: int, avant: list | None) -> None:
    """Remet les réglages rendus par `brut` ; sans effet si le terminal est parti."""
    if avant is None:
        return
    try:
        termios.tcsetattr(fd, termios.TCSADRAIN, avant)
    except termios.error:
        pass
