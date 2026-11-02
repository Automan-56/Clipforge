"""Fonctions utilitaires pour clipforge."""

import logging
import re
import shutil
import subprocess
from pathlib import Path

from clipforge.store import ClipforgeError

logger = logging.getLogger(__name__)


def run_cmd(
    cmd: list[str],
    cwd: Path | None = None,
    capture: bool = True,
    check: bool = True,
) -> str:
    """Exécute une commande shell et retourne la sortie.

    Args:
        cmd: Commande et arguments sous forme de liste.
        cwd: Répertoire de travail (optionnel).
        capture: Si True, capture stdout/stderr. Sinon, utilise le terminal.
        check: Si True, lève une exception si le code de retour est non nul.

    Returns:
        Sortie stdout si capture=True.

    Raises:
        ClipforgeError: Si la commande échoue et check=True.
    """
    logger.debug(f"Exécution : {' '.join(cmd)}")

    try:
        if capture:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                check=check,
            )
            return result.stdout
        else:
            subprocess.run(cmd, cwd=cwd, check=check)
            return ""
    except subprocess.CalledProcessError as e:
        error_msg = f"La commande a échoué : {' '.join(cmd)}"
        if e.stderr:
            error_msg += f"\n{e.stderr}"
        raise ClipforgeError(error_msg) from e
    except FileNotFoundError as e:
        raise ClipforgeError(f"Commande introuvable : {cmd[0]}") from e


def require_binary(name: str) -> Path:
    """Vérifie qu'un binaire est disponible dans le PATH.

    Args:
        name: Nom du binaire (ex: ffmpeg, ffprobe).

    Returns:
        Chemin vers le binaire.

    Raises:
        ClipforgeError: Si le binaire n'est pas trouvé.
    """
    path = shutil.which(name)
    if not path:
        raise ClipforgeError(
            f"Le binaire '{name}' n'est pas trouvé dans le PATH. "
            "Veuillez installer FFmpeg et l'ajouter à votre PATH."
        )
    return Path(path)


def slugify(text: str, max_length: int = 50) -> str:
    """Convertit un texte en slug URL-friendly.

    Args:
        text: Texte à convertir.
        max_length: Longueur maximale du slug.

    Returns:
        Slug en minuscules, avec des tirets.
    """
    # Remplace les caractères non-alphanumériques par des tirets
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower())
    # Supprime les tirets au début et à la fin
    slug = slug.strip("-")
    # Tronque si nécessaire
    if len(slug) > max_length:
        slug = slug[:max_length].rstrip("-")
    return slug or "untitled"


def format_timestamp(seconds: float, format_type: str = "srt") -> str:
    """Formate un timestamp en secondes selon le format demandé.

    Args:
        seconds: Timestamp en secondes.
        format_type: Format de sortie ("srt", "ffmpeg", "human").

    Returns:
        Timestamp formaté.
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    millis = int((secs - int(secs)) * 1000)
    secs_int = int(secs)

    if format_type == "srt":
        return f"{hours:02d}:{minutes:02d}:{secs_int:02d},{millis:03d}"
    elif format_type == "ffmpeg":
        return f"{hours:02d}:{minutes:02d}:{secs_int:02d}.{millis:03d}"
    elif format_type == "human":
        if hours > 0:
            return f"{hours}h {minutes}m {secs_int}s"
        elif minutes > 0:
            return f"{minutes}m {secs_int}s"
        else:
            return f"{secs_int}s"
    else:
        raise ValueError(f"Format inconnu : {format_type}")


def setup_logging(level: str = "INFO") -> None:
    """Configure le logging global.

    Args:
        level: Niveau de logging (DEBUG, INFO, WARNING, ERROR).
    """
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
