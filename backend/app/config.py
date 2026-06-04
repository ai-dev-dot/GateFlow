from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://Think:pg123456@localhost:5432/gateflow_test"
    JWT_SECRET_KEY: str = "your-secret-key-change-in-production"
    JWT_EXPIRE_DAYS: int = 7
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin123"

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
