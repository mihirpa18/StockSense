from pydantic_settings import BaseSettings
from typing import Optional
from dotenv import load_dotenv

# Load environment variables into os.environ for external SDKs (like LangSmith)
load_dotenv()

class Settings(BaseSettings):
    supabase_url: str
    supabase_service_key: str
    supabase_jwt_secret: str
    gemini_api_key: str
    mistral_api_key: str
    frontend_url: str = "http://localhost:5173"

    # LangSmith Observability
    langsmith_tracing: str = "false"
    langsmith_api_key: Optional[str] = None
    langsmith_project: str = "stocksense"

    class Config:
        env_file = ".env"

settings = Settings()
