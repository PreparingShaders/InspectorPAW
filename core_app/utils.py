from datetime import datetime
from typing import Optional, Dict, Any, List
import datetime
import asyncio
import random
import string
from fastapi import HTTPException
from openai import AsyncOpenAI
from . import models
from .config import settings
from . import auth, crud
from sqlalchemy.orm import Session
from .models import User
import httpx # Убедимся, что httpx импортирован

def generate_verification_code(length: int = 6) -> str:
    """Генерирует случайный числовой код указанной длины."""
    return "".join(random.choices(string.digits, k=length))

async def send_verification_email(to_email: str, code: str):
    """
    Отправляет email с кодом верификации через Brevo.
    """
    subject = "Код подтверждения регистрации в ProgressLAB"
    html_content = f"""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Код подтверждения</title>
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #121212; color: #E0E0E0; margin: 0; padding: 0;">
        <div style="max-width: 600px; margin: 40px auto; padding: 20px; background-color: #1E1E1E; border-radius: 12px; border: 1px solid #333; box-shadow: 0 0 25px rgba(255, 255, 255, 0.1);">
            <div style="text-align: center; padding-bottom: 20px; border-bottom: 1px solid #333;">
                <h1 style="margin: 0; font-size: 28px; color: #FFFFFF; text-shadow: 0 0 10px rgba(255, 255, 255, 0.5), 0 0 20px rgba(255, 255, 255, 0.5);">ProgressLAB</h1>
            </div>
            <div style="padding: 20px 0; text-align: center; line-height: 1.6; color: #E0E0E0;">
                <p>Добро пожаловать! Для завершения регистрации введите этот код:</p>
                <div style="display: inline-block; margin: 20px 0; padding: 15px 30px; font-size: 36px; font-weight: bold; letter-spacing: 5px; color: #121212; background-color: #FFFFFF; border-radius: 8px; box-shadow: 0 0 15px rgba(255, 255, 255, 0.5);">{code}</div>
                <p>Этот код действителен в течение 15 минут.</p>
                <p>Если вы не запрашивали регистрацию, просто проигнорируйте это письмо.</p>
            </div>
            <div style="text-align: center; padding-top: 20px; border-top: 1px solid #333; font-size: 12px; color: #777;">
                <p>&copy; {datetime.datetime.now().year} ProgressLAB. Все права защищены.</p>
            </div>
        </div>
    </body>
    </html>
    """
    await send_email_brevo(to_email=to_email, subject=subject, html_content=html_content)

async def send_password_reset_email(to_email: str, code: str):
    """
    Отправляет email с кодом сброса пароля через Brevo.
    """
    subject = "Код для сброса пароля в ProgressLAB"
    html_content = f"""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Сброс пароля</title>
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #121212; color: #E0E0E0; margin: 0; padding: 0;">
        <div style="max-width: 600px; margin: 40px auto; padding: 20px; background-color: #1E1E1E; border-radius: 12px; border: 1px solid #333; box-shadow: 0 0 25px rgba(255, 255, 255, 0.1);">
            <div style="text-align: center; padding-bottom: 20px; border-bottom: 1px solid #333;">
                <h1 style="margin: 0; font-size: 28px; color: #FFFFFF; text-shadow: 0 0 10px rgba(255, 255, 255, 0.5), 0 0 20px rgba(255, 255, 255, 0.5);">ProgressLAB</h1>
            </div>
            <div style="padding: 20px 0; text-align: center; line-height: 1.6; color: #E0E0E0;">
                <p>Вы запросили сброс пароля. Используйте этот код для продолжения:</p>
                <div style="display: inline-block; margin: 20px 0; padding: 15px 30px; font-size: 36px; font-weight: bold; letter-spacing: 5px; color: #121212; background-color: #FFFFFF; border-radius: 8px; box-shadow: 0 0 15px rgba(255, 255, 255, 0.5);">{code}</div>
                <p>Этот код действителен в течение 15 минут.</p>
                <p>Если вы не запрашивали сброс пароля, просто проигнорируйте это письмо.</p>
            </div>
            <div style="text-align: center; padding-top: 20px; border-top: 1px solid #333; font-size: 12px; color: #777;">
                <p>&copy; {datetime.datetime.now().year} ProgressLAB. Все права защищены.</p>
            </div>
        </div>
    </body>
    </html>
    """
    await send_email_brevo(to_email=to_email, subject=subject, html_content=html_content)


async def send_email_brevo(
    to_email: str,
    subject: str,
    html_content: str,
    sender_name: str = "ProgressLAB",
    sender_email: str = "classname1984@gmail.com"
):
    """
    Отправляет email через Brevo API.
    """
    if not settings.BREVO_API_KEY:
        print("BREVO_API_KEY не установлен. Отправка email пропущена.")
        return

    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "accept": "application/json",
        "api-key": settings.BREVO_API_KEY,
        "content-type": "application/json"
    }
    payload = {
        "sender": {"name": sender_name, "email": sender_email},
        "to": [{"email": to_email}],
        "subject": subject,
        "htmlContent": html_content
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            print(f"Email успешно отправлен на {to_email}. Brevo Response: {response.json()}")
    except httpx.HTTPStatusError as e:
        print(f"Ошибка HTTP при отправке email через Brevo: {e.response.status_code} - {e.response.text}")
        raise HTTPException(status_code=500, detail=f"Ошибка при отправке email: {e.response.text}")
    except httpx.RequestError as e:
        print(f"Ошибка запроса при отправке email через Brevo: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка сети при отправке email: {e}")
    except Exception as e:
        print(f"Неизвестная ошибка при отправке email через Brevo: {e}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера при отправке email: {e}")


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
    Собирает данные в компактный JSON с детальной разбивкой остатков по БЖУ.
    """
    now = datetime.datetime.now()
    user_targets = calculate_user_targets(user, latest_weight_kg, latest_body_fat_percentage)

    # Вычисляем остатки (дельта) для каждого макронутриента
    def get_remaining(nutrient: str):
        target = user_targets.get(f"target_{nutrient}", 0)
        actual = consumed_today.get(nutrient, 0)
        return max(0, round(target - actual))

    remaining = {
        "calories": get_remaining("calories"),
        "protein": get_remaining("protein"),
        "fat": get_remaining("fat"),
        "carbohydrates": get_remaining("carbohydrates")
    }

    # Подтягиваем оценку опасности из существующей логики
    progress_metrics = calculate_progress_lab_score(
        target=user_targets,
        actual=consumed_today,
        current_dt=now
    )

    # Формирование контекста
    context = {
        "user_profile": {
            "gender": user.gender,
            "age": (date.today().year - user.date_of_birth.year) if user.date_of_birth else None,
            "height_cm": user.height_cm,
            "weight_kg": latest_weight_kg,
            "goal": user.goal,
        },
        "daily_stats": {
            "time_now": now.strftime("%Y-%m-%d %H:%M"),
            "targets": user_targets,
            "already_consumed": consumed_today,
            "daily_score": progress_metrics.get("daily_score") # Добавляем daily_score
        },
        "proposed_meal": analyzed_meal,
        "progress_assessment": {
            "remaining_macros": remaining, # Теперь здесь полный расклад по БЖУ
            "danger_status": progress_metrics.get("danger_status"),
            "probability_of_success": progress_metrics.get("probability_of_success")
        },
        "meta": {"monitoring_window": "05:00-23:50"}
    }

    return context


from datetime import date
from typing import Optional, Dict


def calculate_user_targets(
        user: models.User,
        latest_weight_kg: Optional[float],
        latest_body_fat_percentage: Optional[float]
) -> Dict[str, int]:
    """
    Рассчитывает целевые КБЖУ по продвинутому алгоритму с защитой от экстремальных значений.
    """
    if not latest_weight_kg or latest_weight_kg <= 0:
        return {"target_calories": 0, "target_protein": 0, "target_fat": 0, "target_carbohydrates": 0}

    bmr = 0
    lean_body_mass: Optional[float] = None

    # 1. Расчет BMR
    if latest_body_fat_percentage and latest_body_fat_percentage > 0:
        lean_body_mass = latest_weight_kg * (1 - (latest_body_fat_percentage / 100))
        bmr = 370 + (21.6 * lean_body_mass)
    elif user.date_of_birth and user.height_cm and user.gender:
        age = (date.today() - user.date_of_birth).days / 365.25
        if user.gender == 'male':
            bmr = (10 * latest_weight_kg) + (6.25 * user.height_cm) - (5 * age) + 5
        elif user.gender == 'female':
            bmr = (10 * latest_weight_kg) + (6.25 * user.height_cm) - (5 * age) - 161

    if bmr <= 0:
        bmr = 1800

    # 2. Расчет TDEE
    activity_multipliers = {
        'sedentary': 1.2, 'light': 1.375, 'moderate': 1.55,
        'active': 1.725, 'very_active': 1.9
    }
    multiplier = activity_multipliers.get(user.activity_level, 1.2)
    tdee = bmr * multiplier

    # 3. Корректировка калорий под цель (с безопасными лимитами)
    # goal_intensity теперь в диапазоне от -3 до +3
    intensity_scaled = (float(user.goal_intensity) + 3) / 6 # Масштабируем -3..+3 в 0.0..1.0

    if user.goal == 'fat_loss':
        # Дефицит от 5% (intensity_scaled=0) до 25% (intensity_scaled=1)
        pct_decrease = 0.05 + (intensity_scaled * 0.20) # 0.20 = 0.25 - 0.05
        target_calories = tdee * (1.0 - pct_decrease)
        # Страховка: не опускаем калории ниже BMR без жесткой необходимости
        if target_calories < bmr:
            target_calories = bmr
    elif user.goal == 'mass_gain':
        # Профицит от 2% (intensity_scaled=0) до 15% (intensity_scaled=1)
        pct_increase = 0.02 + (intensity_scaled * 0.13) # 0.13 = 0.15 - 0.02
        target_calories = tdee * (1.0 + pct_increase)
    else:
        target_calories = tdee

    # 4. Расчет БЖУ с поправкой на состав тела (LBM)
    # Если знаем LBM, считаем от нее (более точно), если нет — от общего веса
    if lean_body_mass:
        target_protein = 2.3 * lean_body_mass  # Около 2.3г на сухую массу
        target_fat = 1.0 * lean_body_mass  # Около 1.0г на сухую массу
    else:
        # Защита от овер-трансляции макросов на избыточный вес
        # Ограничиваем расчетный вес, если у пользователя ожирение (для расчета БЖУ)
        base_weight = latest_weight_kg
        target_protein = 2.0 * base_weight
        target_fat = 1.0 * base_weight

    # Минимальный порог углеводов для нормальной работы мозга и тренировок (хотя бы 1.5г на кг)
    min_carbs = 1.5 * (lean_body_mass if lean_body_mass else latest_weight_kg)

    # Считаем остаток калорий
    current_macros_calories = (target_protein * 4) + (target_fat * 9)
    remaining_calories = target_calories - current_macros_calories

    if remaining_calories < (min_carbs * 4):
        # Если калорий не хватает на минимальные углеводы, аккуратно поджимаем жиры (но не ниже 0.7г/кг)
        min_fat_allowed = 0.7 * (lean_body_mass if lean_body_mass else latest_weight_kg)
        if target_fat > min_fat_allowed:
            # Высвобождаем калории из жиров в пользу углеводов
            fat_pool = (target_fat - min_fat_allowed) * 9
            target_fat = min_fat_allowed
            remaining_calories += fat_pool

        # Пересчитываем углеводы по остаточному принципу
        target_carbohydrates = max(20.0, remaining_calories / 4)  # Финальный пол — 20г (кето-минимум)
    else:
        target_carbohydrates = remaining_calories / 4

    return {
        "target_calories": round(target_calories),
        "target_protein": round(target_protein),
        "target_fat": round(target_fat),
        "target_carbohydrates": round(target_carbohydrates),
        "target_fiber": 25  # Стандартная рекомендация для взрослых
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

def get_nutrient_tooltips(target: Dict, actual: Dict, time_factor: float, recommendations: Optional[Dict] = None, coach_advice: Optional[str] = None) -> Dict[str, str]:
    if recommendations is None:
        recommendations = {}
    
    default_daily_score_advice = "Оценка показывает, насколько равномерно вы идете к цели в течение дня. Переборы по калориям, жирам и углеводам срезают баллы, а вот выполнение нормы по белку — наоборот, поощряется бонусами. Чтобы набрать максимум, старайтесь избегать резких скачков и питайтесь равномерно в течении дня.\nМаксимум 120 баллов."

    return {
        "daily_score": coach_advice or recommendations.get("daily_score", default_daily_score_advice),
        "calories": recommendations.get("calories", _generate_nutrient_tooltip(target.get('calories', 0), actual.get('calories', 0), time_factor, "Калории", "ккал")),
        "protein": recommendations.get("protein", _generate_nutrient_tooltip(target.get('protein', 0), actual.get('protein', 0), time_factor, "Белки", "г")),
        "fat": recommendations.get("fat", _generate_nutrient_tooltip(target.get('fat', 0), actual.get('fat', 0), time_factor, "Жиры", "г")),
        "carbohydrates": recommendations.get("carbohydrates", _generate_nutrient_tooltip(target.get('carbohydrates', 0), actual.get('carbohydrates', 0), time_factor, "Углеводы", "г"))
    }

def calculate_progress_lab_score(target: Dict[str, float], actual: Dict[str, float], current_dt: Optional[datetime.datetime] = None, recommendations: Optional[Dict] = None, coach_advice: Optional[str] = None) -> Dict[str, Any]:
    now = current_dt if current_dt else datetime.datetime.now(settings.MSK_TZ)
    current_time = now.hour + now.minute / 60
    start_h, end_h = 5.0, 23.0
    time_factor = max(0.05, min(1.0, (current_time - start_h) / (end_h - start_h)))

    macros_pace = {}
    for key in ['calories', 'protein', 'fat', 'carbohydrates']:
        t_val = target.get(key, 0)
        a_val = actual.get(key, 0)
        expected = t_val * time_factor
        macros_pace[key] = {'actual': a_val, 'expected': expected, 'target': t_val}

    tooltips = get_nutrient_tooltips(target, actual, time_factor, recommendations, coach_advice)

    pace_recommendation = {
        "macros_pace": macros_pace,
        "formatted_time": now.strftime("%H:%M"),
        "tooltips": tooltips
    }

    if not any(actual.values()):
        return {
            "daily_score": 0, "status_color": "#5A6978",
            "status_message": {"calories": "Нет данных", "protein": "Нет данных", "fat": "Нет данных", "carbohydrates": "Нет данных"},
            "y_axis_pos": 0, "time_progress": round(time_factor * 100, 1),
            "target_delta": {key: round(target.get(key, 0)) for key in ['calories', 'protein', 'fat', 'carbohydrates']},
            "nutrient_statuses": {"calories": "OK", "protein": "OK", "fat": "OK", "carbohydrates": "OK"},
            "probability_of_success": 100,
            "danger_status": False,
            "pace_recommendation": pace_recommendation,
        }

    total_score = 0.0
    weights = {'calories': 40, 'protein': 30, 'fat': 15, 'carbohydrates': 15}
    tolerance_threshold = 0.3
    for param, max_weight in weights.items():
        t_val = target.get(param, 0)
        a_val = actual.get(param, 0)
        if t_val == 0: continue
        expected_now = t_val * max(max(time_factor, tolerance_threshold), 0.1)
        ratio = a_val / expected_now if expected_now > 0 else 1.0
        param_score = max_weight
        if ratio < 0.8: param_score *= (a_val / (t_val * time_factor + 1e-6))
        elif ratio > 1.2 and param != 'protein': param_score -= (ratio - 1.2) * 30
        if a_val > t_val and param != 'protein': param_score -= ((a_val / t_val) - 1.0) * 100
        total_score += max(0, param_score)

    final_score = total_score
    day_calorie_ratio = actual.get('calories', 0) / (target.get('calories', 1) + 1e-6)
    
    # Более гибкий расчет на основе выполнения цели по калориям
    if day_calorie_ratio < 1.0:
        # Штраф за недобор, но не слишком сильный
        final_score *= (1 - (1 - day_calorie_ratio) * 0.2)
    else:
        # Более сильный штраф за перебор
        final_score *= (1 - (day_calorie_ratio - 1) * 0.5)

    day_fat_ratio = actual.get('fat', 0) / (target.get('fat', 1) + 1e-6)
    day_carbs_ratio = actual.get('carbohydrates', 0) / (target.get('carbohydrates', 1) + 1e-6)
    if day_fat_ratio > 1.15: final_score -= 10
    if day_carbs_ratio < 0.85: final_score -= 5


    if actual.get('protein', 0) > target.get('protein', 0) and actual.get('calories', 0) <= target.get('calories', 1) * 1.05:
        bonus = (actual.get('protein', 0) / (target.get('protein', 1) + 1e-6) - 1.0) * 50
        final_score += min(bonus, 20)

    final_score = round(max(0, min(final_score, 120)))
    color = "#e11d48"
    if final_score > 105: color = "#FFD700"
    elif 95 <= final_score <= 105: color = "#F0F0F0"
    elif 80 <= final_score <= 94: color = "#f59e0b"
    
    status_tooltips = get_nutrient_tooltips(target, actual, time_factor, recommendations, coach_advice)

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
        if ratio > 1.10 and key != 'protein':
            nutrient_statuses[key] = "CRITICAL_LIMIT"
        elif ratio > 0.95 and key != 'protein':
            nutrient_statuses[key] = "WARNING"
        else:
            nutrient_statuses[key] = "OK"

    danger_status = False
    if nutrient_statuses['fat'] == "CRITICAL_LIMIT" or nutrient_statuses['calories'] == "CRITICAL_LIMIT":
        danger_status = True
    if current_time < 12.0 and (actual.get('fat', 0) / (target.get('fat', 1) + 1e-6)) > 0.9:
        danger_status = True
    if current_time < 18.0 and (actual.get('calories', 0) / (target.get('calories', 1) + 1e-6)) > 0.95:
        danger_status = True

    probability_of_success = min(100, final_score)
    remaining_time_factor = 1.0 - time_factor
    
    if danger_status:
        probability_of_success = min(probability_of_success, 40)
    elif remaining_time_factor < 0.2 and target_delta['calories'] > target.get('calories', 1) * 0.3:
        probability_of_success = min(probability_of_success, 30)
    elif target_delta['fat'] < 10 and remaining_time_factor > 0.25:
        probability_of_success = min(probability_of_success, 60)

    probability_of_success = round(max(0, probability_of_success))

    return {
        "daily_score": final_score,
        "status_color": color,
        "status_message": status_tooltips,
        "y_axis_pos": final_score,
        "time_progress": round(time_factor * 100, 1),
        "target_delta": target_delta,
        "nutrient_statuses": nutrient_statuses,
        "probability_of_success": probability_of_success,
        "danger_status": danger_status,
        "pace_recommendation": pace_recommendation,
    }

def get_user_features(user: User, db: Session) -> dict:
    """
    Возвращает словарь с флагами доступных пользователю функций.
    """
    is_premium = auth.is_premium_user(user)

    # Ограничение на чат
    can_use_ai_chat = is_premium

    # Ограничение на анализ еды
    can_analyze_meal = False
    if is_premium:
        can_analyze_meal = True
    else:
        meals_today = crud.count_meals_today(db, user_id=user.id)
        if meals_today < 5:
            can_analyze_meal = True
            
    return {
        "is_premium": is_premium,
        "can_use_ai_chat": can_use_ai_chat,
        "can_analyze_meal": can_analyze_meal,
    }