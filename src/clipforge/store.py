"""Stockage persistant des états de projets."""

import json
import uuid
from pathlib import Path
from typing import Any

from clipforge.config import Settings
from clipforge.models import ProjectState


class ClipforgeError(Exception):
    """Exception de base pour clipforge."""

    pass


class ProjectStore:
    """Gestionnaire de stockage pour les projets clipforge."""

    def __init__(self, settings: Settings) -> None:
        """Initialise le store avec les paramètres donnés."""
        self.settings = settings
        self.workspace = settings.workspace_dir
        self.workspace.mkdir(parents=True, exist_ok=True)

    def get_project_dir(self, project_id: str) -> Path:
        """Retourne le répertoire d'un projet."""
        return self.workspace / project_id

    def create_project(self, source: str, title: str, duration: float, config: dict[str, Any], project_id: str | None = None) -> ProjectState:
        """Crée un nouveau projet avec un ID unique."""
        if project_id is None:
            project_id = str(uuid.uuid4())
        project_dir = self.get_project_dir(project_id)
        project_dir.mkdir(parents=True, exist_ok=True)

        state = ProjectState(
            id=project_id,
            source=source,
            title=title,
            duration=duration,
            config=config,
        )

        self.save_state(state)
        return state

    def load_state(self, project_id: str) -> ProjectState:
        """Charge l'état d'un projet depuis le disque."""
        state_file = self.get_project_dir(project_id) / "state.json"
        if not state_file.exists():
            raise ClipforgeError(f"Projet {project_id} introuvable")

        with open(state_file, encoding="utf-8") as f:
            data = json.load(f)

        return ProjectState.model_validate(data)

    def save_state(self, state: ProjectState) -> None:
        """Sauvegarde l'état d'un projet de manière atomique."""
        project_dir = self.get_project_dir(state.id)
        project_dir.mkdir(parents=True, exist_ok=True)

        state_file = project_dir / "state.json"
        temp_file = state_file.with_suffix(".tmp")

        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(state.model_dump(mode="json"), f, indent=2, ensure_ascii=False)

        temp_file.replace(state_file)

    def get_file_path(self, project_id: str, filename: str) -> Path:
        """Retourne le chemin d'un fichier dans le répertoire du projet."""
        project_dir = self.get_project_dir(project_id)
        project_dir.mkdir(parents=True, exist_ok=True)
        return project_dir / filename

    def list_projects(self) -> list[ProjectState]:
        """Liste tous les projets existants."""
        projects: list[ProjectState] = []
        for project_dir in self.workspace.iterdir():
            if not project_dir.is_dir():
                continue
            state_file = project_dir / "state.json"
            if state_file.exists():
                try:
                    state = self.load_state(project_dir.name)
                    projects.append(state)
                except Exception:
                    continue
        return projects

    def delete_project(self, project_id: str) -> None:
        """Supprime un projet et tous ses fichiers."""
        project_dir = self.get_project_dir(project_id)
        if not project_dir.exists():
            raise ClipforgeError(f"Projet {project_id} introuvable")

        import shutil
        shutil.rmtree(project_dir)
