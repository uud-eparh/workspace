from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "OpenLedger"
    VERSION: str = "0.1.0"
    DEBUG: bool = True
    
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/openledger"
    REDIS_URL: str = "redis://localhost:6379"
    
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Роли по умолчанию
    DEFAULT_ROLES: dict = {
        "master_admin": "Мастер-администратор",
        "master_user": "Мастер-пользователь",
        "user": "Пользователь"
    }
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
