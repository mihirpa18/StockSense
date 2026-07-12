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

    # SerpApi (Google Finance) — used for fundamentals/about/news; NSE Node
    # service still handles live price, so this only gets hit on cache-miss.
    serpapi_key: Optional[str] = None

    # LangSmith Observability
    langsmith_tracing: str = "false"
    langsmith_api_key: Optional[str] = None
    langsmith_project: str = "stocksense"
    
    # Upstash Redis — token-bucket rate limiting, SerpApi response caching,
    # and (later) the arq background job queue all share this one connection.
    redis_url: str


    class Config:
        env_file = ".env"

settings = Settings()
