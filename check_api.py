import os
import json
import requests
from dotenv import load_dotenv

# --- НАСТРОЙКИ ---
load_dotenv()

# Ключи из .env
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
OPENROUTER_KEY = os.getenv("OPEN_ROUTER_API_KEY")

# URL твоего воркера
PROXY_URL = "https://inspectorgpt.classname1984.workers.dev"

# --- ТВОИ СПИСКИ МОДЕЛЕЙ ---
NATIVE_GEMINI_MODELS = [
        # Топ-выбор: скорость, баланс и высокие лимиты
        'gemini-2.5-flash',
        'gemini-flash-latest',
        # Облегченные версии для максимальной экономии/скорости
        'gemini-2.5-flash-lite',
        'gemini-flash-lite-latest',
        'gemini-3.1-flash-lite',
        # Превью-версии (могут иметь более жесткие лимиты)
        'gemini-3-flash-preview'
    ]

OPEN_ROUTER_MODELS = [
        'nvidia/nemotron-3-super-120b-a12b:free',
        'poolside/laguna-m.1:free',
        'openai/gpt-oss-120b:free',
        'z-ai/glm-4.5-air:free',
        # old list
        'nvidia/nemotron-3-nano-30b-a3b:free',
        'nvidia/nemotron-nano-9b-v2:free',
        'nvidia/nemotron-nano-12b-v2-vl:free',
        'z-ai/glm-4.5-air:free',
        'minimax/minimax-m2.5:free',
        'openai/gpt-oss-120b:free',
        'nvidia/nemotron-3-super-120b-a12b:free'
    ]

def test_model(model_name, is_gemini=True):
    print(f"Тестируем: {model_name:.<40}", end=" ", flush=True)

    headers = {"Content-Type": "application/json"}

    if is_gemini:
        # Для Gemini через воркер (путь v1beta)
        url = f"{PROXY_URL}/v1beta/models/{model_name}:generateContent?key={GEMINI_KEY}"
        payload = {"contents": [{"parts": [{"text": "Say OK"}]}]}
    else:
        # Для OpenRouter через воркер (путь v1)
        url = f"{PROXY_URL}/v1/chat/completions"
        headers["Authorization"] = f"Bearer {OPENROUTER_KEY}"
        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": "Say OK"}]
        }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=20)

        if response.status_code != 200:
            print(f"❌ Код {response.status_code}")
            return False

        res_data = response.json()

        if is_gemini:
            text = res_data['candidates'][0]['content']['parts'][0]['text']
        else:
            text = res_data['choices'][0]['message']['content']

        if "OK" in text.upper():
            print("✅ OK")
            return True
        else:
            print(f"⚠️ Текст: {text[:15]}...")
            return False

    except Exception as e:
        print(f"❌ Ошибка")
        return False


def main():
    working_gemini = []
    working_or = []

    print("=" * 60)
    print("ЗАПУСК ТЕСТА ЧЕРЕЗ WORKER PROXY")
    print("=" * 60)

    print("\n[1] ПРОВЕРКА NATIVE GEMINI (Google)")
    for m in NATIVE_GEMINI_MODELS:
        if test_model(m, is_gemini=True):
            working_gemini.append(m)

    print("\n[2] ПРОВЕРКА OPENROUTER (Free/Paid)")
    for m in OPEN_ROUTER_MODELS:
        if test_model(m, is_gemini=False):
            working_or.append(m)

    print("\n" + "=" * 60)
    print("РЕЗУЛЬТАТЫ:")
    print(f"Доступно Gemini: {len(working_gemini)} из {len(NATIVE_GEMINI_MODELS)}")
    print(f"Доступно OpenRouter: {len(working_or)} из {len(OPEN_ROUTER_MODELS)}")
    print("=" * 60)


if __name__ == "__main__":
    main()