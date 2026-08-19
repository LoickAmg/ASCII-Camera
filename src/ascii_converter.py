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


def _prepare_grid(
    frame: np.ndarray,
    width: int,
    charset: str,
    char_aspect: float,
    normalize: bool,
    need_color: bool,
) -> tuple[np.ndarray, np.ndarray | None, int]:
    """Logique commune à `frame_to_ascii`/`frame_to_ansi`/`render_frame_to_image` :
    redimensionne, applique l'étirement de contraste optionnel, choisit l'indice
    de caractère par cellule, et prépare la grille couleur si demandée (BGR).
    """
    if width < 1:
        raise ValueError("width doit être >= 1")
    if len(charset) < 2:
        raise ValueError("charset doit contenir au moins 2 caractères")
    if need_color and frame.ndim != 3:
        raise ValueError("le rendu en couleur nécessite une image couleur (BGR, 3 canaux)")

    gray_source = to_grayscale(frame)
    height, src_width = gray_source.shape[:2]
    target_height = max(1, round(width * (height / src_width) * char_aspect))

    small_gray = resize_nearest(gray_source, width, target_height)
    if normalize:
        small_gray = stretch_contrast(small_gray)
    indices = _char_indices(small_gray, len(charset))

    small_color = resize_nearest(frame, width, target_height) if need_color else None
    return indices, small_color, target_height


def _colored_char(charset: str, index: int) -> str:
    """Caractère à dessiner pour une cellule en rendu couleur : jamais un espace.

    La rampe mappe les pixels très clairs *en luminance* sur l'espace (dernier
    caractère). Un rouge, vert ou bleu pur a une luminance perçue élevée alors
    que c'est un pixel saturé et important visuellement (idem pour du blanc) :
    sans ce garde-fou, ces pixels ne dessineraient rien du tout en couleur
    (l'espace est invisible même avec une couleur de remplissage) et
    disparaîtraient purement et simplement du rendu.
    """
    char = charset[index]
    if char != " ":
        return char
    for candidate in reversed(charset):
        if candidate != " ":
            return candidate
    return "."


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
    indices, _, _ = _prepare_grid(frame, width, charset, char_aspect, normalize, need_color=False)
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
    indices, small_color, target_height = _prepare_grid(
        frame, width, charset, char_aspect, normalize, need_color=True
    )

    lines = []
    for row_idx in range(target_height):
        parts = []
        for col_idx in range(width):
            blue, green, red = (int(v) for v in small_color[row_idx, col_idx])
            char = _colored_char(charset, indices[row_idx, col_idx])
            parts.append(f"\x1b[38;2;{red};{green};{blue}m{char}")
        lines.append("".join(parts) + "\x1b[0m")
    return "\n".join(lines)


def _load_font(font_size: int):
    from PIL import ImageFont

    try:
        return ImageFont.load_default(size=font_size)
    except TypeError:
        return ImageFont.load_default()


def _char_metrics(font) -> tuple[int, int]:
    from PIL import Image, ImageDraw

    probe = Image.new("RGB", (1, 1))
    probe_draw = ImageDraw.Draw(probe)
    bbox = probe_draw.textbbox((0, 0), "M", font=font)
    char_width = max(1, bbox[2] - bbox[0])
    char_height = max(1, bbox[3] - bbox[1] + 2)
    return char_width, char_height


def render_ascii_to_image(
    ascii_text: str,
    font_size: int = 12,
    background: tuple[int, int, int] = (0, 0, 0),
    foreground: tuple[int, int, int] = (0, 255, 70),
):
    """Rend une chaîne ASCII (texte brut, sans codes ANSI) en image PNG, couleur unique."""
    from PIL import Image, ImageDraw

    font = _load_font(font_size)
    lines = ascii_text.split("\n") if ascii_text else [""]
    char_width, char_height = _char_metrics(font)

    max_line_len = max((len(line) for line in lines), default=1)
    image_width = max(1, char_width * max_line_len)
    image_height = max(1, char_height * len(lines))

    image = Image.new("RGB", (image_width, image_height), color=background)
    draw = ImageDraw.Draw(image)
    for row, line in enumerate(lines):
        draw.text((0, row * char_height), line, font=font, fill=foreground)
    return image


def render_frame_to_image(
    frame: np.ndarray,
    width: int = DEFAULT_WIDTH,
    charset: str = ASCII_CHARS,
    char_aspect: float = DEFAULT_CHAR_ASPECT,
    normalize: bool = False,
    font_size: int = 12,
    background: tuple[int, int, int] = (0, 0, 0),
    foreground: tuple[int, int, int] = (0, 255, 70),
    colored: bool = True,
):
    """Convertit une image en ASCII et la rend directement en image PNG (Pillow).

    `colored=True` (défaut) peint chaque caractère avec la couleur d'origine
    du pixel correspondant (comme `frame_to_ansi`, mais en image plutôt qu'en
    texte ANSI). `colored=False` utilise une seule couleur (`foreground`),
    comme `render_ascii_to_image`.
    """
    from PIL import Image, ImageDraw

    indices, small_color, target_height = _prepare_grid(
        frame, width, charset, char_aspect, normalize, need_color=colored
    )

    font = _load_font(font_size)
    char_width, char_height = _char_metrics(font)

    image = Image.new(
        "RGB", (char_width * width, char_height * target_height), color=background
    )
    draw = ImageDraw.Draw(image)

    for row in range(target_height):
        for col in range(width):
            if colored:
                # Jamais d'espace en couleur : un pixel saturé (rouge/vert/bleu
                # pur, blanc...) a une luminance perçue élevée et serait sinon
                # invisible alors qu'il porte une information de couleur importante.
                char = _colored_char(charset, indices[row, col])
                blue, green, red = (int(v) for v in small_color[row, col])
                fill = (red, green, blue)
            else:
                char = charset[indices[row, col]]
                if char == " ":
                    continue
                fill = foreground
            draw.text((col * char_width, row * char_height), char, font=font, fill=fill)

    return image
