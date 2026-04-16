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

# --- Глобальная переменная для отслеживания даты обновления моделей ---
LAST_MODEL_UPDATE_DATE = None

def update_ai_chat_models_if_needed():
    """
    Проверяет, нужно ли обновлять список моделей, и если да, то обновляет.
    """
    global LAST_MODEL_UPDATE_DATE
    today = date.today()
    
    if LAST_MODEL_UPDATE_DATE == today and settings.AI_CHAT_MODELS:
        print("--- Список моделей AI-коуча уже актуален. ---")
        return

    print("--- Обновление списка бесплатных моделей AI-коуча... ---")
    try:
        response = requests.get("https://openrouter.ai/api/v1/models")
        if response.status_code != 200:
            print("Ошибка при получении моделей от OpenRouter.")
            return

        models_data = response.json().get('data', [])
        
        chat_keywords = ['instruct', 'chat', 'it']
        free_model_ids = [
            model.get('id') for model in models_data 
            if model.get('pricing', {}).get('prompt') == "0" 
            and model.get('pricing', {}).get('completion') == "0"
            and any(keyword in model.get('id', '').lower() for keyword in chat_keywords)
        ]
        
        available_best_models = [
            model_id for model_id in settings.AI_COACH_PRIORITY_MODELS 
            if model_id in free_model_ids
        ]
        
        other_free_models = [
            model_id for model_id in free_model_ids 
            if model_id not in settings.AI_COACH_PRIORITY_MODELS
        ]
        
        Settings.AI_CHAT_MODELS = (available_best_models + other_free_models)[:10]
        LAST_MODEL_UPDATE_DATE = today
        print(f"--- Список моделей AI-коуча обновлен: {Settings.AI_CHAT_MODELS} ---")

    except Exception as e:
        print(f"Не удалось обновить список моделей: {e}")


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
async def call_ai_model(file_content: Optional[bytes], description: Optional[str]) -> (str, str):
    prompt = """
    Ты — эксперт-нутрициолог с математическим уклоном. 
    Твоя задача — проанализировать еду (фото или описание) и рассчитать КБЖУ.

    ### ПРАВИЛА РАСЧЕТА:
    1. Сначала определи вес (weight), белки (P), жиры (F) и углеводы (C) в граммах.
    2. Итоговые калории (Kcal) ОБЯЗАТЕЛЬНО рассчитывай строго по формуле: 
       Kcal = (P * 4) + (C * 4) + (F * 9)
    3. Округляй все числовые значения до целых чисел.
    4. Сумма калорий в ответе не может отличаться от результата формулы.

    ### ФОРМАТ ОТВЕТА (STRICT JSON):
    Верни короткое описание блюда  и JSON-объект без лишнего текста, пояснений и Markdown-разметки:
    {
      "food_name": "Название блюда",
      "weight_g": 0,
      "calories": 0,
      "proteins_g": 0,
      "fats_g": 0,
      "carbs_g": 0,
      "confidence_score": 0.0
    }
    """
    
    for model_name in settings.NUTRITION_MODELS:
        try:
            print(f"Attempting to use model for nutrition analysis: {model_name}")
            
            if model_name in settings.NATIVE_GEMINI_MODELS:
                content_parts = []
                full_prompt = f"{prompt}\nДополнительное описание: {description}" if description else prompt
                
                if file_content:
                    img = Image.open(io.BytesIO(file_content))
                    content_parts.append(img)
                content_parts.append(full_prompt)
                
                response = await asyncio.to_thread(gemini_client.models.generate_content, model=model_name, contents=content_parts)
                return response.text, model_name

            elif model_name in settings.OPEN_ROUTER_MODELS:
                messages = [{"role": "system", "content": prompt}]
                content_parts = []
                if description:
                    content_parts.append({"type": "text", "text": description})
                if file_content:
                    base64_image = base64.b64encode(file_content).decode('utf-8')
                    content_parts.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                    })
                
                if content_parts:
                    messages.append({"role": "user", "content": content_parts})
                
                chat_completion = await open_router_client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    max_tokens=300,
                )
                return chat_completion.choices[0].message.content, model_name
            
            else:
                print(f"Model {model_name} not found in any API list, skipping.")
                continue

        except Exception as e:
            print(f"Model {model_name} failed: {e}")
            continue
            
    raise HTTPException(status_code=503, detail="All AI models are currently unavailable. Please try again later.")


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
        db: Session = Depends(get_db),
        current_user: models.User = Depends(auth.get_current_user)
):
    update_ai_chat_models_if_needed()

    if not file and not description:
        raise HTTPException(status_code=400, detail="Please provide a photo or a description.")
    
    file_content = await file.read() if file else None

    try:
        raw_ai_response, nutrition_model_used = await call_ai_model(file_content=file_content, description=description)
    except HTTPException as e:
        raise e

    if not raw_ai_response:
        raise HTTPException(status_code=500, detail="AI model returned an empty response.")

    try:
        json_match = re.search(r'{.*}', raw_ai_response, re.DOTALL)
        if not json_match:
            raise HTTPException(status_code=500, detail="AI model did not return a valid JSON object. Response: " + raw_ai_response)
        
        json_string = json_match.group(0)
        ai_data = json.loads(json_string)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="AI model returned invalid JSON. Response: " + raw_ai_response)

    food_name = ai_data.get("food_name", "Неизвестное блюдо")
    proteins_g = round(float(ai_data.get("proteins_g", 0)))
    fats_g = round(float(ai_data.get("fats_g", 0)))
    carbs_g = round(float(ai_data.get("carbs_g", 0)))
    
    calculated_calories = (proteins_g * 4) + (fats_g * 9) + (carbs_g * 4)
    calories = round(calculated_calories)

    analyzed_meal_totals = {
        "food_name": food_name,
        "total_calories": calories,
        "total_protein": proteins_g,
        "total_fat": fats_g,
        "total_carbohydrates": carbs_g
    }

    latest_metric = crud.get_latest_user_metric(db, user_id=current_user.id)
    user_targets = utils.calculate_user_targets(
        current_user,
        latest_metric.weight_kg if latest_metric else None,
        latest_metric.body_fat_percentage if latest_metric else None
    )

    today_stats = crud.get_user_stats_by_period(db, user_id=current_user.id, start_date=date.today(), end_date=date.today())
    consumed_today = {
        "calories": today_stats.total_calories or 0,
        "protein": today_stats.total_protein or 0,
        "fat": today_stats.total_fat or 0,
        "carbohydrates": today_stats.total_carbohydrates or 0
    }

    ai_advice, coach_model_used = await utils.get_ai_coach_advice(
        user_targets=user_targets,
        consumed_today=consumed_today,
        analyzed_meal=analyzed_meal_totals,
        current_time=datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=3)))
    )

    return schemas.AnalysisResponse(
        suggested_totals=schemas.MealTotals(**analyzed_meal_totals),
        ai_response_text=food_name,
        ai_coach_advice=ai_advice,
        nutrition_model_used=nutrition_model_used,
        coach_model_used=coach_model_used
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
            score_result = utils.calculate_progress_lab_score(target_macros, actual_macros)
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
        period_summary=period_summary
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