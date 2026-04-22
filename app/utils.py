from datetime import date, timedelta
from typing import Optional, Dict, Any, List
import math
import datetime
import asyncio
import requests
from openai import AsyncOpenAI
from . import models
from .config import settings

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


async def prepare_ai_context(
    user: models.User,
    consumed_today: Dict,
    analyzed_meal: Dict,
    latest_weight_kg: Optional[float],
    latest_body_fat_percentage: Optional[float]
) -> Dict[str, Any]:
    """
    Собирает все необходимые данные в единый JSON для AI-коуча.
    """
    current_time = datetime.datetime.now()
    user_targets = calculate_user_targets(user, latest_weight_kg, latest_body_fat_percentage)

    # Добавляем съедаемое блюдо к уже съеденному для полного анализа
    total_consumed_with_meal = {
        'calories': consumed_today.get('calories', 0) + analyzed_meal.get('total_calories', 0),
        'protein': consumed_today.get('protein', 0) + analyzed_meal.get('total_protein', 0),
        'fat': consumed_today.get('fat', 0) + analyzed_meal.get('total_fat', 0),
        'carbohydrates': consumed_today.get('carbohydrates', 0) + analyzed_meal.get('total_carbohydrates', 0),
    }

    progress_metrics = calculate_progress_lab_score(
        target=user_targets,
        actual=total_consumed_with_meal,
        current_dt=current_time
    )

    # Добавляем ai_model к user_targets, если он есть у пользователя
    # user_targets['ai_model'] = user.ai_model

    return {
        "user_targets": user_targets,
        "consumed_today": consumed_today,
        "analyzed_meal": analyzed_meal,
        "current_time": current_time,
        "progress_metrics": progress_metrics
    }


async def get_ai_coach_advice(ai_context: Dict) -> (str, str):
    """
    Генерирует персональный совет от AI-коуча на основе полного контекста дня.
    Возвращает кортеж (совет, использованная_модель).
    """
    # Extract data from context
    user_targets = ai_context["user_targets"]
    consumed_today = ai_context["consumed_today"]
    analyzed_meal = ai_context["analyzed_meal"]
    current_time = ai_context["current_time"]
    progress_metrics = ai_context["progress_metrics"]

    model_id_to_use = user_targets.get('ai_model') or (settings.AI_CHAT_MODELS[0] if settings.AI_CHAT_MODELS else "google/gemini-flash-1.5")
    print(f"--- AI Coach использует модель: {model_id_to_use} ---")

    time_str = current_time.strftime("%H:%M")
    target_delta = progress_metrics.get("target_delta", {})

    prompt = f"""
    Ты — элитный нутрициолог-коуч. Твой стиль — прямой, честный и мотивирующий. Ты не боишься говорить правду, но всегда делаешь это, чтобы помочь пользователю достичь цели.

    ### Полный контекст твоего дня:
    - **Время:** {time_str}
    - **Твои дневные цели:** Калории: {user_targets.get('calories', 0)}, Белки: {user_targets.get('protein', 0)}г, Жиры: {user_targets.get('fat', 0)}г, Углеводы: {user_targets.get('carbohydrates', 0)}г.
    - **Уже съедено сегодня:** Калории: {round(consumed_today.get('calories', 0))}, Белки: {round(consumed_today.get('protein', 0))}г, Жиры: {round(consumed_today.get('fat', 0))}г, Углеводы: {round(consumed_today.get('carbohydrates', 0))}г.
    - **Ты собираешься съесть:** "{analyzed_meal.get('food_name', 'неизвестное блюдо')}" (Калории: {analyzed_meal.get('total_calories', 0)}, Б: {analyzed_meal.get('total_protein', 0)}г, Ж: {analyzed_meal.get('total_fat', 0)}г, У: {analyzed_meal.get('total_carbohydrates', 0)}г).

    ### Анализ твоего прогресса (с учетом этого блюда):
    - **Общий балл дня:** {progress_metrics.get('daily_score', 'N/A')} из 100.
    - **Вероятность успеха:** {progress_metrics.get('probability_of_success', 'N/A')}.
    - **Остаток до цели:** Белки: {target_delta.get('protein', 0)}г, Жиры: {target_delta.get('fat', 0)}г, Углеводы: {target_delta.get('carbohydrates', 0)}г.
    - **Статус опасности:** {'Да, есть риск провала' if progress_metrics.get('danger_status') else 'Нет, все под контролем'}.

    ### Твоя задача (отвечай в стиле "ты", 3-4 предложения):
    1.  **Начни с главного — с вердикта.** Основываясь на "Анализе прогресса", скажи, стоит ли есть это блюдо.
        - *Пример: "Твой балл падает до {progress_metrics.get('daily_score')}, а вероятность успеха становится низкой. Так что нет, это блюдо сейчас — плохая идея."*
    2.  **Объясни "почему" на цифрах.** Кратко и по делу, почему твой вердикт именно такой.
        - *Пример: "У тебя в остатке всего {target_delta.get('fat', 0)}г жиров, а это блюдо содержит {analyzed_meal.get('total_fat', 0)}г. Ты уйдешь в критический перебор."*
    3.  **Дай один, самый важный совет.** Что делать вместо этого? Или как исправить ситуацию, если блюдо уже съедено?
        - *Пример: "Замени его на куриную грудку на гриле. Тебе критически не хватает {target_delta.get('protein', 0)}г белка, и это лучший способ его добрать без лишнего жира."*
    """

    try:
        open_router_client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=settings.OPEN_ROUTER_API_KEY,
        )
        chat_completion = await open_router_client.chat.completions.create(
            model=model_id_to_use,
            messages=[
                {"role": "system", "content": "Ты — элитный нутрициолог-коуч. Твой стиль — прямой, честный и мотивирующий. Отвечай в стиле 'ты'."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
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
    now = current_dt if current_dt else datetime.datetime.now()
    current_time = now.hour + now.minute / 60
    start_h, end_h = 5.0, 23.0
    time_factor = max(0.05, min(1.0, (current_time - start_h) / (end_h - start_h)))

    if not any(actual.values()):
        return {
            "daily_score": 0, "status_color": "#5A6978",
            "status_message": {"calories": "Нет данных", "protein": "Нет данных", "fat": "Нет данных", "carbohydrates": "Нет данных"},
            "y_axis_pos": 0, "time_progress": round(time_factor * 100, 1),
            "target_delta": {key: round(target.get(key, 0)) for key in ['calories', 'protein', 'fat', 'carbohydrates']},
            "nutrient_statuses": {"calories": "OK", "protein": "OK", "fat": "OK", "carbohydrates": "OK"},
            "probability_of_success": "ВЫСОКИЙ",
            "danger_status": False,
        }

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
    }
