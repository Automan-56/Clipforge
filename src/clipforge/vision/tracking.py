"""Suivi du locuteur actif."""

import logging
from collections import defaultdict
from typing import NamedTuple

import cv2
import mediapipe as mp

from clipforge.vision.faces import Face, FaceDetector

logger = logging.getLogger(__name__)


class TrackedFace(NamedTuple):
    """Visage suivi avec identité stable."""

    id: int
    bbox: tuple[int, int, int, int]
    confidence: float
    mouth_openness: float  # 0-1, mesure de l'ouverture de la bouche


class SpeakerTracker:
    """Suivi du locuteur actif."""

    def __init__(
        self,
        iou_threshold: float = 0.3,
        hysteresis_duration: float = 1.0,
        mouth_variance_window: float = 1.0,
    ) -> None:
        """Initialise le tracker.

        Args:
            iou_threshold: Seuil IoU pour l'association de visages.
            hysteresis_duration: Durée d'hystérésis en secondes.
            mouth_variance_window: Fenêtre pour la variance de la bouche (secondes).
        """
        self.iou_threshold = iou_threshold
        self.hysteresis_duration = hysteresis_duration
        self.mouth_variance_window = mouth_variance_window

        self.face_detector = FaceDetector()
        self.mp_face_mesh = mp.solutions.face_mesh.FaceMesh(
            max_num_faces=5,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

        self.next_id = 0
        self.tracked_faces: dict[int, TrackedFace] = {}
        self.last_active_speaker: int | None = None
        self.last_active_time: float = 0.0
        self.mouth_history: dict[int, list[float]] = defaultdict(list)

    def _iou(self, bbox1: tuple[int, int, int, int], bbox2: tuple[int, int, int, int]) -> float:
        """Calcule l'IoU entre deux boîtes."""
        x1, y1, w1, h1 = bbox1
        x2, y2, w2, h2 = bbox2

        # Intersection
        xi1 = max(x1, x2)
        yi1 = max(y1, y2)
        xi2 = min(x1 + w1, x2 + w2)
        yi2 = min(y1 + h1, y2 + h2)

        if xi2 <= xi1 or yi2 <= yi1:
            return 0.0

        inter_area = (xi2 - xi1) * (yi2 - yi1)
        union_area = w1 * h1 + w2 * h2 - inter_area

        return inter_area / union_area if union_area > 0 else 0.0

    def _mouth_openness(self, frame: cv2.typing.MatLike, bbox: tuple[int, int, int, int]) -> float:
        """Calcule l'ouverture de la bouche."""
        x, y, w, h = bbox

        # Extraire la région de la bouche
        mouth_region = frame[y : y + h, x : x + w]
        if mouth_region.size == 0:
            return 0.0

        # Utiliser Face Mesh pour les landmarks
        rgb_frame = cv2.cvtColor(mouth_region, cv2.COLOR_BGR2RGB)
        results = self.mp_face_mesh.process(rgb_frame)

        if not results.multi_face_landmarks:
            return 0.0

        # Prendre le premier visage
        landmarks = results.multi_face_landmarks[0]

        # Landmarks de la bouche (indices 13 et 14 pour la lèvre supérieure/inférieure)
        upper_lip = landmarks.landmark[13]
        lower_lip = landmarks.landmark[14]

        # Distance verticale normalisée
        openness = abs(lower_lip.y - upper_lip.y)

        return min(1.0, openness * 5.0)  # Normaliser approximativement

    def _associate_faces(self, detected_faces: list[Face]) -> dict[int, Face]:
        """Associe les visages détectés aux IDs suivis."""
        associated: dict[int, Face] = {}
        used_ids = set()

        # Trier par confiance décroissante
        detected_faces.sort(key=lambda f: f.confidence, reverse=True)

        for face in detected_faces:
            best_id = None
            best_iou = self.iou_threshold

            for tracked_id, tracked in self.tracked_faces.items():
                if tracked_id in used_ids:
                    continue

                iou = self._iou(face.bbox, tracked.bbox)
                if iou > best_iou:
                    best_iou = iou
                    best_id = tracked_id

            if best_id is not None:
                associated[best_id] = face
                used_ids.add(best_id)
            else:
                # Nouveau visage
                new_id = self.next_id
                self.next_id += 1
                associated[new_id] = face

        return associated

    def _get_mouth_variance(self, face_id: float, current_time: float) -> float:
        """Calcule la variance de l'ouverture de la bouche."""
        history = self.mouth_history[face_id]

        # Nettoyer l'historique (garder seulement la fenêtre)
        while history and (current_time - history[0][0]) > self.mouth_variance_window:
            history.pop(0)

        if len(history) < 2:
            return 0.0

        # Calculer la variance
        values = [v for _, v in history]
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)

        return variance

    def track(
        self,
        frame: cv2.typing.MatLike,
        timestamp: float,
    ) -> tuple[int | None, list[TrackedFace]]:
        """Suit le locuteur actif.

        Args:
            frame: Image OpenCV.
            timestamp: Timestamp en secondes.

        Returns:
            (active_speaker_id, tracked_faces).
        """
        # Détecter les visages
        detected_faces = self.face_detector.detect(frame)

        # Associer aux IDs suivis
        associated = self._associate_faces(detected_faces)

        # Mettre à jour les visages suivis
        current_tracked: list[TrackedFace] = []
        for face_id, face in associated.items():
            mouth_openness = self._mouth_openness(frame, face.bbox)
            self.mouth_history[face_id].append((timestamp, mouth_openness))

            tracked = TrackedFace(
                id=face_id,
                bbox=face.bbox,
                confidence=face.confidence,
                mouth_openness=mouth_openness,
            )
            current_tracked.append(tracked)

        self.tracked_faces = {f.id: f for f in current_tracked}

        # Nettoyer les visages perdus
        lost_ids = set(self.tracked_faces.keys()) - set(associated.keys())
        for lost_id in lost_ids:
            del self.tracked_faces[lost_id]
            if lost_id in self.mouth_history:
                del self.mouth_history[lost_id]

        # Choisir le locuteur actif
        active_speaker = self._choose_active_speaker(current_tracked, timestamp)

        return active_speaker, current_tracked

    def _choose_active_speaker(self, faces: list[TrackedFace], timestamp: float) -> int | None:
        """Choisit le locuteur actif."""
        if not faces:
            # Aucun visage : revenir doucement vers le centre
            if (timestamp - self.last_active_time) > 2.0:
                self.last_active_speaker = None
            return self.last_active_speaker

        if len(faces) == 1:
            # Un seul visage : le suivre
            self.last_active_speaker = faces[0].id
            self.last_active_time = timestamp
            return faces[0].id

        # Plusieurs visages : utiliser la variance de la bouche
        best_id = None
        best_variance = 0.0

        for face in faces:
            variance = self._get_mouth_variance(face.id, timestamp)
            if variance > best_variance:
                best_variance = variance
                best_id = face.id

        if best_id is None:
            # Fallback : le plus grand visage
            best_id = max(faces, key=lambda f: f.bbox[2] * f.bbox[3]).id

        # Hystérésis
        if self.last_active_speaker != best_id:
            if (timestamp - self.last_active_time) < self.hysteresis_duration:
                return self.last_active_speaker
            self.last_active_speaker = best_id
            self.last_active_time = timestamp

        return best_id

    def __del__(self) -> None:
        """Nettoie les ressources."""
        if hasattr(self, "mp_face_mesh"):
            self.mp_face_mesh.close()
