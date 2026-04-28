from pydantic_settings import BaseSettings
from typing import List
import json


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080  # 7 days
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    BOT_TOKEN: str = ""
    WEBAPP_URL: str = "http://localhost:3000"
    ADMIN_WEBAPP_URL: str = "http://localhost:3001"

    BACKEND_CORS_ORIGINS: str = '["http://localhost:3000","http://localhost:3001"]'

    @property
    def cors_origins(self) -> List[str]:
        return json.loads(self.BACKEND_CORS_ORIGINS)

    class Config:
        env_file = ".env"


settings = Settings()
