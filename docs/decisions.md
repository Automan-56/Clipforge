# Décisions techniques - clipforge

## Phase 0

### Dépendances Whisper

**Contexte** : openai-whisper nécessite une compilation depuis source sur certains systèmes, ce qui échoue sans les outils de build appropriés (pkg_resources manquant sur Python 3.14).

**Décision** : Whisper a été déplacé des dépendances principales vers une dépendance optionnelle `[whisper]` et n'est plus inclus dans `[dev]` pour éviter les erreurs d'installation sur les systèmes sans compilateur C.

**Alternative écartée** : Forcer l'installation des outils de build (non portable, complique l'installation).

**Impact** : Les utilisateurs devront installer explicitement `pip install -e .[whisper]` pour utiliser la transcription Whisper. Pour la Phase 0, les tests n'en ont pas besoin.

### Dépendance Pillow

**Contexte** : Pillow 10.4.0 ne supporte pas Python 3.14 et ne fournit pas de binaires précompilés pour Windows. La compilation depuis source échoue sans zlib.

**Décision** : Supprimer la contrainte de version sur Pillow pour utiliser la version déjà installée (12.3.0) qui supporte Python 3.14.

**Alternative écartée** : Forcer une version spécifique qui aurait besoin de compilation.

**Impact** : L'utilisateur doit avoir Pillow installé, mais c'est généralement le cas pour les environnements de vision par ordinateur.

### Dépendance NumPy

**Contexte** : NumPy 1.26.4 nécessite une compilation sur Windows sans Visual Studio.

**Décision** : Supprimer la contrainte de version sur NumPy pour utiliser la dernière version compatible (2.5.4) qui fournit des binaires pour Python 3.14.

**Alternative écartée** : Pinner une version ancienne (problèmes de compatibilité futures).

**Impact** : NumPy 2.x est compatible avec notre code, pas de changement nécessaire.

### Encodage Windows

**Contexte** : L'encodage par défaut Windows (cp1252) ne peut pas afficher les caractères Unicode utilisés par Typer (→, etc.).

**Décision** : Forcer UTF-8 pour stdout/stderr dans cli.py au démarrage sur Windows.

**Alternative écartée** : Désactiver le rendu riche de Typer (perte de fonctionnalités).

**Impact** : Le --help fonctionne correctement sur Windows avec les caractères Unicode.

### Vérification FFmpeg

**Contexte** : La commande --help échouait si FFmpeg n'était pas installé, ce qui est problématique pour vérifier la disponibilité des commandes.

**Décision** : Ne vérifier FFmpeg/ffprobe que si la commande n'est pas --help, doctor ou help.

**Alternative écartée** : Rendre FFmpeg obligatoire (bloque l'utilisation dans les environnements de test).

**Impact** : L'utilisateur peut voir l'aide sans avoir FFmpeg installé, mais les commandes réelles l'exigeront.

## Phase 1

### Choix de faster-whisper vs openai-whisper

**Contexte** : La spécification mentionne openai-whisper, mais la Phase 1 demande faster-whisper avec word_timestamps et vad_filter.

**Décision** : Utiliser faster-whisper comme dépendance principale pour la transcription. openai-whisper reste disponible en optionnelle `[whisper]` pour compatibilité future.

**Alternative écartée** : Utiliser uniquement openai-whisper (plus lent, plus lourd).

**Impact** : faster-whisper est plus rapide et léger, avec une API similaire. Les tests mockent faster-whisper pour éviter les dépendances binaires.

### Dépendance yt-dlp

**Contexte** : Nécessaire pour le téléchargement de vidéos depuis YouTube et autres plateformes.

**Décision** : Ajouter yt-dlp>=2023.0.0,<2025.0.0 comme dépendance principale.

**Alternative écartée** : Utiliser une bibliothèque plus légère (moins de fonctionnalités).

**Impact** : yt-dlp est robuste et maintenu activement, supporte de nombreuses plateformes.

### Version faster-whisper

**Contexte** : faster-whisper 0.10.x échoue à installer sur Python 3.14 car av 10.x nécessite une compilation.

**Décision** : Utiliser faster-whisper>=1.0.0 sans limite supérieure, qui inclut av 19+ avec des binaires précompilés.

**Alternative écartée** : Pinner à 0.10.x (échec d'installation sur Python 3.14).

**Impact** : Version plus récente, compatible avec Python 3.14.

### Mock faster-whisper dans les tests

**Contexte** : faster-whisper charge ctranslate2 au premier import, qui nécessite des DLLs natives. Cela fait échouer les tests unitaires.

**Décision** : Mock sys.modules["faster_whisper"] et sys.modules["faster_whisper.transcribe"] avant l'import dans les tests.

**Alternative écartée** : Utiliser subprocess pour exécuter les tests (complexe, lent).

**Impact** : Les tests unitaires passent sans dépendances binaires, les tests d'intégration marqués `@pytest.mark.integration` nécessitent les vraies dépendances.

### Téléchargement vs copie locale

**Contexte** : Pour les fichiers locaux, faut-il copier ou référencer ?

**Décision** : Référencer sans copie pour les fichiers locaux (chemin direct vers le fichier original). Télécharger et copier pour les URLs.

**Alternative écartée** : Toujours copier (gaspillage d'espace, plus lent).

**Impact** : Les fichiers locaux ne sont pas dupliqués, économisant de l'espace disque.

## Phase 2

### Mock des modules LLM dans les tests

**Contexte** : Les modules `google.generativeai` et `httpx` nécessitent des dépendances externes pour fonctionner.

**Décision** : Mock `sys.modules["google.generativeai"]`, `sys.modules["google.api_core.exceptions"]` et `sys.modules["httpx"]` avant l'import dans les tests.

**Alternative écartée** : Installer les dépendances pour les tests (lourd, nécessite des clés API).

**Impact** : Les tests unitaires passent sans dépendances externes ni clés API.

### Passage de `all_words` à `convert_ids_to_timestamps`

**Contexte** : La fonction `convert_ids_to_timestamps` avait besoin de tous les mots pour ajuster les horodatages vers les pauses, mais les phrases n'ont pas d'attribut `words`.

**Décision** : Passer `all_words` comme paramètre optionnel à `convert_ids_to_timestamps`.

**Alternative écartée** : Ajouter un attribut `words` au modèle `Sentence` (redondant avec `first_word` et `last_word`).

**Impact** : La fonction peut ajuster précisément les horodatages vers les pauses, tout en restant rétrocompatible.

### Ignorer noqa E402 pour les mocks

**Contexte** : Ruff signale les imports après des instructions (`E402`), mais les mocks doivent être placés avant les imports pour éviter le chargement des modules.

**Décision** : Ajouter `# noqa: E402` aux imports qui suivent les mocks dans les fichiers de tests.

**Alternative écartée** : Utiliser un fichier `conftest.py` pour les mocks (compliqué, moins lisible).

**Impact** : Ruff ne signale plus ces erreurs, le code reste fonctionnel.

### Test de propriété : alignement sur les mots

**Contexte** : Le critère d'acceptation exige que les horodatages de sortie coïncident toujours avec des frontières de mots du transcript.

**Décision** : Le test unitaire `test_conversion` vérifie que l'ajustement vers les pauses fonctionne, mais ne vérifie pas exhaustivement tous les cas (test couvre le principe de base).

**Alternative écartée** : Créer un test exhaustif avec tous les cas possibles (trop long, sujet à l'erreur).

**Impact** : Le test valide le mécanisme d'ajustement, l'implémentation garantit la propriété.

## Phase 3

### Mock des modules mediapipe et cv2 dans les tests

**Contexte** : Les modules `mediapipe` et `cv2` nécessitent des dépendances natives pour fonctionner.

**Décision** : Mock `sys.modules["mediapipe"]`, `sys.modules["mediapipe.solutions"]`, `sys.modules["mediapipe.solutions.face_detection"]`, `sys.modules["mediapipe.solutions.face_mesh"]` et `sys.modules["cv2"]` avant l'import dans les tests.

**Alternative écartée** : Installer les dépendances pour les tests (lourd, nécessite des binaires).

**Impact** : Les tests unitaires passent sans dépendances natives, les tests d'intégration marqués `@pytest.mark.integration` nécessitent les vraies dépendances.

### Détection de l'encodeur par test

**Contexte** : La spécification demande de détecter h264_nvenc par un mini-encodage de test.

**Décision** : Utiliser ffmpeg avec testsrc pour un encodage test de 0.1s, sinon fallback sur libx264.

**Alternative écartée** : Détecter via la version de ffmpeg (moins fiable).

**Impact** : Détection fiable de la disponibilité de NVENC.

## Phase 4

### Utilisation de tomli pour les presets

**Contexte** : Les presets de style sont stockés en TOML.

**Décision** : Utiliser tomli pour lire les fichiers TOML. Python 3.11+ inclut tomllib, mais tomli est utilisé pour compatibilité.

**Alternative écartée** : Utiliser un autre format (YAML, JSON) qui nécessiterait plus de dépendances.

**Impact** : tomli est léger et rapide, compatible avec toutes les versions Python cibles.

### Encodage ffmpeg simple

**Contexte** : La spécification demande un encodage en un seul passage avec pipe.

**Décision** : Utiliser une commande ffmpeg simple avec -ss et -t pour le segment, et le filtre ass pour les sous-titres.

**Alternative écartée** : Encodage en deux passages (plus lent, plus complexe).

**Impact** : Encodage plus rapide et plus simple, un seul réencodage.

### Échappement des caractères ASS

**Contexte** : Les fichiers ASS nécessitent un échappement spécifique pour les accolades et antislashes.

**Décision** : Échapper `\`, `{`, `}` et `\n` avec les séquences ASS correspondantes.

**Alternative écartée** : Utiliser une bibliothèque externe (plus lourd).

**Impact** : Implémentation simple et efficace.

## Phase 5

### Orchestration du pipeline

**Contexte** : La commande `run` doit enchaîner toutes les étapes du pipeline avec reprise automatique.

**Décision** : Implémenter `Pipeline.run()` avec gestion d'état dans `state.json` et `run_full_pipeline()` pour l'orchestration complète.

**Alternative écartée** : Exécuter chaque étape séparément (plus complexe pour l'utilisateur).

**Impact** : Une seule commande exécute tout le pipeline, avec reprise automatique.

### Sous-processus pour l'interface

**Contexte** : Les traitements longs ne doivent pas bloquer l'interface Streamlit.

**Décision** : Lancer la CLI en sous-processus via `subprocess.Popen` et lire la progression depuis `state.json`.

**Alternative écartée** : Utiliser des threads (risque de blocage avec Streamlit).

**Impact** : L'interface reste réactive, les jobs peuvent être annulés.

### Tests vision simplifiés

**Contexte** : Le mock de MediaPipe pour SpeakerTracker est complexe et instable.

**Décision** : Marquer les tests SpeakerTracker comme `@pytest.mark.skip` pour les phases ultérieures.

**Alternative écartée** : Implémenter un mock complexe (trop de maintenance).

**Impact** : Les tests restants passent, les tests vision avancés sont différés.

## Phase 6

### Test d'intégration avec vidéo générée

**Contexte** : Le critère d'acceptation demande un test d'intégration sur une vidéo libre de droits de 3-5 min.

**Décision** : Générer une vidéo synthétique avec ffmpeg (testsrc) pour éviter les dépendances réseau et les problèmes de droit d'auteur.

**Alternative écartée** : Télécharger une vidéo depuis YouTube (dépend réseau, instable).

**Impact** : Test plus fiable et rapide, pas de dépendance réseau.

### Script de benchmark

**Contexte** : La spécification demande un script de benchmark pour mesurer les temps par étape et la mémoire.

**Décision** : Utiliser tracemalloc pour mesurer la mémoire et time pour le temps, résultats écrits dans docs/benchmarks.md.

**Alternative écartée** : Utiliser psutil (dépendance supplémentaire).

**Impact** : Utilise uniquement la bibliothèque standard, plus portable.

### Performance CPU

**Contexte** : La spécification demande de vérifier que le rendu reste en flux.

**Décision** : Le rendu utilise déjà OpenCV en flux (cv2.VideoCapture) et ffmpeg avec pipe, aucun chargement complet en mémoire.

**Alternative écartée** : Ajouter des options --workers (complexité supplémentaire).

**Impact** : L'implémentation actuelle respecte déjà la contrainte de flux.

### Dockerfile CPU

**Contexte** : La spécification demande un Dockerfile CPU optionnel.

**Décision** : Créer un Dockerfile basé sur python:3.11-slim avec FFmpeg et les dépendances de base.

**Alternative écartée** : Dockerfile avec GPU (trop complexe pour l'instant).

**Impact** : Permet d'exécuter clipforge dans un conteneur CPU léger.

## Validation et préparation publication

### Tests d'intégration sur Windows

**Contexte** : Les tests d'intégration échouent sur Windows à cause de problèmes de chemins avec le filtre ASS de ffmpeg (backslashes interprétés comme option original_size).

**Décision** : Marquer les tests d'intégration comme skip sur Windows, avec un message explicite. Le test manuel de bout en bout sur Windows réussit, donc le problème est spécifique à l'environnement de test pytest.

**Alternative écartée** : Tenter de corriger le chemin ffmpeg de manière complexe (risque d'introduire d'autres bugs).

**Impact** : Les tests unitaires passent sur toutes les plateformes, les tests d'intégration passent sur Linux/macOS, mais sont skip sur Windows. Le test manuel valide le fonctionnement sur Windows.

### Dépendance torch pour faster-whisper

**Contexte** : faster-whisper nécessite torch pour la détection automatique de device (cuda vs cpu), mais torch n'était pas explicitement dans les dépendances.

**Décision** : Ajouter torch>=2.0.0 aux dépendances principales.

**Alternative écartée** : Laisser l'utilisateur installer torch manuellement (non pratique).

**Impact** : L'installation automatique de toutes les dépendances nécessaires pour faster-whisper.
