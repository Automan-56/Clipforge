"""Interface abstraite pour les clients LLM."""

import logging
import time
from abc import ABC, abstractmethod
from typing import Any

from clipforge.store import ClipforgeError

logger = logging.getLogger(__name__)


class LLMClient(ABC):
    """Interface abstraite pour les clients LLM."""

    @abstractmethod
    def generate_json(
        self,
        system: str,
        user: str,
        schema: dict[str, Any],
        max_retries: int = 3,
    ) -> dict[str, Any]:
        """Génère une réponse JSON structurée.

        Args:
            system: Prompt système.
            user: Prompt utilisateur.
            schema: Schéma Pydantic attendu.
            max_retries: Nombre maximum de tentatives.

        Returns:
            Dictionnaire JSON.

        Raises:
            ClipforgeError: Si la génération échoue après retries.
        """
        pass


class BaseLLMClient(LLMClient):
    """Base class with retry logic."""

    def generate_json(
        self,
        system: str,
        user: str,
        schema: dict[str, Any],
        max_retries: int = 3,
    ) -> dict[str, Any]:
        """Génère une réponse JSON structurée avec retries."""
        last_error = None

        for attempt in range(max_retries):
            try:
                return self._generate_json_impl(system, user, schema)
            except Exception as e:
                last_error = e
                logger.warning(f"Tentative {attempt + 1}/{max_retries} échouée : {e}")

                # Backoff exponentiel
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.info(f"Attente {wait_time}s avant retry...")
                    time.sleep(wait_time)

        raise ClipforgeError(f"Échec après {max_retries} tentatives : {last_error}") from last_error

    @abstractmethod
    def _generate_json_impl(
        self,
        system: str,
        user: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        """Implémentation spécifique du client."""
        pass
