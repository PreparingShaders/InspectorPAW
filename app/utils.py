from datetime import date
from typing import Optional
from . import models

def calculate_user_targets(user: models.User, latest_weight_kg: Optional[float]):
    """
    Рассчитывает целевые КБЖУ для пользователя на основе его профиля и цели.
    Использует формулу Харриса-Бенедикта для BMR.
    """
    # --- 1. Рассчитать BMR (Basal Metabolic Rate) ---
    bmr = 0
    if user.date_of_birth and latest_weight_kg and user.height_cm and user.gender:
        age = (date.today() - user.date_of_birth).days / 365.25
        if user.gender == 'male':
            bmr = 88.362 + (13.397 * latest_weight_kg) + (4.799 * user.height_cm) - (5.677 * age)
        elif user.gender == 'female':
            bmr = 447.593 + (9.247 * latest_weight_kg) + (3.098 * user.height_cm) - (4.330 * age)

    # Если BMR не рассчитан, используем значение по умолчанию.
    # Это не идеально, но лучше, чем ничего.
    if bmr <= 0:
        bmr = 2000

    # --- 2. Применить цель пользователя ---
    # Пока используем простой множитель. В будущем можно добавить TDEE (Total Daily Energy Expenditure)
    target_calories = bmr

    if user.goal == 'fat_loss':
        # Уменьшаем калории на 15-25% в зависимости от интенсивности
        adjustment = 0.85 - (user.goal_intensity * 0.10) if user.goal_intensity else 0.85
        target_calories *= adjustment
    elif user.goal == 'mass_gain':
        # Увеличиваем калории на 15-25%
        adjustment = 1.15 + (user.goal_intensity * 0.10) if user.goal_intensity else 1.15
        target_calories *= adjustment

    # --- 3. Рассчитать макронутриенты ---
    # Пропорции: 30% белки, 30% жиры, 40% углеводы.
    # 1г белка = 4 ккал, 1г жира = 9 ккал, 1г углевода = 4 ккал.
    target_protein = (target_calories * 0.30) / 4
    target_fat = (target_calories * 0.30) / 9
    target_carbohydrates = (target_calories * 0.40) / 4

    return {
        "target_calories": round(target_calories),
        "target_protein": round(target_protein),
        "target_fat": round(target_fat),
        "target_carbohydrates": round(target_carbohydrates)
    }
