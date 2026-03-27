from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date
from passlib.context import CryptContext
from typing import List
from datetime import date
from . import models, schemas

# Создаем контекст для хеширования паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def create_user(db: Session, user: schemas.UserCreate):
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
    """Считает суммарные КБЖУ, используя быстрые денормализованные поля."""
    query = db.query(
        func.sum(models.Meal.total_calories).label("total_calories"),
        func.sum(models.Meal.total_protein).label("total_protein"),
        func.sum(models.Meal.total_fat).label("total_fat"),
        func.sum(models.Meal.total_carbohydrates).label("total_carbohydrates")
    ).filter(models.Meal.user_id == user_id)\
     .filter(models.Meal.status == 'confirmed')\
     .filter(cast(models.Meal.timestamp, Date) >= start_date)\
     .filter(cast(models.Meal.timestamp, Date) <= end_date)
    
    result = query.first()
    return result

# --- FoodItem CRUD ---

def get_or_create_food_item(db: Session, item: schemas.MealFoodItemCreate) -> models.FoodItem:
    """Находит продукт по названию или создает новый, если его КБЖУ предоставлены."""
    db_food_item = db.query(models.FoodItem).filter(func.lower(models.FoodItem.name) == func.lower(item.name)).first()
    if db_food_item:
        return db_food_item
    
    # Создаем новый продукт, только если есть полные данные
    if all([item.calories is not None, item.protein is not None, item.fat is not None, item.carbohydrates is not None]):
        new_food_item = models.FoodItem(
            name=item.name,
            calories=item.calories,
            protein=item.protein,
            fat=item.fat,
            carbohydrates=item.carbohydrates
        )
        db.add(new_food_item)
        db.commit()
        db.refresh(new_food_item)
        return new_food_item
    return None # Не можем создать продукт без данных

# --- Meal CRUD ---

def get_meal_by_id(db: Session, meal_id: int):
    return db.query(models.Meal).filter(models.Meal.id == meal_id).first()

def create_user_meal(db: Session, meal: schemas.MealCreate, user_id: int):
    """Создает пустой 'контейнер' для приема пищи."""
    db_meal = models.Meal(**meal.dict(), user_id=user_id, status='created')
    db.add(db_meal)
    db.commit()
    db.refresh(db_meal)
    return db_meal

def update_meal_photo_and_description(db: Session, meal_id: int, photo_url: str, description: str):
    """Обновляет фото, описание и статус приема пищи."""
    db_meal = get_meal_by_id(db, meal_id)
    if db_meal:
        db_meal.photo_url = photo_url
        db_meal.description = description
        db_meal.status = 'pending_analysis'
        db.commit()
        db.refresh(db_meal)
    return db_meal

def confirm_meal_analysis(db: Session, meal_id: int, confirmed_items: List[schemas.MealFoodItemCreate]):
    """Главная функция: подтверждает анализ, сохраняет продукты и считает итоги."""
    db_meal = get_meal_by_id(db, meal_id)
    if not db_meal:
        return None

    # 1. Очищаем старые продукты, если они были
    db.query(models.MealFoodItem).filter(models.MealFoodItem.meal_id == meal_id).delete()

    total_calories = 0
    total_protein = 0
    total_fat = 0
    total_carbohydrates = 0

    # 2. Добавляем новые подтвержденные продукты
    for item in confirmed_items:
        db_food_item = get_or_create_food_item(db, item)
        if not db_food_item:
            continue # Пропускаем, если продукт не найден и не может быть создан

        db_meal_item = models.MealFoodItem(
            meal_id=meal_id,
            food_item_id=db_food_item.id,
            quantity_grams=item.quantity_grams
        )
        db.add(db_meal_item)

        # 3. Считаем КБЖУ для денормализации
        ratio = item.quantity_grams / 100.0
        total_calories += db_food_item.calories * ratio
        total_protein += db_food_item.protein * ratio
        total_fat += db_food_item.fat * ratio
        total_carbohydrates += db_food_item.carbohydrates * ratio

    # 4. Обновляем денормализованные поля и статус
    db_meal.total_calories = total_calories
    db_meal.total_protein = total_protein
    db_meal.total_fat = total_fat
    db_meal.total_carbohydrates = total_carbohydrates
    db_meal.status = 'confirmed'
    
    db.commit()
    db.refresh(db_meal)
    return db_meal

def get_meals_by_user(db: Session, user_id: int, skip: int = 0, limit: int = 100):
    return db.query(models.Meal).filter(models.Meal.user_id == user_id).offset(skip).limit(limit).all()
