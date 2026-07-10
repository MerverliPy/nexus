"""Configuration management using Pydantic Settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    # Database
    nexus_db_host: str = "localhost"
    nexus_db_port: int = 5432
    nexus_db_name: str = "nexus_db"
    nexus_db_user: str = "nexus_user"
    nexus_db_password: str
    
    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""
    
    # MinIO
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "nexus-data"
    minio_secure: bool = False
    
    # Security
    nexus_secret_key: str
    nexus_encryption_key: str
    nexus_access_token_expire_minutes: int = 60
    nexus_refresh_token_expire_days: int = 7
    
    # LLM
    openrouter_api_key: str = ""
    llm_default_model: str = "anthropic/claude-3-5-sonnet"
    llm_fallback_model: str = "ollama/mistral:7b-instruct"
    llm_max_monthly_cost: float = 50.0
    
    # Notifications
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    
    # Email
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    
    # Application
    nexus_env: str = "development"
    nexus_debug: bool = True
    nexus_log_level: str = "INFO"
    
    @property
    def database_url(self) -> str:
        """Construct database URL."""
        return (
            f"postgresql+asyncpg://{self.nexus_db_user}:{self.nexus_db_password}"
            f"@{self.nexus_db_host}:{self.nexus_db_port}/{self.nexus_db_name}"
        )
    
    @property
    def redis_url(self) -> str:
        """Construct Redis URL."""
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
