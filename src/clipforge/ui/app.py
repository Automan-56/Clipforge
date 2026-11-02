"""Interface utilisateur Streamlit pour clipforge."""

import logging
import tempfile
import zipfile

import streamlit as st

from clipforge.config import Settings
from clipforge.models import ClipCandidate
from clipforge.render import render_clip
from clipforge.store import ClipforgeError, ProjectStore
from clipforge.ui.jobs import JobManager

logger = logging.getLogger(__name__)

# Configuration de la page
st.set_page_config(
    page_title="clipforge",
    page_icon="🎬",
    layout="wide",
)

# Initialiser le gestionnaire de jobs
if "job_manager" not in st.session_state:
    st.session_state.job_manager = JobManager(Settings())

# Initialiser le store
if "store" not in st.session_state:
    st.session_state.store = ProjectStore(Settings())


def render_new_project() -> None:
    """Page de création de nouveau projet."""
    st.header("Nouveau projet")

    # Formulaire
    source_type = st.radio("Type de source", ["URL", "Fichier local"])

    if source_type == "URL":
        source = st.text_input("URL de la vidéo")
    else:
        source = st.file_uploader("Fichier vidéo", type=["mp4", "mov", "avi", "mkv"])
        if source:
            source = f"temp/{source.name}"

    title = st.text_input("Titre (optionnel)")

    col1, col2 = st.columns(2)
    with col1:
        model = st.selectbox("Modèle Whisper", ["tiny", "base", "small", "medium", "large-v3"], index=2)
        provider = st.selectbox("Fournisseur LLM", ["heuristic", "gemini", "ollama"])
    with col2:
        min_sec = st.number_input("Durée minimum (s)", value=30, min_value=10, max_value=300)
        max_sec = st.number_input("Durée maximum (s)", value=60, min_value=30, max_value=600)

    max_clips = st.number_input("Nombre maximum de clips", value=10, min_value=1, max_value=50)

    if st.button("Démarrer le pipeline", type="primary"):
        if not source:
            st.error("Veuillez spécifier une source")
            return

        try:
            with st.spinner("Démarrage du pipeline..."):
                job_id = st.session_state.job_manager.start_pipeline_job(
                    source=source,
                    title=title,
                    model=model,
                    provider=provider,
                    max_clips=max_clips,
                    min_sec=min_sec,
                    max_sec=max_sec,
                )
                st.success(f"Pipeline démarré (Job ID: {job_id})")
                st.session_state.current_project = job_id
                st.rerun()
        except ClipforgeError as e:
            st.error(f"Erreur : {e}")


def render_clips_page(project_id: str) -> None:
    """Page des clips d'un projet."""
    st.header(f"Clips : {project_id}")

    store = st.session_state.store

    # Charger les candidats
    candidates_path = store.get_file_path(project_id, "candidates.json")
    if not candidates_path.exists():
        st.warning("Aucun candidat trouvé. Lancez d'abord l'analyse.")
        return

    import json
    with open(candidates_path, encoding="utf-8") as f:
        candidates_data = json.load(f)
    candidates = [ClipCandidate.model_validate(c) for c in candidates_data]

    # Trier par score
    candidates.sort(key=lambda c: c.final_score, reverse=True)

    # Tableau des clips
    st.subheader("Clips candidats")

    selected_indices = []
    for i, clip in enumerate(candidates):
        with st.expander(f"{clip.title} (Score: {clip.final_score:.1f}/100)"):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.write(f"**Hook**: {clip.hook}")
            with col2:
                st.write(f"**Durée**: {clip.end - clip.start:.1f}s")
            with col3:
                st.write(f"**Score LLM**: {clip.llm_score:.1f}")
                st.write(f"**Score heuristique**: {clip.heuristic_score:.1f}")

            if st.checkbox("Sélectionner", key=f"select_{i}"):
                selected_indices.append(i)

    # Options de rendu
    st.subheader("Options de rendu")
    col1, col2, col3 = st.columns(3)
    with col1:
        preset = st.selectbox("Preset de sous-titres", ["default", "minimal", "bold"])
    with col2:
        st.selectbox("Layout", ["auto", "crop", "blur_fit"])
    with col3:
        draft = st.checkbox("Mode brouillon (720p)")

    if st.button("Rendre les clips sélectionnés", type="primary"):
        if not selected_indices:
            st.warning("Sélectionnez au moins un clip")
            return

        try:
            for idx in selected_indices:
                render_clip(
                    project_id=project_id,
                    clip_id=idx,
                    preset=preset,
                    draft=draft,
                    force=True,
                    settings=Settings(),
                    store=store,
                )
            st.success(f"{len(selected_indices)} clips rendus")
        except ClipforgeError as e:
            st.error(f"Erreur : {e}")

    # Export
    st.subheader("Export")
    if st.button("Télécharger les clips sélectionnés en ZIP"):
        if not selected_indices:
            st.warning("Sélectionnez au moins un clip")
            return

        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
            with zipfile.ZipFile(tmp, "w") as zf:
                # Ajouter les clips
                for idx in selected_indices:
                    clip_path = store.get_file_path(project_id, f"clips/{idx}.mp4")
                    if clip_path.exists():
                        zf.write(clip_path, f"clip_{idx}.mp4")

                # Ajouter le CSV
                csv_content = "Titre,Score,Hook,Début,Fin\n"
                for idx in selected_indices:
                    clip = candidates[idx]
                    csv_content += f"{clip.title},{clip.final_score},{clip.hook},{clip.start:.1f},{clip.end:.1f}\n"
                zf.writestr("clips.csv", csv_content)

            with open(tmp, "rb") as f:
                st.download_button(
                    "Télécharger ZIP",
                    f.read(),
                    file_name="clips.zip",
                    mime="application/zip",
                )


def render_projects_list() -> None:
    """Page de liste des projets."""
    st.header("Projets existants")

    store = st.session_state.store
    projects = store.list_projects()

    if not projects:
        st.info("Aucun projet existant")
        return

    for project in projects:
        with st.expander(f"{project.title or project.id} ({project.id[:8]}...)"):
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Source**: {project.source}")
                st.write(f"**Durée**: {project.duration:.1f}s")
            with col2:
                st.write("**Statut**:")
                for stage_name, status in project.stages.items():
                    st.write(f"  {stage_name}: {status.state}")

            col3, col4 = st.columns(2)
            with col3:
                if st.button("Voir les clips", key=f"view_{project.id}"):
                    st.session_state.current_project = project.id
                    st.rerun()
            with col4:
                if st.button("Supprimer", key=f"delete_{project.id}"):
                    try:
                        store.delete_project(project.id)
                        st.success("Projet supprimé")
                        st.rerun()
                    except ClipforgeError as e:
                        st.error(f"Erreur : {e}")


def main() -> None:
    """Fonction principale de l'interface."""
    st.title("🎬 clipforge")
    st.markdown("Clone open-source d'Opus Clip : transformation de vidéos longues en clips verticaux 9:16")

    # Navigation
    if "current_project" not in st.session_state:
        st.session_state.current_project = None

    if st.session_state.current_project:
        if st.button("← Retour aux projets"):
            st.session_state.current_project = None
            st.rerun()
        render_clips_page(st.session_state.current_project)
    else:
        tab1, tab2 = st.tabs(["Nouveau projet", "Projets existants"])
        with tab1:
            render_new_project()
        with tab2:
            render_projects_list()


if __name__ == "__main__":
    main()
