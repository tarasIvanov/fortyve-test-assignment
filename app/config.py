from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Налаштування застосунку. Значення читаються зі змінних оточення."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://fields:fields@db:5432/fields"
    sql_echo: bool = False


settings = Settings()
