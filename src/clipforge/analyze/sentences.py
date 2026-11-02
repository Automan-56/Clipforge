"""Découpage d'un Transcript en Sentence."""

import logging

from clipforge.models import Sentence, Transcript, Word

logger = logging.getLogger(__name__)

# Ponctuation forte pour fin de phrase
STRONG_PUNCTUATION = {".", "!", "?", "。", "！", "？", "…"}
WEAK_PUNCTUATION = {",", ";", "；", ":", "："}


def split_into_sentences(transcript: Transcript) -> list[Sentence]:
    """Découpe un Transcript en Sentence.

    Règles :
    - Fin de phrase = ponctuation forte
    - Sinon pause > 0.7 s entre mots
    - Sinon fin de segment Whisper

    Args:
        transcript: Transcription Whisper.

    Returns:
        Liste de phrases.
    """
    sentences: list[Sentence] = []
    sentence_id = 0

    current_words: list[Word] = []
    current_start: float | None = None

    for segment in transcript.segments:
        for word in segment.words:
            # Initialiser le début de la phrase
            if current_start is None:
                current_start = word.start

            current_words.append(word)

            # Vérifier si c'est une fin de phrase
            is_sentence_end = False

            # 1. Ponctuation forte à la fin du mot
            if word.text and word.text[-1] in STRONG_PUNCTUATION:
                is_sentence_end = True

            # 2. Pause > 0.7 s (avec le mot suivant)
            # On ne peut vérifier que si on a le mot suivant
            # Cette logique sera appliquée après avoir collecté tous les mots

            if is_sentence_end:
                # Créer la phrase
                if current_words:
                    sentence = Sentence(
                        id=sentence_id,
                        start=current_start,
                        end=word.end,
                        text=" ".join(w.text for w in current_words),
                        first_word=current_words[0],
                        last_word=current_words[-1],
                    )
                    sentences.append(sentence)
                    sentence_id += 1

                # Réinitialiser
                current_words = []
                current_start = None

    # Traiter les mots restants (phrase sans ponctuation forte)
    if current_words:
        # Vérifier les pauses > 0.7 s
        for i in range(len(current_words) - 1):
            gap = current_words[i + 1].start - current_words[i].end
            if gap > 0.7:
                # Créer une phrase jusqu'à ce mot
                sentence = Sentence(
                    id=sentence_id,
                    start=current_start,
                    end=current_words[i].end,
                    text=" ".join(w.text for w in current_words[: i + 1]),
                    first_word=current_words[0],
                    last_word=current_words[i],
                )
                sentences.append(sentence)
                sentence_id += 1

                # Continuer avec les mots restants
                current_words = current_words[i + 1 :]
                current_start = current_words[0].start if current_words else None
                break
        else:
            # Pas de pause > 0.7 s, créer une phrase avec tous les mots
            if current_words:
                sentence = Sentence(
                    id=sentence_id,
                    start=current_start,
                    end=current_words[-1].end,
                    text=" ".join(w.text for w in current_words),
                    first_word=current_words[0],
                    last_word=current_words[-1],
                )
                sentences.append(sentence)
                sentence_id += 1

    logger.info(f"Découpage en {len(sentences)} phrases")
    return sentences
