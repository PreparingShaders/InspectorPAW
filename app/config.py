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

    # --- Списки моделей, разделенные по API ---

    # 1. Модели для прямого вызова через Google Gemini API
    NATIVE_GEMINI_MODELS: List[str] = [
        'gemini-2.5-flash-lite',
        'gemini-3.1-flash-lite',
        'gemini-3.1-flash-lite-preview',
        'gemini-2.5-flash',
    ]

    # 2. Модели для вызова через OpenRouter
    OPEN_ROUTER_MODELS: List[str] = [
        'z-ai/glm-4.5-air:free',
        'nvidia/nemotron-3-nano-30b-a3b:free',
        'nvidia/nemotron-nano-9b-v2:free',
        'nvidia/nemotron-nano-12b-v2-vl:free',
        'google/gemma-4-31b-it:free',
        'minimax/minimax-m2.5:free',
        'openai/gpt-oss-120b:free',
        'nvidia/nemotron-3-super-120b-a12b:free',
        'qwen/qwen3-vl-235b-a22b-thinking',
        'qwen/qwen3-vl-30b-a3b-thinking'
    ]

    # --- Общий, ФИКСИРОВАННЫЙ список моделей для анализа еды ---
    @property
    def NUTRITION_MODELS(self) -> List[str]:
        return [
            'gemini-3.1-flash-lite-preview',
            'gemini-3.1-flash-lite',
            'gemini-2.5-flash-lite',
            'gemini-2.5-flash',
            'qwen/qwen3.5-flash-02-23',
            'google/gemma-4-31b-it:free',
            'openai/gpt-5-nano',
            'google/gemini-2.5-flash-lite',
            'qwen/qwen3-vl-235b-a22b-thinking',
            'qwen/qwen3-vl-30b-a3b-thinking',
            'nvidia/nemotron-nano-12b-v2-vl:free'
        ]

    @property
    def CHAT_MODELS(self) -> List[str]:
        # Объединяем модели OpenRouter и Gemini, отдавая приоритет OpenRouter
        # Используем set для удаления дубликатов, затем преобразуем обратно в список
        combined_models = list(self.OPEN_ROUTER_MODELS)
        for model in self.NATIVE_GEMINI_MODELS:
            if model not in combined_models:
                combined_models.append(model)
        # Сортируем по "настоящему" имени модели, игнорируя префикс до слэша
        return combined_models

    @property
    def ALL_AVAILABLE_AI_MODELS(self) -> List[dict[str, str]]:
        all_models = set(self.CHAT_MODELS + self.NUTRITION_MODELS)
        models_list = []
        for model_id in all_models:
            models_list.append({
                "id": model_id,
                "name": model_id.replace(":", " - ")
            })
        # Здесь тоже применяем более умную сортировку
        return sorted(models_list, key=lambda x: x['name'].split('/')[-1])

    # Указываем, что нужно загружать переменные из .env файла
    model_config = SettingsConfigDict(env_file=".env", extra='ignore')


settings = Settings()