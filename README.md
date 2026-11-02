# clipforge

Clone open-source, 100 % local et gratuit d'Opus Clip : transforme une vidéo longue (podcast, interview, tutoriel) en clips verticaux 9:16 (1080x1920), sous-titrés mot par mot, sans filigrane.

## Fonctionnalités

- **Ingestion** : Import de vidéos depuis YouTube ou fichiers locaux
- **Transcription** : faster-whisper pour la transcription mot par mot
- **Analyse** : LLM (Gemini ou Ollama) ou heuristique pour identifier les meilleurs clips
- **Recadrage** : Détection de visage et plans de recadrage intelligents
- **Rendu** : Génération de clips 9:16 avec sous-titres animés (format ASS)
- **Interface** : Interface web Streamlit pour la gestion des projets

## Avertissement

⚠️ **Droit d'auteur et conditions d'utilisation** : clipforge est un outil technique de traitement vidéo. Il ne transfère aucun droit sur le contenu que vous traitez. Vous êtes responsable de respecter les droits d'auteur et les conditions d'utilisation des plateformes de source (YouTube, etc.) lorsque vous téléchargez et traitez des vidéos. N'utilisez pas cet outil pour enfreindre les droits d'auteur ou les conditions d'utilisation.

## Contraintes

- Aucune dépendance payante ni service obligatoire
- LLM au choix : Gemini (quota gratuit) ou Ollama local
- Fonctionne sans LLM (mode heuristique)
- Cible matérielle : CPU seul, 8 Go de RAM (GPU NVIDIA optionnel)
- Traitement en flux (jamais de chargement complet en mémoire)

## Installation

### Prérequis

- Python 3.11+
- FFmpeg (avec ffprobe)
- (Optionnel) CUDA pour GPU NVIDIA

### Linux

```bash
# Installer FFmpeg
sudo apt update
sudo apt install ffmpeg

# Cloner le dépôt
git clone https://github.com/yourusername/clipforge.git
cd clipforge

# Installer en mode développement
pip install -e .[dev]

# Installer Streamlit pour l'interface (optionnel)
pip install -e .[ui]
```

### macOS

```bash
# Installer FFmpeg avec Homebrew
brew install ffmpeg

# Cloner le dépôt
git clone https://github.com/yourusername/clipforge.git
cd clipforge

# Installer en mode développement
pip install -e .[dev]

# Installer Streamlit pour l'interface (optionnel)
pip install -e .[ui]
```

### Windows

```bash
# Installer FFmpeg depuis https://ffmpeg.org/download.html
# Ajouter ffmpeg à votre PATH

# Cloner le dépôt
git clone https://github.com/Automan-56/Clipforge.git
cd Clipforge

# Installer en mode développement
pip install -e .[dev]

# Installer Streamlit pour l'interface (optionnel)
pip install -e .[ui]
```

## Configuration

### Fichier de configuration

Créer un fichier `.env` ou `clipforge.toml` à la racine du projet :

```toml
[whisper]
model = "small"  # tiny, base, small, medium, large-v3
device = "auto"  # auto, cpu, cuda

[llm]
provider = "heuristic"  # heuristic, gemini, ollama
gemini_api_key = ""  # Clé API Gemini (si provider = gemini)
ollama_base_url = "http://localhost:11434"  # URL Ollama (si provider = ollama)
ollama_model = "llama3.2"  # Modèle Ollama (si provider = ollama)

[crop]
target_aspect = "9:16"
target_width = 1080
target_height = 1920
```

### Configuration Gemini

1. Créer un compte Google AI Studio : https://makersuite.google.com/
2. Générer une clé API : https://makersuite.google.com/app/apikey
3. Ajouter la clé à votre configuration : `gemini_api_key = "votre_clé"`
4. Configurer le provider : `provider = "gemini"`

### Configuration Ollama

1. Installer Ollama : https://ollama.ai/
2. Télécharger un modèle : `ollama pull llama3.2`
3. Configurer le provider : `provider = "ollama"`
4. Vérifier l'URL par défaut : `ollama_base_url = "http://localhost:11434"`

## Utilisation

### Pipeline complet

```bash
# Pipeline complet avec options par défaut
clipforge run video.mp4 --title "Mon Podcast"

# Pipeline avec modèle tiny (plus rapide) et mode heuristique
clipforge run video.mp4 --model tiny --provider heuristic --max-clips 5

# Pipeline avec Gemini
clipforge run video.mp4 --provider gemini --max-clips 10

# Pipeline avec Ollama
clipforge run video.mp4 --provider ollama --max-clips 10

# Pipeline en mode brouillon (720p pour prévisualisation)
clipforge run video.mp4 --draft --top 3
```

### Étapes individuelles

```bash
# Ingestion
clipforge ingest video.mp4 --title "Mon Podcast"
clipforge ingest "https://youtube.com/watch?v=VIDEO_ID" --title "Titre"

# Transcription
clipforge transcribe <project-id> --model small --language fr

# Analyse
clipforge analyze <project-id> --provider heuristic --max-clips 10 --min-sec 30 --max-sec 60

# Recadrage
clipforge reframe <project-id> --layout auto --debug-video

# Rendu
clipforge render <project-id> --clip 0 --preset default --draft
clipforge render <project-id> --top 3 --preset bold
```

### Interface web

```bash
# Lancer l'interface Streamlit
clipforge ui
```

### Vérification des dépendances

```bash
# Diagnostiquer les problèmes d'installation
clipforge doctor
```

## Exemples

### Clip depuis un fichier local

```bash
clipforge run podcast.mp4 --title "Episode 1" --model small --provider heuristic
```

### Clip depuis YouTube

```bash
clipforge ingest "https://youtube.com/watch?v=VIDEO_ID" --title "YouTube Video"
clipforge transcribe <project-id>
clipforge analyze <project-id> --provider gemini
clipforge reframe <project-id>
clipforge render <project-id> --top 5
```

### Mode brouillon rapide

```bash
clipforge run video.mp4 --model tiny --provider heuristic --draft --top 1
```

## Dépannage

### FFmpeg non trouvé

```
Erreur : ffmpeg est requis mais non trouvé dans le PATH
```

**Solution** : Installer FFmpeg et l'ajouter à votre PATH.

- Linux : `sudo apt install ffmpeg`
- macOS : `brew install ffmpeg`
- Windows : Télécharger depuis https://ffmpeg.org/download.html

### yt-dlp mis à jour

```
Erreur : yt-dlp doit être mis à jour
```

**Solution** : Mettre à jour yt-dlp :

```bash
pip install --upgrade yt-dlp
```

### Problèmes de mémoire

```
Erreur : Mémoire insuffisante
```

**Solution** :
- Utiliser un modèle Whisper plus petit : `--model tiny`
- Utiliser le mode brouillon : `--draft`
- Fermer d'autres applications

### Problèmes GPU

```
Erreur : CUDA non disponible
```

**Solution** : Utiliser le mode CPU dans la configuration : `device = "cpu"`

## Architecture

```
clipforge/
├── src/clipforge/
│   ├── analyze/      # Analyse LLM et heuristique
│   ├── ingest/       # Ingestion vidéo
│   ├── models.py     # Modèles Pydantic
│   ├── pipeline.py   # Orchestration du pipeline
│   ├── render/       # Rendu vidéo et sous-titres
│   ├── store.py      # Stockage des projets
│   ├── transcribe/   # Transcription Whisper
│   ├── ui/           # Interface Streamlit
│   ├── utils.py      # Utilitaires
│   └── vision/       # Vision par ordinateur
├── tests/            # Tests unitaires et d'intégration
├── assets/           # Polices et presets
└── docs/             # Documentation
```

## Limites connues

- Les tests SpeakerTracker sont marqués comme skip (mock MediaPipe complexe)
- L'interface Streamlit nécessite streamlit installé (`pip install -e .[ui]`)
- Les modèles Whisper nécessitent un téléchargement initial
- Le traitement vidéo peut être lent sur CPU pour les longues vidéos

## Développement

```bash
# Linter
ruff check src/ tests/

# Formatter
ruff format src/ tests/

# Tests unitaires
pytest -m "not integration"

# Tests d'intégration
pytest -m integration

# Tests avec couverture
pytest --cov=clipforge

# Benchmark
python scripts/benchmark.py
```

## Licence

MIT
