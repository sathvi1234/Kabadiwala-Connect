from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    env: str = "development"
    database_url: str = "sqlite:///./kabadiwala.db"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_exp_minutes: int = 60 * 24 * 7
    cors_origins: str = "http://localhost:5173"
    upload_dir: str = "./uploads"
    otp_dev_code: str = "123456"
    max_upload_mb: int = 5
    max_image_kb: int = 200
    timestamp_tolerance_seconds: int = 900
    handover_distance_flag_km: float = 2.0
    transport_inr_per_km: float = 8.0
    referral_bonus_inr: float = 100.0
    vision_api_key: str = ""
    vision_api_url: str = "https://api.openai.com/v1/chat/completions"
    vision_model: str = "gpt-4o-mini"
    llm_api_key: str = ""
    llm_api_url: str = "https://api.openai.com/v1/chat/completions"
    llm_model: str = "gpt-4o-mini"
    demo_mode: bool = True
    demo_nightly_reset: bool = False

    model_config = SettingsConfigDict(
        env_file=(str(ROOT / ".env"), str(ROOT / "backend" / ".env"), ".env"),
        extra="ignore",
    )

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_dev(self) -> bool:
        return self.env.lower() in {"development", "dev", "local"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
