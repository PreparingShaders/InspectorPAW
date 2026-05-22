from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional
from datetime import timezone, timedelta

class Settings(BaseSettings):
    # --- API Ключи (загружаются из .env) ---
    GEMINI_API_KEY: str
    # Ключ для OpenRouter теперь опционален, т.к. может быть не нужен при работе через воркер
    OPEN_ROUTER_API_KEY: Optional[str] = None
    BREVO_API_KEY: str
    SECRET_KEY: str

    # --- URL Воркера ---
    AI_WORKER_URL: str = "https://inspectorgpt.classname1984.workers.dev"

    # --- Настройки JWT ---
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 5760

    # --- Настройки часового пояса ---
    MSK_TZ: timezone = timezone(timedelta(hours=3))

    # --- Списки моделей, разделенные по API ---

    # 1. Модели для прямого вызова через Google Gemini API (дублирование исправлено)
    NATIVE_GEMINI_MODELS: List[str] = [
        # Топ-выбор: скорость, баланс и высокие лимиты
        'gemini-2.5-flash',
        'gemini-flash-latest',
        # Облегченные версии для максимальной экономии/скорости
        'gemini-2.5-flash-lite',
        'gemini-flash-lite-latest',
        'gemini-3.1-flash-lite',
        # Превью-версии (могут иметь более жесткие лимиты)
        'gemini-3-flash-preview',
        'gemini-3.1-flash-lite-preview',
        # Семейство Gemma (Open Models), отсортированные по убыванию веса/возможностей
        'gemma-4-31b-it',
        'gemma-4-26b-a4b-it',
        'gemma-3-27b-it',
        'gemma-3-12b-it',
        'gemma-3-4b-it',
        'gemma-3-1b-it',
        'gemma-3n-e4b-it',
        'gemma-3n-e2b-it',
    ]

    # 2. Модели для вызова через OpenRouter
    OPEN_ROUTER_MODELS: List[str] = [
        'nvidia/nemotron-3-nano-30b-a3b:free',
        'nvidia/nemotron-nano-9b-v2:free',
        'nvidia/nemotron-nano-12b-v2-vl:free',
        'google/gemma-4-31b-it:free',
        'z-ai/glm-4.5-air:free',
        'minimax/minimax-m2.5:free',
        'openai/gpt-oss-120b:free',
        'nvidia/nemotron-3-super-120b-a12b:free'
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
        # Объединяем модели, отдавая приоритет NATIVE_GEMINI_MODELS.
        combined_models = list(self.NATIVE_GEMINI_MODELS)
        for model in self.OPEN_ROUTER_MODELS:
            if model not in combined_models:
                combined_models.append(model)
        return combined_models

    @property
    def ALL_AVAILABLE_AI_MODELS(self) -> List[dict[str, str]]:
        # Начинаем с моделей для чата, которые уже в правильном порядке
        all_models_ordered = self.CHAT_MODELS
        
        # Добавляем модели для анализа питания, если их еще нет в списке
        for model in self.NUTRITION_MODELS:
            if model not in all_models_ordered:
                all_models_ordered.append(model)

        models_list = []
        for model_id in all_models_ordered:
            models_list.append({
                "id": model_id,
                "name": model_id.replace(":", " - ")
            })
        # Убрана алфавитная сортировка, чтобы сохранить заданный порядок
        return models_list

    # Указываем, что нужно загружать переменные из .env файла
    model_config = SettingsConfigDict(env_file=".env", extra='ignore')


settings = Settings()