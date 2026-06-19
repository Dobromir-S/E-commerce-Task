from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/ecommerce"
    # Override in tests via DATABASE_URL env var pointing to a test DB
    upload_dir: str = "uploads"


settings = Settings()
