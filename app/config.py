from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Налаштування застосунку. Значення читаються зі змінних оточення."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Без значення за замовчуванням навмисно: креденшели не мають лежати в коді,
    # а мовчазний фолбек на чужу базу гірший за падіння на старті.
    database_url: str
    sql_echo: bool = False


settings = Settings()
