"""Tests unitaires pour les utilitaires."""

import pytest

from clipforge.utils import format_timestamp, slugify


class TestSlugify:
    """Tests pour la fonction slugify."""

    def test_slugify_basic(self) -> None:
        assert slugify("Hello World") == "hello-world"
        assert slugify("Test Project") == "test-project"

    def test_slugify_special_chars(self) -> None:
        assert slugify("Hello, World!") == "hello-world"
        assert slugify("Test @#$% Project") == "test-project"

    def test_slugify_max_length(self) -> None:
        assert len(slugify("a" * 100, max_length=50)) <= 50

    def test_slugify_empty(self) -> None:
        assert slugify("") == "untitled"
        assert slugify("@#$%") == "untitled"


class TestFormatTimestamp:
    """Tests pour la fonction format_timestamp."""

    def test_format_timestamp_srt(self) -> None:
        assert format_timestamp(0.0, "srt") == "00:00:00,000"
        assert format_timestamp(1.5, "srt") == "00:00:01,500"
        assert format_timestamp(3661.123, "srt") == "01:01:01,123"

    def test_format_timestamp_ffmpeg(self) -> None:
        assert format_timestamp(0.0, "ffmpeg") == "00:00:00.000"
        assert format_timestamp(1.5, "ffmpeg") == "00:00:01.500"
        assert format_timestamp(3661.123, "ffmpeg") == "01:01:01.123"

    def test_format_timestamp_human(self) -> None:
        assert format_timestamp(5.0, "human") == "5s"
        assert format_timestamp(65.0, "human") == "1m 5s"
        assert format_timestamp(3665.0, "human") == "1h 1m 5s"

    def test_format_timestamp_invalid(self) -> None:
        with pytest.raises(ValueError, match="Format inconnu"):
            format_timestamp(1.0, "invalid")
