"""Module d'analyse LLM et découpage en clips."""

import json
import logging
from collections.abc import Callable
from typing import Any, Literal

from clipforge.analyze.gemini import GeminiClient
from clipforge.analyze.llm import LLMClient
from clipforge.analyze.ollama import OllamaClient
from clipforge.analyze.prompts import (
    get_system_prompt,
    get_user_prompt,
)
from clipforge.analyze.scoring import calculate_heuristic_score
from clipforge.analyze.sentences import split_into_sentences
from clipforge.config import Settings
from clipforge.models import ClipCandidate, Sentence, Transcript, Word
from clipforge.store import ClipforgeError, ProjectStore
from clipforge.utils import format_timestamp

logger = logging.getLogger(__name__)

# Schéma Pydantic pour la validation LLM
CLIP_SCHEMA = {
    "type": "object",
    "properties": {
        "clips": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "start_sentence_id": {"type": "integer"},
                    "end_sentence_id": {"type": "integer"},
                    "title": {"type": "string", "maxLength": 60},
                    "hook": {"type": "string"},
                    "summary": {"type": "string"},
                    "keywords": {"type": "array", "items": {"type": "string"}},
                    "score": {"type": "number", "minimum": 0, "maximum": 100},
                    "reasons": {"type": "string"},
                },
                "required": [
                    "start_sentence_id",
                    "end_sentence_id",
                    "title",
                    "hook",
                    "summary",
                    "keywords",
                    "score",
                    "reasons",
                ],
            },
        },
    },
    "required": ["clips"],
}


def format_sentences_for_llm(
    sentences: list[Sentence],
    start_id: int,
    end_id: int,
) -> str:
    """Formate les phrases pour le LLM.

    Args:
        sentences: Liste des phrases.
        start_id: ID de départ de la fenêtre.
        end_id: ID de fin de la fenêtre.

    Returns:
        Texte formaté.
    """
    lines = []
    for s in sentences:
        if start_id <= s.id <= end_id:
            timestamp = format_timestamp(s.start, "srt")
            lines.append(f"[S{s.id:04d} | {timestamp}] {s.text}")
    return "\n".join(lines)


def create_llm_client(
    provider: Literal["gemini", "ollama"],
    settings: Settings,
) -> LLMClient:
    """Crée un client LLM.

    Args:
        provider: Fournisseur LLM.
        settings: Configuration.

    Returns:
        Client LLM.

    Raises:
        ClipforgeError: Si le fournisseur n'est pas supporté.
    """
    if provider == "gemini":
        return GeminiClient(
            model=settings.gemini_model,
            api_key=settings.gemini_api_key or None,
        )
    elif provider == "ollama":
        return OllamaClient(
            model=settings.ollama_model,
            host=settings.ollama_base_url,
        )
    else:
        raise ClipforgeError(f"Fournisseur LLM non supporté : {provider}")


def validate_candidate(
    candidate: dict[str, Any],
    sentences: list[Sentence],
    transcript_duration: float,
    min_sec: float,
    max_sec: float,
    tolerance: float = 5.0,
) -> tuple[bool, str]:
    """Valide un candidat LLM.

    Args:
        candidate: Candidat LLM.
        sentences: Toutes les phrases.
        transcript_duration: Durée totale.
        min_sec: Durée minimum.
        max_sec: Durée maximum.
        tolerance: Tolérance de durée.

    Returns:
        (valid, error_message).
    """
    # Vérifier que les IDs existent
    ids = {s.id for s in sentences}
    start_id = candidate.get("start_sentence_id")
    end_id = candidate.get("end_sentence_id")

    if start_id not in ids:
        return False, f"start_sentence_id {start_id} n'existe pas"
    if end_id not in ids:
        return False, f"end_sentence_id {end_id} n'existe pas"

    # Vérifier l'ordre
    if start_id > end_id:
        return False, "start_sentence_id > end_sentence_id"

    # Calculer la durée
    start_sentence = next(s for s in sentences if s.id == start_id)
    end_sentence = next(s for s in sentences if s.id == end_id)
    duration = end_sentence.end - start_sentence.start

    if duration < min_sec - tolerance:
        return False, f"Durée {duration:.1f}s < {min_sec}s (tolérance {tolerance}s)"
    if duration > max_sec + tolerance:
        return False, f"Durée {duration:.1f}s > {max_sec}s (tolérance {tolerance}s)"

    # Vérifier les mots-clés
    keywords = candidate.get("keywords", [])
    if not keywords:
        return False, "Aucun mot-clé"

    text = " ".join(s.text for s in sentences if start_id <= s.id <= end_id).lower()
    for kw in keywords:
        if kw.lower() not in text:
            return False, f"Mot-clé '{kw}' absent du texte"

    return True, ""


def convert_ids_to_timestamps(
    candidate: dict[str, Any],
    sentences: list[Sentence],
    transcript_duration: float,
    all_words: list[Word] | None = None,
) -> ClipCandidate:
    """Convertit les IDs de phrases en horodatages.

    Args:
        candidate: Candidat LLM.
        sentences: Toutes les phrases.
        transcript_duration: Durée totale.
        all_words: Tous les mots du transcript.

    Returns:
        ClipCandidate avec horodatages.
    """
    start_id = candidate["start_sentence_id"]
    end_id = candidate["end_sentence_id"]

    start_sentence = next(s for s in sentences if s.id == start_id)
    end_sentence = next(s for s in sentences if s.id == end_id)

    # Calculer start et end
    start = start_sentence.first_word.start - 0.15
    end = end_sentence.last_word.end + 0.35

    # Bornes
    start = max(0.0, start)
    end = min(transcript_duration, end)

    # Ajuster vers la pause la plus proche
    # Trouver le mot le plus proche avec un écart >= 0.25s
    if all_words:
        # Ajuster start
        if start > 0:
            best_word = min(
                all_words,
                key=lambda w: abs(w.start - start),
            )
            if abs(best_word.start - start) >= 0.25:
                start = best_word.start

        # Ajuster end
        best_word = min(
            all_words,
            key=lambda w: abs(w.end - end),
        )
        if abs(best_word.end - end) >= 0.25:
            end = best_word.end

    return ClipCandidate(
        id=0,  # Sera assigné plus tard
        start=start,
        end=end,
        start_sentence_id=start_id,
        end_sentence_id=end_id,
        title=candidate["title"],
        hook=candidate["hook"],
        summary=candidate["summary"],
        keywords=candidate["keywords"],
        llm_score=candidate["score"],
        heuristic_score=0.0,  # Calculé plus tard
        final_score=0.0,  # Calculé plus tard
        reasons=candidate["reasons"].split(". "),
    )


def remove_overlapping_clips(
    candidates: list[ClipCandidate],
    overlap_threshold: float = 0.4,
) -> list[ClipCandidate]:
    """Supprime les clips qui se chevauchent trop.

    Args:
        candidates: Liste de candidats.
        overlap_threshold: Seuil de chevauchement (0-1).

    Returns:
        Liste filtrée.
    """
    if not candidates:
        return []

    # Trier par score décroissant
    sorted_candidates = sorted(candidates, key=lambda c: c.final_score, reverse=True)

    kept: list[ClipCandidate] = []

    for candidate in sorted_candidates:
        overlap = False
        for kept_candidate in kept:
            # Calculer le chevauchement
            overlap_start = max(candidate.start, kept_candidate.start)
            overlap_end = min(candidate.end, kept_candidate.end)
            overlap_duration = max(0, overlap_end - overlap_start)

            candidate_duration = candidate.end - candidate.start
            if candidate_duration > 0:
                overlap_ratio = overlap_duration / candidate_duration
                if overlap_ratio > overlap_threshold:
                    overlap = True
                    break

        if not overlap:
            kept.append(candidate)

    return kept


def analyze_transcript(
    project_id: str,
    provider: Literal["gemini", "ollama", "heuristic"] = "heuristic",
    max_clips: int = 10,
    min_sec: int = 30,
    max_sec: int = 60,
    force: bool = False,
    settings: Settings | None = None,
    store: ProjectStore | None = None,
    on_progress: Callable[[str, float], None] | None = None,
) -> list[ClipCandidate]:
    """Analyse un transcript pour identifier les clips.

    Args:
        project_id: ID du projet.
        provider: Fournisseur LLM.
        max_clips: Nombre maximum de clips.
        min_sec: Durée minimum.
        max_sec: Durée maximum.
        force: Forcer la réexécution.
        settings: Configuration.
        store: Gestionnaire de stockage.
        on_progress: Callback de progression.

    Returns:
        Liste de candidats triée par final_score.

    Raises:
        ClipforgeError: Si l'analyse échoue.
    """
    if settings is None:
        settings = Settings()
    if store is None:
        store = ProjectStore(settings)

    # Charger le transcript
    transcript_path = store.get_file_path(project_id, "transcript.json")
    if not transcript_path.exists():
        raise ClipforgeError(f"Transcript introuvable pour {project_id}")

    with open(transcript_path, encoding="utf-8") as f:
        data = json.load(f)
    transcript = Transcript.model_validate(data)

    # Vérifier le cache
    candidates_path = store.get_file_path(project_id, "candidates.json")
    if candidates_path.exists() and not force:
        logger.info(f"Candidats existants pour {project_id}, chargement")
        with open(candidates_path, encoding="utf-8") as f:
            candidates_data = json.load(f)
        return [ClipCandidate.model_validate(c) for c in candidates_data]

    logger.info(f"Analyse du transcript {project_id} avec {provider}")

    # Découper en phrases
    sentences = split_into_sentences(transcript)

    if provider == "heuristic":
        candidates = analyze_heuristic(
            sentences,
            transcript,
            max_clips,
            min_sec,
            max_sec,
        )
    else:
        candidates = analyze_with_llm(
            sentences,
            transcript,
            provider,
            settings,
            max_clips,
            min_sec,
            max_sec,
            on_progress,
        )

    # Sauvegarder
    with open(candidates_path, "w", encoding="utf-8") as f:
        json.dump([c.model_dump(mode="json") for c in candidates], f, indent=2, ensure_ascii=False)

    logger.info(f"Analyse terminée : {len(candidates)} candidats")
    return candidates


def analyze_with_llm(
    sentences: list[Sentence],
    transcript: Transcript,
    provider: Literal["gemini", "ollama"],
    settings: Settings,
    max_clips: int,
    min_sec: int,
    max_sec: int,
    on_progress: Callable[[str, float], None] | None = None,
) -> list[ClipCandidate]:
    """Analyse avec un LLM."""
    client = create_llm_client(provider, settings)

    # Fenêtrage : 8 minutes avec 60s de chevauchement
    window_duration = 8 * 60  # 8 minutes
    overlap = 60  # 60 secondes

    all_candidates: list[ClipCandidate] = []
    current_id = 0

    # Trouver les phrases dans chaque fenêtre
    i = 0
    while i < len(sentences):
        start_sentence = sentences[i]
        window_end = start_sentence.start + window_duration

        # Trouver la fin de la fenêtre
        j = i
        while j < len(sentences) and sentences[j].start < window_end:
            j += 1

        # Formater pour le LLM
        sentences_text = format_sentences_for_llm(sentences, i, j - 1)

        # Générer
        system = get_system_prompt(transcript.language)
        user = get_user_prompt(sentences_text, max_clips, min_sec, max_sec)

        try:
            result = client.generate_json(system, user, CLIP_SCHEMA)

            # Valider et convertir
            for clip_data in result.get("clips", []):
                valid, error = validate_candidate(
                    clip_data,
                    sentences,
                    transcript.duration,
                    min_sec,
                    max_sec,
                )

                if valid:
                    candidate = convert_ids_to_timestamps(clip_data, sentences, transcript.duration, transcript.words)
                    candidate.id = current_id
                    current_id += 1
                    all_candidates.append(candidate)
                else:
                    logger.warning(f"Candidat rejeté : {error}")

        except Exception as e:
            logger.error(f"Erreur LLM sur fenêtre {i}-{j} : {e}")

        # Prochaine fenêtre avec chevauchement
        i = max(i + 1, j - int(overlap / 5))  # Approximation de phrases pour 60s

        if on_progress:
            on_progress("analyze", i / len(sentences))

    # Calculer les scores heuristiques
    all_words = transcript.words
    for candidate in all_candidates:
        candidate.heuristic_score = calculate_heuristic_score(
            candidate,
            sentences,
            all_words,
        )
        # final_score = 0.7 * llm_score + 0.3 * heuristic_score
        candidate.final_score = 0.7 * candidate.llm_score + 0.3 * candidate.heuristic_score

    # Fusion : supprimer chevauchements > 40%
    candidates = remove_overlapping_clips(all_candidates)

    # Garder les max_clips meilleurs
    candidates = sorted(candidates, key=lambda c: c.final_score, reverse=True)
    candidates = candidates[:max_clips]

    return candidates


def analyze_heuristic(
    sentences: list[Sentence],
    transcript: Transcript,
    max_clips: int,
    min_sec: int,
    max_sec: int,
) -> list[ClipCandidate]:
    """Analyse en mode heuristique (sans LLM)."""
    candidates: list[ClipCandidate] = []
    current_id = 0

    # Fenêtres glissantes alignées sur les phrases
    # Environ 45s par clip
    target_duration = 45.0

    i = 0
    while i < len(sentences):
        start_sentence = sentences[i]
        start_time = start_sentence.start

        # Trouver la fin de la fenêtre (cible ~45s)
        j = i
        while j < len(sentences) and sentences[j].end - start_time < max_sec:
            j += 1

        # Essayer de créer un clip
        if j > i:
            end_sentence = sentences[j - 1]
            duration = end_sentence.end - start_time

            if duration >= min_sec:
                # Titre = première phrase tronquée
                title = start_sentence.text[:60].capitalize()

                candidate = ClipCandidate(
                    id=current_id,
                    start=start_time,
                    end=end_sentence.end,
                    start_sentence_id=i,
                    end_sentence_id=j - 1,
                    title=title,
                    hook=start_sentence.text,
                    summary=f"Extrait de {duration:.0f}s",
                    keywords=[],
                    llm_score=0.0,
                    heuristic_score=0.0,
                    final_score=0.0,
                    reasons=[],
                )

                # Calculer le score heuristique
                candidate.heuristic_score = calculate_heuristic_score(
                    candidate,
                    sentences,
                    transcript.words,
                    target_duration,
                )
                candidate.final_score = candidate.heuristic_score

                candidates.append(candidate)
                current_id += 1

        # Avancer (fenêtres avec un peu de chevauchement)
        i += max(1, int(min_sec / 10))  # Avancer d'environ 3 phrases

        if len(candidates) >= max_clips:
            break

    # Trier par score
    candidates = sorted(candidates, key=lambda c: c.final_score, reverse=True)
    return candidates[:max_clips]
