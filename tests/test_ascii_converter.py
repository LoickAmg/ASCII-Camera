"""Tests de la conversion pure image -> ASCII (numpy + Pillow, pas d'OpenCV)."""

import re
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ascii_converter import (  # noqa: E402
    equalize_histogram,
    frame_to_ansi,
    frame_to_ascii,
    render_ascii_to_image,
    render_frame_to_image,
    resize_nearest,
    stretch_contrast,
    to_grayscale,
)

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _solid_bgr(height: int, width: int, bgr: tuple[int, int, int]) -> np.ndarray:
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[:, :] = bgr
    return frame


def test_resize_nearest_changes_shape():
    image = np.arange(20 * 30, dtype=np.uint8).reshape(20, 30)
    resized = resize_nearest(image, new_width=10, new_height=5)
    assert resized.shape == (5, 10)


def test_resize_nearest_keeps_color_channels():
    image = np.zeros((10, 10, 3), dtype=np.uint8)
    resized = resize_nearest(image, new_width=4, new_height=4)
    assert resized.shape == (4, 4, 3)


def test_to_grayscale_passthrough_for_2d():
    gray = np.array([[10, 20], [30, 40]], dtype=np.uint8)
    assert np.array_equal(to_grayscale(gray), gray)


def test_to_grayscale_of_white_is_white():
    frame = _solid_bgr(4, 4, (255, 255, 255))
    gray = to_grayscale(frame)
    assert (gray == 255).all()


def test_to_grayscale_of_black_is_black():
    frame = _solid_bgr(4, 4, (0, 0, 0))
    gray = to_grayscale(frame)
    assert (gray == 0).all()


def test_frame_to_ascii_shape_matches_width_and_computed_height():
    frame = _solid_bgr(20, 40, (128, 128, 128))
    text = frame_to_ascii(frame, width=20, char_aspect=0.5)
    lines = text.split("\n")
    # hauteur attendue = round(20 * (20/40) * 0.5) = 5
    assert len(lines) == 5
    assert all(len(line) == 20 for line in lines)


def test_frame_to_ascii_dark_pixel_maps_to_first_char():
    frame = _solid_bgr(10, 10, (0, 0, 0))
    text = frame_to_ascii(frame, width=5, charset="@ ")
    assert set(text.replace("\n", "")) == {"@"}


def test_frame_to_ascii_light_pixel_maps_to_last_char():
    frame = _solid_bgr(10, 10, (255, 255, 255))
    text = frame_to_ascii(frame, width=5, charset="@ ")
    assert set(text.replace("\n", "")) == {" "}


def test_frame_to_ascii_rejects_invalid_width():
    frame = _solid_bgr(4, 4, (0, 0, 0))
    with pytest.raises(ValueError):
        frame_to_ascii(frame, width=0)


def test_frame_to_ascii_rejects_tiny_charset():
    frame = _solid_bgr(4, 4, (0, 0, 0))
    with pytest.raises(ValueError):
        frame_to_ascii(frame, width=4, charset="@")


def test_frame_to_ansi_contains_true_color_escape_and_reset():
    frame = _solid_bgr(4, 4, (10, 20, 200))  # BGR -> rouge dominant
    text = frame_to_ansi(frame, width=4, charset="@ ")
    assert "\x1b[38;2;200;20;10m" in text
    assert text.endswith("\x1b[0m")


def test_frame_to_ansi_rejects_grayscale_input():
    gray = np.zeros((4, 4), dtype=np.uint8)
    with pytest.raises(ValueError):
        frame_to_ansi(gray, width=4)


def test_equalize_histogram_stretches_two_tone_image_to_full_range():
    # Deux niveaux de gris proches (peu de contraste) : après égalisation, ils
    # doivent occuper toute la plage 0-255 (contraste maximal).
    gray = np.full((4, 4), 100, dtype=np.uint8)
    gray[:, 2:] = 150
    equalized = equalize_histogram(gray)
    assert set(np.unique(equalized).tolist()) == {0, 255}
    assert (equalized[:, :2] == 0).all()
    assert (equalized[:, 2:] == 255).all()


def test_equalize_histogram_preserves_order():
    gray = np.array([[10, 50, 100, 200]], dtype=np.uint8)
    equalized = equalize_histogram(gray)
    values = equalized[0]
    assert list(values) == sorted(values.tolist())


def test_stretch_contrast_expands_narrow_range():
    gray = np.full((4, 4), 100, dtype=np.uint8)
    gray[:, 2:] = 150
    stretched = stretch_contrast(gray)
    assert set(np.unique(stretched).tolist()) == {0, 255}


def test_stretch_contrast_is_gentler_than_equalize_on_noisy_flat_region():
    # Zone quasi uniforme avec un léger bruit : l'étirement par percentiles
    # reste modéré (peu de valeurs distinctes en sortie), contrairement à
    # l'égalisation complète qui peut étaler ce bruit sur toute la rampe.
    rng = np.random.default_rng(0)
    noisy_flat = np.clip(130 + rng.normal(0, 3, (20, 20)), 0, 255).astype(np.uint8)

    stretched = stretch_contrast(noisy_flat)
    equalized = equalize_histogram(noisy_flat)

    assert np.unique(stretched).size <= np.unique(equalized).size
    assert int(stretched.max()) - int(stretched.min()) <= int(equalized.max()) - int(
        equalized.min()
    )


def test_frame_to_ascii_normalize_reveals_contrast_flat_scene_hides():
    # Scène à faible contraste : sans normalisation, un charset à 2 niveaux ne
    # distingue pas les deux zones (troncature). Avec normalisation, si.
    frame = _solid_bgr(4, 4, (100, 100, 100))
    frame[:, 2:] = (150, 150, 150)

    flat = frame_to_ascii(frame, width=4, charset="@ ", normalize=False)
    assert set(flat.replace("\n", "")) == {"@"}

    contrasted = frame_to_ascii(frame, width=4, charset="@ ", normalize=True)
    chars = {c for line in contrasted.split("\n") for c in line}
    assert chars == {"@", " "}


def test_render_ascii_to_image_has_positive_dimensions():
    image = render_ascii_to_image("AB\nCD")
    assert image.width > 0
    assert image.height > 0


def test_render_ascii_to_image_handles_empty_text():
    image = render_ascii_to_image("")
    assert image.width > 0
    assert image.height > 0


def test_render_frame_to_image_uses_original_pixel_colors():
    # Gauche = rouge, droite = bleu ; charset sans espace pour garantir un
    # glyphe visible sur chaque cellule.
    frame = _solid_bgr(4, 4, (0, 0, 255))
    frame[:, 2:] = (255, 0, 0)

    image = render_frame_to_image(
        frame, width=4, charset="@@", colored=True, background=(0, 0, 0)
    )
    arr = np.array(image).astype(int)
    left_half = arr[:, : arr.shape[1] // 2]
    right_half = arr[:, arr.shape[1] // 2 :]

    assert (left_half[..., 0] - left_half[..., 2]).max() > 50  # rouge (R>B) à gauche
    assert (right_half[..., 2] - right_half[..., 0]).max() > 50  # bleu (B>R) à droite


def test_render_frame_to_image_monochrome_ignores_pixel_color():
    frame = _solid_bgr(4, 4, (0, 0, 255))
    frame[:, 2:] = (255, 0, 0)

    image = render_frame_to_image(
        frame, width=4, charset="@@", colored=False, foreground=(9, 9, 9), background=(0, 0, 0)
    )
    arr = np.array(image)
    # Aucune couleur d'origine (rouge/bleu) ne doit transparaître : seules des
    # nuances de gris entre le fond et l'avant-plan (l'anticrénelage de la
    # police peut mélanger les deux), jamais de teinte rouge ou bleue.
    assert (arr[..., 0] == arr[..., 1]).all()
    assert (arr[..., 1] == arr[..., 2]).all()


def test_render_frame_to_image_rejects_grayscale_when_colored():
    gray = np.zeros((4, 4), dtype=np.uint8)
    with pytest.raises(ValueError):
        render_frame_to_image(gray, width=4, colored=True)


def test_render_frame_to_image_has_positive_dimensions():
    frame = _solid_bgr(8, 8, (0, 0, 0))
    image = render_frame_to_image(frame, width=6, char_aspect=0.5, colored=False)
    assert image.width > 0
    assert image.height > 0


# -- Régression : les pixels saturés/lumineux ne doivent jamais devenir
# -- invisibles en rendu couleur (l'espace, mappé aux luminances les plus
# -- hautes, ne dessine rien même avec une couleur de remplissage -- un blanc
# -- ou un vert/rouge/bleu pur a une luminance perçue élevée mais reste un
# -- pixel important à afficher).


def test_frame_to_ansi_bright_pixel_is_not_an_invisible_space():
    frame = _solid_bgr(4, 4, (255, 255, 255))  # blanc pur -> luminance max
    text = frame_to_ansi(frame, width=4, charset="@%#*+=-:. ")
    stripped = _ANSI_RE.sub("", text).replace("\n", "")
    assert set(stripped) != {" "}


def test_frame_to_ansi_saturated_green_pixel_is_not_an_invisible_space():
    frame = _solid_bgr(4, 4, (0, 255, 0))  # vert pur (BGR) -> luminance perçue élevée
    text = frame_to_ansi(frame, width=4, charset="@%#*+=-:. ", normalize=True)
    stripped = _ANSI_RE.sub("", text).replace("\n", "")
    assert set(stripped) != {" "}


def test_render_frame_to_image_bright_pixel_still_produces_ink():
    frame = _solid_bgr(4, 4, (255, 255, 255))  # blanc pur
    image = render_frame_to_image(frame, width=4, colored=True, background=(0, 0, 0))
    arr = np.array(image)
    assert arr.max() > 0  # pas une image entièrement noire


def test_render_frame_to_image_saturated_color_on_dark_background_is_visible():
    # Reproduit le cas réel : petite zone très saturée sur un fond sombre
    # (ex. un objet coloré filmé dans une pièce peu éclairée).
    frame = _solid_bgr(6, 6, (20, 10, 5))
    frame[2:4, 2:4] = (0, 255, 0)  # vert pur (BGR)

    image = render_frame_to_image(
        frame, width=6, colored=True, normalize=True, background=(0, 0, 0)
    )
    arr = np.array(image).astype(int)
    assert (arr[..., 1] - arr[..., 0]).max() > 50  # de l'encre verte (G > R) quelque part
