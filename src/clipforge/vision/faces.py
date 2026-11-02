"""Détection de visages avec MediaPipe."""

import logging
from typing import NamedTuple

import cv2
import mediapipe as mp

logger = logging.getLogger(__name__)


class Face(NamedTuple):
    """Résultat de détection d'un visage."""

    bbox: tuple[int, int, int, int]  # (x, y, w, h)
    confidence: float


class FaceDetector:
    """Détecteur de visages MediaPipe."""

    def __init__(self, max_faces: int = 5, min_detection_confidence: float = 0.5) -> None:
        """Initialise le détecteur.

        Args:
            max_faces: Nombre maximum de visages à détecter.
            min_detection_confidence: Seuil de confiance minimum.
        """
        self.max_faces = max_faces
        self.min_detection_confidence = min_detection_confidence

        # Initialiser MediaPipe Face Detection
        mp_face_detection = mp.solutions.face_detection
        self.detector = mp_face_detection.FaceDetection(
            model_selection=0,  # 0 = short-range, 1 = long-range
            min_detection_confidence=min_detection_confidence,
        )

    def detect(self, frame: cv2.typing.MatLike) -> list[Face]:
        """Détecte les visages dans une image.

        Args:
            frame: Image OpenCV (BGR).

        Returns:
            Liste de visages détectés.
        """
        # Convertir BGR -> RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Détecter
        results = self.detector.process(rgb_frame)

        faces: list[Face] = []
        if results.detections:
            for detection in results.detections[: self.max_faces]:
                # Extraire la boîte englobante
                bbox = detection.location_data.relative_bounding_box

                # Convertir en coordonnées absolues
                h, w = frame.shape[:2]
                x = int(bbox.xmin * w)
                y = int(bbox.ymin * h)
                bw = int(bbox.width * w)
                bh = int(bbox.height * h)

                # S'assurer que la boîte est valide
                if bw > 0 and bh > 0:
                    faces.append(
                        Face(
                            bbox=(x, y, bw, bh),
                            confidence=detection.score[0] if detection.score else 0.0,
                        )
                    )

        return faces

    def __del__(self) -> None:
        """Nettoie les ressources."""
        if hasattr(self, "detector"):
            self.detector.close()
