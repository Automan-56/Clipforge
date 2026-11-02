"""Détection et configuration de l'encodeur vidéo."""

import logging
import subprocess

from clipforge.utils import require_binary

logger = logging.getLogger(__name__)


def detect_encoder() -> str:
    """Détecte l'encodeur vidéo disponible.

    Returns:
        Nom de l'encodeur (h264_nvenc ou libx264).

    Raises:
        ClipforgeError: Si aucun encodeur n'est disponible.
    """
    require_binary("ffmpeg")

    # Test rapide avec h264_nvenc
    try:
        result = subprocess.run(
            ["ffmpeg", "-f", "lavfi", "-i", "testsrc=duration=0.1:size=320x240", "-c:v", "h264_nvenc", "-f", "null", "-"],
            capture_output=True,
            timeout=5.0,
        )
        if result.returncode == 0:
            logger.info("Encodeur h264_nvenc détecté")
            return "h264_nvenc"
    except Exception:
        pass

    logger.info("Encodeur h264_nvenc non disponible, utilisation de libx264")
    return "libx264"


def get_encoder_params(
    encoder: str,
    draft: bool = False,
) -> list[str]:
    """Retourne les paramètres d'encodage.

    Args:
        encoder: Nom de l'encodeur.
        draft: Mode brouillon.

    Returns:
        Liste de paramètres ffmpeg.
    """
    if encoder == "h264_nvenc":
        if draft:
            return ["-c:v", "h264_nvenc", "-preset", "p1", "-crf", "28"]
        else:
            return ["-c:v", "h264_nvenc", "-preset", "p4", "-crf", "20"]
    else:  # libx264
        if draft:
            return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "28"]
        else:
            return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20"]


def get_audio_params(draft: bool = False) -> list[str]:
    """Retourne les paramètres audio.

    Args:
        draft: Mode brouillon.

    Returns:
        Liste de paramètres ffmpeg.
    """
    bitrate = "96k" if draft else "128k"
    return ["-c:a", "aac", "-b:a", bitrate]
