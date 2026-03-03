"""Application configuration using pydantic-settings."""

from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Tender Portal"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    API_PREFIX: str = "/api/v1"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://tender:tender_dev_2026@localhost:5432/tender_portal"
    DATABASE_URL_SYNC: str = "postgresql://tender:tender_dev_2026@localhost:5432/tender_portal"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT Auth
    JWT_SECRET_KEY: str = "change-this-to-a-real-secret-key"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_MINUTES: int = 1440  # 24 hours

    # Storage
    DOCUMENT_STORAGE_PATH: str = "./storage/documents"

    # Email
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@tenderportal.in"

    # GeM API
    GEM_API_KEY: str = ""
    GEM_API_SECRET: str = ""

    # CAPTCHA Solving (2Captcha)
    CAPTCHA_API_KEY: str = ""  # 2Captcha API key — sign up at https://2captcha.com

    # WhatsApp API (Business API or webhook gateway)
    WHATSAPP_API_URL: str = ""
    WHATSAPP_API_TOKEN: str = ""

    # SMS API (any REST gateway)
    SMS_API_URL: str = ""
    SMS_API_KEY: str = ""

    # OCR
    TESSERACT_CMD: str = "/usr/local/bin/tesseract"

    # Ingestion
    INGESTION_BATCH_SIZE: int = 50
    INGESTION_INTERVAL_MINUTES: int = 30
    MAX_CONCURRENT_DOWNLOADS: int = 10
    REQUEST_TIMEOUT_SECONDS: int = 30
    USER_AGENT: str = "TenderPortal/1.0 (Government Tender Aggregator)"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
