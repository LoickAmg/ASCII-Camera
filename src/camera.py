"""Capture webcam/image et diffusion du flux converti en ASCII (dépend d'OpenCV)."""

from __future__ import annotations

import shutil
import sys
import time

import cv2

from .ascii_converter import frame_to_ansi, frame_to_ascii
from .settings import ASCII_CHARS, DEFAULT_FPS

CLEAR_SCREEN = "\x1b[H\x1b[J"


def terminal_width(default: int = 100) -> int:
    try:
        return shutil.get_terminal_size((default, 24)).columns
    except OSError:
        return default


def stream_webcam(
    camera_index: int = 0,
    width: int | None = None,
    color: bool = False,
    charset: str = ASCII_CHARS,
    mirror: bool = True,
    fps_limit: float = DEFAULT_FPS,
    normalize: bool = True,
) -> None:
    """Capture la webcam en continu et affiche le flux ASCII dans le terminal.

    Boucle jusqu'à interruption (Ctrl+C). `normalize=True` (par défaut) égalise
    l'histogramme de chaque image pour faire ressortir les détails dans les
    zones à faible contraste (peau, mur uni...) — désactivable si besoin.
    """
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        raise RuntimeError(f"Impossible d'ouvrir la caméra {camera_index}")

    render_width = width or terminal_width()
    frame_interval = 1.0 / fps_limit if fps_limit > 0 else 0.0

    try:
        while True:
            start = time.monotonic()
            ok, frame = cap.read()
            if not ok:
                raise RuntimeError("Échec de lecture de la caméra")

            if mirror:
                frame = cv2.flip(frame, 1)

            text = (
                frame_to_ansi(frame, width=render_width, charset=charset, normalize=normalize)
                if color
                else frame_to_ascii(frame, width=render_width, charset=charset, normalize=normalize)
            )
            sys.stdout.write(CLEAR_SCREEN + text + "\n")
            sys.stdout.flush()

            elapsed = time.monotonic() - start
            if frame_interval > elapsed:
                time.sleep(frame_interval - elapsed)
    except KeyboardInterrupt:
        pass
    finally:
        cap.release()


def convert_image_file(
    path: str,
    width: int = 100,
    charset: str = ASCII_CHARS,
    color: bool = False,
    normalize: bool = True,
) -> str:
    """Convertit un fichier image en texte ASCII (ou ANSI coloré)."""
    frame = cv2.imread(path)
    if frame is None:
        raise FileNotFoundError(f"Image introuvable ou illisible : {path}")

    if color:
        return frame_to_ansi(frame, width=width, charset=charset, normalize=normalize)
    return frame_to_ascii(frame, width=width, charset=charset, normalize=normalize)
