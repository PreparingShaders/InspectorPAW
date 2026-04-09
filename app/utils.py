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


def _get_hierarchical_status_message(target: Dict, actual: Dict, time_factor: float, final_score: int) -> str:
    """
    Определяет ОДНО наиболее важное, конкретное сообщение для пользователя на основе иерархии правил.
    Версия 3.0: Приоритет на выполненную норму калорий.
    """
    # Рассчитываем ключевые соотношения для анализа
    day_calorie_ratio = actual['calories'] / target['calories'] if target['calories'] > 0 else 0
    calorie_pace_ratio = (actual['calories'] / (target['calories'] * time_factor)) if (target['calories'] * time_factor) > 0 else 0
    day_protein_ratio = actual['protein'] / target['protein'] if target['protein'] > 0 else 0
    day_fat_ratio = actual['fat'] / target['fat'] if target['fat'] > 0 else 0
    day_carbs_ratio = actual['carbohydrates'] / target['carbohydrates'] if target['carbohydrates'] > 0 else 0

    # 1. ГЛАВНЫЙ ПРИОРИТЕТ: Если дневная норма калорий выполнена.
    if day_calorie_ratio >= 0.98:
        # Составляем сообщение на основе дисбаланса макросов
        fat_over = day_fat_ratio > 1.15 # Перебор жиров более чем на 15%
        carbs_under = day_carbs_ratio < 0.85 # Недобор углеводов более чем на 15%
        
        if fat_over and carbs_under:
            return "Норма калорий выполнена! Есть перебор по жирам и недобор углеводов."
        elif fat_over:
            return "Норма калорий выполнена, но есть небольшой перебор по жирам."
        elif carbs_under:
            return "Норма калорий выполнена, но не хватает углеводов."
        else:
            return "Отличная работа! Дневная норма калорий выполнена."

    # 2. Позитивные сообщения для высоких Score (если норма еще не выполнена)
    if final_score > 105: return "Overdrive: Максимальная эффективность! Продолжайте в том же духе."
    if final_score >= 95: return "Golden Standard: Идеальный темп! Отличная работа."

    # 3. Критический недобор калорий к концу дня
    if day_calorie_ratio < 0.6 and time_factor > 0.7:
        return "Критический недобор калорий. Необходимо срочно полноценно поесть."

    # 4. Значительное отклонение от ТЕМПА питания
    if calorie_pace_ratio < 0.7 and time_factor > 0.4:
        return "Вы отстаете от графика питания. Пора перекусить, чтобы догнать план."
    if calorie_pace_ratio > 1.6: # Немного увеличили порог
        return "Слишком быстрый темп питания. Распределите приемы пищи равномернее."

    # 5. Конкретные рекомендации по макронутриентам (дефицит к вечеру)
    if day_protein_ratio < 0.8 and time_factor > 0.6: return "Недобор белка. Добавьте белковой пищи в ближайший прием."
    if day_carbs_ratio < 0.7 and time_factor > 0.6: return "Недобор углеводов. Включите сложные углеводы в рацион."
    if day_fat_ratio < 0.7 and time_factor > 0.6: return "Недобор жиров. Добавьте полезные жиры."

    # 6. Конкретные рекомендации по макронутриентам (избыток, кроме белка)
    if day_fat_ratio > 1.3: return "Значительный перебор жиров. Постарайтесь сократить их потребление."
    if day_carbs_ratio > 1.3: return "Значительный перебор углеводов. Отдавайте предпочтение белку и овощам."

    # 7. Общее сообщение, если нет явных проблем, но и не "Golden Standard"
    if final_score >= 80: return "Все идет по плану. Продолжайте следить за балансом."

    # 8. Дефолтное сообщение для низкого Score
    return "Требуется корректировка плана питания."


def calculate_progress_lab_score(target: Dict[str, float], actual: Dict[str, float], current_dt: Optional[datetime.datetime] = None) -> Dict[str, Any]:
    """
    Рассчитывает динамический Индекс Дисциплины (Score) для ProgressLab.
    Версия 3.0: Приоритет на выполненную норму калорий.
    """
    # 1. Настройка временного окна
    now = current_dt if current_dt else datetime.datetime.now()
    current_time = now.hour + now.minute / 60
    start_h, end_h = 5.0, 23.0
    time_factor = max(0.05, min(1.0, (current_time - start_h) / (end_h - start_h)))

    if not any(actual.values()):
        return {"daily_score": 0, "status_color": "#5A6978", "status_message": "Нет данных за сегодня", "y_axis_pos": 0, "time_progress": round(time_factor * 100, 1)}

    # 2. Расчет Score на основе темпа
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
        elif ratio > 1.2: param_score -= (ratio - 1.2) * 30

        if a_val > t_val and param != 'protein':
            param_score -= ((a_val / t_val) - 1.0) * 100

        total_score += max(0, param_score)

    # 3. Бонус Белка
    if actual.get('protein', 0) > target.get('protein', 0) and actual.get('calories', 0) <= target.get('calories', 0) * 1.05:
        total_score += min((actual['protein'] / target['protein'] - 1.0) * 20, 20)

    final_score = round(max(0, min(total_score, 120)))
    
    # 4. ПЕРЕОПРЕДЕЛЕНИЕ SCORE, ЕСЛИ НОРМА КАЛОРИЙ ВЫПОЛНЕНА
    day_calorie_ratio = actual['calories'] / target['calories'] if target['calories'] > 0 else 0
    if day_calorie_ratio >= 0.98:
        base_score = 100
        day_fat_ratio = actual.get('fat', 0) / (target.get('fat', 1) + 1e-6)
        day_carbs_ratio = actual.get('carbohydrates', 0) / (target.get('carbohydrates', 1) + 1e-6)
        
        # Небольшие штрафы за дисбаланс
        if day_fat_ratio > 1.15: base_score -= 10
        if day_carbs_ratio < 0.85: base_score -= 5
        
        final_score = max(85, base_score) # Гарантируем, что score не упадет в "красную зону"

    # 5. Определение цвета и финального сообщения
    color = "#e11d48" # Fail
    if final_score > 105: color = "#10b981" # Overdrive
    elif 95 <= final_score <= 105: color = "#FFD700" # Golden Standard
    elif 80 <= final_score <= 94: color = "#f59e0b" # Warning

    status_message = _get_hierarchical_status_message(target, actual, time_factor, final_score)

    return {
        "daily_score": final_score,
        "status_color": color,
        "status_message": status_message,
        "y_axis_pos": final_score,
        "time_progress": round(time_factor * 100, 1)
    }