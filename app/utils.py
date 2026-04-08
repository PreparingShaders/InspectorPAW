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


def calculate_progress_lab_score(target: Dict[str, float], actual: Dict[str, float], current_dt: Optional[datetime.datetime] = None) -> Dict[str, Any]:
    """
    Рассчитывает динамический Индекс Дисциплины (Score) для ProgressLab.
    Учитывает время (05:00 - 23:00) и баланс нутриентов.
    """

    # 1. Настройка временного окна (18 часов мониторинга) / Setup time window (18 hours of monitoring)
    now = current_dt if current_dt else datetime.datetime.now()
    current_time = now.hour + now.minute / 60
    start_h, end_h = 5.0, 23.0  # Monitoring window from 5 AM to 11 PM.

    # Calculate the fraction of the monitoring window that has passed.
    if current_time <= start_h:
        time_factor = 0.05  # Before the window starts, use a small minimum to avoid zero division.
    elif current_time >= end_h:
        time_factor = 1.0   # After the window ends, it's considered fully complete.
    else:
        # Linearly interpolate the time progress within the window.
        time_factor = (current_time - start_h) / (end_h - start_h)

    # If there is no consumption data for the day, return a default "no data" state.
    if not any(actual.values()):
        return {
            "daily_score": 0,
            "status_color": "#000000",
            "status_message": "Нет данных за сегодня",
            "y_axis_pos": 0,
            "time_progress": round(time_factor * 100, 1)
        }

    # 2. Параметры и веса (Parameters and Weights)
    total_score = 0.0
    # Define the weight of each macronutrient in the final score calculation.
    weights = {
        'calories': 40,
        'protein': 30,
        'fat': 15,
        'carbohydrates': 15
    }

    # A tolerance threshold allows consuming up to 30% of the daily target at any time
    # without being penalized for being "ahead of schedule". This accommodates for breakfast.
    tolerance_threshold = 0.3

    status_notes = []  # Not used in the current implementation.
    recommendations = []  # A list to collect dynamic feedback for the user.

    # Iterate over each nutrient to calculate its contribution to the total score.
    for param, max_weight in weights.items():
        t_val = target[param]  # Target value for the nutrient.
        a_val = actual[param]  # Actual consumed value for the nutrient.

        # Calculate the expected consumption at the current time of day.
        # It's the higher of the time-based expectation or the 30% tolerance threshold.
        expected_now = t_val * max(time_factor, tolerance_threshold)

        # Ratio of actual consumption to the expected consumption at this time.
        ratio = a_val / expected_now if expected_now > 0 else 1.0
        
        # Ratio of actual consumption to the total daily target.
        day_ratio = a_val / t_val if t_val > 0 else 0

        # --- Scoring Logic ---
        if ratio <= 1.2:
            # On track or slightly ahead (within a 20% buffer).
            # If falling significantly behind (ratio < 0.8), the score is reduced proportionally.
            param_score = max_weight if ratio >= 0.8 else max_weight * (a_val / (t_val * time_factor + 1e-6))
            
            # Add recommendations if user is falling behind schedule.
            if ratio < 0.8 and time_factor > 0.1:  # Check for under-consumption after the day has started.
                if param == 'calories':
                    recommendations.append("Недобор калорий. Пора перекусить!")
                elif param == 'protein':
                    recommendations.append("Недобор белка. Уделите внимание белковой пище.")
                elif param == 'fat':
                    recommendations.append("Недобор жиров. Добавьте полезные жиры.")
                elif param == 'carbohydrates':
                    recommendations.append("Недобор углеводов. Добавьте сложные углеводы.")
        else:
            # Penalty for being too far ahead of schedule (aggressive over-consumption).
            overage = ratio - 1.2
            param_score = max(0, max_weight - (overage * 30))  # Apply a softened penalty.
            
            # Add recommendations if user is significantly over-consuming relative to the time.
            if overage > 0.2:
                if param == 'calories':
                    recommendations.append("Перебор калорий по графику. Сократите порции.")
                elif param == 'protein':
                    recommendations.append("Перебор белка по графику. Распределите приемы.")
                elif param == 'fat':
                    recommendations.append("Перебор жиров по графику. Будьте внимательнее.")
                elif param == 'carbohydrates':
                    recommendations.append("Перебор углеводов по графику. Выбирайте сложные.")


        # Global penalty for exceeding the total 100% daily limit for any nutrient.
        if a_val > t_val:
            day_over_ratio = (a_val / t_val) - 1.0
            param_score -= day_over_ratio * 100  # Heavy penalty for going over the daily target.
            if day_over_ratio > 0.05:  # If daily target is exceeded by more than 5%.
                if param == 'calories':
                    recommendations.append("Дневной лимит калорий превышен!")
                elif param == 'protein':
                    recommendations.append("Дневной лимит белка превышен!")
                elif param == 'fat':
                    recommendations.append("Дневной лимит жиров превышен!")
                elif param == 'carbohydrates':
                    recommendations.append("Дневной лимит углеводов превышен!")


        total_score += max(0, param_score)

    # 3. Бонус Белка (Protein Overdrive Bonus)
    # Award up to 20 bonus points for exceeding protein target while keeping calories in check.
    # This incentivizes a high-protein diet, which is often beneficial.
    if actual['protein'] > target['protein'] and actual['calories'] <= target['calories'] * 1.05:
        protein_extra = min((actual['protein'] / target['protein'] - 1.0) * 20, 20)
        total_score += protein_extra

    # Finalize the score, clamping it between 0 and a max of 120 (to account for bonuses).
    final_score = round(max(0, min(total_score, 120)))

    # 4. Цветовая палитра и Статус-сообщения (Color Palette and Status Messages)
    color = "#e11d48"  # Default to red (Fail).
    status_text = "Требуется корректировка плана."  # Default Fail message.

    # Determine status color and text based on the final score.
    if final_score > 105:
        color, status_text = "#10b981", "Overdrive: Максимальная эффективность"
    elif 95 <= final_score <= 105:
        color, status_text = "#FFD700", "Golden Standard: Идеальный темп"
    elif 80 <= final_score <= 94:
        color, status_text = "#f59e0b", "Warning: Есть отклонения от графика"
    else:  # final_score < 80
        # If specific recommendations were generated, use them as the status message.
        if recommendations:
            status_text = " ".join(list(set(recommendations)))  # Join unique recommendations.
        else:
            status_text = "Fail: Требуется корректировка плана."  # Fallback message.

    # Special case for a "heavy start" in the morning.
    # If the score is low early in the day, provide a more forgiving message.
    if time_factor < 0.4 and final_score < 80 and not recommendations:
        status_text = "Плотный старт! Score выровняется сам, если не перекусывать до обеда."
        color = "#f59e0b"  # Use a warning color instead of fail red.

    return {
        "daily_score": final_score,
        "status_color": color,
        "status_message": status_text,
        "y_axis_pos": final_score,  # Y-coordinate for the circle on the graph.
        "time_progress": round(time_factor * 100, 1)
    }