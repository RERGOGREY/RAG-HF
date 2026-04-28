from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Groq — ключ передаётся через UI/API на каждый запрос, в env не нужен
    groq_api_key: str | None = None
    groq_model: str = "qwen/qwen3-32b"

    # Qdrant
    qdrant_url: str = "http://qdrant:6333"
    qdrant_collection: str = "hf_corpus"

    # Embeddings / Reranker
    embedding_model: str = "intfloat/multilingual-e5-large"
    reranker_model: str = "BAAI/bge-reranker-large"
    top_k_retrieve: int = 40
    top_k_final: int = 5

    # Redis
    redis_url: str = "redis://redis:6379"
    cache_ttl: int = 3600          # секунд

    # Corpus
    corpus_path: str = "data_pipeline/corpus.jsonl"
    chunk_size: int = 600
    chunk_overlap: int = 80

    # Ports (для supervisord / docker)
    api_port: int = 8000
    ui_port: int = 8501


settings = Settings()
