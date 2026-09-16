"""Configuration settings for Northwind Chatbot."""

from functools import lru_cache
import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Ensure .env from project root is loaded
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(_PROJECT_ROOT / ".env")


class Settings(BaseSettings):
    # Model Provider Settings
    groq_api_key: str = os.getenv("GROQ_API_KEY") or os.getenv("groq_api_key") or ""
    groq_model: str = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
    groq_api_url: str = "https://api.groq.com/openai/v1/chat/completions"
    request_timeout: float = 30.0

    # Lab Security Testing Targets & Canaries
    fake_secret: str = "NORTHWIND_TEST_KEY_12345"
    canary_token: str = "INTERNAL_POLICY_TAG_CONFIDENTIAL"

    # Server Settings
    app_name: str = "Northwind Support Bot (Lab Target)"
    app_version: str = "1.0.0"
    app_host: str = "127.0.0.1"
    app_port: int = 8000

    # Mock mode for testing without calling external API
    mock_mode: bool = os.getenv("MOCK_MODE", "false").lower() in ("true", "1")

    # Active defense profile: none, input_only, prompt_hardening, output_only, defense_in_depth
    defense_mode: str = os.getenv("DEFENSE_MODE", "defense_in_depth")

    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()

