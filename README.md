# ASCII Camera

Convertit un flux webcam, une image ou une vidéo en art ASCII — manipulation de matrices d'images et conversion pixels → caractères, en Python.

## Fonctionnalités

- Flux webcam live converti en ASCII et affiché dans le terminal, en niveaux de gris ou en couleur (ANSI 24 bits)
- Conversion d'une image fixe en ASCII : affichage terminal, sauvegarde en `.txt`, ou rendu en image `.png` (**monochrome ou en couleur**, chaque caractère peint avec la couleur du pixel d'origine)
- **Export vidéo** : convertit un fichier vidéo (ou un enregistrement webcam limité en durée) en vidéo ASCII, image rendue par image
- **Contraste automatique** (`stretch_contrast`, activé par défaut) : étire les niveaux de gris entre le 2e et le 98e percentile avant conversion. Sans ça, une zone à faible contraste (peau uniformément éclairée, mur...) n'utilise qu'une poignée de caractères de la rampe et le rendu paraît aplati en bandes plutôt que détaillé
- Redimensionnement, niveaux de gris, contraste et rendu couleur implémentés **en numpy + Pillow purs** (aucun appel à OpenCV dans la logique de conversion) : entièrement testable sans caméra ni fenêtre graphique
- Rampe de caractères et largeur personnalisables

## Structure du projet

```
ascii-camera/
├── src/
│   ├── main.py               # point d'entrée CLI (argparse)
│   ├── camera.py               # capture webcam/image/vidéo, export vidéo (dépend d'OpenCV)
│   ├── ascii_converter.py        # conversion pure image -> ASCII/PNG (numpy + Pillow, testable)
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

# ... et sauvegarder le résultat en texte et/ou en image rendue (--color pour un rendu couleur)
python -m src.main --source photo.jpg --save photo_ascii.txt --render photo_ascii.png --color

# Exporter une vidéo en vidéo ASCII (couleur, rendue image par image)
python -m src.main --source clip.mp4 --export-video clip_ascii.mp4 --color

# ... ou enregistrer et exporter directement depuis la webcam (durée obligatoire)
python -m src.main --export-video webcam_ascii.mp4 --duration 10
```

Ctrl+C pour arrêter le flux webcam.

### Options principales

| Option | Description |
| --- | --- |
| `--source` | `webcam` (défaut), un index de caméra (`0`, `1`...), ou un chemin d'image/vidéo |
| `--width` | Largeur en caractères (défaut : largeur du terminal, ou 100 sinon) |
| `--charset` | Rampe de caractères, du plus dense (sombre) au plus clair |
| `--color` | Couleur d'origine : ANSI 24 bits dans le terminal, ou par caractère avec `--render`/`--export-video` |
| `--no-normalize` | Désactive l'étirement de contraste automatique (activé par défaut) |
| `--no-mirror` | Désactive l'effet miroir en mode webcam |
| `--fps` | Limite d'images/s en mode webcam (défaut 24), ou force le FPS de sortie avec `--export-video` (défaut : FPS de la source) |
| `--save FICHIER.txt` | Sauvegarde la sortie ASCII (mode image) |
| `--render FICHIER.png` | Rend la sortie ASCII en image PNG (mode image), monochrome ou coloré avec `--color` |
| `--export-video FICHIER.mp4` | Exporte la source (vidéo ou webcam avec `--duration`) en vidéo ASCII rendue |
| `--duration` | Durée en secondes à exporter (obligatoire avec `--export-video` en mode webcam) |
| `--font-size` | Taille de police pour `--render`/`--export-video` (défaut 12) |

### Performance de l'export vidéo

Le rendu image par image dessine chaque caractère individuellement (Pillow) :
c'est le point coûteux. Une vidéo de quelques secondes en largeur 50-100
s'exporte en quelques secondes, mais une largeur élevée (`--width 200`+) ou
une vidéo longue peuvent prendre plusieurs dizaines de secondes, voire plus.
Le nombre d'images traitées s'affiche en continu sur la sortie d'erreur.

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

## Note sur le rendu couleur et les pixels saturés

La rampe de caractères choisit le caractère par **luminance perçue**, du plus
dense (sombre) à l'espace (le plus clair). Un rouge, vert ou bleu pur — ou du
blanc — a une luminance perçue élevée alors que c'est un pixel important
visuellement. En rendu couleur (`--color` avec `--render`/`--export-video`,
ou `frame_to_ansi`), dessiner un espace ne laisse aucune trace même avec une
couleur de remplissage : ces pixels saturés disparaîtraient purement et
simplement sans le garde-fou `_colored_char`, qui substitue automatiquement
le caractère visible le plus clair de la rampe à la place de l'espace dans
ce cas précis (uniquement en mode couleur — le mode texte/monochrome garde
son comportement d'origine, où l'espace reste un vrai "blanc").

## Prochaines étapes possibles

- Barre de progression plus précise pour `--export-video` (temps restant estimé)
- Conteneuriser avec Docker (voir le projet transversal #25 de la roadmap)
