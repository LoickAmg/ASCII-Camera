"""Point d'entrée en ligne de commande."""

from __future__ import annotations

import argparse
import re
import sys

from .ascii_converter import ASCII_CHARS, render_ascii_to_image
from .camera import convert_image_file, stream_webcam

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convertit un flux caméra ou une image en ASCII art."
    )
    parser.add_argument(
        "--source",
        default="webcam",
        help="'webcam' (défaut), un index de caméra (0, 1...), ou un chemin vers une image.",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=None,
        help="Largeur en caractères (défaut : largeur du terminal, ou 100 en mode image).",
    )
    parser.add_argument(
        "--charset",
        default=ASCII_CHARS,
        help="Rampe de caractères, du plus dense (sombre) au plus clair.",
    )
    parser.add_argument(
        "--color",
        action="store_true",
        help="Sortie en couleur ANSI 24 bits (nécessite un terminal compatible).",
    )
    parser.add_argument(
        "--no-mirror", action="store_true", help="Désactive l'effet miroir en mode webcam."
    )
    parser.add_argument(
        "--no-normalize",
        action="store_true",
        help="Désactive l'égalisation d'histogramme (activée par défaut, "
        "fait ressortir les détails dans les zones à faible contraste).",
    )
    parser.add_argument(
        "--fps", type=float, default=24.0, help="Limite d'images par seconde en mode webcam."
    )
    parser.add_argument(
        "--save",
        metavar="FICHIER.txt",
        help="Sauvegarde la sortie ASCII dans un fichier texte (mode image uniquement).",
    )
    parser.add_argument(
        "--render",
        metavar="FICHIER.png",
        help="Rend la sortie ASCII sous forme d'image PNG (mode image uniquement).",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.source == "webcam" or args.source.isdigit():
        camera_index = 0 if args.source == "webcam" else int(args.source)
        stream_webcam(
            camera_index=camera_index,
            width=args.width,
            color=args.color,
            charset=args.charset,
            mirror=not args.no_mirror,
            fps_limit=args.fps,
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
        plain_text = _strip_ansi(ascii_text) if args.color else ascii_text
        image = render_ascii_to_image(plain_text)
        image.save(args.render)
        print(f"Image rendue dans {args.render}", file=sys.stderr)


if __name__ == "__main__":
    main()
