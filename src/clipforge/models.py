"""Modèles de données Pydantic v2 pour clipforge."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class Word(BaseModel):
    """Mot individuel avec horodatage Whisper."""

    start: float = Field(..., description="Début du mot en secondes")
    end: float = Field(..., description="Fin du mot en secondes")
    text: str = Field(..., description="Texte du mot")
    probability: float = Field(..., ge=0.0, le=1.0, description="Confiance Whisper")

    @field_validator("end")
    @classmethod
    def end_after_start(cls, v: float, info: Any) -> float:
        if "start" in info.data and v <= info.data["start"]:
            raise ValueError("end doit être supérieur à start")
        return v


class Segment(BaseModel):
    """Segment de transcription Whisper (phrase ou groupe de mots)."""

    id: int = Field(..., description="Identifiant unique du segment")
    start: float = Field(..., description="Début du segment en secondes")
    end: float = Field(..., description="Fin du segment en secondes")
    text: str = Field(..., description="Texte du segment")
    words: list[Word] = Field(default_factory=list, description="Mots du segment")

    @field_validator("end")
    @classmethod
    def end_after_start(cls, v: float, info: Any) -> float:
        if "start" in info.data and v <= info.data["start"]:
            raise ValueError("end doit être supérieur à start")
        return v


class Transcript(BaseModel):
    """Transcription complète Whisper."""

    language: str = Field(..., description="Code langue ISO 639-1")
    language_probability: float = Field(..., ge=0.0, le=1.0)
    duration: float = Field(..., ge=0.0, description="Durée totale en secondes")
    segments: list[Segment] = Field(default_factory=list, description="Segments de la transcription")

    @property
    def words(self) -> list[Word]:
        """Tous les mots de tous les segments, dans l'ordre."""
        result: list[Word] = []
        for segment in self.segments:
            result.extend(segment.words)
        return result

    @property
    def full_text(self) -> str:
        """Texte complet concaténé des segments."""
        return " ".join(seg.text for seg in self.segments)

    def words_between(self, start: float, end: float) -> list[Word]:
        """Retourne les mots dont l'intervalle intersecte [start, end]."""
        return [
            w for w in self.words
            if not (w.end <= start or w.start >= end)
        ]


class Sentence(BaseModel):
    """Phrase identifiée pour l'analyse LLM."""

    id: int = Field(..., description="Identifiant unique de la phrase")
    start: float = Field(..., description="Début en secondes")
    end: float = Field(..., description="Fin en secondes")
    text: str = Field(..., description="Texte de la phrase")
    first_word: Word = Field(..., description="Premier mot Whisper")
    last_word: Word = Field(..., description="Dernier mot Whisper")

    @field_validator("end")
    @classmethod
    def end_after_start(cls, v: float, info: Any) -> float:
        if "start" in info.data and v <= info.data["start"]:
            raise ValueError("end doit être supérieur à start")
        return v


class ClipCandidate(BaseModel):
    """Candidat de clip identifié par l'analyse."""

    id: int = Field(..., description="Identifiant unique du candidat")
    start: float = Field(..., description="Début du clip en secondes")
    end: float = Field(..., description="Fin du clip en secondes")
    start_sentence_id: int = Field(..., description="ID de la phrase de début")
    end_sentence_id: int = Field(..., description="ID de la phrase de fin")
    title: str = Field(..., description="Titre suggéré du clip")
    hook: str = Field(..., description="Phrase d'accroche")
    summary: str = Field(..., description="Résumé du contenu")
    keywords: list[str] = Field(default_factory=list, description="Mots-clés")
    llm_score: float = Field(default=0.0, ge=0.0, le=100.0, description="Score LLM")
    heuristic_score: float = Field(default=0.0, ge=0.0, le=100.0, description="Score heuristique")
    final_score: float = Field(default=0.0, ge=0.0, le=100.0, description="Score final combiné")
    reasons: list[str] = Field(default_factory=list, description="Justifications du score")

    @field_validator("end")
    @classmethod
    def end_after_start(cls, v: float, info: Any) -> float:
        if "start" in info.data and v <= info.data["start"]:
            raise ValueError("end doit être supérieur à start")
        return v


class CropLayout(str, Enum):
    """Type de layout de recadrage."""

    CROP = "crop"
    BLUR_FIT = "blur_fit"


class CropKeyframe(BaseModel):
    """Keyframe de plan de recadrage."""

    t: float = Field(..., description="Timestamp en secondes")
    x_center: float = Field(..., ge=0.0, description="Position horizontale du centre (0-1)")
    face_count: int = Field(default=0, ge=0, description="Nombre de visages détectés")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confiance de détection")


class CropPlan(BaseModel):
    """Plan de recadrage pour un clip."""

    clip_id: int = Field(..., description="ID du clip associé")
    layout: CropLayout = Field(..., description="Type de layout")
    src_w: int = Field(..., gt=0, description="Largeur source")
    src_h: int = Field(..., gt=0, description="Hauteur source")
    crop_w: int = Field(..., gt=0, description="Largeur de recadrage")
    keyframes: list[CropKeyframe] = Field(default_factory=list, description="Keyframes temporels")


class SubtitleStyle(BaseModel):
    """Style de sous-titrage."""

    font: str = Field(default="Arial", description="Nom de la police")
    size: int = Field(default=48, gt=0, description="Taille en pixels")
    primary_color: str = Field(default="#FFFFFF", description="Couleur principale (hex)")
    highlight_color: str = Field(default="#FFD700", description="Couleur de mise en valeur (hex)")
    accent_color: str = Field(default="#00BFFF", description="Couleur d'accent (hex)")
    outline_color: str = Field(default="#000000", description="Couleur du contour (hex)")
    outline_width: int = Field(default=2, ge=0, description="Épaisseur du contour en pixels")
    margin_v: int = Field(default=50, ge=0, description="Marge verticale en pixels")
    words_per_line: int = Field(default=4, gt=0, description="Mots par ligne")
    uppercase: bool = Field(default=False, description="Mettre en majuscules")
    pop_animation: bool = Field(default=True, description="Activer l'animation de pop")


class StageState(str, Enum):
    """État d'une étape du pipeline."""

    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class StageStatus(BaseModel):
    """Statut d'une étape du pipeline."""

    state: StageState = Field(default=StageState.PENDING, description="État actuel")
    started_at: datetime | None = Field(default=None, description="Heure de début")
    ended_at: datetime | None = Field(default=None, description="Heure de fin")
    error: str | None = Field(default=None, description="Message d'erreur si échec")


class ProjectState(BaseModel):
    """État complet d'un projet clipforge."""

    id: str = Field(..., description="Identifiant unique du projet")
    source: str = Field(..., description="Chemin de la vidéo source")
    title: str = Field(..., description="Titre du projet")
    duration: float = Field(..., ge=0.0, description="Durée de la vidéo en secondes")
    stages: dict[str, StageStatus] = Field(
        default_factory=dict,
        description="Statut de chaque étape (ingest, transcribe, analyze, vision, render)"
    )
    timings: dict[str, float] = Field(
        default_factory=dict,
        description="Temps d'exécution par étape en secondes"
    )
    config: dict[str, Any] = Field(
        default_factory=dict,
        description="Configuration utilisée pour ce projet"
    )
