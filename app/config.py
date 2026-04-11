from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, ClassVar

class Settings(BaseSettings):
    # --- API Ключи (загружаются из .env) ---
    GEMINI_API_KEY: str
    OPEN_ROUTER_API_KEY: str
    SECRET_KEY: str
    
    # --- Настройки JWT ---
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # --- Динамически обновляемый список бесплатных моделей для AI-коуча ---
    AI_CHAT_MODELS: ClassVar[List[str]] = []

    # --- Приоритетный список для выбора лучшей модели из бесплатных ---
    AI_COACH_PRIORITY_MODELS: List[str] = [
        "nvidia/nemotron-3-super-120b-a12b:free",
        "arcee-ai/trinity-large-preview:free",
        "google/gemma-7b-it:free",
    ]

    # --- Списки моделей, разделенные по API ---
    
    # 1. Модели для прямого вызова через Google Gemini API
    NATIVE_GEMINI_MODELS: List[str] = [
        'gemini-3.1-flash-lite-preview',
        'gemini-2.5-flash-lite',
        'gemini-2.5-flash-image',
        'gemini-3.1-flash-image-preview',
        'gemini-2.5-flash',
        'gemini-2.0-flash',
    ]

    # 2. Модели для вызова через OpenRouter
    OPEN_ROUTER_MODELS: List[str] = [
        'nvidia/nemotron-nano-12b-v2-vl:free',
        'openai/gpt-5-nano',
        'google/gemini-2.5-flash-lite',
        'qwen/qwen3-vl-235b-a22b-thinking',
        'qwen/qwen3-vl-30b-a3b-thinking'

    ]

    # --- Общий, ФИКСИРОВАННЫЙ список моделей для анализа еды ---
    @property
    def NUTRITION_MODELS(self) -> List[str]:
        return [
            'gemini-2.5-flash',
            'gemini-3.1-flash-lite-preview',
            'gemini-2.5-flash-lite',
            'gemini-2.5-flash-image',
            'gemini-3.1-flash-image-preview',
            'gemini-2.0-flash',
            'openai/gpt-5-nano',
            'google/gemini-2.5-flash-lite',
            'qwen/qwen3-vl-235b-a22b-thinking',
            'qwen/qwen3-vl-30b-a3b-thinking',
            'nvidia/nemotron-nano-12b-v2-vl:free'
        ]

    # Указываем, что нужно загружать переменные из .env файла
    model_config = SettingsConfigDict(env_file=".env", extra='ignore')

settings = Settings()
