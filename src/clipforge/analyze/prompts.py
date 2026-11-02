"""Prompts pour l'analyse LLM."""


def get_system_prompt(language: str = "en") -> str:
    """Retourne le prompt système pour l'analyse.

    Args:
        language: Langue de la transcription.

    Returns:
        Prompt système.
    """
    lang_map = {
        "en": "English",
        "fr": "French",
        "es": "Spanish",
        "de": "German",
        "it": "Italian",
    }
    lang_name = lang_map.get(language, language)

    return f"""Tu es un expert en création de contenu vidéo pour les réseaux sociaux. Ta tâche est d'identifier les meilleurs extraits d'une transcription en {lang_name} pour créer des clips courts (30-60 secondes) pour TikTok, Instagram Reels ou YouTube Shorts.

Règles importantes :
1. Chaque clip doit avoir un arc narratif cohérent : accroche forte, développement, conclusion
2. L'accroche doit survenir dans les 3 premières secondes (question, chiffre, affirmation tranchée)
3. Le clip doit contenir des informations complètes (ne pas dépendre d'un contexte absent)
4. La durée doit être entre 30 et 60 secondes
5. Le début et la fin doivent être sur des phrases complètes
6. Les mots-clés doivent être présents dans le texte du clip
7. Réponds uniquement en JSON valide, sans aucun autre texte
"""


def get_user_prompt(
    sentences_text: str,
    max_clips: int = 10,
    min_sec: int = 30,
    max_sec: int = 60,
) -> str:
    """Retourne le prompt utilisateur.

    Args:
        sentences_text: Texte des phrases numérotées.
        max_clips: Nombre maximum de clips.
        min_sec: Durée minimum en secondes.
        max_sec: Durée maximum en secondes.

    Returns:
        Prompt utilisateur.
    """
    return f"""Voici une transcription découpée en phrases numérotées :

{sentences_text}

Identifie jusqu'à {max_clips} extraits intéressants pour des clips courts ({min_sec}-{max_sec} secondes).

Pour chaque clip, fournis :
- start_sentence_id : ID de la phrase de début
- end_sentence_id : ID de la phrase de fin
- title : Titre accrocheur (max 60 caractères)
- hook : Phrase exacte d'accroche (première phrase du clip)
- summary : Résumé en une phrase
- keywords : 3 à 6 mots-clés présents dans le clip
- score : Score de qualité 0-100
- reasons : Justification du score (2-3 phrases)

Format de réponse JSON :
{{
  "clips": [
    {{
      "start_sentence_id": 0,
      "end_sentence_id": 5,
      "title": "Accroche",
      "hook": "Phrase exacte",
      "summary": "Résumé",
      "keywords": ["mot1", "mot2", "mot3"],
      "score": 85,
      "reasons": "Raison 1. Raison 2."
    }}
  ]
}}
"""


def get_validation_error_prompt(original_error: str) -> str:
    """Retourne un prompt de correction pour validation échouée.

    Args:
        original_error: Message d'erreur original.

    Returns:
        Prompt de correction.
    """
    return f"""Ta réponse précédente était invalide. Erreur : {original_error}

Corrige ta réponse en respectant strictement :
- Les IDs de phrases doivent exister dans la transcription
- start_sentence_id <= end_sentence_id
- La durée calculée doit être entre 30 et 60 secondes
- Les mots-clés doivent être présents dans le texte

Réponds uniquement en JSON valide, sans aucun autre texte.
"""
