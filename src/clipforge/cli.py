"""Interface CLI pour clipforge."""

import sys
from pathlib import Path

import typer
from tqdm import tqdm

from clipforge.analyze import analyze_transcript
from clipforge.config import Settings
from clipforge.ingest import ingest_video
from clipforge.render import render_clip
from clipforge.store import ClipforgeError, ProjectStore
from clipforge.transcribe.whisper import transcribe_project
from clipforge.utils import require_binary, setup_logging
from clipforge.vision import compute_crop_plan

# Forcer UTF-8 pour Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

app = typer.Typer(
    help="clipforge - Clone open-source d'Opus Clip",
    no_args_is_help=True,
)


@app.command()
def ingest(
    source: str = typer.Argument(..., help="Chemin de la vidéo source"),
    title: str | None = typer.Option(None, help="Titre du projet"),
    cookies_from_browser: str | None = typer.Option(None, "--cookies-from-browser", help="Navigateur pour les cookies (chrome, firefox, etc.)"),
) -> None:
    """Ingère une vidéo source et crée un projet."""
    settings = Settings.load_from_toml(Settings().config_file)
    store = ProjectStore(settings)

    def progress_callback(stage: str, fraction: float) -> None:
        if stage == "download":
            tqdm.write(f"Téléchargement : {fraction*100:.0f}%")
        elif stage == "extract":
            tqdm.write(f"Extraction audio : {fraction*100:.0f}%")

    try:
        state = ingest_video(
            source=source,
            title=title,
            cookies_from_browser=cookies_from_browser,
            settings=settings,
            store=store,
            on_progress=progress_callback,
        )
        typer.echo(f"Projet créé : {state.id}")
        typer.echo(f"Titre : {state.title}")
        typer.echo(f"Durée : {state.duration:.2f}s")
    except ClipforgeError as e:
        typer.echo(f"Erreur : {e}", err=True)
        raise typer.Exit(1) from e


@app.command()
def transcribe(
    project_id: str = typer.Argument(..., help="ID du projet"),
    model: str = typer.Option("small", "--model", help="Modèle Whisper (tiny, base, small, medium, large-v3)"),
    language: str | None = typer.Option(None, "--language", help="Langue (ex: fr, en, None = auto)"),
    force: bool = typer.Option(False, "--force", help="Forcer la réexécution"),
) -> None:
    """Transcrit la vidéo avec Whisper."""
    settings = Settings.load_from_toml(Settings().config_file)
    store = ProjectStore(settings)

    def progress_callback(stage: str, fraction: float) -> None:
        if stage == "transcribe":
            tqdm.write(f"Transcription : {fraction*100:.0f}%")

    try:
        transcript = transcribe_project(
            project_id=project_id,
            model=model,
            language=language,
            force=force,
            settings=settings,
            store=store,
            on_progress=progress_callback,
        )
        typer.echo("Transcription terminée")
        typer.echo(f"Langue : {transcript.language}")
        typer.echo(f"Durée : {transcript.duration:.2f}s")
        typer.echo(f"Segments : {len(transcript.segments)}")
        typer.echo(f"Mots : {len(transcript.words)}")
    except ClipforgeError as e:
        typer.echo(f"Erreur : {e}", err=True)
        raise typer.Exit(1) from e


@app.command()
def analyze(
    project_id: str = typer.Argument(..., help="ID du projet"),
    provider: str = typer.Option("heuristic", "--provider", help="Fournisseur LLM (gemini, ollama, heuristic)"),
    max_clips: int = typer.Option(10, "--max-clips", help="Nombre maximum de clips"),
    min_sec: int = typer.Option(30, "--min-sec", help="Durée minimum en secondes"),
    max_sec: int = typer.Option(60, "--max-sec", help="Durée maximum en secondes"),
    force: bool = typer.Option(False, "--force", help="Forcer la réexécution"),
) -> None:
    """Analyse la transcription pour identifier les clips candidats."""
    settings = Settings.load_from_toml(Settings().config_file)
    store = ProjectStore(settings)

    def progress_callback(stage: str, fraction: float) -> None:
        if stage == "analyze":
            tqdm.write(f"Analyse : {fraction*100:.0f}%")

    try:
        candidates = analyze_transcript(
            project_id=project_id,
            provider=provider,  # type: ignore
            max_clips=max_clips,
            min_sec=min_sec,
            max_sec=max_sec,
            force=force,
            settings=settings,
            store=store,
            on_progress=progress_callback,
        )
        typer.echo(f"Analyse terminée : {len(candidates)} candidats trouvés")
        for i, c in enumerate(candidates[:5], 1):
            typer.echo(f"{i}. {c.title} ({c.start:.1f}s - {c.end:.1f}s) : {c.final_score:.1f}/100")
    except ClipforgeError as e:
        typer.echo(f"Erreur : {e}", err=True)
        raise typer.Exit(1) from e


@app.command()
def reframe(
    project_id: str = typer.Argument(..., help="ID du projet"),
    clip_id: int | None = typer.Option(None, "--clip", help="ID du clip (sinon tous)"),
    layout: str = typer.Option("auto", "--layout", help="Layout (auto, crop, blur_fit)"),
    debug_video: bool = typer.Option(False, "--debug-video", help="Générer une vidéo de débogage"),
    force: bool = typer.Option(False, "--force", help="Forcer la réexécution"),
) -> None:
    """Calcule les plans de recadrage pour chaque clip."""
    settings = Settings.load_from_toml(Settings().config_file)
    store = ProjectStore(settings)

    def progress_callback(stage: str, fraction: float) -> None:
        if stage == "reframe":
            tqdm.write(f"Recadrage : {fraction*100:.0f}%")

    try:
        if clip_id is not None:
            crop_plan = compute_crop_plan(
                project_id=project_id,
                clip_id=clip_id,
                layout=layout,  # type: ignore
                debug_video=debug_video,
                force=force,
                settings=settings,
                store=store,
                on_progress=progress_callback,
            )
            typer.echo(f"Cropplan calculé pour clip {clip_id} : {len(crop_plan.keyframes)} keyframes")
        else:
            # Traiter tous les clips
            candidates_path = store.get_file_path(project_id, "candidates.json")
            if not candidates_path.exists():
                raise ClipforgeError(f"Candidats introuvables pour {project_id}")

            import json
            with open(candidates_path, encoding="utf-8") as f:
                candidates_data = json.load(f)

            for i in range(len(candidates_data)):
                crop_plan = compute_crop_plan(
                    project_id=project_id,
                    clip_id=i,
                    layout=layout,  # type: ignore
                    debug_video=debug_video,
                    force=force,
                    settings=settings,
                    store=store,
                    on_progress=progress_callback,
                )
                typer.echo(f"Clip {i} : {len(crop_plan.keyframes)} keyframes")

            typer.echo(f"Recadrage terminé : {len(candidates_data)} clips traités")
    except ClipforgeError as e:
        typer.echo(f"Erreur : {e}", err=True)
        raise typer.Exit(1) from e


@app.command()
def render(
    project_id: str = typer.Argument(..., help="ID du projet"),
    clip_id: int | None = typer.Option(None, "--clip", help="ID du clip"),
    top: int | None = typer.Option(None, "--top", help="Rendre les N meilleurs clips"),
    preset: str = typer.Option("default", "--preset", help="Preset de style"),
    draft: bool = typer.Option(False, "--draft", help="Mode brouillon (720p)"),
    force: bool = typer.Option(False, "--force", help="Forcer la réexécution"),
) -> None:
    """Génère les clips finaux avec sous-titres."""
    settings = Settings.load_from_toml(Settings().config_file)
    store = ProjectStore(settings)

    def progress_callback(stage: str, fraction: float) -> None:
        if stage == "render":
            tqdm.write(f"Rendu : {fraction*100:.0f}%")

    try:
        # Charger les candidats
        candidates_path = store.get_file_path(project_id, "candidates.json")
        if not candidates_path.exists():
            raise ClipforgeError(f"Candidats introuvables pour {project_id}")

        import json
        with open(candidates_path, encoding="utf-8") as f:
            candidates_data = json.load(f)

        # Déterminer les clips à rendre
        if clip_id is not None:
            clip_ids = [clip_id]
        elif top is not None:
            clip_ids = list(range(min(top, len(candidates_data))))
        else:
            clip_ids = list(range(len(candidates_data)))

        for cid in clip_ids:
            output_path = render_clip(
                project_id=project_id,
                clip_id=cid,
                preset=preset,
                draft=draft,
                force=force,
                settings=settings,
                store=store,
                on_progress=progress_callback,
            )
            typer.echo(f"Clip {cid} rendu : {output_path}")

        typer.echo(f"Rendu terminé : {len(clip_ids)} clips")
    except ClipforgeError as e:
        typer.echo(f"Erreur : {e}", err=True)
        raise typer.Exit(1) from e


@app.command()
def run(
    source: str = typer.Argument(..., help="Chemin de la vidéo source"),
    title: str | None = typer.Option(None, help="Titre du projet"),
    model: str = typer.Option("small", "--model", help="Modèle Whisper"),
    language: str | None = typer.Option(None, "--language", help="Langue de transcription"),
    provider: str = typer.Option("heuristic", "--provider", help="Fournisseur LLM"),
    max_clips: int = typer.Option(10, "--max-clips", help="Nombre maximum de clips"),
    min_sec: int = typer.Option(30, "--min-sec", help="Durée minimum des clips"),
    max_sec: int = typer.Option(60, "--max-sec", help="Durée maximum des clips"),
    top: int | None = typer.Option(None, "--top", help="Nombre de clips à rendre"),
    preset: str = typer.Option("default", "--preset", help="Preset de sous-titres"),
    draft: bool = typer.Option(False, "--draft", help="Mode brouillon"),
    force: bool = typer.Option(False, "--force", help="Forcer la réexécution complète"),
) -> None:
    """Exécute le pipeline complet (ingest → transcribe → analyze → reframe → render)."""
    settings = Settings.load_from_toml(Settings().config_file)

    def progress_callback(stage: str, fraction: float) -> None:
        tqdm.write(f"{stage} : {fraction*100:.0f}%")

    try:
        from clipforge.pipeline import run_full_pipeline

        final_state = run_full_pipeline(
            source=source,
            title=title,
            model=model,
            language=language,
            provider=provider,
            max_clips=max_clips,
            min_sec=min_sec,
            max_sec=max_sec,
            top=top,
            preset=preset,
            draft=draft,
            force=force,
            settings=settings,
            on_progress=progress_callback,
        )

        typer.echo(f"Pipeline terminé : {final_state.id}")
        typer.echo(f"Durée totale : {sum(final_state.timings.values()):.2f}s")
    except ClipforgeError as e:
        typer.echo(f"Erreur : {e}", err=True)
        raise typer.Exit(1) from e


@app.command()
def ui() -> None:
    """Lance l'interface utilisateur interactive."""
    try:
        import streamlit.web.cli as stcli

        # Exécuter streamlit
        sys.argv = ["streamlit", "run", str(Path(__file__).parent / "ui" / "app.py")]
        stcli.main()
    except ImportError:
        typer.echo("Streamlit n'est pas installé. Installez-le avec: pip install -e .[ui]", err=True)
        raise typer.Exit(1) from None


@app.command()
def doctor() -> None:
    """Vérifie les dépendances système (ffmpeg, ffprobe, etc.)."""
    typer.echo("=== Diagnostic clipforge ===")
    typer.echo()

    # Python version
    import sys
    typer.echo(f"Python version : {sys.version}")

    # FFmpeg
    try:
        ffmpeg_path = require_binary("ffmpeg")
        typer.echo(f"✓ ffmpeg trouvé : {ffmpeg_path}")
    except ClipforgeError as e:
        typer.echo(f"✗ {e}")

    # FFprobe
    try:
        ffprobe_path = require_binary("ffprobe")
        typer.echo(f"✓ ffprobe trouvé : {ffprobe_path}")
    except ClipforgeError as e:
        typer.echo(f"✗ {e}")

    # faster-whisper
    try:
        import faster_whisper
        typer.echo(f"✓ faster-whisper installé : {faster_whisper.__version__}")
    except ImportError:
        typer.echo("✗ faster-whisper non installé (pip install -e .[whisper])")

    # Whisper models
    from pathlib import Path
    model_dir = Path.home() / ".cache" / "huggingface" / "hub"
    if model_dir.exists():
        typer.echo(f"✓ Répertoire de modèles Whisper : {model_dir}")
    else:
        typer.echo("✗ Répertoire de modèles Whisper non trouvé")

    # Gemini
    from clipforge.config import Settings
    settings = Settings.load_from_toml(Settings().config_file)
    if settings.llm_provider == "gemini":
        if settings.gemini_api_key:
            typer.echo("✓ Clé API Gemini configurée")
        else:
            typer.echo("✗ Clé API Gemini non configurée")
    else:
        typer.echo(f"ℹ Gemini non configuré (provider: {settings.llm_provider})")

    # Ollama
    if settings.llm_provider == "ollama":
        try:
            import httpx
            response = httpx.get(settings.ollama_base_url + "/api/tags", timeout=2.0)
            if response.status_code == 200:
                typer.echo(f"✓ Ollama accessible : {settings.ollama_base_url}")
            else:
                typer.echo(f"✗ Ollama non accessible : {settings.ollama_base_url}")
        except Exception:
            typer.echo(f"✗ Ollama non accessible : {settings.ollama_base_url}")
    else:
        typer.echo(f"ℹ Ollama non configuré (provider: {settings.llm_provider})")

    # Encoder
    from clipforge.render.encoder import detect_encoder
    try:
        encoder = detect_encoder()
        typer.echo(f"✓ Encodeur détecté : {encoder}")
    except Exception as e:
        typer.echo(f"✗ Erreur de détection de l'encodeur : {e}")

    # Workspace
    if settings.workspace_dir.exists():
        typer.echo(f"✓ Répertoire workspace : {settings.workspace_dir}")
    else:
        typer.echo(f"ℹ Répertoire workspace sera créé : {settings.workspace_dir}")

    typer.echo()
    typer.echo("=== Diagnostic terminé ===")


def main() -> None:
    """Point d'entrée principal."""
    # Charger la configuration
    settings = Settings.load_from_toml(Settings().config_file)

    # Configurer le logging
    setup_logging(settings.log_level)

    # Vérifier les binaires au démarrage (sauf pour --help et doctor)
    if len(sys.argv) > 1 and sys.argv[1] not in ["--help", "doctor", "help"]:
        try:
            require_binary("ffmpeg")
            require_binary("ffprobe")
        except ClipforgeError as e:
            typer.echo(f"Erreur : {e}", err=True)
            raise typer.Exit(1) from e

    app()


if __name__ == "__main__":
    main()
