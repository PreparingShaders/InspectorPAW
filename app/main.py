from datetime import timedelta, date, datetime
from typing import List, Optional
import re
import io
import base64
import asyncio
import requests
from contextlib import asynccontextmanager
import google.genai as genai
from openai import AsyncOpenAI
from PIL import Image
import json

from datetime import timedelta, date, datetime, timezone
from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form, Response, Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from . import crud, models, schemas, auth, utils
from .database import SessionLocal, engine
from .config import settings, Settings

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="InspectorPAW API")

# Монтируем статическую директорию
app.mount("/static", StaticFiles(directory="static"), name="static")

# Настраиваем шаблонизатор
templates = Jinja2Templates(directory="templates")

# --- API Клиенты ---
gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
open_router_client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=settings.OPEN_ROUTER_API_KEY,
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- Веб-страницы ---
@app.get("/")
async def read_login_page(request: Request):
    return templates.TemplateResponse(name="login.html", request=request)


@app.get("/dashboard")
async def read_dashboard_page(request: Request):
    return templates.TemplateResponse(name="index.html", request=request)


@app.get("/profile")
async def read_profile_page(request: Request):
    return templates.TemplateResponse(name="profile.html", request=request)


@app.get("/nutrition")
async def read_nutrition_page(request: Request):
    return templates.TemplateResponse(name="nutrition.html", request=request)


@app.get("/ai-hub")
async def read_ai_hub_page(request: Request):
    return templates.TemplateResponse(name="ai_hub.html", request=request)


# --- AI Логика ---
@app.post("/ai-hub/chat")
async def ai_hub_chat(chat_request: schemas.AIChatRequest, current_user: models.User = Depends(auth.get_current_user)):
    messages = []
    for message in chat_request.history:
        role = "assistant" if message['sender'] == 'ai' else 'user'
        messages.append({"role": role, "content": message['text']})
    messages.append({"role": "user", "content": chat_request.prompt})

    try:
        chat_completion = await open_router_client.chat.completions.create(
            model=chat_request.model,
            messages=messages,
        )
        response_text = chat_completion.choices[0].message.content
        return {"response": response_text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/ai-hub/get-models", response_model=List[schemas.AIModel])
async def get_models():
    try:
        return settings.ALL_AVAILABLE_AI_MODELS
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Не удалось получить список моделей: {e}")


async def get_nutrition_analysis_and_advice(
    file_content: Optional[bytes],
    description: Optional[str],
    ai_context: dict,
    model_to_use: str
) -> (dict, str):
    """
    Выполняет анализ питания и дает совет одним запросом к AI, используя конкретную модель.
    """
    context_str = json.dumps(ai_context, indent=2, ensure_ascii=False)

    prompt = f"""
    Ты — интегрированный ассистент по питанию, сочетающий в себе две роли:
    1.  **Эксперт-нутрициолог:** Ты точно анализируешь еду (по фото или описанию) и рассчитываешь её КБЖУ.
    2.  **Элитный коуч:** Ты даешь прямой, честный и мотивирующий совет, помогая пользователю достичь цели.

    ### ЗАДАЧА:
    Проанализируй предоставленные данные (фото и/или описание еды) и полный контекст дня пользователя.
    Верни **ТОЛЬКО ОДИН JSON-ОБЪЕКТ** без лишнего текста, пояснений и Markdown-разметки.

    ### КОНТЕКСТ ДНЯ ПОЛЬЗОВАТЕЛЯ:
    ```json
    {context_str}
    ```

    ### ПРАВИЛА РАСЧЕТА КБЖУ:
    1.  Определи вес (weight_g), белки (proteins_g), жиры (fats_g) и углеводы (carbs_g).
    2.  Итоговые калории (calories) **ОБЯЗАТЕЛЬНО** рассчитай строго по формуле: `calories = (proteins_g * 4) + (carbs_g * 4) + (fats_g * 9)`.
    3.  Округляй все числовые значения до целых.

    ### ПРАВИЛА ДЛЯ СОВЕТА КОУЧА:
    1.  Стиль: прямой, честный, мотивирующий, в стиле "ты".
    2.  Длина: 3-4 предложения.
    3.  Содержание:
        - Начни с вердикта: стоит ли есть это блюдо, основываясь на данных из `progress_assessment`.
        - Объясни "почему" на цифрах, сравнивая КБЖУ блюда с остатками в `remaining_macros`.
        - Дай один, самый важный совет (например, что съесть вместо этого или как скорректировать день).

    ### ФОРМАТ ОТВЕТА (STRICT JSON):
    ```json
    {{
      "food_analysis": {{
        "food_name": "Название блюда",
        "weight_g": 0,
        "calories": 0,
        "proteins_g": 0,
        "fats_g": 0,
        "carbs_g": 0
      }},
      "coach_advice": "Твой совет здесь."
    }}
    ```
    """

    print(f"Attempting to use model for combined analysis and advice: {model_to_use}")

    if model_to_use in settings.NATIVE_GEMINI_MODELS:
        content_parts = []
        if file_content:
            img = Image.open(io.BytesIO(file_content))
            content_parts.append(img)
        
        full_prompt = f"{prompt}\nДополнительное описание от пользователя: {description}" if description else prompt
        print(full_prompt)
        content_parts.append(full_prompt)
        
        response = await asyncio.to_thread(gemini_client.models.generate_content, model=model_to_use, contents=content_parts)
        return json.loads(response.text), model_to_use

    elif model_to_use in settings.OPEN_ROUTER_MODELS:
        messages = [{"role": "system", "content": "You are an integrated nutrition assistant. Your response must be a single, valid JSON object."}]
        content_parts = [{"type": "text", "text": prompt}]
        
        if description:
             content_parts[0]["text"] += f"\nUser's description: {description}"
        
        if file_content:
            base64_image = base64.b64encode(file_content).decode('utf-8')
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
            })
        
        messages.append({"role": "user", "content": content_parts})
        
        chat_completion = await open_router_client.chat.completions.create(
            model=model_to_use,
            messages=messages,
            max_tokens=1024,
            response_format={"type": "json_object"},
        )
        return json.loads(chat_completion.choices[0].message.content), model_to_use
    
    else:
        raise ValueError(f"Model {model_to_use} is not configured in any known provider.")


# --- API эндпоинты ---
@app.post("/users/", response_model=schemas.User)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    return crud.create_user(db=db, user=user)


@app.post("/token", response_model=schemas.Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = crud.get_user_by_email(db, email=form_data.username)
    if not user or not crud.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(data={"sub": user.email}, expires_delta=access_token_expires)
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/users/me/", response_model=schemas.UserWithTargets)
async def read_users_me(current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    user_from_db = db.query(models.User).options(
        joinedload(models.User.meals),
        joinedload(models.User.metrics)
    ).filter(models.User.id == current_user.id).first()

    if not user_from_db:
        raise HTTPException(status_code=404, detail="User not found in current session")

    latest_metric = crud.get_latest_user_metric(db, user_id=user_from_db.id)
    user_with_targets = schemas.UserWithTargets.from_orm(user_from_db)

    if latest_metric and user_from_db.date_of_birth and user_from_db.gender and user_from_db.height_cm:
        targets = utils.calculate_user_targets(
            user_from_db,
            latest_metric.weight_kg,
            latest_metric.body_fat_percentage
        )
        user_with_targets.calculated_targets = schemas.CalculatedTargets(**targets)

    return user_with_targets


@app.post("/users/me/calculate-targets", response_model=schemas.CalculatedTargets)
async def calculate_targets(request: schemas.TargetCalculationRequest):
    if any([
        request.date_of_birth is None,
        request.gender is None or request.gender == "",
        request.height_cm is None or request.height_cm <= 0,
        request.weight_kg is None or request.weight_kg <= 0,
        request.activity_level is None or request.activity_level == "",
        request.goal is None or request.goal == "",
        request.goal_intensity is None
    ]):
        return schemas.CalculatedTargets(target_calories=0, target_protein=0, target_fat=0, target_carbohydrates=0)

    temp_user = models.User(
        date_of_birth=request.date_of_birth,
        gender=request.gender,
        height_cm=request.height_cm,
        activity_level=request.activity_level,
        goal=request.goal,
        goal_intensity=request.goal_intensity
    )
    targets = utils.calculate_user_targets(
        temp_user,
        request.weight_kg,
        request.body_fat_percentage
    )
    return schemas.CalculatedTargets(**targets)


@app.put("/users/me/", response_model=schemas.User)
def update_current_user(
        user_update: schemas.UserUpdate,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(auth.get_current_user)
):
    return crud.update_user(db, user=current_user, user_update=user_update)


@app.post("/users/me/metrics", response_model=schemas.UserMetrics)
def create_metric_for_current_user(
        metric: schemas.UserMetricsCreate,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(auth.get_current_user)
):
    return crud.create_user_metric(db, metric=metric, user_id=current_user.id)


@app.post("/analyze-meal/", response_model=schemas.AnalysisResponse)
async def analyze_meal(
        description: Optional[str] = Form(None),
        file: Optional[UploadFile] = File(None),
        ai_model: Optional[str] = Form(None),
        db: Session = Depends(get_db),
        current_user: models.User = Depends(auth.get_current_user)
):
    if not file and not description:
        raise HTTPException(status_code=400, detail="Please provide a photo or a description.")
    
    file_content = await file.read() if file else None

    # --- Сбор контекста ---
    today_stats = crud.get_user_stats_by_period(db, user_id=current_user.id, start_date=date.today(), end_date=date.today())
    consumed_today = {
        "calories": today_stats.total_calories or 0,
        "protein": today_stats.total_protein or 0,
        "fat": today_stats.total_fat or 0,
        "carbohydrates": today_stats.total_carbohydrates or 0
    }
    latest_metric = crud.get_latest_user_metric(db, user_id=current_user.id)
    ai_context = await utils.prepare_ai_context(
        user=current_user,
        consumed_today=consumed_today,
        analyzed_meal={},
        latest_weight_kg=latest_metric.weight_kg if latest_metric else None,
        latest_body_fat_percentage=latest_metric.body_fat_percentage if latest_metric else None
    )

    # --- Вызов AI с перебором моделей ---
    models_to_try = list(settings.NUTRITION_MODELS)
    if ai_model and ai_model in models_to_try:
        models_to_try.insert(0, models_to_try.pop(models_to_try.index(ai_model)))

    ai_response = None
    model_used = None
    last_error = None

    for model in models_to_try:
        try:
            ai_response, model_used = await get_nutrition_analysis_and_advice(
                file_content=file_content,
                description=description,
                ai_context=ai_context,
                model_to_use=model
            )
            if ai_response:
                break 
        except Exception as e:
            last_error = e
            print(f"Model {model} failed: {e}. Trying next model.")
            if file_content: # Перематываем ридер файла для следующей попытки
                file.file.seek(0)
                file_content = await file.read()


    if not ai_response:
        raise HTTPException(status_code=503, detail=f"All AI models are currently unavailable. Last error: {last_error}")

    # --- Обработка ответа ---
    food_analysis = ai_response.get("food_analysis", {})
    coach_advice = ai_response.get("coach_advice", "Не удалось получить совет от AI.")

    proteins_g = round(float(food_analysis.get("proteins_g", 0)))
    fats_g = round(float(food_analysis.get("fats_g", 0)))
    carbs_g = round(float(food_analysis.get("carbs_g", 0)))
    calculated_calories = (proteins_g * 4) + (fats_g * 9) + (carbs_g * 4)

    analyzed_meal_totals = {
        "food_name": food_analysis.get("food_name", "Неизвестное блюдо"),
        "total_calories": round(calculated_calories),
        "total_protein": proteins_g,
        "total_fat": fats_g,
        "total_carbohydrates": carbs_g
    }

    return schemas.AnalysisResponse(
        suggested_totals=schemas.MealTotals(**analyzed_meal_totals),
        ai_response_text=analyzed_meal_totals["food_name"],
        ai_coach_advice=coach_advice,
        nutrition_model_used=model_used,
        coach_model_used=model_used
    )


@app.post("/meals/", response_model=schemas.Meal)
def confirm_and_create_meal(
        meal_data: schemas.MealCreate,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(auth.get_current_user)
):
    if meal_data.ai_coach_advice:
        meal_data.food_name = f"{meal_data.food_name}\n\n{meal_data.ai_coach_advice}"

    return crud.create_meal(db=db, meal=meal_data, user_id=current_user.id)


@app.get("/meals/", response_model=List[schemas.Meal])
def read_user_meals(
        skip: int = 0, limit: int = 100, db: Session = Depends(get_db),
        current_user: models.User = Depends(auth.get_current_user)
):
    return crud.get_meals_by_user(db, user_id=current_user.id, skip=skip, limit=limit)


@app.delete("/meals/{meal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_meal(
        meal_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)
):
    db_meal = crud.get_meal_by_id(db, meal_id)
    if not db_meal:
        raise HTTPException(status_code=404, detail="Meal not found")
    if db_meal.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this meal")
    crud.delete_meal(db, meal_id=meal_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/users/me/stats", response_model=schemas.StatsSummary)
def get_user_stats(
        start_date: date, end_date: date, db: Session = Depends(get_db),
        current_user: models.User = Depends(auth.get_current_user)
):
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="Start date cannot be after end date")
    stats = crud.get_user_stats_by_period(db, user_id=current_user.id, start_date=start_date, end_date=end_date)
    return schemas.StatsSummary(
        total_calories=stats.total_calories or 0,
        total_protein=stats.total_protein or 0,
        total_fat=stats.total_fat or 0,
        total_carbohydrates=stats.total_carbohydrates or 0,
        start_date=start_date,
        end_date=end_date
    )


@app.get("/users/me/average-stats", response_model=schemas.AverageSummary)
def get_average_stats(db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    end_date = date.today()
    start_date = end_date - timedelta(days=20)
    
    daily_stats = crud.get_daily_stats_for_period(db, user_id=current_user.id, start_date=start_date, end_date=end_date)
    
    total_calories = sum(s['total_calories'] for s in daily_stats)
    total_protein = sum(s['total_protein'] for s in daily_stats)
    total_fat = sum(s['total_fat'] for s in daily_stats)
    total_carbohydrates = sum(s['total_carbohydrates'] for s in daily_stats)
    
    days_with_data = len(daily_stats) if daily_stats else 1 # Избегаем деления на ноль

    latest_metric = crud.get_latest_user_metric(db, user_id=current_user.id)
    latest_weight = latest_metric.weight_kg if latest_metric else None
    latest_body_fat = latest_metric.body_fat_percentage if latest_metric else None
    targets = utils.calculate_user_targets(current_user, latest_weight, latest_body_fat)

    return schemas.AverageSummary(
        avg_calories=round(total_calories / days_with_data),
        avg_protein=round(total_protein / days_with_data),
        avg_fat=round(total_fat / days_with_data),
        avg_carbohydrates=round(total_carbohydrates / days_with_data),
        target_calories=targets.get("target_calories", 0),
        target_protein=targets.get("target_protein", 0),
        target_fat=targets.get("target_fat", 0),
        target_carbohydrates=targets.get("target_carbohydrates", 0)
    )


@app.get("/users/me/stats/weekly-summary", response_model=schemas.WeeklySummaryResponse)
def get_weekly_summary(db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    return get_summary_for_period(days=7, db=db, current_user=current_user)


@app.get("/users/me/stats/summary-by-period", response_model=schemas.WeeklySummaryResponse)
def get_summary_by_period(days: int, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    return get_summary_for_period(days=days, db=db, current_user=current_user)


def get_summary_for_period(days: int, db: Session, current_user: models.User):
    latest_metric = crud.get_latest_user_metric(db, user_id=current_user.id)

    latest_weight = latest_metric.weight_kg if latest_metric else None
    latest_body_fat = latest_metric.body_fat_percentage if latest_metric else None

    targets = utils.calculate_user_targets(current_user, latest_weight, latest_body_fat)
    target_calories = targets["target_calories"]
    target_protein = targets["target_protein"]
    target_fat = targets["target_fat"]
    target_carbohydrates = targets["target_carbohydrates"]

    end_date = date.today()
    start_date = end_date - timedelta(days=days - 1)

    daily_consumptions = crud.get_daily_stats_for_period(db, user_id=current_user.id, start_date=start_date,
                                                         end_date=end_date)
    
    consumption_map = {str(item["date"]): item for item in daily_consumptions}

    daily_breakdown = []
    total_consumed = {"calories": 0, "protein": 0, "fat": 0, "carbohydrates": 0}
    days_with_data = 0
    progress_lab_summary_for_today = None

    for i in range(days):
        current_date = end_date - timedelta(days=i)
        
        consumed = consumption_map.get(str(current_date))

        consumed_calories = consumed["total_calories"] if consumed else 0
        consumed_protein = consumed["total_protein"] if consumed else 0
        consumed_fat = consumed["total_fat"] if consumed else 0
        consumed_carbohydrates = consumed["total_carbohydrates"] if consumed else 0

        target_macros = {
            "calories": target_calories,
            "protein": target_protein,
            "fat": target_fat,
            "carbohydrates": target_carbohydrates
        }
        actual_macros = {
            "calories": consumed_calories,
            "protein": consumed_protein,
            "fat": consumed_fat,
            "carbohydrates": consumed_carbohydrates
        }

        score_result = {}
        if current_date == date.today():
            # Используем новую расширенную функцию для сегодняшнего дня
            score_result = utils.calculate_progress_lab_score(target_macros, actual_macros)
            progress_lab_summary_for_today = score_result
        else:
            end_of_day_dt = datetime.combine(current_date, datetime.min.time().replace(hour=23))
            score_result = utils.calculate_progress_lab_score(target_macros, actual_macros, current_dt=end_of_day_dt)

        daily_breakdown.append(schemas.DailyStatDetail(
            date=current_date,
            consumed_calories=consumed_calories,
            consumed_protein=consumed_protein,
            consumed_fat=consumed_fat,
            consumed_carbohydrates=consumed_carbohydrates,
            target_calories=target_calories,
            target_protein=target_protein,
            target_fat=target_fat,
            target_carbohydrates=target_carbohydrates,
            status="calculated",
            daily_score=score_result.get("daily_score"),
            status_color=score_result.get("status_color"),
            status_message=score_result.get("status_message"),
            y_axis_pos=score_result.get("y_axis_pos"),
            time_progress=score_result.get("time_progress")
        ))
        
        if consumed:
            days_with_data += 1
            total_consumed["calories"] += consumed_calories
            total_consumed["protein"] += consumed_protein
            total_consumed["fat"] += consumed_fat
            total_consumed["carbohydrates"] += consumed_carbohydrates

    avg_calories = (total_consumed["calories"] / days_with_data) if days_with_data > 0 else 0
    avg_protein = (total_consumed["protein"] / days_with_data) if days_with_data > 0 else 0
    avg_fat = (total_consumed["fat"] / days_with_data) if days_with_data > 0 else 0
    avg_carbohydrates = (total_consumed["carbohydrates"] / days_with_data) if days_with_data > 0 else 0

    period_summary = schemas.AverageSummary(
        avg_calories=round(avg_calories),
        avg_protein=round(avg_protein),
        avg_fat=round(avg_fat),
        avg_carbohydrates=round(avg_carbohydrates),
        **targets
    )

    return schemas.WeeklySummaryResponse(
        daily_breakdown=daily_breakdown,
        period_summary=period_summary,
        progress_lab_summary=progress_lab_summary_for_today
    )

@app.get("/users/me/dashboard-stats", response_model=schemas.DashboardStats)
async def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    msk_tz = timezone(timedelta(hours=3))
    now_msk = datetime.now(msk_tz)

    start_msk = now_msk.replace(hour=0, minute=0, second=0, microsecond=0)
    end_msk = start_msk + timedelta(days=1)
    start_utc = start_msk.astimezone(timezone.utc)
    end_utc = end_msk.astimezone(timezone.utc)

    meals = (
        db.query(models.Meal)
        .filter(
            models.Meal.user_id == current_user.id,
            models.Meal.timestamp >= start_utc,
            models.Meal.timestamp < end_utc
        )
        .all()
    )

    consumed_calories = sum(m.total_calories or 0 for m in meals)
    consumed_protein = sum(m.total_protein or 0 for m in meals)
    consumed_fat = sum(m.total_fat or 0 for m in meals)
    consumed_carbohydrates = sum(m.total_carbohydrates or 0 for m in meals)

    latest_metric = crud.get_latest_user_metric(db, user_id=current_user.id)
    latest_weight = latest_metric.weight_kg if latest_metric else None
    latest_body_fat = latest_metric.body_fat_percentage if latest_metric else None
    targets = utils.calculate_user_targets(current_user, latest_weight, latest_body_fat)

    return schemas.DashboardStats(
        target_calories=targets["target_calories"],
        target_protein=targets["target_protein"],
        target_fat=targets["target_fat"],
        target_carbohydrates=targets["target_carbohydrates"],
        consumed_calories=consumed_calories,
        consumed_protein=consumed_protein,
        consumed_fat=consumed_fat,
        consumed_carbohydrates=consumed_carbohydrates,
    )