from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # LLM
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    LLM_PROVIDER: str = "openai"
    LLM_MODEL: str = "gpt-4o"
    LLM_MODEL_FAST: str = "gpt-4o-mini"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://tutor:senha@localhost:5432/tutoria"
    REDIS_URL: str = "redis://localhost:6379/0"

    # Security
    SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 horas

    # Judge0 (code execution sandbox)
    JUDGE0_API_URL: str = "https://judge0-ce.p.rapidapi.com"
    JUDGE0_API_KEY: str = ""

    # App
    BACKEND_URL: str = "http://localhost:8000"
    FRONTEND_URL: str = "http://localhost:3000"
    PROJECTS_ROOT: str = "/tmp/student_projects"
    DEBUG: bool = True

    # Gmail — recuperação de senha via Senha de App
    # NÃO use sua senha normal do Gmail aqui.
    # Crie uma Senha de App em: myaccount.google.com/security
    #   1. Ative Verificação em duas etapas
    #   2. Pesquise "Senhas de app" → crie para "TutorAndCoder"
    #   3. Cole os 16 dígitos abaixo (sem espaços)
    SMTP_EMAIL: str = ""
    SMTP_PASSWORD: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
 
