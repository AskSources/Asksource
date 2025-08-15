from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):

    app_name: str = "HYBRID-RAG-DGPC"
    app_version: str = "0.1"

    FILE_ALLOWED_TYPES: list[str] = [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
        "application/msword",  # .doc
        "text/plain",  # .txt
        "application/vnd.ms-excel",  # .xls
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"  # .xlsx
    ]
    FILE_DEFAULT_CHUNK_SIZE: int = 512000  # 512KB
    FILE_MAX_SIZE: int = 10  # 10MB 

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"
def get_settings() -> Settings:
    return Settings()
