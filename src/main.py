"""Point d'entrée en ligne de commande."""

from __future__ import annotations

import argparse
import re
import sys

from .ascii_converter import ASCII_CHARS
from .camera import convert_image_file, export_ascii_video, render_image_file, stream_webcam
from .settings import DEFAULT_FPS

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convertit un flux caméra, une image ou une vidéo en ASCII art."
    )
    parser.add_argument(
        "--source",
        default="webcam",
        help="'webcam' (défaut), un index de caméra (0, 1...), ou un chemin "
        "vers une image/vidéo.",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=None,
        help="Largeur en caractères (défaut : largeur du terminal, ou 100 sinon).",
    )
    parser.add_argument(
        "--charset",
        default=ASCII_CHARS,
        help="Rampe de caractères, du plus dense (sombre) au plus clair.",
    )
    parser.add_argument(
        "--color",
        action="store_true",
        help="Couleur d'origine : ANSI 24 bits dans le terminal, ou par caractère "
        "avec --render/--export-video.",
    )
    parser.add_argument(
        "--no-mirror", action="store_true", help="Désactive l'effet miroir en mode webcam."
    )
    parser.add_argument(
        "--no-normalize",
        action="store_true",
        help="Désactive l'étirement de contraste automatique (activé par défaut, "
        "fait ressortir les détails dans les zones à faible contraste).",
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=None,
        help="Limite d'images/s en mode webcam (défaut 24), ou force le FPS de sortie "
        "avec --export-video (défaut : FPS de la source).",
    )
    parser.add_argument(
        "--save",
        metavar="FICHIER.txt",
        help="Sauvegarde la sortie ASCII dans un fichier texte (mode image uniquement).",
    )
    parser.add_argument(
        "--render",
        metavar="FICHIER.png",
        help="Rend la sortie ASCII sous forme d'image PNG (mode image uniquement). "
        "Combiner avec --color pour un rendu en couleur.",
    )
    parser.add_argument(
        "--export-video",
        metavar="FICHIER.mp4",
        help="Exporte la source (fichier vidéo, ou webcam avec --duration) en "
        "vidéo ASCII rendue image par image.",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=None,
        help="Durée en secondes à exporter (obligatoire avec --export-video en mode webcam).",
    )
    parser.add_argument(
        "--font-size",
        type=int,
        default=12,
        help="Taille de police pour --render / --export-video.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    is_camera = args.source == "webcam" or args.source.isdigit()
    if is_camera:
        camera_or_path = 0 if args.source == "webcam" else int(args.source)
    else:
        camera_or_path = args.source

    if args.export_video:
        if is_camera and not args.duration:
            parser.error("--duration est requis avec --export-video en mode webcam.")

        frame_count = export_ascii_video(
            camera_or_path,
            args.export_video,
            width=args.width or 100,
            charset=args.charset,
            color=args.color,
            normalize=not args.no_normalize,
            font_size=args.font_size,
            fps=args.fps,
            duration=args.duration,
            mirror=is_camera and not args.no_mirror,
        )
        print(f"\n{frame_count} images exportées dans {args.export_video}", file=sys.stderr)
        return

    if is_camera:
        stream_webcam(
            camera_index=camera_or_path,
            width=args.width,
            color=args.color,
            charset=args.charset,
            mirror=not args.no_mirror,
            fps_limit=args.fps if args.fps is not None else DEFAULT_FPS,
            normalize=not args.no_normalize,
        )
        return

    ascii_text = convert_image_file(
        args.source,
        width=args.width or 100,
        charset=args.charset,
        color=args.color,
        normalize=not args.no_normalize,
    )
    print(ascii_text)

    if args.save:
        with open(args.save, "w", encoding="utf-8") as handle:
            handle.write(_strip_ansi(ascii_text))
        print(f"\nSauvegardé dans {args.save}", file=sys.stderr)

    if args.render:
        render_image_file(
            args.source,
            args.render,
            width=args.width or 100,
            charset=args.charset,
            normalize=not args.no_normalize,
            color=args.color,
            font_size=args.font_size,
        )
        print(f"Image rendue dans {args.render}", file=sys.stderr)


if __name__ == "__main__":
    main()
