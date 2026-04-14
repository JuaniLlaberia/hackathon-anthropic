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

    # MercadoLibre OAuth
    ML_APP_ID: str = ""
    ML_APP_SECRET: str = ""
    ML_REDIRECT_URI: str = ""  # e.g. https://<ngrok>/api/v1/auth/ml/callback
    BACKEND_BASE_URL: str = "http://localhost:8000"

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
