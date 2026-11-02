"""Pipeline de traitement clipforge."""

import logging
from collections.abc import Callable
from datetime import datetime

from clipforge.analyze import analyze_transcript
from clipforge.config import Settings
from clipforge.ingest import ingest_video
from clipforge.models import ProjectState, StageState, StageStatus
from clipforge.render import render_clip
from clipforge.store import ClipforgeError, ProjectStore
from clipforge.transcribe.whisper import transcribe_project
from clipforge.vision import compute_crop_plan

logger = logging.getLogger(__name__)


class Pipeline:
    """Pipeline de traitement clipforge."""

    def __init__(self, settings: Settings, store: ProjectStore) -> None:
        """Initialise le pipeline.

        Args:
            settings: Configuration clipforge.
            store: Gestionnaire de stockage des projets.
        """
        self.settings = settings
        self.store = store

    def run(
        self,
        project_id: str,
        stages: list[str],
        force: bool = False,
        on_progress: Callable[[str, float], None] | None = None,
        **kwargs,
    ) -> ProjectState:
        """Exécute les étapes spécifiées du pipeline.

        Args:
            project_id: Identifiant du projet.
            stages: Liste des étapes à exécuter (ex: ["ingest", "transcribe"]).
            force: Si True, force la réexécution même si déjà terminé.
            on_progress: Callback appelé pendant l'exécution (stage_name, fraction).
            **kwargs: Paramètres supplémentaires pour les étapes.

        Returns:
            État final du projet.

        Raises:
            ClipforgeError: Si une étape échoue.
        """
        state = self.store.load_state(project_id)

        for stage_name in stages:
            if on_progress:
                on_progress(stage_name, 0.0)

            status = state.stages.get(stage_name, StageStatus())

            # Skip si déjà terminé et pas de force
            if status.state == StageState.DONE and not force:
                logger.info(f"Étape {stage_name} déjà terminée, skip")
                if on_progress:
                    on_progress(stage_name, 1.0)
                continue

            # Marquer comme en cours
            status.state = StageState.RUNNING
            status.started_at = datetime.now()
            status.error = None
            state.stages[stage_name] = status
            self.store.save_state(state)

            try:
                # Exécuter l'étape
                self._run_stage(stage_name, state, on_progress, **kwargs)

                # Marquer comme terminé
                status.state = StageState.DONE
                status.ended_at = datetime.now()
                duration = (status.ended_at - status.started_at).total_seconds()
                state.timings[stage_name] = duration
                state.stages[stage_name] = status
                self.store.save_state(state)

                logger.info(f"Étape {stage_name} terminée en {duration:.2f}s")

            except Exception as e:
                # Marquer comme échoué
                status.state = StageState.FAILED
                status.ended_at = datetime.now()
                status.error = str(e)
                state.stages[stage_name] = status
                self.store.save_state(state)

                error_msg = f"Étape {stage_name} échouée : {e}"
                logger.error(error_msg)
                raise ClipforgeError(error_msg) from e

            if on_progress:
                on_progress(stage_name, 1.0)

        return state

    def _run_stage(
        self,
        stage_name: str,
        state: ProjectState,
        on_progress: Callable[[str, float], None] | None = None,
        **kwargs,
    ) -> None:
        """Exécute une étape spécifique.

        Args:
            stage_name: Nom de l'étape.
            state: État du projet.
            on_progress: Callback de progression.
            **kwargs: Paramètres supplémentaires.

        Raises:
            ClipforgeError: Si l'étape échoue.
        """
        project_id = state.id

        if stage_name == "ingest":
            # L'ingestion crée le projet, donc on passe state.config
            ingest_video(
                source=kwargs.get("source", state.source),
                title=kwargs.get("title", state.title),
                cookies_from_browser=kwargs.get("cookies_from_browser"),
                settings=self.settings,
                store=self.store,
                on_progress=lambda s, f: on_progress(stage_name, f) if on_progress else None,
            )
            # Recharger l'état après ingestion
            state = self.store.load_state(project_id)

        elif stage_name == "transcribe":
            transcribe_project(
                project_id=project_id,
                model=kwargs.get("model", "small"),
                language=kwargs.get("language"),
                force=kwargs.get("force", False),
                settings=self.settings,
                store=self.store,
                on_progress=lambda s, f: on_progress(stage_name, f) if on_progress else None,
            )

        elif stage_name == "analyze":
            analyze_transcript(
                project_id=project_id,
                provider=kwargs.get("provider", "heuristic"),
                max_clips=kwargs.get("max_clips", 10),
                min_sec=kwargs.get("min_sec", 30),
                max_sec=kwargs.get("max_sec", 60),
                force=kwargs.get("force", False),
                settings=self.settings,
                store=self.store,
                on_progress=lambda s, f: on_progress(stage_name, f) if on_progress else None,
            )

        elif stage_name == "reframe":
            # Récupérer le nombre de clips
            import json
            candidates_path = self.store.get_file_path(project_id, "candidates.json")
            if candidates_path.exists():
                with open(candidates_path, encoding="utf-8") as f:
                    candidates_data = json.load(f)
                clip_count = len(candidates_data)
            else:
                clip_count = 0

            for clip_id in range(clip_count):
                compute_crop_plan(
                    project_id=project_id,
                    clip_id=clip_id,
                    layout=kwargs.get("layout", "auto"),
                    debug_video=kwargs.get("debug_video", False),
                    force=kwargs.get("force", False),
                    settings=self.settings,
                    store=self.store,
                    on_progress=lambda s, f: on_progress(stage_name, f) if on_progress else None,
                )

        elif stage_name == "render":
            # Récupérer le nombre de clips
            import json
            candidates_path = self.store.get_file_path(project_id, "candidates.json")
            if candidates_path.exists():
                with open(candidates_path, encoding="utf-8") as f:
                    candidates_data = json.load(f)
                clip_count = len(candidates_data)
            else:
                clip_count = 0

            top = kwargs.get("top", clip_count)
            clip_ids = list(range(min(top, clip_count)))

            for clip_id in clip_ids:
                render_clip(
                    project_id=project_id,
                    clip_id=clip_id,
                    preset=kwargs.get("preset", "default"),
                    draft=kwargs.get("draft", False),
                    force=kwargs.get("force", False),
                    settings=self.settings,
                    store=self.store,
                    on_progress=lambda s, f: on_progress(stage_name, f) if on_progress else None,
                )

        else:
            raise ClipforgeError(f"Étape inconnue : {stage_name}")


def run_full_pipeline(
    source: str,
    title: str | None = None,
    cookies_from_browser: str | None = None,
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
    settings: Settings | None = None,
    on_progress: Callable[[str, float], None] | None = None,
) -> ProjectState:
    """Exécute le pipeline complet.

    Args:
        source: URL ou chemin du fichier source.
        title: Titre du projet.
        cookies_from_browser: Navigateur pour les cookies.
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
        settings: Configuration.
        on_progress: Callback de progression.

    Returns:
        État final du projet.

    Raises:
        ClipforgeError: Si le pipeline échoue.
    """
    if settings is None:
        settings = Settings()
    store = ProjectStore(settings)
    pipeline = Pipeline(settings, store)

    # Étape 1 : Ingestion
    state = store.create_project(source, title or "", 0.0, {})
    project_id = state.id

    pipeline.run(
        project_id=project_id,
        stages=["ingest"],
        force=force,
        on_progress=lambda s, f: on_progress("ingest", f) if on_progress else None,
        source=source,
        title=title,
        cookies_from_browser=cookies_from_browser,
    )

    # Étape 2 : Transcription
    pipeline.run(
        project_id=project_id,
        stages=["transcribe"],
        force=force,
        on_progress=lambda s, f: on_progress("transcribe", f) if on_progress else None,
        model=model,
        language=language,
    )

    # Étape 3 : Analyse
    pipeline.run(
        project_id=project_id,
        stages=["analyze"],
        force=force,
        on_progress=lambda s, f: on_progress("analyze", f) if on_progress else None,
        provider=provider,
        max_clips=max_clips,
        min_sec=min_sec,
        max_sec=max_sec,
    )

    # Étape 4 : Recadrage
    pipeline.run(
        project_id=project_id,
        stages=["reframe"],
        force=force,
        on_progress=lambda s, f: on_progress("reframe", f) if on_progress else None,
        layout="auto",
    )

    # Étape 5 : Rendu
    pipeline.run(
        project_id=project_id,
        stages=["render"],
        force=force,
        on_progress=lambda s, f: on_progress("render", f) if on_progress else None,
        top=top,
        preset=preset,
        draft=draft,
    )

    # Recharger l'état final
    final_state = store.load_state(project_id)

    # Afficher le rapport
    if on_progress:
        on_progress("done", 1.0)

    logger.info("Pipeline terminé")
    logger.info(f"Durée totale : {sum(final_state.timings.values()):.2f}s")
    for stage, duration in final_state.timings.items():
        logger.info(f"  {stage}: {duration:.2f}s")

    return final_state
