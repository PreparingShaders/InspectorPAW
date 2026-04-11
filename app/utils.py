from datetime import date
from typing import Optional, Dict, Any, List
import math
import datetime
import google.genai as genai
import asyncio
from openai import AsyncOpenAI
from . import models
from .config import settings

# --- AI Coach Function ---
async def get_ai_coach_advice(
    user_targets: Dict,
    consumed_today: Dict,
    analyzed_meal: Dict,
    current_time: datetime.datetime
) -> str:
    """
    Генерирует персональный совет от AI-коуча на основе текущей диеты и нового приема пищи.
    """
    # Выбираем лучшую доступную модель из динамического списка
    model_id_to_use = settings.AI_CHAT_MODELS[0] if settings.AI_CHAT_MODELS else "google/gemini-flash-1.5"
    print(f"--- AI Coach использует модель: {model_id_to_use} ---")

    time_str = current_time.strftime("%H:%M")
    
    deltas = {}
    for key in user_targets:
        target = user_targets.get(key, 0)
        consumed = consumed_today.get(key, 0)
        meal_val = analyzed_meal.get(f"total_{key}", 0)
        
        start_h, end_h = 5.0, 23.0
        time_factor = max(0.05, min(1.0, (current_time.hour + current_time.minute / 60 - start_h) / (end_h - start_h)))
        expected_now = target * time_factor
        
        future_consumed = consumed + meal_val
        delta = future_consumed - expected_now
        
        status = "в норме"
        if delta > target * 0.15: status = f"перебор на {round(delta)} ед."
        elif delta < -target * 0.15: status = f"недобор в {round(abs(delta))} ед."
        
        deltas[key] = status

    prompt = f"""
    Ты — дружелюбный и мотивирующий фитнес-коуч. Твоя задача — дать пользователю короткий (2-3 предложения) и полезный совет.
    
    ### Контекст:
    - Сейчас {time_str}.
    - Пользователь собирается съесть: **{analyzed_meal.get('food_name', 'неизвестное блюдо')}** (Калории: {analyzed_meal.get('total_calories', 0)}, Белки: {analyzed_meal.get('total_protein', 0)}г, Жиры: {analyzed_meal.get('total_fat', 0)}г, Углеводы: {analyzed_meal.get('total_carbohydrates', 0)}г).
    - Его дневные цели: Калории: {user_targets.get('calories', 0)}, Белки: {user_targets.get('protein', 0)}г, Жиры: {user_targets.get('fat', 0)}г, Углеводы: {user_targets.get('carbohydrates', 0)}г.
    - С учетом этого блюда, его прогресс относительно текущего времени будет:
        - Калории: {deltas.get('calories', 'в норме')}
        - Белки: {deltas.get('protein', 'в норме')}
        - Жиры: {deltas.get('fat', 'в норме')}
        - Углеводы: {deltas.get('carbohydrates', 'в норме')}

    ### Твоя задача:
    1.  Проанализируй, как это блюдо повлияет на дневной план пользователя.
    2.  Если блюдо помогает закрыть дефицит (например, много белка при его недоборе) — похвали выбор.
    3.  Если блюдо создает сильный перебор (например, много жиров при их избытке) — мягко предупреди и посоветуй, как это скомпенсировать в течение дня (например, "постарайся в следующий раз выбрать что-то менее жирное").
    4.  Дай один главный, самый важный совет, на чем сфокусироваться дальше.
    5.  Твой ответ должен быть в 2-3 предложения, на естественном русском языке, как будто ты пишешь другу в мессенджер.
    """

    try:
        open_router_client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=settings.OPEN_ROUTER_API_KEY,
        )
        chat_completion = await open_router_client.chat.completions.create(
            model=model_id_to_use,
            messages=[
                {"role": "system", "content": "Ты — дружелюбный и мотивирующий фитнес-коуч."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=250,
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        print(f"AI Coach Error using model {model_id_to_use}: {e}")
        return "Не удалось получить совет от AI. Попробуйте позже."


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
    if day_ratio > 1.05: return f"Небольшой перебор"
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
    now = current_dt if current_dt else datetime.datetime.now()
    current_time = now.hour + now.minute / 60
    start_h, end_h = 5.0, 23.0
    time_factor = max(0.05, min(1.0, (current_time - start_h) / (end_h - start_h)))

    if not any(actual.values()):
        return {"daily_score": 0, "status_color": "#5A6978", "status_message": {"calories": "Нет данных", "protein": "Нет данных", "fat": "Нет данных", "carbohydrates": "Нет данных"}, "y_axis_pos": 0, "time_progress": round(time_factor * 100, 1)}

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
    day_calorie_ratio = actual['calories'] / target['calories'] if target['calories'] > 0 else 0
    if day_calorie_ratio >= 0.98:
        base_score = 100
        day_fat_ratio = actual.get('fat', 0) / (target.get('fat', 1) + 1e-6)
        day_carbs_ratio = actual.get('carbohydrates', 0) / (target.get('carbohydrates', 1) + 1e-6)
        if day_fat_ratio > 1.15: base_score -= 10
        if day_carbs_ratio < 0.85: base_score -= 5
        final_score = max(85, base_score)

    if actual.get('protein', 0) > target.get('protein', 0) and actual.get('calories', 0) <= target.get('calories', 0) * 1.05:
        bonus = (actual['protein'] / target['protein'] - 1.0) * 50
        final_score += min(bonus, 20)

    final_score = round(max(0, min(final_score, 120)))

    color = "#e11d48"
    if final_score > 105: color = "#FFD700"
    elif 95 <= final_score <= 105: color = "#F0F0F0"
    elif 80 <= final_score <= 94: color = "#f59e0b"

    tooltips = get_nutrient_tooltips(target, actual, time_factor)

    return {
        "daily_score": final_score,
        "status_color": color,
        "status_message": tooltips,
        "y_axis_pos": final_score,
        "time_progress": round(time_factor * 100, 1)
    }