"""Calcul du score heuristique pour les clips."""

import logging
import re

from clipforge.models import ClipCandidate, Sentence, Word

logger = logging.getLogger(__name__)


def calculate_heuristic_score(
    candidate: ClipCandidate,
    sentences: list[Sentence],
    all_words: list[Word],
    target_duration: float = 45.0,
) -> float:
    """Calcule le score heuristique d'un candidat.

    Args:
        candidate: Candidat à scorer.
        sentences: Toutes les phrases du transcript.
        all_words: Tous les mots du transcript.
        target_duration: Durée cible idéale.

    Returns:
        Score 0-100.
    """
    score = 50.0  # Score de base

    # Trouver les phrases du candidat
    candidate_sentences = [
        s for s in sentences
        if candidate.start_sentence_id <= s.id <= candidate.end_sentence_id
    ]

    if not candidate_sentences:
        return 0.0

    # Durée
    duration = candidate.end - candidate.start
    duration_score = 100.0 - abs(duration - target_duration) / target_duration * 100.0
    score += 0.2 * duration_score

    # Densité de parole (mots par seconde)
    candidate_words = [w for s in candidate_sentences for w in s.words]
    if duration > 0:
        word_density = len(candidate_words) / duration
        # Idéalement ~2-3 mots/seconde
        density_score = 100.0 - abs(word_density - 2.5) / 2.5 * 50.0
        score += 0.15 * max(0, density_score)

    # Accroche forte dans les 3 premières secondes
    first_3_sec_words = [w for w in candidate_words if w.start - candidate.start <= 3.0]
    hook_score = 0.0
    for word in first_3_sec_words:
        # Question
        if word.text.lower() in {"quoi", "pourquoi", "comment", "what", "why", "how"}:
            hook_score = max(hook_score, 80.0)
        # Chiffre
        if re.search(r"\d", word.text):
            hook_score = max(hook_score, 60.0)
        # Affirmation tranchée
        if word.text.lower() in {"c'est", "cest", "en fait", "donc", "alors", "en réalité"}:
            hook_score = max(hook_score, 70.0)
    score += 0.25 * hook_score

    # Absence de longs silences (> 1.5 s)
    silence_count = 0
    for i in range(len(candidate_words) - 1):
        gap = candidate_words[i + 1].start - candidate_words[i].end
        if gap > 1.5:
            silence_count += 1
    silence_score = 100.0 - (silence_count / len(candidate_words)) * 100.0
    score += 0.15 * max(0, silence_score)

    # Variété lexicale (ratio mots uniques / total)
    unique_words = {w.text.lower() for w in candidate_words}
    if candidate_words:
        variety_ratio = len(unique_words) / len(candidate_words)
        variety_score = variety_ratio * 100.0
        score += 0.15 * variety_score

    # Limites
    return max(0.0, min(100.0, score))
