"""Client Ollama pour l'analyse LLM locale."""

import logging
from typing import Any

import httpx

from clipforge.analyze.llm import BaseLLMClient
from clipforge.store import ClipforgeError

logger = logging.getLogger(__name__)


class OllamaClient(BaseLLMClient):
    """Client pour Ollama (LLM local)."""

    def __init__(
        self,
        model: str = "llama3.2",
        host: str = "http://localhost:11434",
        num_ctx: int = 8192,
    ) -> None:
        """Initialise le client Ollama.

        Args:
            model: Nom du modèle Ollama.
            host: URL du serveur Ollama.
            num_ctx: Taille du contexte (tokens).
        """
        self.model = model
        self.host = host
        self.num_ctx = num_ctx
        self.client = httpx.Client(timeout=120.0)

    def _generate_json_impl(
        self,
        system: str,
        user: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        """Implémentation Ollama de la génération JSON."""
        # Construire le prompt pour forcer JSON
        json_instruction = (
            "Réponds uniquement en JSON valide, sans aucun autre texte. "
            "Voici le schéma attendu :\n"
            f"{schema}\n\n"
        )

        full_user = json_instruction + user

        response = self.client.post(
            f"{self.host}/api/generate",
            json={
                "model": self.model,
                "system": system,
                "prompt": full_user,
                "stream": False,
                "options": {
                    "num_ctx": self.num_ctx,
                    "temperature": 0.7,
                },
            },
        )

        response.raise_for_status()
        result = response.json()

        # Extraire la réponse
        text = result.get("response", "")

        # Parser le JSON
        import json
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise ClipforgeError(f"Réponse JSON invalide : {e}") from e
