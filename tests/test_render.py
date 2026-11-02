"""Tests unitaires pour le module de rendu."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

# Mock tomli before import
sys.modules["tomli"] = MagicMock()

from clipforge.models import SubtitleStyle, Word  # noqa: E402
from clipforge.render.subtitles import ass_color, escape_ass, generate_ass, load_preset  # noqa: E402
from clipforge.store import ClipforgeError  # noqa: E402

# Configure tomli mock
sys.modules["tomli"].load.return_value = {"style": {
    "font": "Arial",
    "size": 72,
    "primary_color": "#FFFFFF",
    "highlight_color": "#FFFF00",
    "accent_color": "#00FF00",
    "outline_color": "#000000",
    "outline_width": 6,
    "margin_v": 100,
    "words_per_line": 3,
    "uppercase": False,
    "pop_animation": False,
}}


class TestEscapeAss:
    """Tests pour escape_ass."""

    def test_escape_backslash(self) -> None:
        assert escape_ass("test\\value") == "test\\\\value"

    def test_escape_braces(self) -> None:
        assert escape_ass("test{value}") == "test\\{value\\}"
        assert escape_ass("test}value") == "test\\}value"

    def test_escape_newline(self) -> None:
        assert escape_ass("test\nvalue") == "test\\Nvalue"


class TestAssColor:
    """Tests pour ass_color."""

    def test_hex_to_ass(self) -> None:
        assert ass_color("#FFFFFF") == "&HFFFFFF"
        assert ass_color("#FF0000") == "&H0000FF"  # RGB -> BGR
        assert ass_color("#00FF00") == "&H00FF00"
        assert ass_color("#0000FF") == "&HFF0000"

    def test_already_ass_format(self) -> None:
        assert ass_color("&HFFFFFF") == "&HFFFFFF"


class TestGenerateAss:
    """Tests pour generate_ass."""

    def test_basic_generation(self) -> None:
        words = [
            Word(start=0.0, end=0.5, text="Hello", probability=0.95),
            Word(start=0.5, end=1.0, text="world", probability=0.90),
        ]

        style = SubtitleStyle(
            font="Arial",
            size=72,
            primary_color="#FFFFFF",
            highlight_color="#FFFF00",
            accent_color="#00FF00",
            outline_color="#000000",
            outline_width=6,
            margin_v=100,
            words_per_line=3,
            uppercase=False,
            pop_animation=False,
        )

        ass = generate_ass(words, style, [], 2.0, 1080, 1920)

        assert "[Script Info]" in ass
        assert "PlayResX: 1080" in ass
        assert "PlayResY: 1920" in ass
        assert "[V4+ Styles]" in ass
        assert "[Events]" in ass
        assert "Dialogue:" in ass

    def test_uppercase(self) -> None:
        words = [Word(start=0.0, end=0.5, text="Hello", probability=0.95)]

        style = SubtitleStyle(
            font="Arial",
            size=72,
            primary_color="#FFFFFF",
            highlight_color="#FFFF00",
            accent_color="#00FF00",
            outline_color="#000000",
            outline_width=6,
            margin_v=100,
            words_per_line=3,
            uppercase=True,
            pop_animation=False,
        )

        ass = generate_ass(words, style, [], 1.0, 1080, 1920)

        assert "HELLO" in ass

    def test_keywords_highlight(self) -> None:
        words = [
            Word(start=0.0, end=0.5, text="Hello", probability=0.95),
            Word(start=0.5, end=1.0, text="world", probability=0.90),
        ]

        style = SubtitleStyle(
            font="Arial",
            size=72,
            primary_color="#FFFFFF",
            highlight_color="#FFFF00",
            accent_color="#00FF00",
            outline_color="#000000",
            outline_width=6,
            margin_v=100,
            words_per_line=3,
            uppercase=False,
            pop_animation=False,
        )

        ass = generate_ass(words, style, ["world"], 2.0, 1080, 1920)

        # Le mot "world" devrait avoir la couleur d'accentuation
        assert ass_color(style.accent_color) in ass


class TestLoadPreset:
    """Tests pour load_preset."""

    def test_load_preset_success(self) -> None:
        # Ce test nécessite un fichier preset réel
        # Pour l'instant, on mock tomli
        pass

    def test_load_preset_not_found(self) -> None:
        presets_dir = Path("/tmp/presets")

        try:
            load_preset("nonexistent", presets_dir)
            raise AssertionError("Devrait lever ClipforgeError")
        except ClipforgeError:
            pass
