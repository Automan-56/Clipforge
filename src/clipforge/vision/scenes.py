"""Détection de coupures par différence d'histogrammes."""

import logging
from typing import NamedTuple

import cv2

logger = logging.getLogger(__name__)


class SceneCut(NamedTuple):
    """Coupe de scène détectée."""

    timestamp: float
    confidence: float


class SceneDetector:
    """Détecteur de coupures de scène."""

    def __init__(self, threshold: float = 0.3, min_interval: float = 1.0) -> None:
        """Initialise le détecteur.

        Args:
            threshold: Seuil de différence d'histogramme (0-1).
            min_interval: Intervalle minimum entre coupures (secondes).
        """
        self.threshold = threshold
        self.min_interval = min_interval
        self.last_histogram: cv2.typing.MatLike | None = None
        self.last_cut_time: float = 0.0

    def detect(self, frame: cv2.typing.MatLike, timestamp: float) -> bool:
        """Détecte si une coupure de scène se produit.

        Args:
            frame: Image OpenCV.
            timestamp: Timestamp en secondes.

        Returns:
            True si une coupure est détectée.
        """
        # Calculer l'histogramme
        hist = self._compute_histogram(frame)

        if self.last_histogram is None:
            self.last_histogram = hist
            return False

        # Calculer la différence
        diff = cv2.compareHist(self.last_histogram, hist, cv2.HISTCMP_CORREL)

        # Si la corrélation est faible, c'est une coupure
        is_cut = diff < (1.0 - self.threshold)

        # Vérifier l'intervalle minimum
        if is_cut and (timestamp - self.last_cut_time) < self.min_interval:
            is_cut = False

        if is_cut:
            self.last_cut_time = timestamp

        self.last_histogram = hist
        return is_cut

    def _compute_histogram(self, frame: cv2.typing.MatLike) -> cv2.typing.MatLike:
        """Calcule l'histogramme d'une image."""
        # Convertir en HSV pour une meilleure robustesse
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # Calculer l'histogramme 2D (Hue, Saturation)
        hist = cv2.calcHist(
            [hsv],
            [0, 1],
            None,
            [50, 60],
            [0, 180, 0, 256],
        )

        # Normaliser
        cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX)

        return hist

    def reset(self) -> None:
        """Réinitialise le détecteur."""
        self.last_histogram = None
        self.last_cut_time = 0.0
