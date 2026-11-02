"""Client Gemini pour l'analyse LLM."""

import logging
import os
from typing import Any

import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted

from clipforge.analyze.llm import BaseLLMClient
from clipforge.store import ClipforgeError

logger = logging.getLogger(__name__)


class GeminiClient(BaseLLMClient):
    """Client pour l'API Gemini."""

    def __init__(self, model: str = "gemini-1.5-flash", api_key: str | None = None) -> None:
        """Initialise le client Gemini.

        Args:
            model: Nom du modèle Gemini.
            api_key: Clé API (None = depuis GEMINI_API_KEY).
        """
        self.model = model
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")

        if not self.api_key:
            raise ClipforgeError(
                "Clé API Gemini non trouvée. "
                "Définissez GEMINI_API_KEY ou passez --api-key."
            )

        genai.configure(api_key=self.api_key)

    def _generate_json_impl(
        self,
        system: str,
        user: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        """Implémentation Gemini de la génération JSON."""
        client = genai.GenerativeModel(self.model, system_instruction=system)

        # Utiliser le mode JSON structuré
        response = client.generate_content(
            user,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.7,
            ),
        )

        result = response.text

        # Parser le JSON
        import json
        try:
            return json.loads(result)
        except json.JSONDecodeError as e:
            raise ClipforgeError(f"Réponse JSON invalide : {e}") from e

    def generate_json(
        self,
        system: str,
        user: str,
        schema: dict[str, Any],
        max_retries: int = 3,
    ) -> dict[str, Any]:
        """Génère une réponse JSON structurée avec gestion du quota."""
        last_error = None

        for attempt in range(max_retries):
            try:
                return self._generate_json_impl(system, user, schema)
            except ResourceExhausted as e:
                last_error = e
                logger.warning(f"Quota épuisé (tentative {attempt + 1}/{max_retries})")

                # Attendre plus longtemps pour le quota (backoff exponentiel)
                if attempt < max_retries - 1:
                    wait_time = 5 * (2 ** attempt)  # 5s, 10s, 20s
                    logger.info(f"Attente {wait_time}s avant retry (quota)...")
                    import time
                    time.sleep(wait_time)
            except Exception as e:
                last_error = e
                logger.warning(f"Tentative {attempt + 1}/{max_retries} échouée : {e}")

                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.info(f"Attente {wait_time}s avant retry...")
                    import time
                    time.sleep(wait_time)

        raise ClipforgeError(f"Échec après {max_retries} tentatives : {last_error}") from last_error
