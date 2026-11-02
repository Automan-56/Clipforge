"""Rendu vidéo avec sous-titres incrustés."""

import logging
import subprocess
from collections.abc import Callable
from pathlib import Path

from clipforge.config import Settings
from clipforge.models import ClipCandidate, Transcript
from clipforge.render.encoder import detect_encoder, get_audio_params, get_encoder_params
from clipforge.render.subtitles import generate_ass, load_preset
from clipforge.store import ClipforgeError, ProjectStore

logger = logging.getLogger(__name__)


def render_clip(
    project_id: str,
    clip_id: int,
    preset: str = "default",
    draft: bool = False,
    force: bool = False,
    settings: Settings | None = None,
    store: ProjectStore | None = None,
    on_progress: Callable[[str, float], None] | None = None,
) -> Path:
    """Rendu un clip avec sous-titres.

    Args:
        project_id: ID du projet.
        clip_id: ID du clip.
        preset: Nom du preset de style.
        draft: Mode brouillon.
        force: Forcer la réexécution.
        settings: Configuration.
        store: Gestionnaire de stockage.
        on_progress: Callback de progression.

    Returns:
        Chemin du fichier rendu.

    Raises:
        ClipforgeError: Si le rendu échoue.
    """
    if settings is None:
        settings = Settings()
    if store is None:
        store = ProjectStore(settings)

    # Charger les candidats et transcript
    candidates_path = store.get_file_path(project_id, "candidates.json")
    transcript_path = store.get_file_path(project_id, "transcript.json")
    video_path = store.get_file_path(project_id, "source.mp4")

    if not candidates_path.exists():
        raise ClipforgeError(f"Candidats introuvables pour {project_id}")
    if not transcript_path.exists():
        raise ClipforgeError(f"Transcript introuvable pour {project_id}")
    if not video_path.exists():
        raise ClipforgeError(f"Vidéo source introuvable pour {project_id}")

    import json

    with open(candidates_path, encoding="utf-8") as f:
        candidates_data = json.load(f)
    candidates = [ClipCandidate.model_validate(c) for c in candidates_data]

    if clip_id >= len(candidates):
        raise ClipforgeError(f"Clip ID {clip_id} invalide")

    clip = candidates[clip_id]

    with open(transcript_path, encoding="utf-8") as f:
        transcript_data = json.load(f)
    transcript = Transcript.model_validate(transcript_data)

    # Vérifier le cache
    output_path = store.get_file_path(project_id, f"clips/{clip_id}.mp4")
    if output_path.exists() and not force:
        logger.info(f"Clip {clip_id} déjà rendu")
        return output_path

    logger.info(f"Rendu du clip {clip_id} avec preset {preset}")

    # Charger le preset
    presets_dir = Path(__file__).parent.parent.parent.parent / "assets" / "presets"
    style = load_preset(preset, presets_dir)

    # Extraire les mots du clip
    clip_words = transcript.words_between(clip.start, clip.end)

    # Générer le fichier ASS
    ass_content = generate_ass(
        clip_words,
        style,
        clip.keywords,
        clip.end - clip.start,
        1080 if not draft else 720,
        1920 if not draft else 1280,
    )

    # Écrire le fichier ASS temporaire
    ass_path = store.get_file_path(project_id, f"clips/{clip_id}.ass")
    ass_path.parent.mkdir(parents=True, exist_ok=True)
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(ass_content)

    # Encoder
    encoder = detect_encoder()
    video_params = get_encoder_params(encoder, draft)
    audio_params = get_audio_params(draft)

    # Dimensions
    width = 1080 if not draft else 720
    height = 1920 if not draft else 1280

    # Chemins relatifs pour ffmpeg (évite les problèmes sur Windows)
    ass_rel = ass_path.relative_to(ass_path.parent.parent)
    output_rel = output_path.relative_to(output_path.parent.parent)
    cwd = ass_path.parent.parent

    # Commande ffmpeg
    cmd = [
        "ffmpeg",
        "-y",
        "-ss", str(clip.start),
        "-t", str(clip.end - clip.start),
        "-i", str(video_path),
        *video_params,
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-af", "afade=t=in:st=0:d=0.1,afade=t=out:st=0:d=0.1",
        "-vf", f"scale={width}:{height},ass={ass_rel}",
        *audio_params,
        str(output_rel),
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True, cwd=str(cwd))
        logger.info(f"Clip {clip_id} rendu avec succès")
    except subprocess.CalledProcessError as e:
        # Nettoyer le fichier partiel
        if output_path.exists():
            output_path.unlink()
        raise ClipforgeError(f"Erreur de rendu : {e.stderr}") from e

    return output_path
