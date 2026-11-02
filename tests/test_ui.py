"""Tests pour l'interface utilisateur Streamlit."""

import sys
from unittest.mock import MagicMock

# Mock streamlit et mediapipe avant l'import
sys.modules["streamlit"] = MagicMock()
sys.modules["streamlit.web"] = MagicMock()
sys.modules["streamlit.web.cli"] = MagicMock()
sys.modules["mediapipe"] = MagicMock()
sys.modules["mediapipe.solutions"] = MagicMock()

from clipforge.config import Settings  # noqa: E402


class TestUI:
    """Tests pour l'interface utilisateur."""

    def test_job_manager_initialization(self) -> None:
        """Test l'initialisation du JobManager."""
        settings = Settings()
        from clipforge.ui.jobs import JobManager

        job_manager = JobManager(settings)
        assert job_manager.settings == settings
        assert job_manager.running_jobs == {}

    def test_job_manager_cancel_nonexistent(self) -> None:
        """Test l'annulation d'un job inexistant."""
        settings = Settings()
        from clipforge.ui.jobs import JobManager

        job_manager = JobManager(settings)
        result = job_manager.cancel_job("nonexistent")
        assert result is False

    def test_job_manager_is_running_nonexistent(self) -> None:
        """Test le statut d'un job inexistant."""
        settings = Settings()
        from clipforge.ui.jobs import JobManager

        job_manager = JobManager(settings)
        result = job_manager.is_job_running("nonexistent")
        assert result is False
