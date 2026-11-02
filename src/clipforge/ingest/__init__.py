"""Module d'ingestion vidéo et audio."""

import hashlib
import logging
import re
from collections.abc import Callable
from pathlib import Path

import ffmpeg
import yt_dlp

from clipforge.config import Settings
from clipforge.models import ProjectState
from clipforge.store import ClipforgeError, ProjectStore
from clipforge.utils import require_binary, slugify

logger = logging.getLogger(__name__)


def generate_project_id(source: str, is_url: bool) -> str:
    """Génère un ID de projet déterministe.

    Args:
        source: URL ou chemin du fichier.
        is_url: True si source est une URL.

    Returns:
        ID de projet unique.
    """
    if is_url:
        # Pour les URLs : extracteur + id de la vidéo
        try:
            info = yt_dlp.YoutubeDL({"quiet": True}).extract_info(
                source, download=False, process=False
            )
            extractor = info.get("extractor_key", "unknown")
            video_id = info.get("id", "unknown")
            return f"{extractor}-{video_id}"
        except Exception:
            # Fallback : hash de l'URL
            return hashlib.md5(source.encode()).hexdigest()[:12]
    else:
        # Pour les fichiers locaux : slug + hash court
        path = Path(source)
        name = slugify(path.stem)
        file_hash = hashlib.md5(str(path.absolute()).encode()).hexdigest()[:8]
        return f"{name}-{file_hash}"


def extract_audio(
    video_path: Path,
    output_path: Path,
    on_progress: Callable[[float], None] | None = None,
) -> float:
    """Extrait l'audio d'une vidéo vers WAV 16 kHz mono.

    Args:
        video_path: Chemin de la vidéo source.
        output_path: Chemin de sortie WAV.
        on_progress: Callback de progression (fraction 0-1).

    Returns:
        Durée de l'audio en secondes.

    Raises:
        ClipforgeError: Si l'extraction échoue.
    """
    require_binary("ffmpeg")
    require_binary("ffprobe")

    # Écrire dans un fichier .part pour atomicité
    part_path = output_path.with_suffix(output_path.suffix + ".part")
    
    # Créer le répertoire parent si nécessaire
    part_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Obtenir la durée avec ffprobe
        probe = ffmpeg.probe(str(video_path))
        duration = float(probe["format"]["duration"])

        # Vérifier qu'il y a une piste audio
        audio_streams = [
            s for s in probe["streams"] if s["codec_type"] == "audio"
        ]
        if not audio_streams:
            raise ClipforgeError("Le fichier ne contient aucune piste audio")

        logger.info(f"Extraction audio : {video_path} -> {part_path}")

        # Extraire l'audio avec ffmpeg
        (
            ffmpeg.input(str(video_path))
            .output(
                str(part_path),
                format="wav",
                acodec="pcm_s16le",
                ac=1,  # mono
                ar=16000,  # 16 kHz
                loglevel="error",
            )
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )

        # Renommer de manière atomique
        part_path.replace(output_path)

        logger.info(f"Audio extrait avec succès : {output_path}")
        return duration

    except ffmpeg.Error as e:
        # Nettoyer le fichier partiel
        if part_path.exists():
            part_path.unlink()
        error_msg = e.stderr.decode() if e.stderr else "Erreur inconnue"
        raise ClipforgeError(f"Erreur lors de l'extraction audio : {error_msg}") from e
    except KeyboardInterrupt:
        # Nettoyer le fichier partiel en cas d'interruption
        if part_path.exists():
            part_path.unlink()
        raise ClipforgeError("Extraction audio interrompue par l'utilisateur") from None
    except Exception as e:
        if part_path.exists():
            part_path.unlink()
        raise ClipforgeError(f"Erreur inattendue lors de l'extraction audio : {e}") from e


def download_video(
    url: str,
    output_path: Path,
    cookies_from_browser: str | None = None,
    on_progress: Callable[[float], None] | None = None,
) -> Path:
    """Télécharge une vidéo depuis une URL.

    Args:
        url: URL de la vidéo.
        output_path: Chemin de sortie.
        cookies_from_browser: Navigateur pour les cookies (chrome, firefox, etc.).
        on_progress: Callback de progression (fraction 0-1).

    Returns:
        Chemin du fichier téléchargé.

    Raises:
        ClipforgeError: Si le téléchargement échoue.
    """
    ydl_opts = {
        "format": "best[height<=1080][ext=mp4]/best[height<=1080]/best",
        "outtmpl": str(output_path),
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "retries": 3,
        "fragment_retries": 10,
    }

    if cookies_from_browser:
        ydl_opts["cookiesfrombrowser"] = (cookies_from_browser,)

    def progress_hook(d: dict) -> None:
        if on_progress and d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 1
            downloaded = d.get("downloaded_bytes", 0)
            fraction = min(downloaded / total, 1.0)
            on_progress(fraction)

    ydl_opts["progress_hooks"] = [progress_hook]

    try:
        logger.info(f"Téléchargement depuis {url}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # yt-dlp peut changer le nom du fichier (ajouter .mkv, etc.)
        # Trouver le fichier correspondant
        if not output_path.exists():
            possible_files = list(output_path.parent.glob(f"{output_path.stem}.*"))
            if possible_files:
                downloaded = possible_files[0]
                downloaded.rename(output_path)
            else:
                raise ClipforgeError("Fichier téléchargé introuvable")

        logger.info(f"Téléchargement terminé : {output_path}")
        return output_path

    except yt_dlp.utils.DownloadError as e:
        raise ClipforgeError(
            f"Erreur de téléchargement : {e}. "
            "La vidéo peut être privée, supprimée ou géo-bloquée."
        ) from e
    except Exception as e:
        raise ClipforgeError(f"Erreur lors du téléchargement : {e}") from e


def ingest_video(
    source: str,
    title: str | None = None,
    cookies_from_browser: str | None = None,
    settings: Settings | None = None,
    store: ProjectStore | None = None,
    on_progress: Callable[[str, float], None] | None = None,
) -> ProjectState:
    """Ingère une vidéo (URL ou fichier local).

    Args:
        source: URL ou chemin local de la vidéo.
        title: Titre optionnel du projet.
        cookies_from_browser: Navigateur pour les cookies.
        settings: Configuration clipforge.
        store: Gestionnaire de stockage.
        on_progress: Callback (étape, fraction).

    Returns:
        État du projet créé.

    Raises:
        ClipforgeError: Si l'ingestion échoue.
    """
    if settings is None:
        settings = Settings()
    if store is None:
        store = ProjectStore(settings)

    # Déterminer si c'est une URL
    url_pattern = re.compile(
        r"^(https?|ftp)://[-\w.]*(\/[\w.-]*)*\/?$"
    )
    is_url = bool(url_pattern.match(source))

    # Générer l'ID de projet
    project_id = generate_project_id(source, is_url)

    # Vérifier si le projet existe déjà
    try:
        existing_state = store.load_state(project_id)
        logger.info(f"Projet {project_id} existe déjà, chargement")
        return existing_state
    except ClipforgeError:
        pass  # Projet n'existe pas, on le crée

    logger.info(f"Création du projet {project_id}")

    # Chemins de sortie
    project_dir = store.get_project_dir(project_id)
    source_path = project_dir / "source.mp4"
    audio_path = project_dir / "audio.wav"

    # Télécharger ou référencer la vidéo
    if is_url:
        download_video(
            source,
            source_path,
            cookies_from_browser=cookies_from_browser,
            on_progress=lambda f: on_progress("download", f) if on_progress else None,
        )
    else:
        # Fichier local : vérifier qu'il existe
        local_path = Path(source)
        if not local_path.exists():
            raise ClipforgeError(f"Fichier introuvable : {source}")
        if not local_path.is_file():
            raise ClipforgeError(f"Ce n'est pas un fichier : {source}")

        # Référencer sans copie
        source_path = local_path
        logger.info(f"Utilisation du fichier local : {source_path}")

    # Extraire l'audio
    duration = extract_audio(
        source_path,
        audio_path,
        on_progress=lambda f: on_progress("extract", f) if on_progress else None,
    )

    # Déterminer le titre
    if title is None:
        if is_url:
            try:
                info = yt_dlp.YoutubeDL({"quiet": True}).extract_info(
                    source, download=False, process=False
                )
                title = info.get("title", source)
            except Exception:
                title = source
        else:
            title = Path(source).stem

    # Créer l'état du projet
    state = store.create_project(
        source=str(source_path),
        title=title,
        duration=duration,
        config=settings.model_dump(),
        project_id=project_id,
    )

    logger.info(f"Projet {project_id} créé avec succès")
    return state
