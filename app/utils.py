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


def calculate_progress_lab_score(target: Dict[str, float], actual: Dict[str, float], current_dt: Optional[datetime.datetime] = None) -> Dict[str, Any]:
    """
    Рассчитывает динамический Индекс Дисциплины (Score) для ProgressLab.
    Учитывает время (05:00 - 23:00) и баланс нутриентов.
    """

    # 1. Настройка временного окна (18 часов мониторинга)
    now = current_dt if current_dt else datetime.datetime.now()
    current_time = now.hour + now.minute / 60
    start_h, end_h = 5.0, 23.0

    if current_time <= start_h:
        time_factor = 0.05  # Минимальный порог
    elif current_time >= end_h:
        time_factor = 1.0
    else:
        time_factor = (current_time - start_h) / (end_h - start_h)

    # 2. Параметры и веса
    total_score = 0.0
    weights = {
        'calories': 40,
        'protein': 30,
        'fat': 15,
        'carbohydrates': 15
    }

    # Буфер лояльности: разрешаем съесть до 30% нормы в любое время без штрафа за скорость
    tolerance_threshold = 0.3

    status_notes = []
    recommendations = [] # Список для сбора рекомендаций

    for param, max_weight in weights.items():
        t_val = target[param]
        a_val = actual[param]

        # Ожидание с учетом "смягчения" для завтрака
        expected_now = t_val * max(time_factor, tolerance_threshold)

        # Текущее соотношение относительно времени
        ratio = a_val / expected_now if expected_now > 0 else 1.0
        
        # Соотношение относительно дневной цели
        day_ratio = a_val / t_val if t_val > 0 else 0

        # Логика начисления баллов
        if ratio <= 1.2:
            # Идем в графике или чуть впереди (коридор нормы)
            # Если сильно отстаем от времени (ratio < 0.8), балл снижается пропорционально
            param_score = max_weight if ratio >= 0.8 else max_weight * (a_val / (t_val * time_factor + 1e-6))
            
            # Добавляем рекомендации для недобора
            if ratio < 0.8 and time_factor > 0.1: # Недобор, если уже не самое начало дня
                if param == 'calories':
                    recommendations.append("Недобор калорий. Пора перекусить!")
                elif param == 'protein':
                    recommendations.append("Недобор белка. Уделите внимание белковой пище.")
                elif param == 'fat':
                    recommendations.append("Недобор жиров. Добавьте полезные жиры.")
                elif param == 'carbohydrates':
                    recommendations.append("Недобор углеводов. Добавьте сложные углеводы.")
        else:
            # Штраф за агрессивный перебор относительно времени (жизнь в долг)
            overage = ratio - 1.2
            param_score = max(0, max_weight - (overage * 30))  # Смягченный коэфф. штрафа
            
            # Добавляем рекомендации для перебора
            if overage > 0.2: # Значительный перебор относительно графика
                if param == 'calories':
                    recommendations.append("Перебор калорий по графику. Сократите порции.")
                elif param == 'protein':
                    recommendations.append("Перебор белка по графику. Распределите приемы.")
                elif param == 'fat':
                    recommendations.append("Перебор жиров по графику. Будьте внимательнее.")
                elif param == 'carbohydrates':
                    recommendations.append("Перебор углеводов по графику. Выбирайте сложные.")


        # Глобальный штраф за превышение 100% дневного лимита
        if a_val > t_val:
            day_over_ratio = (a_val / t_val) - 1.0
            param_score -= day_over_ratio * 100
            if day_over_ratio > 0.05: # Если превышение дневной цели более чем на 5%
                if param == 'calories':
                    recommendations.append("Дневной лимит калорий превышен!")
                elif param == 'protein':
                    recommendations.append("Дневной лимит белка превышен!")
                elif param == 'fat':
                    recommendations.append("Дневной лимит жиров превышен!")
                elif param == 'carbohydrates':
                    recommendations.append("Дневной лимит углеводов превышен!")


        total_score += max(0, param_score)

    # 3. Бонус Белка (Overdrive)
    # Даем до +20 баллов, если белок > 100%, а калории в норме
    if actual['protein'] > target['protein'] and actual['calories'] <= target['calories'] * 1.05:
        protein_extra = min((actual['protein'] / target['protein'] - 1.0) * 20, 20)
        total_score += protein_extra

    # Финализация значения (0 - 120)
    final_score = round(max(0, min(total_score, 120)))

    # 4. Цветовая палитра и Статус-сообщения
    color = "#e11d48" # Default to red (Fail)
    status_text = "Требуется корректировка плана." # Default Fail message

    if final_score > 105:
        color, status_text = "#10b981", "Overdrive: Максимальная эффективность"
    elif 95 <= final_score <= 105:
        color, status_text = "#ffffff", "Golden Standard: Идеальный темп"
    elif 80 <= final_score <= 94:
        color, status_text = "#f59e0b", "Warning: Есть отклонения от графика"
    else: # final_score < 80
        # Если есть конкретные рекомендации, используем их
        if recommendations:
            status_text = " ".join(list(set(recommendations))) # Удаляем дубликаты и объединяем
        else:
            status_text = "Fail: Требуется корректировка плана." # Fallback если нет конкретных рекомендаций

    # Специфическая подсказка для утреннего перебора
    if time_factor < 0.4 and final_score < 80 and not recommendations: # Если нет других конкретных рекомендаций
        status_text = "Плотный старт! Score выровняется сам, если не перекусывать до обеда."
        color = "#f59e0b" # Устанавливаем оранжевый цвет для этого предупреждения

    return {
        "daily_score": final_score,
        "status_color": color,
        "status_message": status_text,
        "y_axis_pos": final_score,  # Координата для круга на графике
        "time_progress": round(time_factor * 100, 1)
    }