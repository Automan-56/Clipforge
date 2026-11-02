"""Configuration Pydantic Settings pour clipforge."""

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration globale de clipforge.

    Priorité : CLI > variables d'environnement > fichier config.toml > valeurs par défaut.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="CLIPFORGE_",
        extra="ignore",
    )

    # Chemins
    workspace_dir: Path = Field(
        default=Path("workspace"),
        description="Répertoire de travail pour les projets"
    )
    config_file: Path = Field(
        default=Path("clipforge.toml"),
        description="Fichier de configuration TOML"
    )

    # Transcription (Whisper)
    whisper_model: str = Field(
        default="base",
        description="Modèle Whisper (tiny, base, small, medium, large)"
    )
    whisper_device: Literal["cpu", "cuda", "auto"] = Field(
        default="auto",
        description="Périphérique d'exécution Whisper"
    )

    # LLM
    llm_provider: Literal["gemini", "ollama", "none"] = Field(
        default="none",
        description="Fournisseur LLM (none = mode heuristique)"
    )
    gemini_api_key: str = Field(
        default="",
        description="Clé API Gemini (optionnel)"
    )
    gemini_model: str = Field(
        default="gemini-1.5-flash",
        description="Modèle Gemini"
    )
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="URL du serveur Ollama"
    )
    ollama_model: str = Field(
        default="llama3.2",
        description="Modèle Ollama"
    )

    # Recadrage
    crop_target_aspect: str = Field(
        default="9:16",
        description="Ratio de cible (ex: 9:16)"
    )
    crop_target_width: int = Field(
        default=1080,
        description="Largeur cible en pixels"
    )
    crop_target_height: int = Field(
        default=1920,
        description="Hauteur cible en pixels"
    )
    face_detection_interval: float = Field(
        default=0.5,
        ge=0.1,
        description="Intervalle entre détections de visage en secondes"
    )

    # Rendu
    output_format: Literal["mp4", "webm"] = Field(
        default="mp4",
        description="Format de sortie vidéo"
    )
    output_codec: str = Field(
        default="libx264",
        description="Codec vidéo"
    )
    output_preset: str = Field(
        default="medium",
        description="Preset d'encodage FFmpeg"
    )
    output_crf: int = Field(
        default=23,
        ge=0,
        le=51,
        description="CRF qualité (0=perteless, 51=pire)"
    )

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        description="Niveau de logging"
    )

    @field_validator("workspace_dir", "config_file")
    @classmethod
    def resolve_path(cls, v: Path) -> Path:
        """Résout les chemins relatifs par rapport au répertoire courant."""
        if not v.is_absolute():
            return Path.cwd() / v
        return v

    @classmethod
    def load_from_toml(cls, config_path: Path) -> "Settings":
        """Charge la configuration depuis un fichier TOML."""
        try:
            import tomli
        except ImportError:
            import tomllib as tomli  # Python 3.11+

        if not config_path.exists():
            return cls()

        with open(config_path, "rb") as f:
            data = tomli.load(f)

        # Aplatir les sections imbriquées pour correspondre aux préfixes
        flat_data: dict = {}
        for section, values in data.items():
            if isinstance(values, dict):
                for key, value in values.items():
                    flat_data[key] = value
            else:
                flat_data[section] = values

        return cls(**flat_data)

    def update_from_dict(self, updates: dict) -> "Settings":
        """Retourne une nouvelle instance avec les mises à jour."""
        return self.model_copy(update=updates)
