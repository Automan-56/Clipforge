"""Test d'intégration pour le rendu vidéo."""

import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from clipforge.config import Settings
from clipforge.models import ClipCandidate, Segment, Transcript, Word
from clipforge.render import render_clip
from clipforge.store import ProjectStore


@pytest.mark.integration
def test_render_integration() -> None:
    """Test d'intégration du rendu avec ffmpeg réel."""
    # Vérifier que ffmpeg et ffprobe sont disponibles
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("ffmpeg ou ffprobe non disponible")
    
    # Skip sur Windows (problèmes de chemin ffmpeg)
    import platform
    if platform.system() == "Windows":
        pytest.skip("Test d'intégration skip sur Windows (problèmes de chemin ffmpeg)")
    """Test d'intégration du rendu avec ffmpeg réel."""
    # Créer un répertoire temporaire
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Générer une vidéo synthétique
        video_path = tmpdir_path / "source.mp4"
        cmd = [
            "ffmpeg",
            "-f", "lavfi",
            "-i", "testsrc=duration=3:size=640x360:rate=30",
            "-f", "lavfi",
            "-i", "sine=frequency=1000:duration=3",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-c:a", "aac",
            "-shortest",
            "-y",
            str(video_path),
        ]
        subprocess.run(cmd, check=True, capture_output=True)

        # Créer un store temporaire
        settings = Settings()
        settings.workspace_dir = tmpdir_path / "workspace"
        store = ProjectStore(settings)

        # Créer un projet factice
        project_id = "test_project"
        project_dir = store.get_project_dir(project_id)
        project_dir.mkdir(parents=True, exist_ok=True)

        # Copier la vidéo
        shutil.copy(video_path, store.get_file_path(project_id, "source.mp4"))

        # Créer un transcript factice
        words = [
            Word(start=0.0, end=0.5, text="Hello", probability=0.95),
            Word(start=0.5, end=1.0, text="world", probability=0.90),
            Word(start=1.0, end=1.5, text="this", probability=0.95),
            Word(start=1.5, end=2.0, text="is", probability=0.90),
            Word(start=2.0, end=2.5, text="a", probability=0.95),
            Word(start=2.5, end=3.0, text="test", probability=0.90),
        ]

        segments = [
            Segment(id=0, start=0.0, end=3.0, text="Hello world this is a test", words=words),
        ]

        transcript = Transcript(
            language="en",
            language_probability=0.95,
            duration=3.0,
            segments=segments,
        )

        transcript_path = store.get_file_path(project_id, "transcript.json")
        with open(transcript_path, "w", encoding="utf-8") as f:
            f.write(transcript.model_dump_json(indent=2))

        # Créer un candidat factice
        clip = ClipCandidate(
            id=0,
            start=0.0,
            end=3.0,
            start_sentence_id=0,
            end_sentence_id=0,
            title="Test Clip",
            hook="Hello world",
            summary="A test clip",
            keywords=["test"],
            llm_score=85.0,
            heuristic_score=75.0,
            final_score=82.0,
            reasons=["Good content"],
        )

        candidates_path = store.get_file_path(project_id, "candidates.json")
        with open(candidates_path, "w", encoding="utf-8") as f:
            f.write(f"[{clip.model_dump_json(indent=2)}]")

        # Rendre le clip
        output_path = render_clip(
            project_id=project_id,
            clip_id=0,
            preset="default",
            draft=True,  # Utiliser draft pour le test
            force=True,
            settings=settings,
            store=store,
        )

        # Vérifier que le fichier existe
        assert output_path.exists()

        # Vérifier les propriétés avec ffprobe
        probe_cmd = ["ffprobe", "-v", "error", "-show_entries", "stream=width,height,codec_name,duration", "-of", "json", str(output_path)]
        result = subprocess.run(probe_cmd, check=True, capture_output=True, text=True)

        import json
        probe_data = json.loads(result.stdout)

        # Vérifier que c'est une vidéo
        assert "streams" in probe_data
        video_stream = next((s for s in probe_data["streams"] if s["codec_type"] == "video"), None)
        assert video_stream is not None

        # Vérifier les dimensions (draft mode = 720x1280)
        assert video_stream["width"] == 720
        assert video_stream["height"] == 1280

        # Vérifier la durée (avec tolérance)
        duration = float(video_stream["duration"])
        assert 2.9 <= duration <= 3.1  # Tolérance de 0.1s
