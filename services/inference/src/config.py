"""
Configuration settings for the inference service.
"""

import os
from pathlib import Path

from pydantic_settings import BaseSettings


# Default model - TinyLlama is small (~700MB) and fast on CPU
DEFAULT_MODEL_REPO = "TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF"
DEFAULT_MODEL_FILE = "tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf"


def get_model_path() -> str:
    """Get model path, downloading if necessary."""
    model_dir = Path(os.getenv("MODEL_DIR", "./models"))
    model_path = model_dir / DEFAULT_MODEL_FILE

    # If model doesn't exist, download it
    if not model_path.exists():
        print(f"Model not found at {model_path}")
        print(f"Downloading {DEFAULT_MODEL_FILE} from HuggingFace...")
        print("(This is a one-time ~700MB download)")

        try:
            from huggingface_hub import hf_hub_download

            model_dir.mkdir(parents=True, exist_ok=True)
            downloaded_path = hf_hub_download(
                repo_id=DEFAULT_MODEL_REPO,
                filename=DEFAULT_MODEL_FILE,
                local_dir=str(model_dir),
                local_dir_use_symlinks=False,
            )
            print(f"Model downloaded to: {downloaded_path}")
            return str(downloaded_path)
        except Exception as e:
            print(f"Error downloading model: {e}")
            print("Please download manually or set MODEL_PATH env var")
            raise

    return str(model_path)


class Settings(BaseSettings):
    """Inference service configuration."""

    # Model settings
    model_path: str = ""
    context_length: int = int(os.getenv("CONTEXT_LENGTH", "2048"))
    max_tokens_default: int = int(os.getenv("MAX_TOKENS_DEFAULT", "256"))

    # Inference settings
    inference_timeout: int = int(os.getenv("INFERENCE_TIMEOUT", "60"))
    temperature_default: float = float(os.getenv("TEMPERATURE_DEFAULT", "0.7"))

    # Server settings
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))

    # Mode
    mode: str = os.getenv("INFERENCE_MODE", "cpu")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Auto-detect model path if not set
        if not self.model_path or self.model_path == "/models/model.gguf":
            self.model_path = get_model_path()

    class Config:
        env_prefix = "INFERENCE_"


settings = Settings()

