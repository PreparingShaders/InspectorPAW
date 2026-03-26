from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Секретный ключ для подписи JWT токенов.
    # Должен быть длинной, случайной строкой.
    # Рекомендуется загружать из переменной окружения (например, SECRET_KEY="your_secret_key")
    SECRET_KEY: str = "your-super-secret-key" # TODO: Изменить на реальный ключ в продакшене!
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30 # Время жизни токена доступа в минутах

    model_config = SettingsConfigDict(env_file=".env") # Загружать переменные из файла .env

settings = Settings()
