"""Application configuration via pydantic-settings."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    llm_provider: str = Field(default="mock", description="mock | real")
    llm_api_key: str = Field(default="", description="API key for real LLM provider")
    llm_model: str = Field(default="", description="Model name for real LLM provider")
    llm_timeout_seconds: float = Field(default=60, gt=0)
    llm_min_interval_seconds: float = Field(default=5, ge=0)
    llm_max_attempts: int = Field(default=3, ge=1)
    llm_max_output_tokens: int = Field(default=2000, ge=1)
    llm_thinking_budget: int | None = Field(default=None, ge=0)
    use_mock_rag: bool = Field(
        default=True, description="Use in-memory keyword RAG instead of ChromaDB"
    )
    chroma_dir: str = Field(default=".chroma", description="ChromaDB persistence directory")
    db_path: str = Field(default="data/app.db", description="SQLite database path")
    email_mode: str = Field(default="file", description="file | smtp")
    smtp_host: str = Field(default="", description="SMTP server hostname")
    smtp_port: int = Field(default=587, description="SMTP server port")
    smtp_user: str = Field(default="", description="SMTP username")
    smtp_password: str = Field(default="", description="SMTP password")
    smtp_test_to: str = Field(default="", description="Recipient for opt-in SMTP integration tests")


def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
