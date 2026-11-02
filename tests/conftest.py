"""Fixtures pytest pour les tests."""

import pytest

from clipforge.models import Segment, Transcript, Word


@pytest.fixture
def sample_transcript_30min() -> Transcript:
    """Fixture : transcript synthétique de 30 minutes.

    Génère un transcript avec des segments et mots réalistes pour tester
    l'analyse sans commiter de gros fichiers.
    """
    # Créer un transcript synthétique
    segments: list[Segment] = []
    segment_id = 0
    current_time = 0.0

    # 30 minutes = 1800 secondes
    # Créer ~180 segments de ~10 secondes chacun
    for _i in range(180):
        segment_duration = 10.0
        words: list[Word] = []

        # ~20 mots par segment
        for j in range(20):
            word_start = current_time + j * 0.5
            word_end = word_start + 0.4
            words.append(
                Word(
                    start=round(word_start, 3),
                    end=round(word_end, 3),
                    text=f"mot{j}",
                    probability=0.95,
                )
            )

        segment = Segment(
            id=segment_id,
            start=round(current_time, 3),
            end=round(current_time + segment_duration, 3),
            text=" ".join(f"mot{j}" for j in range(20)),
            words=words,
        )
        segments.append(segment)

        segment_id += 1
        current_time += segment_duration

    return Transcript(
        language="fr",
        language_probability=0.98,
        duration=1800.0,
        segments=segments,
    )
