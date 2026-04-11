from datetime import date
from typing import Optional, Dict, Any, List
import math
import datetime
from . import models

def calculate_user_targets(user: models.User, latest_weight_kg: Optional[float], latest_body_fat_percentage: Optional[float]):
    """
    Рассчитывает целевые КБЖУ по продвинутому алгоритму.
    BMR: Кетч-МакАрдл (при наличии % жира), иначе Миффлин-Сан Жеор.
    TDEE: Множитель активности.
    Макросы: На основе веса тела с защитой от отрицательных углеводов.
    """
    bmr = 0
    # --- 1. Рассчитать BMR (Basal Metabolic Rate) ---
    # Use Katch-McArdle formula if body fat percentage is available, as it's more accurate.
    if latest_weight_kg and latest_body_fat_percentage and latest_body_fat_percentage > 0:
        lean_body_mass = latest_weight_kg * (1 - (latest_body_fat_percentage / 100))
        bmr = 370 + (21.6 * lean_body_mass)
    # Fallback to Mifflin-St Jeor formula if body fat is not available.
    elif user.date_of_birth and latest_weight_kg and user.height_cm and user.gender:
        # Calculate age in years from date of birth.
        age = (date.today() - user.date_of_birth).days / 365.25
        if user.gender == 'male':
            bmr = (10 * latest_weight_kg) + (6.25 * user.height_cm) - (5 * age) + 5
        elif user.gender == 'female':
            bmr = (10 * latest_weight_kg) + (6.25 * user.height_cm) - (5 * age) - 161

    # Provide a sensible default BMR if calculation is not possible, to avoid division by zero.
    if bmr <= 0:
        bmr = 1800

    # --- 2. Рассчитать TDEE (Total Daily Energy Expenditure) ---
    activity_multipliers = {
        'sedentary': 1.2, 'light': 1.375, 'moderate': 1.55,
        'active': 1.725, 'very_active': 1.9
    }
    # Get the multiplier based on user's activity level, defaulting to 'sedentary'.
    multiplier = activity_multipliers.get(user.activity_level, 1.2)
    tdee = bmr * multiplier

    # --- 3. Применить цель пользователя (Apply user's goal) ---
    target_calories = tdee
    # Adjust TDEE based on the user's goal (fat loss or mass gain) and intensity.
    # The adjustment ranges from -10% to -25% for fat loss, and +10% to +25% for mass gain.
    if user.goal == 'fat_loss':
        adjustment = 1.0 - (0.10 + (user.goal_intensity * 0.15))
        target_calories *= adjustment
    elif user.goal == 'mass_gain':
        adjustment = 1.0 + (0.10 + (user.goal_intensity * 0.15))
        target_calories *= adjustment

    # --- 4. Рассчитать макронутриенты с защитой от ошибок (Calculate macronutrients with error protection) ---
    # If weight is not available, we cannot calculate macros, so return zeroed targets.
    if not latest_weight_kg or latest_weight_kg <= 0:
        return {"target_calories": 0, "target_protein": 0, "target_fat": 0, "target_carbohydrates": 0}

    # Protein target is fixed at 2.0g per kg of body weight.
    target_protein = 2.0 * latest_weight_kg
    calories_from_protein = target_protein * 4

    # Fat target is fixed at 1.0g per kg of body weight.
    target_fat = 1.0 * latest_weight_kg
    calories_from_fat = target_fat * 9

    # The sum of calories from protein and fat represents the minimum required calories.
    min_calories_from_macros = calories_from_protein + calories_from_fat

    # Edge case: If the target calories are too low (e.g., extreme fat loss goal),
    # they might not be enough to cover the essential protein and fat minimums.
    if target_calories < min_calories_from_macros:
        # In this case, adjust the target calories up to the minimum required,
        # and set carbohydrates to zero to prioritize protein and fat.
        target_calories = min_calories_from_macros
        target_carbohydrates = 0
    else:
        # Standard calculation: The remaining calories are allocated to carbohydrates.
        remaining_calories = target_calories - min_calories_from_macros
        target_carbohydrates = remaining_calories / 4

    return {
        "target_calories": round(target_calories),
        "target_protein": round(target_protein),
        "target_fat": round(target_fat),
        "target_carbohydrates": round(target_carbohydrates)
    }


def _get_status_for_nutrient(target_val: float, actual_val: float, time_factor: float, nutrient_name: str) -> str:
    """Анализирует статус одного нутриента и возвращает короткое сообщение."""
    if target_val == 0:
        return "Не отслеживается"

    day_ratio = actual_val / target_val

    # 1. Норма выполнена или есть перебор
    if day_ratio > 1.15 and nutrient_name != 'белка': # Для белка перебор не так страшен
        return f"Значительный перебор"
    if day_ratio > 1.05:
        return f"Небольшой перебор"
    if day_ratio >= 0.95:
        return "Норма выполнена"

    # 2. Анализ темпа, если норма еще не выполнена
    pace_ratio = (actual_val / (target_val * time_factor)) if time_factor > 0 else 0

    if pace_ratio >= 0.85:
        return "По плану"
    else:
        if time_factor > 0.7: # Если день близится к концу
            return "Критический недобор"
        else:
            return "Отставание от графика"

def get_detailed_status_messages(target: Dict, actual: Dict, time_factor: float) -> Dict[str, str]:
    """
    Формирует детальные сообщения по каждому макронутриенту.
    """
    statuses = {}
    nutrient_map = {
        'calories': 'калорий',
        'protein': 'белка',
        'fat': 'жиров',
        'carbohydrates': 'углеводов'
    }

    for key, name in nutrient_map.items():
        statuses[key] = _get_status_for_nutrient(target.get(key, 0), actual.get(key, 0), time_factor, name)

    return statuses

def _generate_nutrient_tooltip(target_val: float, actual_val: float, time_factor: float, name: str, unit: str) -> str:
    """Генерирует детальную подсказку для одного нутриента."""
    if target_val == 0:
        return f"{name.capitalize()}: не отслеживается"

    expected_val = target_val * time_factor
    
    # Определяем статус на основе процентного отклонения
    if actual_val > expected_val * 1.15:
        status = "опережение" if name.lower() == "белки" else "превышение"
    elif actual_val < expected_val * 0.85:
        status = "отставание"
    else:
        status = "в норме"

    # Формируем сообщение
    return f"{name.capitalize()}: {status} ({round(actual_val)} из {round(expected_val)} {unit})"

def get_nutrient_tooltips(target: Dict, actual: Dict, time_factor: float) -> Dict[str, str]:
    """Возвращает словарь с детальными подсказками по каждому нутриенту."""
    
    tooltips = {
        "calories": _generate_nutrient_tooltip(
            target.get('calories', 0), actual.get('calories', 0), time_factor, "Калории", "ккал"
        ),
        "protein": _generate_nutrient_tooltip(
            target.get('protein', 0), actual.get('protein', 0), time_factor, "Белки", "г"
        ),
        "fat": _generate_nutrient_tooltip(
            target.get('fat', 0), actual.get('fat', 0), time_factor, "Жиры", "г"
        ),
        "carbohydrates": _generate_nutrient_tooltip(
            target.get('carbohydrates', 0), actual.get('carbohydrates', 0), time_factor, "Углеводы", "г"
        )
    }
    return tooltips


def calculate_progress_lab_score(target: Dict[str, float], actual: Dict[str, float], current_dt: Optional[datetime.datetime] = None) -> Dict[str, Any]:
    """
    Рассчитывает динамический Индекс Дисциплины (Score) для ProgressLab.
    Версия 4.4: Замена status_message на детальные тултипы.
    """
    # 1. Настройка временного окна
    now = current_dt if current_dt else datetime.datetime.now()
    current_time = now.hour + now.minute / 60
    start_h, end_h = 5.0, 23.0
    time_factor = max(0.05, min(1.0, (current_time - start_h) / (end_h - start_h)))

    if not any(actual.values()):
        return {"daily_score": 0, "status_color": "#5A6978", "status_message": {"calories": "Нет данных", "protein": "Нет данных", "fat": "Нет данных", "carbohydrates": "Нет данных"}, "y_axis_pos": 0, "time_progress": round(time_factor * 100, 1)}

    # 2. Расчет Score
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
        elif ratio > 1.2 and param != 'protein':
             param_score -= (ratio - 1.2) * 30

        if a_val > t_val and param != 'protein':
            param_score -= ((a_val / t_val) - 1.0) * 100

        total_score += max(0, param_score)

    final_score = total_score

    # 3. Переопределение Score, если норма калорий выполнена
    day_calorie_ratio = actual['calories'] / target['calories'] if target['calories'] > 0 else 0
    if day_calorie_ratio >= 0.98:
        base_score = 100
        day_fat_ratio = actual.get('fat', 0) / (target.get('fat', 1) + 1e-6)
        day_carbs_ratio = actual.get('carbohydrates', 0) / (target.get('carbohydrates', 1) + 1e-6)
        
        if day_fat_ratio > 1.15: base_score -= 10
        if day_carbs_ratio < 0.85: base_score -= 5
        
        final_score = max(85, base_score)

    # 4. Бонус Белка
    if actual.get('protein', 0) > target.get('protein', 0) and actual.get('calories', 0) <= target.get('calories', 0) * 1.05:
        bonus = (actual['protein'] / target['protein'] - 1.0) * 50
        final_score += min(bonus, 20)

    final_score = round(max(0, min(final_score, 120)))

    # 5. Определение цвета
    color = "#e11d48" # Fail - Красный
    if final_score > 105: color = "#FFD700" # Overdrive - Золотой
    elif 95 <= final_score <= 105: color = "#F0F0F0" # Golden Standard - Белый
    elif 80 <= final_score <= 94: color = "#f59e0b" # Warning - Оранжевый

    # 6. Получение детальных сообщений
    tooltips = get_nutrient_tooltips(target, actual, time_factor)

    return {
        "daily_score": final_score,
        "status_color": color,
        "status_message": tooltips, # ЗАМЕНА: теперь здесь детальный объект
        "y_axis_pos": final_score,
        "time_progress": round(time_factor * 100, 1)
    }