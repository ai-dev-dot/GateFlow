from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # 必需从 .env 读取，不设默认值——缺配置时启动失败而非静默用错数据库
    DATABASE_URL: str
    JWT_SECRET_KEY: str = "your-secret-key-change-in-production"
    JWT_EXPIRE_DAYS: int = 7
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin123"

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
