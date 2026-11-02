"""Tests pour l'orchestrateur de pipeline."""

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

# Mock faster-whisper before imports
sys.modules["faster_whisper"] = MagicMock()
sys.modules["faster_whisper.transcribe"] = MagicMock()

from clipforge.config import Settings  # noqa: E402
from clipforge.models import StageState, StageStatus  # noqa: E402
from clipforge.pipeline import Pipeline  # noqa: E402
from clipforge.store import ClipforgeError, ProjectStore  # noqa: E402


class TestPipeline:
    """Tests pour la classe Pipeline."""

    def test_run_stage_ingest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            settings = Settings()
            settings.workspace_dir = tmpdir_path / "workspace"
            store = ProjectStore(settings)
            pipeline = Pipeline(settings, store)

            # Créer un projet factice
            state = store.create_project("test_source", "Test", 10.0, {})

            # Mock ingest_video
            with patch("clipforge.pipeline.ingest_video") as mock_ingest:
                mock_ingest.return_value = state

                pipeline._run_stage("ingest", state)

                mock_ingest.assert_called_once()

    def test_run_stage_transcribe(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            settings = Settings()
            settings.workspace_dir = tmpdir_path / "workspace"
            store = ProjectStore(settings)
            pipeline = Pipeline(settings, store)

            state = store.create_project("test_source", "Test", 10.0, {})
            project_id = state.id

            # Créer audio.wav
            audio_path = store.get_file_path(project_id, "audio.wav")
            audio_path.parent.mkdir(parents=True, exist_ok=True)
            audio_path.write_bytes(b"fake audio")

            with patch("clipforge.pipeline.transcribe_project") as mock_transcribe:
                pipeline._run_stage("transcribe", state)
                mock_transcribe.assert_called_once()

    def test_run_stage_analyze(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            settings = Settings()
            settings.workspace_dir = tmpdir_path / "workspace"
            store = ProjectStore(settings)
            pipeline = Pipeline(settings, store)

            state = store.create_project("test_source", "Test", 10.0, {})
            project_id = state.id

            # Créer transcript.json
            transcript_path = store.get_file_path(project_id, "transcript.json")
            transcript_path.parent.mkdir(parents=True, exist_ok=True)
            transcript_path.write_text('{"language":"en","language_probability":0.95,"duration":10.0,"segments":[]}')

            with patch("clipforge.pipeline.analyze_transcript") as mock_analyze:
                pipeline._run_stage("analyze", state)
                mock_analyze.assert_called_once()

    def test_run_stage_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            settings = Settings()
            settings.workspace_dir = tmpdir_path / "workspace"
            store = ProjectStore(settings)
            pipeline = Pipeline(settings, store)

            state = store.create_project("test_source", "Test", 10.0, {})

            try:
                pipeline._run_stage("unknown", state)
                raise AssertionError("Devrait lever ClipforgeError")
            except ClipforgeError:
                pass

    def test_skip_completed_stage(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            settings = Settings()
            settings.workspace_dir = tmpdir_path / "workspace"
            store = ProjectStore(settings)
            pipeline = Pipeline(settings, store)

            state = store.create_project("test_source", "Test", 10.0, {})
            project_id = state.id

            # Marquer une étape comme terminée
            state.stages["ingest"] = StageStatus(state=StageState.DONE)
            store.save_state(state)

            progress_called = []

            def progress_callback(stage: str, fraction: float) -> None:
                progress_called.append((stage, fraction))

            pipeline.run(
                project_id=project_id,
                stages=["ingest"],
                force=False,
                on_progress=progress_callback,
            )

            # L'étape doit être skipée
            assert progress_called[-1] == ("ingest", 1.0)

    def test_resume_on_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            settings = Settings()
            settings.workspace_dir = tmpdir_path / "workspace"
            store = ProjectStore(settings)
            pipeline = Pipeline(settings, store)

            state = store.create_project("test_source", "Test", 10.0, {})
            project_id = state.id

            # Marquer une étape comme échouée
            state.stages["ingest"] = StageStatus(state=StageState.FAILED, error="Test error")
            store.save_state(state)

            # Mock ingest_video pour réussir au second essai
            with patch("clipforge.pipeline.ingest_video") as mock_ingest:
                mock_ingest.return_value = state

                pipeline.run(
                    project_id=project_id,
                    stages=["ingest"],
                    force=False,
                )

                # L'étape doit être réexécutée
                mock_ingest.assert_called_once()



