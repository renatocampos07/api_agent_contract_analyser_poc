from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    ENVIRONMENT: str = "production"
    STORAGE_TYPE: str = "local"
    AUTH_TYPE: str = "none"
    
    LLM_PROVIDER: str = "azure"
    OPENAI_API_TYPE: str | None = None
    OPENAI_API_VERSION: str | None = None
    OPENAI_API_BASE: str | None = None
    OPENAI_API_KEY: str | None = None
    OPENAI_API_DEPLOYMENT_NAME: str | None = None
    ANTHROPIC_API_KEY: str | None = None
    
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    class Config:
        env_file = ".env"

settings = Settings()