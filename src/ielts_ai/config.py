"""Application configuration via pydantic-settings."""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    
    llm_provider: str = Field(default="mock", description="mock | real")
    llm_api_key: str = Field(default="", description="API key for real LLM provider")
    llm_model: str = Field(default="", description="Model name for real LLM provider")
    use_mock_rag: bool = Field(default=True, description="Use in-memory keyword RAG instead of ChromaDB")
    chroma_dir: str = Field(default=".chroma", description="ChromaDB persistence directory")
    db_path: str = Field(default="data/app.db", description="SQLite database path")
    email_mode: str = Field(default="file", description="file | smtp")
    smtp_host: str = Field(default="", description="SMTP server hostname")
    smtp_port: int = Field(default=587, description="SMTP server port")
    smtp_user: str = Field(default="", description="SMTP username")
    smtp_password: str = Field(default="", description="SMTP password")

def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
