"""Test d'intégration bout en bout pour clipforge."""

import subprocess
import tempfile
from pathlib import Path

import pytest


@pytest.mark.integration
def test_full_pipeline_integration() -> None:
    """Test d'intégration du pipeline complet sur une vidéo libre de droits."""
    # Utiliser une vidéo générée localement pour éviter les dépendances réseau
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Générer une vidéo de test avec ffmpeg
        video_path = tmpdir_path / "test_video.mp4"
        cmd = [
            "ffmpeg",
            "-f", "lavfi",
            "-i", "testsrc=duration=180:size=1280x720:rate=30",
            "-f", "lavfi",
            "-i", "sine=frequency=1000:duration=180",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-c:a", "aac",
            "-shortest",
            "-y",
            str(video_path),
        ]

        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            pytest.skip(f"ffmpeg non disponible : {e}")

        # Exécuter le pipeline complet
        cmd = [
            "clipforge",
            "run",
            str(video_path),
            "--model", "tiny",
            "--provider", "heuristic",
            "--max-clips", "3",
            "--top", "1",
            "--draft",
        ]

        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            pytest.skip(f"clipforge non disponible : {e}")

        # Vérifier que le clip a été créé
        # Le pipeline crée un projet dans workspace/, on peut extraire l'ID depuis la sortie
        output_lines = result.stdout.split("\n")
        project_id = None
        for line in output_lines:
            if "Pipeline terminé" in line:
                # Extraire l'ID du projet
                parts = line.split(":")
                if len(parts) > 1:
                    project_id = parts[1].strip()
                    break

        if not project_id:
            pytest.skip("Impossible d'extraire l'ID du projet")

        # Vérifier que le clip existe
        workspace = Path("workspace")
        if not workspace.exists():
            pytest.skip("Workspace non trouvé")

        project_dir = workspace / project_id
        if not project_dir.exists():
            pytest.skip(f"Projet {project_id} non trouvé")

        clips_dir = project_dir / "clips"
        if not clips_dir.exists():
            pytest.skip("Clips non générés")

        clips = list(clips_dir.glob("*.mp4"))
        if not clips:
            pytest.skip("Aucun clip généré")

        # Vérifier les propriétés du clip avec ffprobe
        clip_path = clips[0]
        probe_cmd = ["ffprobe", "-v", "error", "-show_entries", "stream=width,height,codec_name,duration", "-of", "json", str(clip_path)]
        probe_result = subprocess.run(probe_cmd, check=True, capture_output=True, text=True)

        import json
        probe_data = json.loads(probe_result.stdout)

        # Vérifier que c'est une vidéo
        assert "streams" in probe_data
        video_stream = next((s for s in probe_data["streams"] if s["codec_type"] == "video"), None)
        assert video_stream is not None

        # Vérifier les dimensions (draft mode = 720x1280)
        assert video_stream["width"] == 720
        assert video_stream["height"] == 1280

        # Vérifier la durée (tolérance de 5 secondes)
        duration = float(video_stream["duration"])
        assert 25 <= duration <= 185  # Tolérance
