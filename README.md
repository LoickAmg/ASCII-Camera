# ASCII Camera

Convertit un flux webcam (ou une image) en art ASCII en temps réel dans le terminal — manipulation de matrices d'images et conversion pixels → caractères, en Python.

## Fonctionnalités

- Flux webcam live converti en ASCII et affiché dans le terminal, en niveaux de gris ou en couleur (ANSI 24 bits)
- Conversion d'une image fixe en ASCII : affichage terminal, sauvegarde en `.txt`, ou rendu en image `.png`
- **Contraste automatique** (`stretch_contrast`, activé par défaut) : étire les niveaux de gris entre le 2e et le 98e percentile avant conversion. Sans ça, une zone à faible contraste (peau uniformément éclairée, mur...) n'utilise qu'une poignée de caractères de la rampe et le rendu paraît aplati en bandes plutôt que détaillé
- Redimensionnement, niveaux de gris et contraste implémentés **en numpy pur** (aucun appel à OpenCV dans la logique de conversion) : entièrement testable sans caméra ni fenêtre graphique
- Rampe de caractères et largeur personnalisables

## Structure du projet

```
ascii-camera/
├── src/
│   ├── main.py               # point d'entrée CLI (argparse)
│   ├── camera.py               # capture webcam/image (dépend d'OpenCV)
│   ├── ascii_converter.py        # conversion pure image -> ASCII (numpy + Pillow, testable)
│   └── settings.py                 # constantes par défaut (rampe, largeur, FPS...)
├── tests/
│   └── test_ascii_converter.py       # tests unitaires (pytest)
├── .github/workflows/ci.yml # lint (ruff) + tests (pytest) sur push/PR
├── requirements.txt
└── requirements-dev.txt
```

## Installation

```bash
python -m venv .venv
source .venv/bin/activate  # Windows : .venv\Scripts\activate
pip install -r requirements-dev.txt
```

## Utilisation

```bash
# Flux webcam en direct (niveaux de gris, largeur = celle du terminal)
python -m src.main

# En couleur (nécessite un terminal compatible ANSI 24 bits, ex. Windows Terminal)
python -m src.main --color

# Largeur et rampe de caractères personnalisées
python -m src.main --width 160 --charset " .:-=+*#%@"

# Convertir une image fixe et l'afficher dans le terminal
python -m src.main --source photo.jpg

# ... et sauvegarder le résultat en texte et/ou en image rendue
python -m src.main --source photo.jpg --save photo_ascii.txt --render photo_ascii.png
```

Ctrl+C pour arrêter le flux webcam.

### Options principales

| Option | Description |
| --- | --- |
| `--source` | `webcam` (défaut), un index de caméra (`0`, `1`...), ou un chemin d'image |
| `--width` | Largeur en caractères (défaut : largeur du terminal en mode webcam, 100 en mode image) |
| `--charset` | Rampe de caractères, du plus dense (sombre) au plus clair |
| `--color` | Sortie en couleur ANSI 24 bits |
| `--no-normalize` | Désactive l'étirement de contraste automatique (activé par défaut) |
| `--no-mirror` | Désactive l'effet miroir en mode webcam |
| `--fps` | Limite d'images par seconde en mode webcam |
| `--save FICHIER.txt` | Sauvegarde la sortie ASCII (mode image) |
| `--render FICHIER.png` | Rend la sortie ASCII en image PNG (mode image) |

## Lancer les tests

```bash
pytest
```

Les tests ne dépendent que de `numpy` et `Pillow` — la logique de conversion (`ascii_converter.py`) n'importe jamais OpenCV, donc pas besoin de caméra ni de bibliothèques graphiques système pour les exécuter (utile en CI).

## Lint

```bash
ruff check .
```

## Notes sur le contraste automatique

`ascii_converter.py` propose deux méthodes numpy pures :

- **`stretch_contrast`** (utilisée par défaut) : étirement linéaire entre deux percentiles. Douce, stable d'une image à l'autre en vidéo, n'amplifie pas trop le bruit de capteur sur les zones uniformes.
- **`equalize_histogram`** : égalisation d'histogramme complète, disponible séparément. Plus agressive : maximise le contraste mais peut faire ressortir le bruit ("effet de friture") sur une zone quasi uniforme, et peut scintiller d'une image à l'autre en flux vidéo (l'histogramme change légèrement à chaque frame).

## Prochaines étapes possibles

- Rendu `--render` en couleur (actuellement monochrome)
- Export du flux ASCII en vidéo (concaténation d'images rendues)
- Conteneuriser avec Docker (voir le projet transversal #25 de la roadmap)
