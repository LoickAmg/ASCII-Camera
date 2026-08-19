"""Capture webcam/image/vidéo et diffusion ou export du flux converti en ASCII
(dépend d'OpenCV)."""

from __future__ import annotations

import shutil
import sys
import time

import cv2
import numpy as np

from .ascii_converter import frame_to_ansi, frame_to_ascii, render_frame_to_image
from .settings import ASCII_CHARS, DEFAULT_CHAR_ASPECT, DEFAULT_FPS

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


def render_image_file(
    path: str,
    output_path: str,
    width: int = 100,
    charset: str = ASCII_CHARS,
    normalize: bool = True,
    color: bool = False,
    font_size: int = 12,
) -> None:
    """Convertit un fichier image en ASCII et sauvegarde le rendu en PNG.

    `color=True` peint chaque caractère avec la couleur d'origine du pixel ;
    sinon rendu monochrome (comme le mode terminal sans `--color`).
    """
    frame = cv2.imread(path)
    if frame is None:
        raise FileNotFoundError(f"Image introuvable ou illisible : {path}")

    image = render_frame_to_image(
        frame, width=width, charset=charset, normalize=normalize, font_size=font_size, colored=color
    )
    image.save(output_path)


def export_ascii_video(
    source: int | str,
    output_path: str,
    width: int = 100,
    charset: str = ASCII_CHARS,
    color: bool = True,
    normalize: bool = True,
    char_aspect: float = DEFAULT_CHAR_ASPECT,
    font_size: int = 10,
    fps: float | None = None,
    duration: float | None = None,
    mirror: bool = False,
) -> int:
    """Convertit une source vidéo (fichier, ou webcam limitée par `duration`) en
    une vidéo ASCII rendue image par image (concaténation des rendus PNG dans
    un flux vidéo via `cv2.VideoWriter`). Renvoie le nombre d'images écrites.

    Le rendu par image est le point coûteux (dessiner chaque caractère un par
    un) : sur une source longue ou une largeur élevée, l'export peut prendre
    plusieurs dizaines de secondes, voire plus.
    """
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise RuntimeError(f"Impossible d'ouvrir la source vidéo {source!r}")

    source_fps = cap.get(cv2.CAP_PROP_FPS) or 0
    output_fps = fps or (source_fps if source_fps > 0 else DEFAULT_FPS)
    max_frames = int(duration * output_fps) if duration else None

    writer = None
    frame_count = 0

    try:
        while max_frames is None or frame_count < max_frames:
            ok, frame = cap.read()
            if not ok:
                break

            if mirror:
                frame = cv2.flip(frame, 1)

            image = render_frame_to_image(
                frame,
                width=width,
                charset=charset,
                char_aspect=char_aspect,
                normalize=normalize,
                font_size=font_size,
                colored=color,
            )
            frame_bgr = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

            if writer is None:
                out_height, out_width = frame_bgr.shape[:2]
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                writer = cv2.VideoWriter(output_path, fourcc, output_fps, (out_width, out_height))
                if not writer.isOpened():
                    raise RuntimeError(
                        f"Impossible de créer le fichier vidéo {output_path!r} "
                        "(essaie une extension .avi si .mp4 échoue)"
                    )

            writer.write(frame_bgr)
            frame_count += 1
            if frame_count % 10 == 0:
                print(f"\r{frame_count} images exportées...", end="", file=sys.stderr, flush=True)
    finally:
        cap.release()
        if writer is not None:
            writer.release()

    return frame_count
