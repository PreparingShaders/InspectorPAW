import datetime
import pytest
from app.utils import calculate_progress_lab_score


def test_achieve_overdrive_score_at_end_of_day():
    """
    Проверяет, что при выполнении условий "Бонуса за белок" в конце дня,
    итоговый score будет больше 105 (Overdrive).
    """
    # 1. Задаем цели
    target = {
        "calories": 2500, 
        "protein": 180, 
        "fat": 80, 
        "carbohydrates": 265
    }

    # 2. Подбираем "идеальные" фактические данные для бонуса
    actual = {
        "calories": 2600,      # Чуть больше нормы, но в пределах 5%
        "protein": 200,        # Значительно БОЛЬШЕ нормы (180г) -> активирует бонус
        "fat": 80,             # Точно в цель
        "carbohydrates": 270   # Близко к цели
    }

    # 3. "Обманываем" функцию, говоря ей, что сейчас конец дня
    fake_end_of_day = datetime.datetime(2023, 1, 1, 23, 0)

    # 4. Вызываем функцию с поддельным временем
    result = calculate_progress_lab_score(target, actual, current_dt=fake_end_of_day)
    # ...
    result = calculate_progress_lab_score(target, actual, current_dt=fake_end_of_day)

    print(f"\nDEBUG RESULT: {result}")  # Добавьте это

    assert result["daily_score"] > 105
    # 5. Проверяем, что мы получили "Overdrive"
    assert result["daily_score"] > 105
    assert result["status_color"] == "#FFD700" # Золотой цвет
    assert result["status_message"] == "Идеальный темп!"
