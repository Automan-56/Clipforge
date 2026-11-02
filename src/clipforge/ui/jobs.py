"""Gestion des jobs de traitement en sous-processus."""

import logging
import subprocess

from clipforge.config import Settings
from clipforge.store import ClipforgeError, ProjectStore

logger = logging.getLogger(__name__)


class JobManager:
    """Gestionnaire de jobs de traitement."""

    def __init__(self, settings: Settings) -> None:
        """Initialise le gestionnaire de jobs.

        Args:
            settings: Configuration clipforge.
        """
        self.settings = settings
        self.store = ProjectStore(settings)
        self.running_jobs: dict[str, subprocess.Popen] = {}

    def start_pipeline_job(
        self,
        source: str,
        title: str | None = None,
        model: str = "small",
        language: str | None = None,
        provider: str = "heuristic",
        max_clips: int = 10,
        min_sec: int = 30,
        max_sec: int = 60,
        top: int | None = None,
        preset: str = "default",
        draft: bool = False,
        force: bool = False,
    ) -> str:
        """Démarre un job de pipeline en sous-processus.

        Args:
            source: URL ou chemin du fichier source.
            title: Titre du projet.
            model: Modèle Whisper.
            language: Langue de transcription.
            provider: Fournisseur LLM.
            max_clips: Nombre maximum de clips.
            min_sec: Durée minimum des clips.
            max_sec: Durée maximum des clips.
            top: Nombre de clips à rendre.
            preset: Preset de sous-titres.
            draft: Mode brouillon.
            force: Force la réexécution.

        Returns:
            ID du projet créé.

        Raises:
            ClipforgeError: Si le démarrage échoue.
        """
        # Construire la commande
        cmd = [
            "clipforge",
            "run",
            source,
            "--model", model,
            "--provider", provider,
            "--max-clips", str(max_clips),
            "--min-sec", str(min_sec),
            "--max-sec", str(max_sec),
            "--preset", preset,
        ]

        if title:
            cmd.extend(["--title", title])
        if language:
            cmd.extend(["--language", language])
        if top:
            cmd.extend(["--top", str(top)])
        if draft:
            cmd.append("--draft")
        if force:
            cmd.append("--force")

        # Démarrer le sous-processus
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except FileNotFoundError as err:
            raise ClipforgeError("clipforge non trouvé dans le PATH") from err

        # Obtenir l'ID du projet depuis le processus
        # Pour l'instant, on retourne un ID factice
        job_id = f"job_{len(self.running_jobs)}"
        self.running_jobs[job_id] = process

        logger.info(f"Job {job_id} démarré (PID: {process.pid})")
        return job_id

    def cancel_job(self, job_id: str) -> bool:
        """Annule un job en cours.

        Args:
            job_id: ID du job.

        Returns:
            True si annulé, False si introuvable.
        """
        if job_id not in self.running_jobs:
            return False

        process = self.running_jobs[job_id]
        process.terminate()
        process.wait(timeout=5.0)

        del self.running_jobs[job_id]
        logger.info(f"Job {job_id} annulé")
        return True

    def get_job_status(self, project_id: str) -> dict[str, any]:
        """Récupère le statut d'un job depuis state.json.

        Args:
            project_id: ID du projet.

        Returns:
            Dictionnaire avec le statut du job.
        """
        try:
            state = self.store.load_state(project_id)
            return {
                "stages": {name: status.model_dump() for name, status in state.stages.items()},
                "timings": state.timings,
                "config": state.config,
            }
        except ClipforgeError:
            return {"stages": {}, "timings": {}, "config": {}}

    def is_job_running(self, job_id: str) -> bool:
        """Vérifie si un job est en cours.

        Args:
            job_id: ID du job.

        Returns:
            True si en cours.
        """
        if job_id not in self.running_jobs:
            return False

        process = self.running_jobs[job_id]
        return process.poll() is None
