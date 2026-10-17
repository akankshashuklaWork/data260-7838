"""Configuration for the HW6 rental-listing memory service."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Settings are environment-overridable so each experiment is reproducible."""

    model_config = SettingsConfigDict(env_file=REPOSITORY_ROOT / ".env", env_prefix="HW6_", extra="ignore")

    sid4: int = 7838
    port_base: int = 8638
    mongodb_uri: str = "mongodb://127.0.0.1:27017"
    mongodb_db: str = "s7838_doc"
    model_name: str = "qwen2:7b"
    ollama_base_url: str = "http://127.0.0.1:11434"
    short_term_n: int = 12
    memory_policy: str = "none"
    summarize_every_user_msgs: int = 5
    episodic_top_k: int = 4
    embedding_dimensions: int = 128
    use_deterministic_model: bool = False
    telemetry_path: Path = REPOSITORY_ROOT / "reports" / "hw06" / "raw" / "chat_token_log.jsonl"
    agent_file: Path = REPOSITORY_ROOT / "AGENT.md"
    memory_file: Path = REPOSITORY_ROOT / "memory" / "MEMORY.md"


@lru_cache
def get_settings() -> Settings:
    return Settings()
