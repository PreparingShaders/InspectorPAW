from datetime import timedelta, date, datetime
from typing import List
import os
import uuid

from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Body
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from . import crud, models, schemas, auth
from .database import SessionLocal, engine
from .config import settings

# Создаем все таблицы в базе данных
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="InspectorPAW API")

# Создаем директорию для загрузок, если ее нет
UPLOAD_DIRECTORY = "static/uploads"
os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)

# Монтируем статическую директорию для доступа к загруженным файлам
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- Dependency ---
def get_db():
    """
    Эта функция-зависимость создает сессию с базой данных для каждого запроса
    и закрывает ее после выполнения.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- User and Auth Endpoints ---

@app.post("/users/", response_model=schemas.User)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """
    Эндпоинт для регистрации нового пользователя.
    """
    db_user = crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    return crud.create_user(db=db, user=user)

@app.post("/token", response_model=schemas.Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    Эндпоинт для получения JWT токена доступа.
    Принимает username (email) и password.
    """
    user = crud.get_user_by_email(db, email=form_data.username)
    if not user or not crud.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/me/", response_model=schemas.User)
async def read_users_me(current_user: models.User = Depends(auth.get_current_user)):
    """
    Эндпоинт для получения информации о текущем авторизованном пользователе.
    """
    return current_user

# --- Stats Endpoint ---

@app.get("/users/me/stats", response_model=schemas.StatsSummary)
def get_user_stats(
    start_date: date,
    end_date: date,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """
    Эндпоинт для получения статистики по КБЖУ за указанный период.
    """
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

# --- Food and Meal Endpoints ---

@app.post("/food_items/", response_model=schemas.FoodItem)
def create_food_item(food_item: schemas.FoodItemCreate, db: Session = Depends(get_db)):
    """
    Эндпоинт для создания нового продукта в базе данных.
    """
    db_food_item = crud.get_food_item_by_name(db, name=food_item.name)
    if db_food_item:
        raise HTTPException(status_code=400, detail="Food item already exists")
    return crud.create_food_item(db=db, food_item=food_item)

@app.post("/users/me/meals/", response_model=schemas.Meal)
def create_meal_for_user(
    meal: schemas.MealCreate, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(auth.get_current_user)
):
    """
    Эндпоинт для создания нового приема пищи для текущего пользователя.
    """
    return crud.create_user_meal(db=db, meal=meal, user_id=current_user.id)

@app.get("/users/me/meals/", response_model=List[schemas.Meal])
def read_meals_for_user(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(auth.get_current_user)
):
    """
    Эндпоинт для получения списка приемов пищи текущего пользователя.
    """
    meals = crud.get_meals_by_user(db, user_id=current_user.id, skip=skip, limit=limit)
    return meals

@app.post("/meals/{meal_id}/photo", response_model=schemas.Meal)
async def upload_meal_photo(
    meal_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """
    Эндпоинт для загрузки фотографии к приему пищи.
    """
    db_meal = crud.get_meal_by_id(db, meal_id)
    if not db_meal:
        raise HTTPException(status_code=404, detail="Meal not found")
    if db_meal.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to update this meal")

    file_extension = os.path.splitext(file.filename)[1]
    file_name = f"{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(UPLOAD_DIRECTORY, file_name)

    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())
    
    photo_url = f"/static/uploads/{file_name}"
    updated_meal = crud.update_meal_photo_url(db, meal_id, photo_url)
    return updated_meal

@app.post("/meals/{meal_id}/analyze", response_model=schemas.Meal)
async def analyze_meal_photo(
    meal_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """
    Эндпоинт-заглушка для анализа фото еды.
    Возвращает предопределенный результат и добавляет его к приему пищи.
    """
    db_meal = crud.get_meal_by_id(db, meal_id)
    if not db_meal:
        raise HTTPException(status_code=404, detail="Meal not found")
    if db_meal.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to analyze this meal")
    if not db_meal.photo_url:
        raise HTTPException(status_code=400, detail="Meal has no photo to analyze")

    # --- ИМИТАЦИЯ РАБОТЫ ИИ ---
    recognized_items = [
        {"name": "Яичница", "calories": 155, "protein": 13, "fat": 11, "carbohydrates": 1.1, "quantity_grams": 100},
        {"name": "Авокадо", "calories": 160, "protein": 2, "fat": 15, "carbohydrates": 9, "quantity_grams": 50},
        {"name": "Хлеб цельнозерновой", "calories": 247, "protein": 13, "fat": 3.4, "carbohydrates": 41, "quantity_grams": 30},
    ]

    food_items_to_add = []
    for item in recognized_items:
        food_item_schema = schemas.FoodItemCreate(
            name=item["name"], calories=item["calories"], protein=item["protein"],
            fat=item["fat"], carbohydrates=item["carbohydrates"]
        )
        db_food_item = crud.get_or_create_food_item(db, food_item=food_item_schema)
        
        food_items_to_add.append(schemas.MealFoodItemCreate(
            food_item_id=db_food_item.id, quantity_grams=item["quantity_grams"]
        ))

    updated_meal = crud.add_food_items_to_meal(db, meal_id=meal_id, items=food_items_to_add)
    return updated_meal


@app.get("/")
def read_root():
    return {"message": "InspectorPAW is online!", "status": "Gym ready"}
