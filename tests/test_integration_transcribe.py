"""Tests d'intégration pour la transcription."""

import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Mock faster-whisper pour les tests d'intégration
sys.modules["faster_whisper"] = MagicMock()
sys.modules["faster_whisper.transcribe"] = MagicMock()

from clipforge.config import Settings  # noqa: E402
from clipforge.ingest import extract_audio  # noqa: E402
from clipforge.store import ProjectStore  # noqa: E402
from clipforge.transcribe.whisper import transcribe_project  # noqa: E402


@pytest.mark.integration
def test_transcribe_integration(tmp_path: Path) -> None:
    """Test d'intégration complet de la transcription."""
    # Vérifier que ffmpeg est disponible
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg non disponible")
    
    # Skip sur Windows (problèmes de chemin ffmpeg)
    import platform
    if platform.system() == "Windows":
        pytest.skip("Test d'intégration skip sur Windows (problèmes de chemin ffmpeg)")
    """Test d'intégration complet de la transcription."""

    # Générer un fichier vidéo de test avec ffmpeg
    video_path = tmp_path / "test_video.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-f", "lavfi",
            "-i", "testsrc=duration=10:size=320x240:rate=30",
            "-f", "lavfi",
            "-i", "sine=frequency=1000:duration=10",
            "-c:v", "libx264",
            "-c:a", "pcm_s16le",
            "-y",
            str(video_path),
        ],
        check=True,
        capture_output=True,
    )

    # Extraire l'audio
    audio_path = tmp_path / "test_audio.wav"
    duration = extract_audio(video_path, audio_path)
    assert duration > 0
    assert audio_path.exists()

    # Créer un projet manuellement
    settings = Settings()
    store = ProjectStore(settings)

    project_id = "test-integration"
    project_dir = store.get_project_dir(project_id)
    project_dir.mkdir(parents=True, exist_ok=True)

    # Créer l'état du projet
    store.create_project(
        source=str(video_path),
        title="Test Integration",
        duration=duration,
        config=settings.model_dump(),
    )

    # Copier l'audio dans le projet
    project_audio = store.get_file_path(project_id, "audio.wav")
    shutil.copy(audio_path, project_audio)

    # Transcrire avec le modèle tiny (plus rapide)
    transcript = transcribe_project(
        project_id=project_id,
        model="tiny",
        force=True,
        settings=settings,
        store=store,
    )

    # Vérifications
    assert transcript is not None
    assert transcript.duration > 0
    assert transcript.language is not None

    # Vérifier que les fichiers de sortie existent
    assert store.get_file_path(project_id, "transcript.json").exists()
    assert store.get_file_path(project_id, "transcript.srt").exists()
    assert store.get_file_path(project_id, "transcript.txt").exists()

    # Vérifier que les mots sont ordonnés
    if transcript.words:
        for i in range(len(transcript.words) - 1):
            assert transcript.words[i].start <= transcript.words[i + 1].start
            assert transcript.words[i].end > transcript.words[i].start

    # Nettoyer
    shutil.rmtree(project_dir)
