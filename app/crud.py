from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date
from passlib.context import CryptContext
from typing import List
from datetime import date
from . import models, schemas

# Создаем контекст для хеширования паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверяет, соответствует ли введенный пароль хешированному."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Хеширует пароль."""
    return pwd_context.hash(password)

def get_user_by_email(db: Session, email: str):
    """Находит пользователя по email."""
    return db.query(models.User).filter(models.User.email == email).first()

def create_user(db: Session, user: schemas.UserCreate):
    """Создает нового пользователя и сохраняет в базу данных."""
    hashed_password = get_password_hash(user.password)
    db_user = models.User(
        email=user.email, 
        hashed_password=hashed_password,
        date_of_birth=user.date_of_birth,
        gender=user.gender,
        height_cm=user.height_cm,
        goal=user.goal,
        goal_intensity=user.goal_intensity
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# --- Stats CRUD ---

def get_user_stats_by_period(db: Session, user_id: int, start_date: date, end_date: date):
    """Считает суммарные КБЖУ для пользователя за указанный период."""
    
    ratio = models.MealFoodItem.quantity_grams / 100.0

    # Исправленный запрос: начинаем с Meal, чтобы избежать двойного join
    query = db.query(
        func.sum(models.FoodItem.calories * ratio).label("total_calories"),
        func.sum(models.FoodItem.protein * ratio).label("total_protein"),
        func.sum(models.FoodItem.fat * ratio).label("total_fat"),
        func.sum(models.FoodItem.carbohydrates * ratio).label("total_carbohydrates")
    ).select_from(models.Meal)\
     .join(models.MealFoodItem, models.Meal.id == models.MealFoodItem.meal_id)\
     .join(models.FoodItem, models.MealFoodItem.food_item_id == models.FoodItem.id)\
     .filter(models.Meal.user_id == user_id)\
     .filter(cast(models.Meal.timestamp, Date) >= start_date)\
     .filter(cast(models.Meal.timestamp, Date) <= end_date)
    
    result = query.first()
    return result

# --- FoodItem CRUD ---

def get_food_item_by_name(db: Session, name: str):
    """Находит продукт по названию."""
    return db.query(models.FoodItem).filter(models.FoodItem.name == name).first()

def get_or_create_food_item(db: Session, food_item: schemas.FoodItemCreate):
    """Проверяет, существует ли продукт, и создает его, если нет."""
    db_food_item = get_food_item_by_name(db, name=food_item.name)
    if db_food_item:
        return db_food_item
    return create_food_item(db, food_item)

def create_food_item(db: Session, food_item: schemas.FoodItemCreate):
    """Создает новый продукт."""
    db_food_item = models.FoodItem(**food_item.dict())
    db.add(db_food_item)
    db.commit()
    db.refresh(db_food_item)
    return db_food_item

# --- Meal CRUD ---

def get_meal_by_id(db: Session, meal_id: int):
    """Находит прием пищи по ID."""
    return db.query(models.Meal).filter(models.Meal.id == meal_id).first()

def update_meal_photo_url(db: Session, meal_id: int, photo_url: str):
    """Обновляет URL фотографии для приема пищи."""
    db_meal = get_meal_by_id(db, meal_id)
    if db_meal:
        db_meal.photo_url = photo_url
        db.commit()
        db.refresh(db_meal)
    return db_meal

def add_food_items_to_meal(db: Session, meal_id: int, items: List[schemas.MealFoodItemCreate]):
    """Добавляет список продуктов к приему пищи."""
    db_meal = get_meal_by_id(db, meal_id)
    if not db_meal:
        return None

    for item in items:
        db_meal_food_item = models.MealFoodItem(
            meal_id=db_meal.id,
            food_item_id=item.food_item_id,
            quantity_grams=item.quantity_grams
        )
        db.add(db_meal_food_item)
    
    db.commit()
    db.refresh(db_meal)
    return db_meal

def create_user_meal(db: Session, meal: schemas.MealCreate, user_id: int):
    """Создает новый прием пищи для пользователя."""
    db_meal = models.Meal(**meal.dict(exclude={"food_items"}), user_id=user_id)
    db.add(db_meal)
    db.commit()
    db.refresh(db_meal)

    for item in meal.food_items:
        db_meal_food_item = models.MealFoodItem(
            meal_id=db_meal.id,
            food_item_id=item.food_item_id,
            quantity_grams=item.quantity_grams
        )
        db.add(db_meal_food_item)
    
    db.commit()
    db.refresh(db_meal)
    return db_meal

def get_meals_by_user(db: Session, user_id: int, skip: int = 0, limit: int = 100):
    """Получает список приемов пищи для пользователя."""
    return db.query(models.Meal).filter(models.Meal.user_id == user_id).offset(skip).limit(limit).all()
