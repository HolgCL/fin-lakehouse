"""Runtime configuration, loaded from environment / .env (see .env.example)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    sec_user_agent: str = "fin-lakehouse/0.1 (contact: set SEC_USER_AGENT in .env)"
    dbt_target: str = "dev"
