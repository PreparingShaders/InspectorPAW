from datetime import timedelta, date
from typing import List, Optional
import os
import uuid

from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from . import crud, models, schemas, auth
from .database import SessionLocal, engine
from .config import settings

# Создаем все таблицы в базе данных
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="InspectorPAW API")

# Настройка статических файлов
UPLOAD_DIRECTORY = "static/uploads"
os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- Зависимости ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_meal(meal_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)) -> models.Meal:
    """Зависимость для получения приема пищи и проверки прав доступа."""
    db_meal = crud.get_meal_by_id(db, meal_id)
    if not db_meal:
        raise HTTPException(status_code=404, detail="Meal not found")
    if db_meal.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this meal")
    return db_meal

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

# --- Статистика ---
@app.get("/users/me/stats", response_model=schemas.StatsSummary)
def get_user_stats(start_date: date, end_date: date, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="Start date cannot be after end date")
    stats = crud.get_user_stats_by_period(db, user_id=current_user.id, start_date=start_date, end_date=end_date)
    return schemas.StatsSummary(
        total_calories=stats.total_calories or 0, total_protein=stats.total_protein or 0,
        total_fat=stats.total_fat or 0, total_carbohydrates=stats.total_carbohydrates or 0,
        start_date=start_date, end_date=end_date
    )

# --- Процесс работы с едой ---
@app.post("/meals/", response_model=schemas.Meal)
def create_meal_container(meal: schemas.MealCreate, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    """Шаг 1: Создает пустой 'контейнер' для приема пищи."""
    return crud.create_user_meal(db=db, meal=meal, user_id=current_user.id)

@app.post("/meals/{meal_id}/upload", response_model=schemas.Meal)
async def upload_meal_data(
    meal: models.Meal = Depends(get_current_meal),
    description: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """Шаг 2: Загружает фото и/или описание к приему пищи."""
    photo_url = meal.photo_url
    if file:
        file_extension = os.path.splitext(file.filename)[1]
        file_name = f"{uuid.uuid4()}{file_extension}"
        file_path = os.path.join(UPLOAD_DIRECTORY, file_name)
        with open(file_path, "wb") as buffer:
            buffer.write(await file.read())
        photo_url = f"/static/uploads/{file_name}"
    
    return crud.update_meal_photo_and_description(db, meal.id, photo_url, description)

@app.post("/meals/{meal_id}/analyze", response_model=List[schemas.MealFoodItemCreate])
async def analyze_meal(meal: models.Meal = Depends(get_current_meal)):
    """Шаг 3: 'Анализирует' данные и возвращает ПРЕДВАРИТЕЛЬНЫЙ список продуктов."""
    if not meal.photo_url and not meal.description:
        raise HTTPException(status_code=400, detail="Meal has no photo or description to analyze")

    # --- ИМИТАЦИЯ РАБОТЫ ИИ ---
    # В будущем здесь будет вызов вашей модели, которая примет meal.photo_url и meal.description
    recognized_items = [
        {"name": "Яичница", "calories": 155, "protein": 13, "fat": 11, "carbohydrates": 1.1, "quantity_grams": 100},
        {"name": "Авокадо", "calories": 160, "protein": 2, "fat": 15, "carbohydrates": 9, "quantity_grams": 50},
    ]
    if "хлеб" in (meal.description or "").lower():
         recognized_items.append(
             {"name": "Хлеб цельнозерновой", "calories": 247, "protein": 13, "fat": 3.4, "carbohydrates": 41, "quantity_grams": 30}
         )
    return recognized_items

@app.post("/meals/{meal_id}/confirm", response_model=schemas.Meal)
async def confirm_analysis(
    confirmation: schemas.AnalysisConfirmation,
    meal: models.Meal = Depends(get_current_meal),
    db: Session = Depends(get_db)
):
    """Шаг 4: Принимает финальный список от пользователя и сохраняет его в БД."""
    return crud.confirm_meal_analysis(db, meal_id=meal.id, confirmed_items=confirmation.items)

@app.get("/meals/", response_model=List[schemas.Meal])
def read_user_meals(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    """Получает список всех приемов пищи пользователя."""
    return crud.get_meals_by_user(db, user_id=current_user.id, skip=skip, limit=limit)

@app.get("/")
def read_root():
    return {"message": "InspectorPAW is online!", "status": "Gym ready"}
