import os
import asyncio
from dotenv import load_dotenv
from openai import AsyncOpenAI
from google import genai
from google.genai import types

# --- НАСТРОЙКИ ---
load_dotenv()

# Твой URL воркера (убедись, что в .env он без лишних пробелов)
WORKER_URL = os.getenv("WORKER_URL", "https://inspectorgpt.classname1984.workers.dev").rstrip('/')

OR_KEY = os.getenv("OPEN_ROUTER_API_KEY")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

print("=" * 50)
print(f"ЗАПУСК ТЕСТОВ ЧЕРЕЗ ВОРКЕР: {WORKER_URL}")
print("=" * 50)

# --- ИНИЦИАЛИЗАЦИЯ КЛИЕНТОВ ЧЕРЕЗ ПРОКСИ ---

# 1. Клиент OpenRouter (через воркер)
# OpenRouter ожидает путь /v1/... поэтому добавляем его в base_url
or_client = AsyncOpenAI(
    api_key=OR_KEY,
    base_url=f"{WORKER_URL}/v1",
    default_headers={
        "HTTP-Referer": "https://github.com/Aleksey/InspectorAI",
        "X-Title": "InspectorAI_Debug"
    }
)

# 2. Клиент Gemini (через воркер)
# SDK Gemini само формирует пути, поэтому передаем чистый URL воркера
gemini_client = genai.Client(
    api_key=GEMINI_KEY,
    http_options=types.HttpOptions(base_url=WORKER_URL),
)


# --- ФУНКЦИИ ТЕСТИРОВАНИЯ ---

async def test_openrouter():
    print("\n[1/2] ТЕСТ: OpenRouter (через воркер)...")
    if not OR_KEY:
        print("❌ ОШИБКА: Ключ OpenRouter не найден в .env")
        return

    try:
        # Используем максимально стабильную бесплатную модель Google через OpenRouter
        model = "qwen/qwen3.6-plus-preview:free"

        response = await or_client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Say 'OpenRouter via Worker OK'"}],
            max_tokens=20,
            timeout=20.0
        )

        content = response.choices[0].message.content
        if content:
            print(f"✅ УСПЕХ! Ответ ({model}): {content.strip()}")
        else:
            print(f"⚠️ ТЕХНИЧЕСКИЙ УСПЕХ: Ключ принят, но модель вернула пустоту (None).")

    except Exception as e:
        print(f"❌ ОШИБКА OpenRouter: {e}")
        if "401" in str(e):
            print("👉 Подсказка: Если напрямую ключ работал, значит воркер не передает заголовки (headers).")


async def test_gemini():
    print("\n[2/2] ТЕСТ: Gemini (через воркер)...")
    if not GEMINI_KEY:
        print("❌ ОШИБКА: Ключ Gemini не найден в .env")
        return

    try:
        # Стандартная модель Gemini 2.0 Flash
        model = "gemini-2.5-flash"
        response = gemini_client.models.generate_content(
            model=model,
            contents="Say 'Gemini via Worker OK'"
        )
        print(f"✅ УСПЕХ! Ответ: {response.text.strip()}")
    except Exception as e:
        print(f"❌ ОШИБКА Gemini: {e}")


async def main():
    # Запускаем тесты
    await test_openrouter()
    await test_gemini()

    print("\n" + "=" * 50)
    print("Диагностика через прокси завершена.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass