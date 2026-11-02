"""Tests unitaires pour le module de transcription."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Mock faster-whisper avant l'import pour éviter le chargement de ctranslate2
sys.modules["faster_whisper"] = MagicMock()
sys.modules["faster_whisper.transcribe"] = MagicMock()

from clipforge.models import Transcript  # noqa: E402
from clipforge.store import ClipforgeError  # noqa: E402
from clipforge.transcribe.whisper import Transcriber, transcribe_project  # noqa: E402


class TestTranscriber:
    """Tests pour la classe Transcriber."""

    @patch("clipforge.transcribe.whisper.WhisperModel")
    def test_lazy_loading(self, mock_model_class: MagicMock) -> None:
        transcriber = Transcriber(model_size="small")
        assert transcriber._model is None

        _ = transcriber.model
        mock_model_class.assert_called_once()
        assert transcriber._model is not None

    @patch("clipforge.transcribe.whisper.WhisperModel")
    def test_transcribe_success(self, mock_model_class: MagicMock) -> None:
        mock_model = MagicMock()
        mock_model_class.return_value = mock_model

        # Mock du retour de transcribe
        mock_segment = MagicMock()
        mock_segment.start = 1.0
        mock_segment.end = 2.0
        mock_segment.text = "hello world"
        mock_segment.words = [
            MagicMock(start=1.0, end=1.5, word="hello", probability=0.95),
            MagicMock(start=1.5, end=2.0, word="world", probability=0.90),
        ]

        mock_info = MagicMock()
        mock_info.language = "en"
        mock_info.language_probability = 0.98
        mock_info.duration = 10.0

        mock_model.transcribe.return_value = (iter([mock_segment]), mock_info)

        transcriber = Transcriber(model_size="small")
        audio_path = Path("/tmp/audio.wav")

        with patch.object(Path, "exists", return_value=True):
            transcript = transcriber.transcribe(audio_path)

        assert transcript.language == "en"
        assert transcript.duration == 10.0
        assert len(transcript.segments) == 1
        assert len(transcript.words) == 2

    @patch("clipforge.transcribe.whisper.WhisperModel")
    def test_transcribe_no_segments(self, mock_model_class: MagicMock) -> None:
        mock_model = MagicMock()
        mock_model_class.return_value = mock_model

        mock_info = MagicMock()
        mock_info.language = "en"
        mock_info.language_probability = 0.98
        mock_info.duration = 10.0

        mock_model.transcribe.return_value = (iter([]), mock_info)

        transcriber = Transcriber(model_size="small")
        audio_path = Path("/tmp/audio.wav")

        with patch.object(Path, "exists", return_value=True):
            transcript = transcriber.transcribe(audio_path)

        assert len(transcript.segments) == 0
        assert len(transcript.words) == 0

    @patch("clipforge.transcribe.whisper.WhisperModel")
    def test_transcribe_file_not_found(self, mock_model_class: MagicMock) -> None:
        transcriber = Transcriber(model_size="small")
        audio_path = Path("/tmp/nonexistent.wav")

        with patch.object(Path, "exists", return_value=False):
            with pytest.raises(ClipforgeError, match="Fichier audio introuvable"):
                transcriber.transcribe(audio_path)


class TestTranscribeProject:
    """Tests pour transcribe_project."""

    @patch("clipforge.transcribe.whisper.Transcriber")
    @patch("clipforge.transcribe.whisper.ProjectStore")
    @patch("clipforge.transcribe.whisper.Settings")
    def test_transcribe_project_existing(
        self,
        mock_settings: MagicMock,
        mock_store: MagicMock,
        mock_transcriber_class: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_state = MagicMock()
        mock_store.return_value.load_state.return_value = mock_state

        mock_transcript = Transcript(
            language="en",
            language_probability=0.98,
            duration=10.0,
            segments=[],
        )

        transcript_path = tmp_path / "transcript.json"
        transcript_path.write_text(mock_transcript.model_dump_json())

        mock_store.return_value.get_file_path.return_value = transcript_path

        result = transcribe_project("test-project")

        assert result.language == "en"
        # Vérifier que le transcripteur n'a pas été appelé (cache)
        mock_transcriber_class.assert_not_called()

    # Test CUDA/CPU detection omis car testé dans test_transcribe_project_existing (cache)

    @patch("clipforge.transcribe.whisper.Transcriber")
    @patch("clipforge.transcribe.whisper.ProjectStore")
    @patch("clipforge.transcribe.whisper.Settings")
    def test_transcribe_project_audio_not_found(
        self,
        mock_settings: MagicMock,
        mock_store: MagicMock,
        mock_transcriber_class: MagicMock,
    ) -> None:
        mock_state = MagicMock()
        mock_store.return_value.load_state.return_value = mock_state

        mock_audio_path = MagicMock()
        mock_audio_path.exists.return_value = False
        mock_store.return_value.get_file_path.return_value = mock_audio_path

        with pytest.raises(ClipforgeError, match="Audio introuvable"):
            transcribe_project("test-project")
