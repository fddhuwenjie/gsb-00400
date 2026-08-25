from pydantic_settings import BaseSettings
from pydantic import field_validator
from pathlib import Path
import secrets
import logging

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    APP_NAME: str = "Knowledge Base System"
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/knowledge.db"
    KNOWLEDGE_INBOX: Path = Path("/data/Knowledge_Inbox")
    VECTOR_DB_PATH: Path = Path("/data/vector_store")
    UPLOAD_DIR: Path = Path("/data/uploads")
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    
    @field_validator('SECRET_KEY', mode='before')
    @classmethod
    def set_secret_key(cls, v):
        if not v:
            logger.warning(
                "SECRET_KEY未设置，使用随机临时密钥。生产环境请配置SECRET_KEY环境变量。"
            )
            return secrets.token_urlsafe(32)
        return v
    
    class Config:
        env_file = ".env"

settings = Settings()
