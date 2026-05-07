import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# 加载项目根目录的 .env 文件
load_dotenv(Path(__file__).parent.parent.parent / ".env")


class Settings(BaseSettings):
    # Milvus 配置
    MILVUS_HOST: str = os.getenv("MILVUS_HOST", "milvus")
    MILVUS_PORT: int = int(os.getenv("MILVUS_PORT", "19530"))
    MILVUS_URI: str = os.getenv("MILVUS_URI", "http://milvus:19530")

    # LLM 配置
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_API_BASE: str = os.getenv("OPENAI_API_BASE", "https://api.minimaxi.com/v1")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "MiniMax-M2.7")

    # Ollama Embedding 配置
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_EMBEDDING_MODEL: str = os.getenv("OLLAMA_EMBEDDING_MODEL", "qwen3-embedding:0.6b-q8_0")

    # Embedding 配置 (Qwen3-embedding-0.6B 本地模型)
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "models/qwen3-embedding-0.6b")
    EMBEDDING_DIM: int = int(os.getenv("EMBEDDING_DIM", "1024"))

    # 向量库配置
    DEFAULT_COLLECTION: str = os.getenv("DEFAULT_COLLECTION", "vuln_kb")
    TOP_K: int = int(os.getenv("TOP_K", "5"))

    # API 配置
    API_PREFIX: str = "/api"
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "*")

    # 会话配置
    SESSION_EXPIRE_SECONDS: int = int(os.getenv("SESSION_EXPIRE_SECONDS", "3600"))
    SESSION_DB_PATH: str = os.getenv("SESSION_DB_PATH", "data/sessions.db")
    SESSION_MAX_HISTORY: int = int(os.getenv("SESSION_MAX_HISTORY", "100"))

    # 长期记忆配置
    MEMORY_WINDOW_SIZE: int = int(os.getenv("MEMORY_WINDOW_SIZE", "4"))
    MEMORY_SUMMARY_ENABLED: bool = os.getenv("MEMORY_SUMMARY_ENABLED", "true").lower() == "true"

    class Config:
        env_file = ".env"


settings = Settings()
