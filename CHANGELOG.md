# Changelog

## [Unreleased]

### Corrections
- Déplacement de faster-whisper vers les dépendances principales (plus besoin d'extra [whisper])
- Correction des erreurs colorama sur Windows dans la commande doctor
- Mise à jour de l'URL du dépôt GitHub vers Automan-56/Clipforge

### Phase 6 - Qualité, performance et livraison

#### Ajouté
- Script de benchmark (scripts/benchmark.py) pour tester les performances
- Test d'intégration bout en bout (tests/test_integration.py)
- Commande `clipforge doctor` améliorée avec diagnostic complet
- Dockerfile CPU optionnel
- README complet en français avec installation, configuration et dépannage

#### Modifié
- Amélioration de la commande `doctor` pour vérifier tous les composants
- README étendu avec exemples et dépannage

## [0.1.0] - Phase 5

### Ajouté
- Orchestration du pipeline complet (pipeline.py)
- Gestionnaire de jobs pour l'interface (ui/jobs.py)
- Interface utilisateur Streamlit (ui/app.py)
- Dépendance streamlit pour l'interface

## [0.0.5] - Phase 4

### Ajouté
- Génération de sous-titres ASS (render/subtitles.py)
- Détection d'encodeur (render/encoder.py)
- Rendu vidéo en un passage (render/__init__.py)
- Presets de style (assets/presets/)

## [0.0.4] - Phase 3

### Ajouté
- Détection de visages (vision/faces.py)
- Suivi du locuteur (vision/tracking.py)
- Détection de coupures (vision/scenes.py)
- Lissage et keyframes (vision/cropplan.py)

## [0.0.3] - Phase 2

### Ajouté
- Découpage en phrases (analyze/sentences.py)
- Interface LLM (analyze/llm.py)
- Client Gemini (analyze/gemini.py)
- Client Ollama (analyze/ollama.py)
- Prompts (analyze/prompts.py)
- Score heuristique (analyze/scoring.py)

## [0.0.2] - Phase 1

### Ajouté
- Ingestion vidéo (ingest/__init__.py)
- Transcription Whisper (transcribe/whisper.py)
- Dépendances yt-dlp et faster-whisper

## [0.0.1] - Phase 0

### Ajouté
- Structure du projet
- Modèles Pydantic (models.py)
- Configuration (config.py)
- Stockage (store.py)
- Utilitaires (utils.py)
- Pipeline squelette (pipeline.py)
- CLI (cli.py)
