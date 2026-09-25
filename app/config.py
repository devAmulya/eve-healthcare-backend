from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Centralised app configuration. Values are read from environment
    variables first, then from a .env file if present. Nothing here
    is hardcoded so the same image works locally, in docker-compose,
    and in tests (tests override DATABASE_URL directly).
    """

    database_url: str = "postgresql://eve_user:eve_pass@localhost:5432/eve_healthcare"
    jwt_secret_key: str = "insecure-dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
