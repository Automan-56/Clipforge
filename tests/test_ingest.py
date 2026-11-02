"""Tests unitaires pour le module d'ingestion."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from clipforge.ingest import extract_audio, generate_project_id
from clipforge.store import ClipforgeError


class TestGenerateProjectId:
    """Tests pour generate_project_id."""

    @patch("clipforge.ingest.yt_dlp.YoutubeDL")
    def test_generate_project_id_url(self, mock_ydl: MagicMock) -> None:
        # Simplifier : tester seulement le fallback hash
        mock_ydl.side_effect = Exception("Network error")
        project_id = generate_project_id("https://youtube.com/watch?v=abc123", is_url=True)
        assert len(project_id) == 12  # hash tronqué

    @patch("clipforge.ingest.yt_dlp.YoutubeDL")
    def test_generate_project_id_url_fallback(self, mock_ydl: MagicMock) -> None:
        mock_ydl.side_effect = Exception("Network error")

        project_id = generate_project_id("https://example.com/video", is_url=True)
        assert len(project_id) == 12  # hash tronqué

    def test_generate_project_id_local(self) -> None:
        project_id = generate_project_id("/path/to/My Video.mp4", is_url=False)
        assert "my-video" in project_id.lower()
        # slugify remplace les espaces par des tirets, donc il peut y avoir plusieurs parties
        assert "-" in project_id


class TestExtractAudio:
    """Tests pour extract_audio."""

    @patch("clipforge.ingest.require_binary")
    @patch("clipforge.ingest.ffmpeg.probe")
    @patch("clipforge.ingest.ffmpeg.input")
    def test_extract_audio_success(
        self,
        mock_input: MagicMock,
        mock_probe: MagicMock,
        mock_require: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_require.return_value = Path("/usr/bin/ffmpeg")
        mock_probe.return_value = {
            "format": {"duration": "120.5"},
            "streams": [{"codec_type": "audio"}],
        }

        # Simuler que ffmpeg crée le fichier .part
        def fake_run(*args, **kwargs):
            part_path = tmp_path / "audio.wav.part"
            part_path.touch()
            return (b"", b"")

        mock_input.return_value.output.return_value.overwrite_output.return_value.run.side_effect = fake_run

        video_path = tmp_path / "video.mp4"
        video_path.touch()
        output_path = tmp_path / "audio.wav"

        duration = extract_audio(video_path, output_path)

        assert duration == 120.5
        assert output_path.exists()

    @patch("clipforge.ingest.require_binary")
    @patch("clipforge.ingest.ffmpeg.probe")
    def test_extract_audio_no_audio_track(
        self,
        mock_probe: MagicMock,
        mock_require: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_require.return_value = Path("/usr/bin/ffmpeg")
        mock_probe.return_value = {
            "format": {"duration": "120.5"},
            "streams": [{"codec_type": "video"}],
        }

        video_path = tmp_path / "video.mp4"
        video_path.touch()
        output_path = tmp_path / "audio.wav"

        with pytest.raises(ClipforgeError, match="aucune piste audio"):
            extract_audio(video_path, output_path)

    @patch("clipforge.ingest.require_binary")
    @patch("clipforge.ingest.ffmpeg.probe")
    @patch("clipforge.ingest.ffmpeg.input")
    def test_extract_audio_ffmpeg_error(
        self,
        mock_input: MagicMock,
        mock_probe: MagicMock,
        mock_require: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_require.return_value = Path("/usr/bin/ffmpeg")
        mock_probe.return_value = {
            "format": {"duration": "120.5"},
            "streams": [{"codec_type": "audio"}],
        }
        # Simuler une erreur ffmpeg générique
        mock_input.side_effect = RuntimeError("FFmpeg error")

        video_path = tmp_path / "video.mp4"
        video_path.touch()
        output_path = tmp_path / "audio.wav"

        with pytest.raises(ClipforgeError, match="Erreur inattendue"):
            extract_audio(video_path, output_path)

        # Vérifier que le fichier partiel est nettoyé
        part_path = output_path.with_suffix(".wav.part")
        assert not part_path.exists()
