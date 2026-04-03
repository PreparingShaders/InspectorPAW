from datetime import timedelta, date, datetime
from typing import List, Optional
import re
import io
import base64
import asyncio
import google.genai as genai
from openai import AsyncOpenAI
from PIL import Image

from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form, Response, Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from . import crud, models, schemas, auth, utils
from .database import SessionLocal, engine
from .config import settings

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="InspectorPAW API")

# Монтируем статическую директорию
app.mount("/static", StaticFiles(directory="static"), name="static")

# Настраиваем шаблонизатор
templates = Jinja2Templates(directory="templates")

# --- API Клиенты ---

# 1. Конфигурируем нативный API Gemini
# Возвращаем к исходному способу инициализации клиента
gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)

# 2. Конфигурируем клиент для OpenRouter
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


@app.get("/analyze")
async def read_analyze_page(request: Request):
    return templates.TemplateResponse(name="analyze.html", request=request)


# --- AI Логика ---
async def call_ai_model(file_content: Optional[bytes], description: Optional[str]) -> str:
    prompt = """
    Ты — эксперт-диетолог. Проанализируй изображение еды и/или текстовое описание. 
    Твоя задача — вернуть структурированный ответ с названием блюда, его весом в граммах и КБЖУ.
    Формат ответа должен быть строго таким:
    Название: [Название блюда]
    Вес: [Вес в граммах]
    Калории: [Количество]
    Белки: [Количество]
    Жиры: [Количество]
    Углеводы: [Количество]
    """
    
    for model_name in settings.NUTRITION_MODELS:
        try:
            print(f"Attempting to use model: {model_name}")
            
            # --- Логика для нативных моделей Gemini ---
            if model_name in settings.NATIVE_GEMINI_MODELS:
                content_parts = []
                # Убедимся, что full_prompt определен до использования
                full_prompt = f"{prompt}\nДополнительное описание: {description}" if description else prompt
                
                if file_content:
                    img = Image.open(io.BytesIO(file_content))
                    content_parts.append(img)
                content_parts.append(full_prompt)
                
                # Возвращаем к исходному способу вызова модели
                response = await asyncio.to_thread(gemini_client.models.generate_content, model=model_name, contents=content_parts)
                return response.text

            # --- Логика для OpenRouter ---
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
                return chat_completion.choices[0].message.content
            
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
    latest_metric = crud.get_latest_user_metric(db, user_id=current_user.id)

    user_with_targets = schemas.UserWithTargets.from_orm(current_user)

    if latest_metric and current_user.date_of_birth and current_user.gender and current_user.height_cm:
        targets = utils.calculate_user_targets(
            current_user,
            latest_metric.weight_kg,
            latest_metric.body_fat_percentage
        )
        user_with_targets.calculated_targets = schemas.CalculatedTargets(**targets)

    return user_with_targets


@app.post("/users/me/calculate-targets", response_model=schemas.CalculatedTargets)
async def calculate_targets(request: schemas.TargetCalculationRequest):
    # Более надежная и явная проверка на наличие всех необходимых полей
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

    # Создаем временный объект User для передачи в функцию расчета
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
        current_user: models.User = Depends(auth.get_current_user)
):
    if not file and not description:
        raise HTTPException(status_code=400, detail="Please provide a photo or a description.")
    
    file_content = await file.read() if file else None

    try:
        ai_response_text = await call_ai_model(file_content=file_content, description=description)
    except HTTPException as e:
        raise e

    # Проверяем, что ответ не пустой
    if not ai_response_text:
        raise HTTPException(status_code=500, detail="AI model returned an empty response.")

    calories_match = re.search(r"Калории: (\d+\.?\d*)", ai_response_text, re.IGNORECASE)
    protein_match = re.search(r"Белки: (\d+\.?\d*)", ai_response_text, re.IGNORECASE)
    fat_match = re.search(r"Жиры: (\d+\.?\d*)", ai_response_text, re.IGNORECASE)
    carbs_match = re.search(r"Углеводы: (\d+\.?\d*)", ai_response_text, re.IGNORECASE)

    calories = float(calories_match.group(1)) if calories_match else 0
    protein = float(protein_match.group(1)) if protein_match else 0
    fat = float(fat_match.group(1)) if fat_match else 0
    carbs = float(carbs_match.group(1)) if carbs_match else 0
    
    suggested_totals = schemas.MealTotals(
        total_calories=calories, total_protein=protein, total_fat=fat, total_carbohydrates=carbs
    )
    return schemas.AnalysisResponse(
        suggested_totals=suggested_totals, ai_response_text=ai_response_text
    )


@app.post("/meals/", response_model=schemas.Meal)
def confirm_and_create_meal(
        meal_data: schemas.MealCreate,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(auth.get_current_user)
):
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


@app.get("/users/me/stats/weekly-summary", response_model=schemas.WeeklySummaryResponse)
def get_weekly_summary(db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    latest_metric = crud.get_latest_user_metric(db, user_id=current_user.id)

    latest_weight = latest_metric.weight_kg if latest_metric else None
    latest_body_fat = latest_metric.body_fat_percentage if latest_metric else None

    targets = utils.calculate_user_targets(current_user, latest_weight, latest_body_fat)
    target_calories = targets["target_calories"]
    target_protein = targets["target_protein"]
    target_fat = targets["target_fat"]
    target_carbohydrates = targets["target_carbohydrates"]

    end_date = date.today()
    start_date = end_date - timedelta(days=6)

    print(f"DEBUG: get_weekly_summary - start_date: {start_date}, end_date: {end_date}")  # LOG
    daily_consumptions = crud.get_daily_stats_for_period(db, user_id=current_user.id, start_date=start_date,
                                                         end_date=end_date)
    print(f"DEBUG: get_weekly_summary - daily_consumptions from CRUD: {daily_consumptions}")  # LOG

    # Преобразуем ключи в consumption_map в строки для согласованности
    consumption_map = {str(item["date"]): item for item in daily_consumptions}

    print(f"DEBUG: get_weekly_summary - consumption_map (with string keys): {consumption_map}")  # LOG

    daily_breakdown = []
    total_consumed = {"calories": 0, "protein": 0, "fat": 0, "carbohydrates": 0}
    days_with_data = 0

    for i in range(7):
        current_date = end_date - timedelta(days=i)
        # Преобразуем current_date в строку для поиска в карте
        consumed = consumption_map.get(str(current_date))

        if consumed:
            days_with_data += 1
            consumed_calories = consumed["total_calories"]
            consumed_protein = consumed["total_protein"]
            consumed_fat = consumed["total_fat"]
            consumed_carbohydrates = consumed["total_carbohydrates"]

            total_consumed["calories"] += consumed_calories
            total_consumed["protein"] += consumed_protein
            total_consumed["fat"] += consumed_fat
            total_consumed["carbohydrates"] += consumed_carbohydrates

            if abs(consumed_calories - target_calories) < (target_calories * 0.1):
                status = "completed"
            elif consumed_calories > target_calories:
                status = "over_limit"
            else:
                status = "under_limit"
        else:
            status = "no_data" # Ensure status is set even if no consumption

        daily_breakdown.append(schemas.DailyStatDetail(
            date=current_date,
            consumed_calories=consumed_calories,
            consumed_protein=consumed_protein,
            consumed_fat=consumed_fat,
            consumed_carbohydrates=consumed_carbohydrates,
            target_calories=target_calories,
            status=status
        ))

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
    today = date.today()
    
    # Получаем цели пользователя
    latest_metric = crud.get_latest_user_metric(db, user_id=current_user.id)
    latest_weight = latest_metric.weight_kg if latest_metric else None
    latest_body_fat = latest_metric.body_fat_percentage if latest_metric else None
    targets = utils.calculate_user_targets(current_user, latest_weight, latest_body_fat)

    # Получаем потребление за сегодня
    today_stats = crud.get_daily_stats_for_period(db, user_id=current_user.id, start_date=today, end_date=today)
    
    consumed_calories = 0
    consumed_protein = 0
    consumed_fat = 0
    consumed_carbohydrates = 0

    if today_stats:
        # crud.get_daily_stats_for_period возвращает список словарей, берем первый (и единственный) элемент
        day_data = today_stats[0] 
        consumed_calories = day_data['total_calories']
        consumed_protein = day_data['total_protein']
        consumed_fat = day_data['total_fat']
        consumed_carbohydrates = day_data['total_carbohydrates']

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
