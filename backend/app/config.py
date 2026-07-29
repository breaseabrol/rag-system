from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    #---Database---
    database_url: str = "postgresql://raguser:ragpass@localhost:5432/ragdb"
    db_pool_size: int = 5
    db_max_overflow: int = 10

    # --- Embeddings ---
    embedding_model_name: str = "all-MiniLM-L6-v2"
    embedding_dim: int = 384

    # --- LLM (Ollama, local) ---
    ollama_base_url: str = "http://localhost:111434"
    ollama_model: str = "llama3.1"

    # -- Retrieval ---
    retrieval_top_k: int = 5
    bm25_weight: float = 0.5
    ann_weight: float = 0.5

    # -- Chunking ---
    chunk_size: int = 400
    chunk_overlap: int = 70

settings = Settings()