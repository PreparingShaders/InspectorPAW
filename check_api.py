import os
import json
import subprocess
from dotenv import load_dotenv

# --- НАСТРОЙКИ ---
load_dotenv()

# Получаем ключ Gemini из .env файла
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

def run_command(command):
    """Безопасно выполняет команду в оболочке и возвращает результат."""
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            shell=True,
            check=True
        )
        return result.stdout, None
    except subprocess.CalledProcessError as e:
        return e.stdout, e.stderr

def main():
    """
    Получает список моделей Gemini через REST API, тестирует их и формирует
    список рабочих моделей.
    """
    print("=" * 50)
    print("Проверка моделей Gemini через REST API (curl)...")
    print("=" * 50)

    if not GEMINI_KEY:
        print("❌ КРИТИЧЕСКАЯ ОШИБКА: Ключ GEMINI_API_KEY не найден в .env файле.")
        return

    # --- 1. Получаем список моделей ---
    print("\n--- [1/2] Запрос списка доступных моделей... ---")
    list_models_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_KEY}"
    command = f"curl -s -H 'Content-Type: application/json' -X GET '{list_models_url}'"
    
    stdout, stderr = run_command(command)

    if stderr:
        print(f"❌ ОШИБКА при выполнении curl: {stderr}")
        return

    try:
        data = json.loads(stdout)
        if 'error' in data:
            print(f"❌ ОШИБКА API: {data['error']['message']}")
            return
        
        all_models = data.get('models', [])
        generative_models = [
            m for m in all_models 
            if 'generateContent' in m.get('supportedGenerationMethods', [])
        ]
        
        if not generative_models:
            print("Не найдено моделей, поддерживающих генерацию контента.")
            return
            
        print(f"✅ Найдено {len(generative_models)} моделей для генерации контента.")

    except json.JSONDecodeError:
        print(f"❌ ОШИБКА: Не удалось разобрать ответ от API. Ответ: {stdout}")
        return

    # --- 2. Тестируем каждую модель ---
    print("\n--- [2/2] Тестирование ответа от каждой модели... ---")
    
    working_models = [] # <-- Создаем пустой список для рабочих моделей

    for model in sorted(generative_models, key=lambda m: m['name']):
        model_name = model['name']
        print(f"Тестируем: '{model_name}'...", end=" ", flush=True)
        
        test_url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={GEMINI_KEY}"
        post_data = '{"contents":[{"parts":[{"text":"Say OK"}]}]}'
        command = f"curl -s -H 'Content-Type: application/json' -d '{post_data}' -X POST '{test_url}'"
        
        stdout, stderr = run_command(command)

        if stderr:
            print(f"❌ ОШИБКА curl: {stderr}")
            continue

        try:
            response_data = json.loads(stdout)
            if 'error' in response_data:
                print(f"❌ ОШИБКА API: {response_data['error']['message']}")
            elif response_data.get('candidates'):
                text = response_data['candidates'][0]['content']['parts'][0]['text']
                if "OK" in text:
                    print("✅ ОТВЕЧАЕТ")
                    # <-- Добавляем короткое имя модели в список
                    short_model_name = model_name.replace("models/", "")
                    working_models.append(short_model_name)
                else:
                    print(f"⚠️  Ответ пустой или некорректный (Текст: {text})")
            else:
                prompt_feedback = response_data.get('promptFeedback', {})
                if prompt_feedback.get('blockReason'):
                    reason = prompt_feedback['blockReason']
                    print(f"❌ ЗАБЛОКИРОВАНО: {reason}")
                else:
                    print(f"⚠️  Неизвестный формат ответа: {stdout}")
        except json.JSONDecodeError:
            print(f"❌ ОШИБКА: Не удалось разобрать JSON ответа. Ответ: {stdout}")

    # --- 3. Выводим итоговый список ---
    print("\n" + "=" * 50)
    print("ГОТОВЫЙ СПИСОК РАБОЧИХ МОДЕЛЕЙ GEMINI:")
    print("=" * 50)
    
    if working_models:
        print("NATIVE_GEMINI_MODELS = [")
        for m in sorted(working_models):
            print(f"    '{m}',")
        print("]")
    else:
        print("Рабочие модели не найдены.")

    print("\nПроверка завершена.")


if __name__ == "__main__":
    main()

NATIVE_GEMINI_MODELS = [
    # Топ-выбор: скорость, баланс и высокие лимиты
    'gemini-2.5-flash',
    'gemini-flash-latest',

    # Облегченные версии для максимальной экономии/скорости
    'gemini-2.5-flash-lite',
    'gemini-flash-lite-latest',

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