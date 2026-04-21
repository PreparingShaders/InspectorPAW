from datetime import date, timedelta
from typing import Optional, Dict, Any, List
import math
import datetime
import google.genai as genai
import asyncio
import requests
from openai import AsyncOpenAI
from . import models
from .config import settings, Settings

async def test_model(model_id: str) -> Optional[str]:
    """
    Тестирует модель, отправляя короткий запрос и ожидая ответ в течение 7 секунд.
    Возвращает model_id, если тест успешен, иначе None.
    """
    try:
        async with asyncio.timeout(7):
            client = AsyncOpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=settings.OPEN_ROUTER_API_KEY,
            )
            chat_completion = await client.chat.completions.create(
                model=model_id,
                messages=[{"role": "user", "content": "Ответь 'ок'"}],
                max_tokens=5,
            )
            response_text = chat_completion.choices[0].message.content.strip().lower()
            if "ок" in response_text:
                return model_id
            return None
    except Exception:
        return None

async def get_available_ai_models() -> List[Dict[str, str]]:
    """
    Получает список бесплатных моделей с OpenRouter и тестирует их.
    Возвращает список словарей рабочих моделей.
    """
    print("--- Обновление списка бесплатных моделей AI-коуча... ---")
    try:
        response = requests.get("https://openrouter.ai/api/v1/models")
        if response.status_code != 200:
            print("Ошибка при получении моделей от OpenRouter.")
            return []

        models_data = response.json().get('data', [])
        
        potential_models = [
            {"id": model.get("id"), "name": model.get("name") or model.get("id")}
            for model in models_data 
            if model.get("id") and "free" in model.get("id").lower()
        ]

        for model in potential_models:
            print(model)
        print(len(potential_models))

        tasks = [test_model(model["id"]) for model in potential_models]
        tested_models_results = await asyncio.gather(*tasks)
        
        working_model_ids = {model_id for model_id in tested_models_results if model_id}
        
        working_models = [
            model for model in potential_models if model["id"] in working_model_ids
        ]
        
        print(f"Найдено {len(working_models)} рабочих бесплатных моделей.")
        return working_models

    except Exception as e:
        print(f"Не удалось обновить список моделей: {e}")
        return []


# --- AI Coach Function ---
async def get_ai_coach_advice(
    user_targets: Dict,
    consumed_today: Dict,
    analyzed_meal: Dict,
    current_time: datetime.datetime
) -> (str, str):
    """
    Генерирует персональный совет от AI-коуча на основе текущей диеты и нового приема пищи.
    Возвращает кортеж (совет, использованная_модель).
    """
    # Выбираем лучшую доступную модель из динамического списка
    model_id_to_use = user_targets.get('ai_model') or (settings.AI_CHAT_MODELS[0] if settings.AI_CHAT_MODELS else "google/gemini-flash-1.5")
    print(f"--- AI Coach использует модель: {model_id_to_use} ---")

    time_str = current_time.strftime("%H:%M")

    prompt = f"""
    Ты — эксперт-нутрициолог с математическим уклоном и немного дерзким характером. Твоя задача — дать пользователю четкий, основанный на цифрах совет. Говори прямо, как есть.

    ### Контекст:
    - Сейчас {time_str}.
    - Дневные цели пользователя:
        - Калории: {user_targets.get('calories', 0)}
        - Белки (P): {user_targets.get('protein', 0)} г
        - Жиры (F): {user_targets.get('fat', 0)} г
        - Углеводы (C): {user_targets.get('carbohydrates', 0)} г
    - Пользователь собирается съесть: **{analyzed_meal.get('food_name', 'неизвестное блюдо')}** (P: {analyzed_meal.get('total_protein', 0)}г, F: {analyzed_meal.get('total_fat', 0)}г, C: {analyzed_meal.get('total_carbohydrates', 0)}г).
    - Сегодня уже съедено: P: {round(consumed_today.get('protein', 0))}г, F: {round(consumed_today.get('fat', 0))}г, C: {round(consumed_today.get('carbohydrates', 0))}г.

    ### Твоя задача (отвечай в стиле "ты"):
    1.  **Проанализируй тайминг и график.** Сравни текущее потребление с ожидаемым на {time_str}. Объясни, идет ли пользователь с опережением или отставанием по макронутриентам.
        - *Пример: "Сейчас только {time_str}, а ты уже съел {round(consumed_today.get('fat', 0) + analyzed_meal.get('total_fat', 0))} грамм жиров из твоих {user_targets.get('fat', 0)}. Ты идешь с опережением графика."*
    2.  **Дай прямой совет по следующему шагу.** Если есть перебор по одному макросу (например, жирам), а по другому недобор (белки), дай конкретную рекомендацию.
        - *Пример: "У тебя осталось всего {round(user_targets.get('fat', 0) - (consumed_today.get('fat', 0) + analyzed_meal.get('total_fat', 0)))} грамм жиров, но тебе еще надо {round(user_targets.get('protein', 0) - (consumed_today.get('protein', 0) + analyzed_meal.get('total_protein', 0)))} грамм белка. Выбери нежирное мясо или творог, иначе провал миссии, бро."*
    3.  **Добавь важное напоминание.** Если ты видишь, что в рационе нет овощей или фруктов, напомни о важности клетчатки.
        - *Пример: "Я заметил у тебя отсутствие клетчатки в течение дня. Если хочешь нормально какать, советую ее добавить."*
    4.  **Будь кратким (3-4 предложения) и мотивирующим, но строгим.**
    """

    try:
        open_router_client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=settings.OPEN_ROUTER_API_KEY,
        )
        chat_completion = await open_router_client.chat.completions.create(
            model=model_id_to_use,
            messages=[
                {"role": "system", "content": "Ты — эксперт-нутрициолог с математическим уклоном и немного дерзким характером. Отвечай в стиле 'ты'."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=250,
        )
        return chat_completion.choices[0].message.content, model_id_to_use
    except Exception as e:
        print(f"AI Coach Error using model {model_id_to_use}: {e}")
        return "Не удалось получить совет от AI. Попробуйте позже.", model_id_to_use


def calculate_user_targets(user: models.User, latest_weight_kg: Optional[float], latest_body_fat_percentage: Optional[float]):
    """
    Рассчитывает целевые КБЖУ по продвинутому алгоритму.
    """
    bmr = 0
    if latest_weight_kg and latest_body_fat_percentage and latest_body_fat_percentage > 0:
        lean_body_mass = latest_weight_kg * (1 - (latest_body_fat_percentage / 100))
        bmr = 370 + (21.6 * lean_body_mass)
    elif user.date_of_birth and latest_weight_kg and user.height_cm and user.gender:
        age = (date.today() - user.date_of_birth).days / 365.25
        if user.gender == 'male':
            bmr = (10 * latest_weight_kg) + (6.25 * user.height_cm) - (5 * age) + 5
        elif user.gender == 'female':
            bmr = (10 * latest_weight_kg) + (6.25 * user.height_cm) - (5 * age) - 161

    if bmr <= 0:
        bmr = 1800

    activity_multipliers = {
        'sedentary': 1.2, 'light': 1.375, 'moderate': 1.55,
        'active': 1.725, 'very_active': 1.9
    }
    multiplier = activity_multipliers.get(user.activity_level, 1.2)
    tdee = bmr * multiplier

    if user.goal == 'fat_loss':
        adjustment = 1.0 - (0.10 + (user.goal_intensity * 0.15))
        target_calories = tdee * adjustment
    elif user.goal == 'mass_gain':
        adjustment = 1.0 + (0.10 + (user.goal_intensity * 0.15))
        target_calories = tdee * adjustment
    else:
        target_calories = tdee

    if not latest_weight_kg or latest_weight_kg <= 0:
        return {"target_calories": 0, "target_protein": 0, "target_fat": 0, "target_carbohydrates": 0}

    target_protein = 2.0 * latest_weight_kg
    calories_from_protein = target_protein * 4
    target_fat = 1.0 * latest_weight_kg
    calories_from_fat = target_fat * 9
    min_calories_from_macros = calories_from_protein + calories_from_fat

    if target_calories < min_calories_from_macros:
        target_calories = min_calories_from_macros
        target_carbohydrates = 0
    else:
        remaining_calories = target_calories - min_calories_from_macros
        target_carbohydrates = remaining_calories / 4

    return {
        "target_calories": round(target_calories),
        "target_protein": round(target_protein),
        "target_fat": round(target_fat),
        "target_carbohydrates": round(target_carbohydrates)
    }


def _get_status_for_nutrient(target_val: float, actual_val: float, time_factor: float, nutrient_name: str) -> str:
    if target_val == 0: return "Не отслеживается"
    day_ratio = actual_val / target_val
    if day_ratio > 1.15 and nutrient_name != 'белка': return f"Значительный перебор"
    if day_ratio > 1.05: return "Небольшой перебор"
    if day_ratio >= 0.95: return "Норма выполнена"
    pace_ratio = (actual_val / (target_val * time_factor)) if time_factor > 0 else 0
    if pace_ratio >= 0.85: return "По плану"
    else:
        if time_factor > 0.7: return "Критический недобор"
        else: return "Отставание от графика"

def get_detailed_status_messages(target: Dict, actual: Dict, time_factor: float) -> Dict[str, str]:
    statuses = {}
    nutrient_map = {'calories': 'калорий', 'protein': 'белка', 'fat': 'жиров', 'carbohydrates': 'углеводов'}
    for key, name in nutrient_map.items():
        statuses[key] = _get_status_for_nutrient(target.get(key, 0), actual.get(key, 0), time_factor, name)
    return statuses

def _generate_nutrient_tooltip(target_val: float, actual_val: float, time_factor: float, name: str, unit: str) -> str:
    if target_val == 0: return f"{name.capitalize()}: не отслеживается"
    expected_val = target_val * time_factor
    if actual_val > expected_val * 1.15: status = "опережение" if name.lower() == "белки" else "превышение"
    elif actual_val < expected_val * 0.85: status = "отставание"
    else: status = "в норме"
    return f"{name.capitalize()}: {status} ({round(actual_val)} из {round(expected_val)} {unit})"

def get_nutrient_tooltips(target: Dict, actual: Dict, time_factor: float) -> Dict[str, str]:
    return {
        "calories": _generate_nutrient_tooltip(target.get('calories', 0), actual.get('calories', 0), time_factor, "Калории", "ккал"),
        "protein": _generate_nutrient_tooltip(target.get('protein', 0), actual.get('protein', 0), time_factor, "Белки", "г"),
        "fat": _generate_nutrient_tooltip(target.get('fat', 0), actual.get('fat', 0), time_factor, "Жиры", "г"),
        "carbohydrates": _generate_nutrient_tooltip(target.get('carbohydrates', 0), actual.get('carbohydrates', 0), time_factor, "Углеводы", "г")
    }

def calculate_progress_lab_score(target: Dict[str, float], actual: Dict[str, float], current_dt: Optional[datetime.datetime] = None) -> Dict[str, Any]:
    # --- Existing initial calculations ---
    now = current_dt if current_dt else datetime.datetime.now()
    current_time = now.hour + now.minute / 60
    start_h, end_h = 5.0, 23.0
    time_factor = max(0.05, min(1.0, (current_time - start_h) / (end_h - start_h)))

    # --- Handle empty data case ---
    if not any(actual.values()):
        return {
            "daily_score": 0, "status_color": "#5A6978",
            "status_message": {"calories": "Нет данных", "protein": "Нет данных", "fat": "Нет данных", "carbohydrates": "Нет данных"},
            "y_axis_pos": 0, "time_progress": round(time_factor * 100, 1),
            "target_delta": {key: round(target.get(key, 0)) for key in ['calories', 'protein', 'fat', 'carbohydrates']},
            "nutrient_statuses": {"calories": "OK", "protein": "OK", "fat": "OK", "carbohydrates": "OK"},
            "probability_of_success": "ВЫСОКИЙ",
            "danger_status": False,
            "status_title": "Начните день",
            "smart_advice": "Добавьте свой первый прием пищи, чтобы начать анализ."
        }

    # --- Existing score calculation logic ---
    total_score = 0.0
    weights = {'calories': 40, 'protein': 30, 'fat': 15, 'carbohydrates': 15}
    tolerance_threshold = 0.3
    for param, max_weight in weights.items():
        t_val = target.get(param, 0)
        a_val = actual.get(param, 0)
        if t_val == 0: continue
        expected_now = t_val * max(time_factor, tolerance_threshold)
        ratio = a_val / expected_now if expected_now > 0 else 1.0
        param_score = max_weight
        if ratio < 0.8: param_score *= (a_val / (t_val * time_factor + 1e-6))
        elif ratio > 1.2 and param != 'protein': param_score -= (ratio - 1.2) * 30
        if a_val > t_val and param != 'protein': param_score -= ((a_val / t_val) - 1.0) * 100
        total_score += max(0, param_score)

    final_score = total_score
    day_calorie_ratio = actual.get('calories', 0) / target.get('calories', 1)
    if day_calorie_ratio >= 0.98:
        base_score = 100
        day_fat_ratio = actual.get('fat', 0) / target.get('fat', 1)
        day_carbs_ratio = actual.get('carbohydrates', 0) / target.get('carbohydrates', 1)
        if day_fat_ratio > 1.15: base_score -= 10
        if day_carbs_ratio < 0.85: base_score -= 5
        final_score = max(85, base_score)

    if actual.get('protein', 0) > target.get('protein', 0) and actual.get('calories', 0) <= target.get('calories', 1) * 1.05:
        bonus = (actual.get('protein', 0) / target.get('protein', 1) - 1.0) * 50
        final_score += min(bonus, 20)

    final_score = round(max(0, min(final_score, 120)))
    color = "#e11d48"
    if final_score > 105: color = "#FFD700"
    elif 95 <= final_score <= 105: color = "#F0F0F0"
    elif 80 <= final_score <= 94: color = "#f59e0b"
    tooltips = get_nutrient_tooltips(target, actual, time_factor)

    # --- NEW LOGIC STARTS HERE ---

    # 1. Reverse Engineering
    target_delta = {
        key: max(0, round(target.get(key, 0) - actual.get(key, 0)))
        for key in ['calories', 'protein', 'fat', 'carbohydrates']
    }

    nutrient_statuses = {}
    for key in ['calories', 'protein', 'fat', 'carbohydrates']:
        t_val = target.get(key, 0)
        a_val = actual.get(key, 0)
        if t_val == 0:
            nutrient_statuses[key] = "OK"
            continue
        ratio = a_val / t_val
        if ratio > 1.05 and key != 'protein':
            nutrient_statuses[key] = "CRITICAL_LIMIT"
        elif ratio > 0.95 and key != 'protein':
            nutrient_statuses[key] = "WARNING"
        else:
            nutrient_statuses[key] = "OK"

    # 2. Predictive Analysis
    danger_status = False
    if nutrient_statuses['fat'] == "CRITICAL_LIMIT" or nutrient_statuses['calories'] == "CRITICAL_LIMIT":
        danger_status = True
    if current_time < 12.0 and (actual.get('fat', 0) / (target.get('fat', 1))) > 0.8:
        danger_status = True
    if current_time < 18.0 and (actual.get('calories', 0) / (target.get('calories', 1))) > 0.9:
        danger_status = True

    probability_of_success = "ВЫСОКИЙ"
    remaining_time_factor = 1.0 - time_factor
    if danger_status:
        probability_of_success = "НИЗКИЙ"
    elif remaining_time_factor < 0.2 and target_delta['calories'] > target.get('calories', 1) * 0.3:
        probability_of_success = "НИЗКИЙ"
    elif target_delta['fat'] < 10 and remaining_time_factor > 0.25:
        probability_of_success = "СРЕДНИЙ"

    # 3. Contextual Verdict (REWRITTEN)
    status_title = "Анализ дня"
    smart_advice = ""

    # --- Sentence Constructor ---
    if nutrient_statuses['calories'] == 'CRITICAL_LIMIT':
        status_title = "Лимит превышен"
        smart_advice = "Лимит калорий на сегодня исчерпан. До конца дня рекомендуется пить только воду или зеленый чай."
    elif nutrient_statuses['fat'] == 'CRITICAL_LIMIT':
        status_title = "Критический перебор жиров"
        smart_advice = f"Ты превысил лимит жиров. Чтобы улучшить балл, до конца дня полностью исключи масла и орехи, фокусируясь на чистом белке. Осталось добрать {target_delta['protein']}г белка."
    elif danger_status:
        status_title = "Риск провала"
        time_left_phrase = "уже" if time_factor > 0.5 else "только"
        smart_advice = f"Слушай, сейчас {time_left_phrase} {now.strftime('%H:%M')}, а ты потратил почти все жиры. У тебя серьезные проблемы с балансом. Срочно удели внимание нежирному белку, которого осталось {target_delta['protein']}г."
    elif target_delta['protein'] > target.get('protein', 1) * 0.6 and time_factor > 0.6:
        status_title = "Критический недобор белка"
        smart_advice = f"Времени осталось немного, а тебе еще нужно набрать {target_delta['protein']}г белка. Это приоритет №1, чтобы улучшить результат. Сфокусируйся на этом."
    elif final_score > 95:
        status_title = "Идеальный темп"
        smart_advice = f"Ты уверенно движешься к цели. Осталось набрать {target_delta['protein']}г белка и {target_delta['carbohydrates']}г углеводов, время еще есть. Так держать!"
    else:
        status_title = "Все по плану"
        smart_advice = f"Ты в графике. Чтобы достичь цели, тебе осталось {target_delta['calories']} ккал, из которых {target_delta['protein']}г белка — твой главный приоритет."

    # --- Final return statement ---
    return {
        "daily_score": final_score,
        "status_color": color,
        "status_message": tooltips,
        "y_axis_pos": final_score,
        "time_progress": round(time_factor * 100, 1),
        "target_delta": target_delta,
        "nutrient_statuses": nutrient_statuses,
        "probability_of_success": probability_of_success,
        "danger_status": danger_status,
        "status_title": status_title,
        "smart_advice": smart_advice
    }