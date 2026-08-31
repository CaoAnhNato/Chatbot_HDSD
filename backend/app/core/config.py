from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    PROJECT_NAME: str = "Multimodal HDSD Chatbot Assistant"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    # Qwen / DashScope API Settings
    DASHSCOPE_API_KEY: str = ""
    QWEN_API_KEY: str = ""
    QWEN_BASE_URL: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    QWEN_MODEL_NAME: str = "qwen3.7-flash"
    LLM_TEMPERATURE: float = 0.2
    LLM_TOP_P: float = 0.5
    LLM_MAX_TOKENS: int = 2048

    @property
    def effective_api_key(self) -> str:
        return self.DASHSCOPE_API_KEY or self.QWEN_API_KEY

    # Embedding & HuggingFace Space Microservice Settings
    EMBEDDING_MODEL_NAME: str = "AITeamVN/Vietnamese_Embedding_v2"
    EMBEDDING_DIMENSION: int = 1024
    HF_SPACE_URL: str = "https://hf.co/spaces/Nato1306/vietnamese-embedding-api"
    HF_EMBEDDING_API_URL: str = "https://nato1306-vietnamese-embedding-api.hf.space"
    USE_REMOTE_EMBEDDING: bool = False

    # Cloud Database & Supabase Settings
    DATABASE_URL: Optional[str] = "postgresql://postgres:cEzQV7AuXRXnmxGb@db.tykwgiubhnxedlpxszdn.supabase.co:5432/postgres"
    SUPABASE_URL: Optional[str] = "https://tykwgiubhnxedlpxszdn.supabase.co"
    SUPABASE_PASS: str = "cEzQV7AuXRXnmxGb"
    SUPABASE_ANON_KEY: Optional[str] = None

    # Vector Database Settings
    VECTOR_DB_TYPE: str = "chroma"  # "chroma", "qdrant", or "pgvector"
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "hdsd_chunks"
    CHROMA_COLLECTION_DN: str = "hdsd_chunks"
    CHROMA_COLLECTION_PHUONG: str = "hdsd_phuong_chunks"
    DEFAULT_COLLECTION: str = "hdsd_phuong_chunks"
    CHROMA_PERSIST_DIRECTORY: str = "./chroma_data"

    # Storage Settings
    IMAGE_STORAGE_PATH: str = "./data/extracted_images"
    BASE_IMAGE_CDN_URL: str = "https://chatbothdsd-production.up.railway.app/static/images"

    # Redis Cache Settings
    REDIS_ENABLED: bool = False
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    # Audit & Error Logging Settings
    ENABLE_AUDIT_LOG: bool = True
    LOG_DIR: str = "./data/logs"
    CHAT_AUDIT_LOG_FILE: str = "chat_audit.jsonl"
    CHAT_ERROR_LOG_FILE: str = "chat_errors.jsonl"

    # Deployment & CI/CD Metadata
    GITHUB_REPO_URL: str = "https://github.com/CaoAnhNato/Chatbot_HDSD.git"
    VERCEL_FRONTEND_URL: str = "https://chatbot-hdsd.vercel.app"
    RAILWAY_BACKEND_URL: str = "https://chatbothdsd-production.up.railway.app"
    CORS_ORIGINS: str = "http://localhost:3000,https://chatbot-hdsd.vercel.app,https://chatbothdsd-production.up.railway.app"
    
    class Config:
        env_file = (".env", "../.env", "backend/.env")
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
