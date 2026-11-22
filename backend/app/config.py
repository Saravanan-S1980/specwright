"""Settings and model IDs. The only place model names live.

Model routing: cheap fast model for parsing and tagging, main model for
synthesis and specs, deep model for critique. Override any of them with
environment variables without touching code.
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    model_fast: str = os.getenv("SPECWRIGHT_MODEL_FAST", "claude-haiku-5-5")
    model_main: str = os.getenv("SPECWRIGHT_MODEL_MAIN", "claude-sonnet-5-5")
    model_deep: str = os.getenv("SPECWRIGHT_MODEL_DEEP", "claude-opus-5-5")
    max_upload_bytes: int = 5 * 1024 * 1024  # 5 MB is plenty for a demo CSV


settings = Settings()
