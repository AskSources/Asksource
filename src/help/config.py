import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from pathlib import Path


ENV_FILE_PATH = Path(__file__).parent.parent / '.env'

class Settings(BaseSettings):
    MONGODB_URL: str
    MONGODB_DATABASE: str
    APP_NAME: str
    APP_VERSION: str

    FILE_ALLOWED_TYPES: list[str] = [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
        "text/plain",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    ]
    FILE_DEFAULT_CHUNK_SIZE: int = 512000
    FILE_MAX_SIZE: int = 10

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE_PATH), 
        env_file_encoding='utf-8',
        extra='ignore'
    )

@lru_cache()
def get_settings():
    return Settings()