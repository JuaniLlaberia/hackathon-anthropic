from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://hackathon:hackathon@localhost:5432/hackathon"

    # Kapso
    KAPSO_WEBHOOK_SECRET: str = ""
    KAPSO_API_URL: str = "https://api.kapso.io/v1"
    KAPSO_API_KEY: str = ""
    KAPSO_PHONE_NUMBER_ID: str = ""

    # Anthropic
    ANTHROPIC_API_KEY: str = ""

    # Cloudinary
    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
