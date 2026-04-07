from datetime import date
from typing import Optional, Dict, Any, List

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
    Рассчитывает ежедневный Индекс Дисциплины (Score) на основе целевых и фактических КБЖУ.

    Args:
        target: Словарь с целевыми значениями КБЖУ (kcal, protein, fat, carb).
                Пример: {'kcal': 2000, 'protein': 150, 'fat': 70, 'carb': 200}
        actual: Словарь с фактическими значениями КБЖУ (kcal, protein, fat, carb).
                Пример: {'kcal': 2050, 'protein': 160, 'fat': 75, 'carb': 190}

    Returns:
        Словарь, содержащий daily_score, status_color, y_axis_pos и achievements.
    """
    
    score = 100.0
    achievements: List[str] = []

    # --- Вспомогательная функция для расчета процентного отклонения ---
    def get_deviation_percent(actual_val: float, target_val: float) -> float:
        if target_val == 0:
            # Для КБЖУ предполагается, что цели всегда > 0.
            # Если target_val может быть 0, и actual_val > 0, это будет бесконечное отклонение.
            # В данном контексте, если target_val == 0, и actual_val > 0,
            # это скорее ошибка в данных или логике.
            # Для безопасности, если target_val == 0, возвращаем 0, чтобы избежать деления на ноль.
            # В реальном приложении, возможно, стоит бросить ошибку или применить максимальный штраф.
            return 0.0 

        return (abs(actual_val - target_val) / target_val) * 100

    # --- Калории (Вес: 40%) ---
    kcal_deviation_percent = get_deviation_percent(actual['kcal'], target['kcal'])
    if kcal_deviation_percent > 5:
        penalty_kcal = (kcal_deviation_percent - 5) * 0.8
        score -= penalty_kcal

    # --- Белки (Вес: 30%) ---
    if actual['protein'] < target['protein']:
        protein_deviation_percent = (target['protein'] - actual['protein']) / target['protein'] * 100 if target['protein'] != 0 else 0
        penalty_prot = protein_deviation_percent * 0.6
        score -= penalty_prot
    
    # Бонус (Overdrive) для Белков
    # Если фактический белок >= (целевой белок + 15г)
    # И фактические калории <= (целевые калории * 1.05)
    if actual['protein'] >= (target['protein'] + 15) and actual['kcal'] <= (target['kcal'] * 1.05):
        score += 7
        achievements.append("Protein Bonus Active")

    # --- Жиры и Углеводы (Вес по 15% каждый) ---
    for macro in ['fat', 'carb']:
        macro_deviation_percent = get_deviation_percent(actual[macro], target[macro])
        if macro_deviation_percent > 15:
            penalty_macro = (macro_deviation_percent - 15) * 0.2
            score -= penalty_macro

    # --- Граничные условия ---
    score = max(0.0, score)  # Минимальный Score: 0
    score = min(120.0, score) # Максимальный Score: 120

    # Округляем итоговый Score до целого числа
    final_score = round(score)

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
        "y_axis_pos": final_score, # y_axis_pos равен daily_score для рендеринга
        "achievements": achievements
    }