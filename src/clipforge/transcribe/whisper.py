"""Module de transcription avec faster-whisper."""

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from faster_whisper import WhisperModel

from clipforge.config import Settings
from clipforge.models import Segment, Transcript, Word
from clipforge.store import ClipforgeError, ProjectStore

logger = logging.getLogger(__name__)


class Transcriber:
    """Transcripteur Whisper avec chargement paresseux."""

    def __init__(
        self,
        model_size: str = "small",
        device: Literal["cpu", "cuda", "auto"] = "auto",
        compute_type: str = "int8",
        language: str | None = None,
    ) -> None:
        """Initialise le transcripteur.

        Args:
            model_size: Taille du modèle (tiny, base, small, medium, large-v3).
            device: Périphérique d'exécution.
            compute_type: Type de calcul (int8, float16, float32).
            language: Langue (None = détection automatique).
        """
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self._model: WhisperModel | None = None

    @property
    def model(self) -> WhisperModel:
        """Charge le modèle de manière paresseuse."""
        if self._model is None:
            logger.info(f"Chargement du modèle Whisper {self.model_size}")
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
            logger.info("Modèle Whisper chargé")
        return self._model

    def transcribe(
        self,
        audio_path: Path,
        on_progress: Callable[[str, float], None] | None = None,
    ) -> Transcript:
        """Transcrit un fichier audio.

        Args:
            audio_path: Chemin du fichier audio WAV.
            on_progress: Callback (étape, fraction).

        Returns:
            Transcription.

        Raises:
            ClipforgeError: Si la transcription échoue.
        """
        if not audio_path.exists():
            raise ClipforgeError(f"Fichier audio introuvable : {audio_path}")

        logger.info(f"Transcription de {audio_path}")

        try:
            segments_iter, info = self.model.transcribe(
                str(audio_path),
                word_timestamps=True,
                vad_filter=True,
                vad_parameters={
                    "min_silence_duration_ms": 500,
                },
                condition_on_previous_text=False,
                language=self.language,
            )

            # Convertir l'itérateur en liste
            segments_list = list(segments_iter)

            # Vérifier qu'on a des segments
            if not segments_list:
                logger.warning("Aucun segment détecté dans l'audio")
                return Transcript(
                    language=info.language if info.language else "unknown",
                    language_probability=info.language_probability if info.language_probability else 0.0,
                    duration=info.duration if info.duration else 0.0,
                    segments=[],
                )

            # Construire les segments
            transcript_segments: list[Segment] = []
            word_count = 0

            for i, seg in enumerate(segments_list):
                # Construire les mots
                words: list[Word] = []
                for word_info in seg.words:
                    words.append(
                        Word(
                            start=round(word_info.start, 3),
                            end=round(word_info.end, 3),
                            text=word_info.word.strip(),
                            probability=word_info.probability if word_info.probability else 0.0,
                        )
                    )
                    word_count += 1

                # Créer le segment
                transcript_segments.append(
                    Segment(
                        id=i,
                        start=round(seg.start, 3),
                        end=round(seg.end, 3),
                        text=seg.text.strip(),
                        words=words,
                    )
                )

                # Callback de progression
                if on_progress:
                    fraction = (i + 1) / len(segments_list)
                    on_progress("transcribe", fraction)

            logger.info(f"Transcription terminée : {word_count} mots détectés")

            # Avertissement si aucun mot
            if word_count == 0:
                logger.warning("Aucun mot détecté dans la transcription")

            return Transcript(
                language=info.language if info.language else "unknown",
                language_probability=info.language_probability if info.language_probability else 0.0,
                duration=info.duration if info.duration else 0.0,
                segments=transcript_segments,
            )

        except Exception as e:
            raise ClipforgeError(f"Erreur lors de la transcription : {e}") from e


def transcribe_project(
    project_id: str,
    model: str = "small",
    language: str | None = None,
    force: bool = False,
    settings: Settings | None = None,
    store: ProjectStore | None = None,
    on_progress: Callable[[str, float], None] | None = None,
) -> Transcript:
    """Transcrit l'audio d'un projet.

    Args:
        project_id: ID du projet.
        model: Modèle Whisper à utiliser.
        language: Langue (None = auto).
        force: Forcer la réexécution.
        settings: Configuration.
        store: Gestionnaire de stockage.
        on_progress: Callback (étape, fraction).

    Returns:
        Transcription.

    Raises:
        ClipforgeError: Si la transcription échoue.
    """
    if settings is None:
        settings = Settings()
    if store is None:
        store = ProjectStore(settings)

    # Charger l'état du projet (pour vérifier qu'il existe)
    store.load_state(project_id)

    # Vérifier si déjà transcrit
    transcript_path = store.get_file_path(project_id, "transcript.json")
    if transcript_path.exists() and not force:
        logger.info(f"Transcription existante pour {project_id}, chargement")
        import json
        with open(transcript_path, encoding="utf-8") as f:
            data = json.load(f)
        return Transcript.model_validate(data)

    # Chemin de l'audio
    audio_path = store.get_file_path(project_id, "audio.wav")
    if not audio_path.exists():
        raise ClipforgeError(f"Audio introuvable pour le projet {project_id}")

    # Déterminer le device
    device = settings.whisper_device
    if device == "auto":
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"

    # Déterminer le compute_type
    compute_type = "float16" if device == "cuda" else "int8"

    # Transcrire
    transcriber = Transcriber(
        model_size=model,
        device=device,
        compute_type=compute_type,
        language=language,
    )

    transcript = transcriber.transcribe(
        audio_path,
        on_progress=on_progress,
    )

    # Sauvegarder la transcription
    with open(transcript_path, "w", encoding="utf-8") as f:
        f.write(transcript.model_dump_json(indent=2))

    # Sauvegarder aussi en SRT et TXT pour le débogage
    srt_path = store.get_file_path(project_id, "transcript.srt")
    txt_path = store.get_file_path(project_id, "transcript.txt")

    # Écrire SRT
    with open(srt_path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(transcript.segments, 1):
            start = seg.start
            end = seg.end
            # Format SRT: 00:00:00,000
            start_srt = f"{int(start//3600):02d}:{int((start%3600)//60):02d}:{int(start%60):02d},{int((start%1)*1000):03d}"
            end_srt = f"{int(end//3600):02d}:{int((end%3600)//60):02d}:{int(end%60):02d},{int((end%1)*1000):03d}"
            f.write(f"{i}\n{start_srt} --> {end_srt}\n{seg.text}\n\n")

    # Écrire TXT
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(transcript.full_text)

    logger.info(f"Transcription sauvegardée pour {project_id}")
    return transcript
