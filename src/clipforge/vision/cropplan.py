"""Calcul du plan de recadrage avec lissage."""

import logging
from typing import Literal

from clipforge.models import CropKeyframe, CropPlan

logger = logging.getLogger(__name__)


class CropPlanCalculator:
    """Calculateur de plan de recadrage."""

    def __init__(
        self,
        ema_alpha: float = 0.15,
        dead_zone_percent: float = 0.04,
        max_velocity: float = 100.0,  # pixels per second
    ) -> None:
        """Initialise le calculateur.

        Args:
            ema_alpha: Alpha pour la moyenne mobile exponentielle.
            dead_zone_percent: Zone morte en pourcentage de la largeur du crop.
            max_velocity: Vitesse maximale en pixels/seconde.
        """
        self.ema_alpha = ema_alpha
        self.dead_zone_percent = dead_zone_percent
        self.max_velocity = max_velocity

        self.last_x_center: float | None = None
        self.last_timestamp: float | None = None

    def compute(
        self,
        target_x_center: float,
        crop_width: float,
        src_width: float,
        timestamp: float,
        is_scene_cut: bool = False,
    ) -> float:
        """Calcule la position lissée du centre du crop.

        Args:
            target_x_center: Position cible du centre.
            crop_width: Largeur du crop.
            src_width: Largeur de la source.
            timestamp: Timestamp en secondes.
            is_scene_cut: Si c'est une coupure de scène.

        Returns:
            Position lissée du centre.
        """
        # Clamp la cible aux bornes
        min_x = crop_width / 2
        max_x = src_width - crop_width / 2
        target_x_center = max(min_x, min(max_x, target_x_center))

        # Si coupure de scène, réinitialiser le lissage
        if is_scene_cut:
            self.last_x_center = None
            self.last_timestamp = None
            return target_x_center

        # Première frame
        if self.last_x_center is None:
            self.last_x_center = target_x_center
            self.last_timestamp = timestamp
            return target_x_center

        # Calculer le delta de temps
        dt = timestamp - self.last_timestamp
        if dt <= 0:
            return self.last_x_center

        # Zone morte
        dead_zone = crop_width * self.dead_zone_percent
        delta = target_x_center - self.last_x_center

        if abs(delta) < dead_zone:
            # Dans la zone morte, ne pas bouger
            smoothed_x = self.last_x_center
        else:
            # Appliquer l'EMA
            smoothed_x = self.ema_alpha * target_x_center + (1 - self.ema_alpha) * self.last_x_center

        # Limiter la vitesse
        velocity = (smoothed_x - self.last_x_center) / dt
        if abs(velocity) > self.max_velocity:
            direction = 1 if velocity > 0 else -1
            smoothed_x = self.last_x_center + direction * self.max_velocity * dt

        # Clamp aux bornes
        smoothed_x = max(min_x, min(max_x, smoothed_x))

        self.last_x_center = smoothed_x
        self.last_timestamp = timestamp

        return smoothed_x

    def reset(self) -> None:
        """Réinitialise le lissage."""
        self.last_x_center = None
        self.last_timestamp = None


def generate_keyframes(
    src_width: int,
    src_height: int,
    crop_width: int,
    x_centers: list[tuple[float, float]],  # (timestamp, x_center)
    layout: Literal["crop", "blur_fit"] = "crop",
) -> list[CropKeyframe]:
    """Génère les keyframes pour le plan de recadrage.

    Args:
        src_width: Largeur de la source.
        src_height: Hauteur de la source.
        crop_width: Largeur du crop.
        x_centers: Liste des positions centres avec timestamps.
        layout: Type de layout.

    Returns:
        Liste de keyframes.
    """
    keyframes: list[CropKeyframe] = []

    for timestamp, x_center in x_centers:
        keyframe = CropKeyframe(
            t=timestamp,
            x_center=x_center,
            face_count=0,  # Serait calculé à partir du tracking
            confidence=0.0,
        )
        keyframes.append(keyframe)

    return keyframes


def create_crop_plan(
    clip_id: int,
    src_width: int,
    src_height: int,
    layout: Literal["crop", "blur_fit"],
    keyframes: list[CropKeyframe],
) -> CropPlan:
    """Crée un CropPlan.

    Args:
        clip_id: ID du clip.
        src_width: Largeur de la source.
        src_height: Hauteur de la source.
        layout: Type de layout.
        keyframes: Keyframes calculés.

    Returns:
        CropPlan.
    """
    crop_width = int(src_height * 9 / 16)  # 9:16 ratio

    return CropPlan(
        clip_id=clip_id,
        layout=layout,
        src_w=src_width,
        src_h=src_height,
        crop_w=crop_width,
        keyframes=keyframes,
    )
