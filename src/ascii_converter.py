"""Conversion pure image -> ASCII (numpy uniquement, aucune dépendance à OpenCV).

Ce module manipule des matrices d'images (tableaux numpy) et ne dépend que de
`numpy` (+ `Pillow` pour le rendu en image) : il est donc entièrement testable
sans caméra, sans fenêtre graphique et sans OpenCV installé.
"""

from __future__ import annotations

import numpy as np

from .settings import ASCII_CHARS, DEFAULT_CHAR_ASPECT, DEFAULT_WIDTH


def resize_nearest(image: np.ndarray, new_width: int, new_height: int) -> np.ndarray:
    """Redimensionne une image (H, W) ou (H, W, C) par plus-proche-voisin."""
    height, width = image.shape[:2]
    new_width = max(1, new_width)
    new_height = max(1, new_height)

    row_indices = np.clip((np.arange(new_height) * height / new_height).astype(int), 0, height - 1)
    col_indices = np.clip((np.arange(new_width) * width / new_width).astype(int), 0, width - 1)

    return image[row_indices[:, None], col_indices]


def to_grayscale(frame: np.ndarray) -> np.ndarray:
    """Convertit une image en niveaux de gris.

    Suppose une image couleur au format BGR (convention OpenCV) si elle a 3
    canaux ; renvoie l'image telle quelle si elle est déjà en niveaux de gris.
    """
    if frame.ndim == 2:
        return frame

    blue = frame[..., 0].astype(np.float32)
    green = frame[..., 1].astype(np.float32)
    red = frame[..., 2].astype(np.float32)
    gray = 0.114 * blue + 0.587 * green + 0.299 * red
    return gray.astype(np.uint8)


def _char_indices(gray: np.ndarray, n_chars: int) -> np.ndarray:
    scaled = gray.astype(np.float32) / 255.0 * (n_chars - 1)
    return np.clip(scaled.astype(int), 0, n_chars - 1)


def equalize_histogram(gray: np.ndarray) -> np.ndarray:
    """Égalisation d'histogramme complète (numpy pur, aucune dépendance à OpenCV).

    Étale les niveaux de gris sur toute la plage 0-255 en fonction de leur
    fréquence. Très efficace pour maximiser le contraste, mais agressif : sur
    une zone quasi uniforme (peau, mur...), le moindre bruit de capteur peut
    se retrouver étalé sur toute la rampe de caractères ("effet de friture"),
    et le résultat peut scintiller d'une image à l'autre en vidéo (l'histogramme
    change légèrement à chaque frame). Utile ponctuellement sur une image
    fixe ; voir `stretch_contrast` pour une alternative plus douce, utilisée
    par défaut par `frame_to_ascii`/`frame_to_ansi`.
    """
    histogram, _ = np.histogram(gray.flatten(), bins=256, range=(0, 255))
    cumulative = histogram.cumsum()
    nonzero = cumulative[cumulative > 0]
    if nonzero.size == 0:
        return gray
    cdf_min = nonzero.min()
    denom = max(1, gray.size - cdf_min)
    lookup = np.clip(np.round((cumulative - cdf_min) / denom * 255), 0, 255).astype(np.uint8)
    return lookup[gray]


def stretch_contrast(
    gray: np.ndarray, low_percentile: float = 2.0, high_percentile: float = 98.0
) -> np.ndarray:
    """Étirement de contraste linéaire entre deux percentiles (numpy pur).

    Plus doux que `equalize_histogram` : une simple mise à l'échelle, pas de
    redistribution par fréquence. Amplifie donc beaucoup moins le bruit sur
    les zones à faible contraste (peau, mur uni...) et reste stable d'une
    image à l'autre en vidéo — c'est la méthode utilisée par défaut
    (`normalize=True`) par `frame_to_ascii` et `frame_to_ansi`.
    """
    low = np.percentile(gray, low_percentile)
    high = np.percentile(gray, high_percentile)
    if high <= low:
        return gray
    stretched = (gray.astype(np.float32) - low) / (high - low) * 255.0
    return np.clip(stretched, 0, 255).astype(np.uint8)


def frame_to_ascii(
    frame: np.ndarray,
    width: int = DEFAULT_WIDTH,
    charset: str = ASCII_CHARS,
    char_aspect: float = DEFAULT_CHAR_ASPECT,
    normalize: bool = False,
) -> str:
    """Convertit une image (BGR ou niveaux de gris) en une chaîne ASCII multi-lignes.

    `normalize=True` applique un étirement de contraste (`stretch_contrast`)
    avant la conversion : recommandé sur de vraies images (webcam, photo),
    utile pour faire ressortir les détails dans les zones à faible contraste.
    """
    if width < 1:
        raise ValueError("width doit être >= 1")
    if len(charset) < 2:
        raise ValueError("charset doit contenir au moins 2 caractères")

    gray = to_grayscale(frame)
    height, src_width = gray.shape[:2]
    target_height = max(1, round(width * (height / src_width) * char_aspect))
    small = resize_nearest(gray, width, target_height)
    if normalize:
        small = stretch_contrast(small)

    indices = _char_indices(small, len(charset))
    lines = ["".join(charset[i] for i in row) for row in indices]
    return "\n".join(lines)


def frame_to_ansi(
    frame: np.ndarray,
    width: int = DEFAULT_WIDTH,
    charset: str = ASCII_CHARS,
    char_aspect: float = DEFAULT_CHAR_ASPECT,
    normalize: bool = False,
) -> str:
    """Comme `frame_to_ascii`, mais colore chaque caractère avec la couleur du
    pixel d'origine via des séquences ANSI 24 bits (terminal compatible requis).

    `normalize=True` étire le contraste des niveaux de gris utilisés pour
    choisir le caractère (la couleur ANSI, elle, reste toujours fidèle au
    pixel d'origine).
    """
    if frame.ndim != 3:
        raise ValueError("frame_to_ansi nécessite une image couleur (BGR, 3 canaux)")

    height, src_width = frame.shape[:2]
    target_height = max(1, round(width * (height / src_width) * char_aspect))
    small = resize_nearest(frame, width, target_height)
    gray = to_grayscale(small)
    if normalize:
        gray = stretch_contrast(gray)
    indices = _char_indices(gray, len(charset))

    lines = []
    for row_idx in range(target_height):
        parts = []
        for col_idx in range(width):
            blue, green, red = (int(v) for v in small[row_idx, col_idx])
            char = charset[indices[row_idx, col_idx]]
            parts.append(f"\x1b[38;2;{red};{green};{blue}m{char}")
        lines.append("".join(parts) + "\x1b[0m")
    return "\n".join(lines)


def render_ascii_to_image(
    ascii_text: str,
    font_size: int = 12,
    background: tuple[int, int, int] = (0, 0, 0),
    foreground: tuple[int, int, int] = (0, 255, 70),
):
    """Rend une chaîne ASCII (texte brut, sans codes ANSI) en image PNG (Pillow)."""
    from PIL import Image, ImageDraw, ImageFont

    try:
        font = ImageFont.load_default(size=font_size)
    except TypeError:
        font = ImageFont.load_default()

    lines = ascii_text.split("\n") if ascii_text else [""]

    probe = Image.new("RGB", (1, 1))
    probe_draw = ImageDraw.Draw(probe)
    bbox = probe_draw.textbbox((0, 0), "M", font=font)
    char_width = max(1, bbox[2] - bbox[0])
    char_height = max(1, bbox[3] - bbox[1] + 2)

    max_line_len = max((len(line) for line in lines), default=1)
    image_width = max(1, char_width * max_line_len)
    image_height = max(1, char_height * len(lines))

    image = Image.new("RGB", (image_width, image_height), color=background)
    draw = ImageDraw.Draw(image)
    for row, line in enumerate(lines):
        draw.text((0, row * char_height), line, font=font, fill=foreground)
    return image
