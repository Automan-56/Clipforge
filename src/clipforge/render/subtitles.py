"""Génération de sous-titres ASS."""

import logging
from pathlib import Path

from clipforge.models import SubtitleStyle, Word
from clipforge.store import ClipforgeError

logger = logging.getLogger(__name__)

# Ponctuation forte
STRONG_PUNCTUATION = {".", "!", "?", "。", "！", "？", "…"}


def escape_ass(text: str) -> str:
    """Échappe les caractères spéciaux pour ASS."""
    return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}").replace("\n", "\\N")


def ass_color(hex_color: str) -> str:
    """Convertit une couleur hexa au format ASS."""
    # Format attendu : &HAABBGGRR
    if hex_color.startswith("#"):
        hex_color = hex_color[1:]
    # Convertir RGB -> BGR pour ASS
    if len(hex_color) == 6:
        r = hex_color[0:2]
        g = hex_color[2:4]
        b = hex_color[4:6]
        return f"&H{b}{g}{r}"
    return hex_color


def generate_ass(
    words: list[Word],
    style: SubtitleStyle,
    keywords: list[str],
    duration: float,
    video_width: int = 1080,
    video_height: int = 1920,
) -> str:
    """Génère un fichier ASS pour les sous-titres.

    Args:
        words: Mots du clip.
        style: Style de sous-titres.
        keywords: Mots à accentuer.
        duration: Durée du clip.
        video_width: Largeur de la vidéo.
        video_height: Hauteur de la vidéo.

    Returns:
        Contenu du fichier ASS.
    """
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {video_width}",
        f"PlayResY: {video_height}",
        "WrapStyle: 2",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        f"Format: Name={style.font}, Fontsize={style.size}, PrimaryColour={ass_color(style.primary_color)}, SecondaryColour=&H00000000, OutlineColour={ass_color(style.outline_color)}, BackColour=&H80000000, Bold=-1, BorderStyle=1, Outline={style.outline_width}, Shadow=2, Alignment=2, MarginV={style.margin_v}",
        "",
        "[Events]",
    ]

    # Regrouper les mots en lignes
    current_line: list[Word] = []
    line_start = 0.0

    for _i, word in enumerate(words):
        # Vérifier si on doit commencer une nouvelle ligne
        needs_new_line = False

        if not current_line:
            # Premier mot de la ligne
            current_line.append(word)
            line_start = word.start
        else:
            # Vérifier la longueur de la ligne
            line_text = " ".join(w.text for w in current_line + [word])
            if len(line_text) > 22:
                needs_new_line = True
            # Vérifier la pause
            gap = word.start - current_line[-1].end
            if gap > 0.4:
                needs_new_line = True
            # Vérifier la ponctuation
            if current_line[-1].text and current_line[-1].text[-1] in STRONG_PUNCTUATION:
                needs_new_line = True

            if needs_new_line:
                # Écrire la ligne actuelle
                lines.extend(_generate_line_events(
                    current_line,
                    line_start,
                    words,
                    style,
                    keywords,
                ))
                current_line = [word]
                line_start = word.start
            else:
                current_line.append(word)

    # Dernière ligne
    if current_line:
        lines.extend(_generate_line_events(
            current_line,
            line_start,
            words,
            style,
            keywords,
        ))

    return "\n".join(lines)


def _generate_line_events(
    line_words: list[Word],
    line_start: float,
    all_words: list[Word],
    style: SubtitleStyle,
    keywords: list[str],
) -> list[str]:
    """Génère les événements Dialogue pour une ligne."""
    events: list[str] = []
    line_text = " ".join(w.text for w in line_words)

    if style.uppercase:
        line_text = line_text.upper()

    start_time = line_start * 10  # ASS time is in centiseconds

    for i, word in enumerate(line_words):
        word_end = word.end * 10
        if i < len(line_words) - 1:
            next_start = line_words[i + 1].start * 10
        else:
            next_start = min(word_end + 500, start_time + 10000)  # Max 10s pour le dernier mot

        # Déterminer la couleur
        if word.text.lower() in [kw.lower() for kw in keywords]:
            color = ass_color(style.accent_color)
        else:
            color = ass_color(style.primary_color)

        if style.pop_animation:
            # Transformation de mise à l'écale
            scale = f"\\t({int((word.start - line_start) * 10)}\\,\\fscy110)"
        else:
            scale = ""

        # Format ASS: Dialog format
        # Using escape for braces and building the string carefully
        line_text_escaped = escape_ass(line_text)
        ass_line = f"Dialogue: {start_time},{next_start},Default,,0,0,0,,{scale}{{\\bord1c&H000000&}}\\c1{color}}}{line_text_escaped}"
        events.append(ass_line)

    return events


def load_preset(preset_name: str, presets_dir: Path) -> SubtitleStyle:
    """Charge un preset de style depuis un fichier TOML.

    Args:
        preset_name: Nom du preset.
        presets_dir: Répertoire des presets.

    Returns:
        Style de sous-titres.

    Raises:
        ClipforgeError: Si le preset n'existe pas.
    """
    try:
        import tomli
    except ImportError as err:
        raise ClipforgeError("tomli est requis pour les presets. Installez-le avec pip install tomli.") from err

    preset_path = presets_dir / f"{preset_name}.toml"
    if not preset_path.exists():
        raise ClipforgeError(f"Preset introuvable : {preset_name}")

    with open(preset_path, encoding="utf-8") as f:
        data = tomli.load(f)

    style_data = data.get("style", {})
    
    # Vérifier si la police personnalisée existe
    font = style_data.get("font", "Arial")
    fontsdir = style_data.get("fontsdir")
    if fontsdir:
        font_path = Path(fontsdir) / f"{font}.ttf"
        if not font_path.exists():
            import logging
            logging.warning(f"Police {font} introuvable, utilisation de Arial à la place")
            style_data["font"] = "Arial"
            style_data.pop("fontsdir", None)
    
    return SubtitleStyle(**style_data)
