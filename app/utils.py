from datetime import date
from typing import Optional, Dict, Any, List
import math
from . import models

def calculate_user_targets(user: models.User, latest_weight_kg: Optional[float], latest_body_fat_percentage: Optional[float]):
    """
    Рассчитывает целевые КБЖУ по продвинутому алгоритму.
    BMR: Кетч-МакАрдл (при наличии % жира), иначе Миффлин-Сан Жеор.
    TDEE: Множитель активности.
    Макросы: На основе веса тела с защитой от отрицательных углеводов.
    """
    bmr = 0
    # --- 1. Рассчитать BMR ---
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

    # --- 2. Рассчитать TDEE ---
    activity_multipliers = {
        'sedentary': 1.2, 'light': 1.375, 'moderate': 1.55,
        'active': 1.725, 'very_active': 1.9
    }
    multiplier = activity_multipliers.get(user.activity_level, 1.2)
    tdee = bmr * multiplier

    # --- 3. Применить цель пользователя ---
    target_calories = tdee
    if user.goal == 'fat_loss':
        adjustment = 1.0 - (0.10 + (user.goal_intensity * 0.15))
        target_calories *= adjustment
    elif user.goal == 'mass_gain':
        adjustment = 1.0 + (0.10 + (user.goal_intensity * 0.15))
        target_calories *= adjustment

    # --- 4. Рассчитать макронутриенты с защитой от ошибок ---
    if not latest_weight_kg or latest_weight_kg <= 0:
        return {"target_calories": 0, "target_protein": 0, "target_fat": 0, "target_carbohydrates": 0}

    # Белки: Строго 2г на кг
    target_protein = 2.0 * latest_weight_kg
    calories_from_protein = target_protein * 4

    # Жиры: 1.0г на кг
    target_fat = 1.0 * latest_weight_kg
    calories_from_fat = target_fat * 9

    # Калорийность белков и жиров является "полом"
    min_calories_from_macros = calories_from_protein + calories_from_fat

    # Проверка на пограничный случай
    if target_calories < min_calories_from_macros:
        # Если цель калорий слишком низкая, корректируем ее до минимума
        # и устанавливаем углеводы в 0.
        target_calories = min_calories_from_macros
        target_carbohydrates = 0
    else:
        # Стандартный расчет
        remaining_calories = target_calories - min_calories_from_macros
        target_carbohydrates = remaining_calories / 4

    return {
        "target_calories": round(target_calories),
        "target_protein": round(target_protein),
        "target_fat": round(target_fat),
        "target_carbohydrates": round(target_carbohydrates)
    }


def calculate_daily_score(target: Dict[str, float], actual: Dict[str, float]) -> Dict[str, Any]:
    """
    Рассчитывает ежедневный Индекс Дисциплины (Score) на основе целевых и фактических КБЖУ
    с постепенным ростом в течение дня.
    """
    
    total_score = 0
    achievements: List[str] = []

    # --- Вспомогательная функция для безопасного расчета процента выполнения ---
    def get_completion_ratio(actual_val: float, target_val: float) -> float:
        if target_val <= 0:
            return 0.0
        return actual_val / target_val

    # --- Калории (Максимум 40 очков) ---
    kcal_ratio = get_completion_ratio(actual['calories'], target['calories'])
    if kcal_ratio <= 1.0: # Недобор или точное попадание
        # Параболическая функция: медленный старт, быстрый рост в середине, замедление у цели
        kcal_score = 40 * (1 - (1 - kcal_ratio)**2)
    else: # Перебор
        # Штраф за перебор свыше 5%
        overage_ratio = kcal_ratio - 1.0
        penalty = max(0, overage_ratio - 0.05) * 200 # Усиленный штраф
        kcal_score = 40 - penalty
    total_score += kcal_score

    # --- Белки (Максимум 30 очков + 10 бонусных) ---
    protein_ratio = get_completion_ratio(actual['protein'], target['protein'])
    protein_score = 0
    if protein_ratio <= 1.0:
        protein_score = 30 * protein_ratio
    else: # Перебор (бонус)
        protein_score = 30
        # Бонус до 10 очков за перебор до 50% сверх нормы, если калории в норме
        if kcal_ratio <= 1.05:
            bonus_ratio = min((protein_ratio - 1.0) * 2, 1.0) # Бонус до 50% сверх нормы
            protein_bonus = 10 * bonus_ratio
            protein_score += protein_bonus
            if protein_bonus > 0:
                achievements.append("Protein Bonus Active")
    total_score += protein_score

    # --- Жиры и Углеводы (Максимум по 15 очков) ---
    for macro, weight in [('fat', 15), ('carbohydrates', 15)]:
        macro_ratio = get_completion_ratio(actual[macro], target[macro])
        macro_score = 0
        if macro_ratio <= 1.0:
            macro_score = weight * macro_ratio
        else: # Перебор
            # Штраф за перебор свыше 20%
            overage_ratio = macro_ratio - 1.0
            penalty = max(0, overage_ratio - 0.20) * 100
            macro_score = weight - penalty
        total_score += macro_score

    # --- Граничные условия ---
    final_score = round(max(0, min(total_score, 120)))

    # --- Определение визуального статуса ---
    status_color: str
    if final_score > 105:
        status_color = "green"
    elif 95 <= final_score <= 105:
        status_color = "white"
    elif 80 <= final_score <= 94:
        status_color = "orange"
    else: # final_score < 80
        status_color = "red"

    # --- Формирование выходных данных ---
    return {
        "daily_score": final_score,
        "status_color": status_color,
        "y_axis_pos": final_score,
        "achievements": achievements
    }