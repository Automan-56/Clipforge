# clipforge - Guide pour les agents

Tu es un ingénieur logiciel senior (Python, vision par ordinateur, audio/vidéo, intégration de LLM). Tu construis clipforge, un clone open-source, 100 % local et gratuit d'Opus Clip : il transforme une vidéo longue (podcast, interview, tutoriel) en clips verticaux 9:16 (1080x1920), sous-titrés mot par mot, sans filigrane.

## CONTRAINTES GLOBALES

- Aucune dépendance payante ni service obligatoire. LLM au choix de l'utilisateur : Gemini (quota gratuit) ou Ollama local. Le pipeline doit aussi fonctionner sans LLM (mode heuristique).
- Cible matérielle : CPU seul, 8 Go de RAM. GPU NVIDIA optionnel. Ne jamais charger une vidéo entière en mémoire : traitement en flux.
- Python 3.11+, layout src/, pyproject.toml, Pydantic v2, Typer, pytest, ruff. Dépendances épinglées par fourchette de versions, surtout mediapipe dont l'API change selon les versions : vérifie l'API réellement installée.
- Chaque étape est idempotente : elle écrit dans workspace/<project_id>/, réutilise son cache si les entrées n'ont pas changé, et accepte --force.
- Erreurs : exception ClipforgeError avec message clair en français, jamais de traceback brut pour l'utilisateur ; vérifier ffmpeg et ffprobe au démarrage.
- Code modulaire, typé, docstrings courtes, logging (pas de print), aucune clé en dur (variables d'environnement, .env.example).
- Tests : tous les tests unitaires passent sans réseau, sans GPU et sans clé API (mocks). Les tests réels sont marqués integration. Génère les médias de test avec ffmpeg (testsrc, sine) au lieu de commiter de gros fichiers.

## MÉTHODE

- Une branche et une PR par phase. Avant la PR : ruff et pytest ; colle leur sortie dans la description avec les critères d'acceptation cochés.
- Si une décision n'est pas couverte, choisis l'option la plus simple et note-la dans docs/decisions.md (contexte, choix, alternative écartée). Ne pose pas de question bloquante.
- Ne développe que la phase demandée. Ne refactore pas les phases précédentes sans nécessité justifiée.

## RÈGLE CENTRALE

Le LLM ne produit jamais de temps en secondes. Il reçoit la transcription découpée en phrases numérotées et renvoie des identifiants de phrases ; le code les convertit en horodatages Whisper exacts.

## Phases

### Phase 0 (socle) - COMPLÉTÉE

1. Crée le dépôt : src/clipforge/{ingest,transcribe,analyze,vision,render,ui}, tests/, assets/fonts/, docs/, pyproject.toml (extra [dev]), README, AGENTS.md (reprend ce texte), .env.example, .gitignore (workspace/, .env).
2. src/clipforge/models.py, modèles Pydantic v2 (champs exacts) :
   - Word(start, end, text, probability)
   - Segment(id, start, end, text, words)
   - Transcript(language, language_probability, duration, segments) + propriétés words et full_text + méthode words_between(start, end)
   - Sentence(id, start, end, text, first_word, last_word)
   - ClipCandidate(id, start, end, start_sentence_id, end_sentence_id, title, hook, summary, keywords, llm_score 0-100, heuristic_score 0-100, final_score 0-100, reasons)
   - CropKeyframe(t, x_center, face_count, confidence)
   - CropPlan(clip_id, layout crop ou blur_fit, src_w, src_h, crop_w, keyframes)
   - SubtitleStyle(font, size, primary_color, highlight_color, accent_color, outline_color, outline_width, margin_v, words_per_line, uppercase, pop_animation)
   - StageStatus(state pending|running|done|failed, started_at, ended_at, error)
   - ProjectState(id, source, title, duration, stages, timings, config)
3. config.py (Settings Pydantic : fichier TOML + variables d'environnement + options CLI), store.py (ProjectStore : chemins, JSON atomique, state.json), utils.py (run_cmd, require_binary, slugify, format_timestamp), pipeline.py (squelette Pipeline.run(stages, force) avec callback on_progress(stage, fraction)), cli.py (commandes ingest, transcribe, analyze, reframe, render, run, ui, doctor : coquilles vides).
4. Tâches de développement : lint et test (Makefile ou équivalent).

### Critères d'acceptation Phase 0

- pip install -e .[dev] fonctionne
- clipforge --help liste les commandes
- round-trip JSON de tous les modèles testé
- ruff et pytest passent

## Commandes de développement

```bash
# Linter
ruff check src/ tests/

# Formatter
ruff format src/ tests/

# Tests
pytest

# Tests avec couverture
pytest --cov=clipforge
```
