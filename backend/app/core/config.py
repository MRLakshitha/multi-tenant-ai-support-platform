from typing import List, Optional, Dict, Any
from pydantic_settings import BaseSettings
from pydantic import Field
from pathlib import Path
import os

class Settings(BaseSettings):
    PROJECT_NAME: str = "Multi-Tenant AI Support Platform"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = Field(..., min_length=32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day
    
    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./support_platform.db"
    SYNC_DATABASE_URL: str = "sqlite:///./support_platform.db"
    
    # AI Providers (Groq or OpenAI or Mock/Local fallback)
    AI_PROVIDER: str = "groq"  # "groq", "openai", or "mock"
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o"
    
    # Telephony Provider (mock if None)
    TELEPHONY_PROVIDER: Optional[str] = None  # "twilio", "exotel", or None
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["*"]
    
        # Multi-tenant Default Tenants
    DEFAULT_TENANT_IDS: List[str] = [
        "cust-a-freshcart",
        "cust-b-biterush",
        "cust-c-swiftride",
        "cust-d-stylenova",
        "cust-e-voltexpress"
    ]

    class Config:
        env_file = str(Path(__file__).resolve().parents[2] / ".env")
        case_sensitive = True


settings = Settings()
