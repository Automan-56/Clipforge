"""Module de vision par ordinateur pour le recadrage 9:16."""

import json
import logging
from collections.abc import Callable
from typing import Literal

import cv2

from clipforge.config import Settings
from clipforge.models import ClipCandidate, CropPlan
from clipforge.store import ClipforgeError, ProjectStore
from clipforge.vision.cropplan import (
    CropPlanCalculator,
    create_crop_plan,
    generate_keyframes,
)
from clipforge.vision.scenes import SceneDetector
from clipforge.vision.tracking import SpeakerTracker

logger = logging.getLogger(__name__)


def compute_crop_plan(
    project_id: str,
    clip_id: int,
    layout: Literal["auto", "crop", "blur_fit"] = "auto",
    sample_rate: float = 5.0,
    max_width: int = 640,
    debug_video: bool = False,
    force: bool = False,
    settings: Settings | None = None,
    store: ProjectStore | None = None,
    on_progress: Callable[[str, float], None] | None = None,
) -> CropPlan:
    """Calcule le plan de recadrage pour un clip.

    Args:
        project_id: ID du projet.
        clip_id: ID du clip.
        layout: Type de layout.
        sample_rate: Taux d'échantillonnage (images/s).
        max_width: Largeur maximale pour le redimensionnement.
        debug_video: Créer une vidéo de débogage.
        force: Forcer la réexécution.
        settings: Configuration.
        store: Gestionnaire de stockage.
        on_progress: Callback de progression.

    Returns:
        Plan de recadrage.

    Raises:
        ClipforgeError: Si le calcul échoue.
    """
    if settings is None:
        settings = Settings()
    if store is None:
        store = ProjectStore(settings)

    # Charger les candidats
    candidates_path = store.get_file_path(project_id, "candidates.json")
    if not candidates_path.exists():
        raise ClipforgeError(f"Candidats introuvables pour {project_id}")

    with open(candidates_path, encoding="utf-8") as f:
        candidates_data = json.load(f)
    candidates = [ClipCandidate.model_validate(c) for c in candidates_data]

    if clip_id >= len(candidates):
        raise ClipforgeError(f"Clip ID {clip_id} invalide")

    clip = candidates[clip_id]

    # Vérifier le cache
    cropplan_path = store.get_file_path(project_id, f"cropplan_{clip_id}.json")
    if cropplan_path.exists() and not force:
        logger.info(f"Cropplan existant pour clip {clip_id}, chargement")
        with open(cropplan_path, encoding="utf-8") as f:
            data = json.load(f)
        return CropPlan.model_validate(data)

    logger.info(f"Calcul du cropplan pour clip {clip_id}")

    # Chemin de la vidéo source
    video_path = store.get_file_path(project_id, "source.mp4")
    if not video_path.exists():
        raise ClipforgeError(f"Vidéo source introuvable pour {project_id}")

    # Ouvrir la vidéo
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ClipforgeError(f"Impossible d'ouvrir {video_path}")

    # Positionner au début du clip
    cap.set(cv2.CAP_PROP_POS_MSEC, clip.start * 1000)

    # Obtenir les dimensions
    src_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    src_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)

    crop_w = int(src_h * 9 / 16)

    # Initialiser les composants
    tracker = SpeakerTracker()
    scene_detector = SceneDetector()
    crop_calculator = CropPlanCalculator()

    # Debug video
    debug_writer = None
    if debug_video:
        debug_path = store.get_file_path(project_id, f"debug_{clip_id}.mp4")
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        debug_writer = cv2.VideoWriter(
            str(debug_path),
            fourcc,
            fps,
            (src_w, src_h),
        )

    # Calculer le nombre de frames à traiter
    duration = clip.end - clip.start
    total_frames = int(duration * fps)
    frames_to_process = int(duration * sample_rate)

    # Calculer l'intervalle entre frames
    frame_interval = max(1, total_frames // frames_to_process)

    x_centers: list[tuple[float, float]] = []
    face_frames = 0  # Nombre de frames avec visage détecté

    for i in range(frames_to_process):
        # Lire la frame
        for _ in range(frame_interval):
            ret, frame = cap.read()
            if not ret:
                break

        if not ret:
            break

        # Redimensionner si nécessaire
        scale = min(1.0, max_width / src_w)
        if scale < 1.0:
            frame = cv2.resize(frame, (int(src_w * scale), int(src_h * scale)))

        # Timestamp
        timestamp = clip.start + i / sample_rate

        # Détecter les visages
        active_speaker, tracked_faces = tracker.track(frame, timestamp)

        # Détecter les coupures
        is_scene_cut = scene_detector.detect(frame, timestamp)

        if is_scene_cut:
            crop_calculator.reset()

        # Calculer la position cible
        if active_speaker is not None:
            speaker_face = next((f for f in tracked_faces if f.id == active_speaker), None)
            if speaker_face:
                bx, by, bw, bh = speaker_face.bbox
                target_x = bx + bw / 2
                face_frames += 1
            else:
                target_x = src_w / 2
        else:
            target_x = src_w / 2

        # Ajuster à l'échelle originale
        target_x = target_x / scale

        # Calculer la position lissée
        smoothed_x = crop_calculator.compute(
            target_x,
            crop_w,
            src_w,
            timestamp,
            is_scene_cut,
        )

        x_centers.append((timestamp, smoothed_x))

        # Debug
        if debug_writer:
            debug_frame = frame.copy()
            # Dessiner la fenêtre de crop
            crop_left = int(smoothed_x - crop_w / 2)
            crop_right = int(smoothed_x + crop_w / 2)
            cv2.rectangle(debug_frame, (crop_left, 0), (crop_right, src_h), (0, 255, 0), 2)

            # Dessiner les visages
            for face in tracked_faces:
                bx, by, bw, bh = face.bbox
                color = (0, 0, 255) if face.id == active_speaker else (255, 0, 0)
                cv2.rectangle(debug_frame, (bx, by), (bx + bw, by + bh), color, 2)

            debug_writer.write(debug_frame)

        # Progression
        if on_progress:
            on_progress("reframe", (i + 1) / frames_to_process)

    cap.release()
    if debug_writer:
        debug_writer.release()

    # Déterminer le layout automatique
    if layout == "auto":
        face_ratio = face_frames / frames_to_process if frames_to_process > 0 else 0
        layout_final = "blur_fit" if face_ratio < 0.6 else "crop"
    else:
        layout_final = layout

    # Générer les keyframes
    keyframes = generate_keyframes(src_w, src_h, crop_w, x_centers, layout_final)

    # Créer le crop plan
    crop_plan = create_crop_plan(clip_id, src_w, src_h, layout_final, keyframes)

    # Sauvegarder
    with open(cropplan_path, "w", encoding="utf-8") as f:
        f.write(crop_plan.model_dump_json(indent=2))

    logger.info(f"Cropplan calculé pour clip {clip_id} : {len(keyframes)} keyframes, layout {layout_final}")
    return crop_plan
