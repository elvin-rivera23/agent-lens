"""
Configuration settings for the inference service.
"""

import os

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Inference service configuration."""

    # Model settings
    model_path: str = os.getenv("MODEL_PATH", "/models/model.gguf")
    context_length: int = int(os.getenv("CONTEXT_LENGTH", "4096"))
    max_tokens_default: int = int(os.getenv("MAX_TOKENS_DEFAULT", "256"))

    # Inference settings
    inference_timeout: int = int(os.getenv("INFERENCE_TIMEOUT", "60"))
    temperature_default: float = float(os.getenv("TEMPERATURE_DEFAULT", "0.7"))

    # Server settings
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))

    # Mode
    mode: str = os.getenv("INFERENCE_MODE", "cpu")

    class Config:
        env_prefix = "INFERENCE_"


settings = Settings()
