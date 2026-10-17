"""Centralized configuration for FlytBase Asset Intelligence Copilot."""

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    # Project workspace root (computed from file location)
    WORKSPACE_ROOT: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent.parent.parent
    )

    # Core Directories & Boundaries
    DATASET_ROOT: str = "sample-data"
    ARTIFACTS_DIR: str = "artifacts"
    REFERENCE_TODAY: str = "2026-10-17"

    # Gemma 4 LLM API & Model Slots
    GEMINI_API_KEY: Optional[str] = None
    OPENROUTER_API_KEY: Optional[str] = None
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "gemma4"

    ROUTER_MODEL: str = "gemma-4-26b-a4b-it"
    REASONING_MODEL: str = "gemma-4-31b-it"

    # DigitalOcean Spaces Storage
    DO_SPACES_KEY: Optional[str] = None
    DO_SPACES_SECRET: Optional[str] = None
    DO_SPACES_ENDPOINT: str = "https://nyc3.digitaloceanspaces.com"
    DO_SPACES_BUCKET: str = "flytbase-asset-intelligence"
    DO_SPACES_REGION: str = "nyc3"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def dataset_path(self) -> Path:
        """Absolute path to the active dataset directory."""
        path = Path(self.DATASET_ROOT)
        if not path.is_absolute():
            path = (self.WORKSPACE_ROOT / path).resolve()
        return path

    @property
    def artifacts_path(self) -> Path:
        """Absolute path to the artifacts directory."""
        path = Path(self.ARTIFACTS_DIR)
        if not path.is_absolute():
            path = (self.WORKSPACE_ROOT / path).resolve()
        return path


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Singleton getter for application settings."""
    return Settings()
