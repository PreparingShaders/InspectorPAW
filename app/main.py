from datetime import timedelta, date
from typing import List, Optional
import re

from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from . import crud, models, schemas, auth
from .database import SessionLocal, engine
from .config import settings

# Создаем все таблицы в базе данных
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="InspectorPAW API")

# --- Зависимости ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Аутентификация и Пользователи ---
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

@app.get("/users/me/", response_model=schemas.User)
async def read_users_me(current_user: models.User = Depends(auth.get_current_user)):
    return current_user

@app.put("/users/me/", response_model=schemas.User)
def update_current_user(
    user_update: schemas.UserUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """Обновляет профиль текущего пользователя."""
    return crud.update_user(db, user=current_user, user_update=user_update)

# --- Метрики пользователя ---
@app.post("/users/me/metrics", response_model=schemas.UserMetrics)
def create_metric_for_current_user(
    metric: schemas.UserMetricsCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """Создает новую запись метрик (вес, сон и т.д.) для текущего пользователя."""
    return crud.create_user_metric(db, metric=metric, user_id=current_user.id)

# --- Процесс работы с едой ---

@app.post("/analyze-meal/", response_model=schemas.AnalysisResponse)
async def analyze_meal(
    description: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    current_user: models.User = Depends(auth.get_current_user) # Защищаем эндпоинт
):
    """
    Шаг 1: Принимает фото и/или описание, возвращает текст ответа ИИ и предложенные КБЖУ.
    """
    if not file and not description:
        raise HTTPException(status_code=400, detail="Please provide a photo or a description.")

    # --- ИМИТАЦИЯ ВЫЗОВА ИИ И ПОЛУЧЕНИЯ ТЕКСТОВОГО ОТВЕТА ---
    # В будущем здесь будет реальный вызов вашей AI-модели
    ai_response_text = "Проанализировав изображение и описание, я думаю, это куриная грудка (около 150г) с рисом. "
    ai_response_text += "Примерные КБЖУ: Калории: 350, Белки: 40, Жиры: 8, Углеводы: 30."
    
    # --- ПАРСИНГ ТЕКСТОВОГО ОТВЕТА ИИ ---
    # Используем регулярные выражения для извлечения чисел
    calories = float(re.search(r"Калории: (\d+\.?\d*)", ai_response_text, re.IGNORECASE).group(1) or 0)
    protein = float(re.search(r"Белки: (\d+\.?\d*)", ai_response_text, re.IGNORECASE).group(1) or 0)
    fat = float(re.search(r"Жиры: (\d+\.?\d*)", ai_response_text, re.IGNORECASE).group(1) or 0)
    carbs = float(re.search(r"Углеводы: (\d+\.?\d*)", ai_response_text, re.IGNORECASE).group(1) or 0)

    suggested_totals = schemas.MealTotals(
        total_calories=calories,
        total_protein=protein,
        total_fat=fat,
        total_carbohydrates=carbs
    )

    return schemas.AnalysisResponse(
        suggested_totals=suggested_totals,
        ai_response_text=ai_response_text
    )

@app.post("/meals/", response_model=schemas.Meal)
def confirm_and_create_meal(
    meal_data: schemas.MealCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """
    Шаг 2: Принимает финальные (отредактированные) КБЖУ и создает запись о приеме пищи.
    """
    return crud.create_meal(db=db, meal=meal_data, user_id=current_user.id)

# --- История и Статистика ---

@app.get("/meals/", response_model=List[schemas.Meal])
def read_user_meals(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(auth.get_current_user)
):
    """Получает историю приемов пищи пользователя."""
    return crud.get_meals_by_user(db, user_id=current_user.id, skip=skip, limit=limit)

@app.delete("/meals/{meal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_meal(
    meal_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """Удаляет прием пищи."""
    db_meal = crud.get_meal_by_id(db, meal_id)
    if not db_meal:
        raise HTTPException(status_code=404, detail="Meal not found")
    if db_meal.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this meal")
    
    crud.delete_meal(db, meal_id=meal_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@app.get("/users/me/stats", response_model=schemas.StatsSummary)
def get_user_stats(
    start_date: date, 
    end_date: date, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(auth.get_current_user)
):
    """Получает статистику по КБЖУ за указанный период."""
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

@app.get("/")
def read_root():
    return {"message": "InspectorPAW is online!", "status": "Gym ready"}
