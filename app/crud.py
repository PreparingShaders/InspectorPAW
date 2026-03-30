from sqlalchemy.orm import Session
from sqlalchemy import func
from passlib.context import CryptContext
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
    """Считает суммарные КБЖУ по сохраненным приемам пищи."""
    query = db.query(
        func.sum(models.Meal.total_calories).label("total_calories"),
        func.sum(models.Meal.total_protein).label("total_protein"),
        func.sum(models.Meal.total_fat).label("total_fat"),
        func.sum(models.Meal.total_carbohydrates).label("total_carbohydrates")
    ).filter(
        models.Meal.user_id == user_id,
        func.date(models.Meal.timestamp) >= start_date,
        func.date(models.Meal.timestamp) <= end_date
    )
    
    result = query.first()
    return result

# --- Meal CRUD ---

def create_meal(db: Session, meal: schemas.MealCreate, user_id: int) -> models.Meal:
    """Создает запись о приеме пищи с итоговыми КБЖУ."""
    db_meal = models.Meal(
        user_id=user_id,
        meal_type=meal.meal_type,
        total_calories=meal.total_calories,
        total_protein=meal.total_protein,
        total_fat=meal.total_fat,
        total_carbohydrates=meal.total_carbohydrates
    )
    db.add(db_meal)
    db.commit()
    db.refresh(db_meal)
    return db_meal

def get_meals_by_user(db: Session, user_id: int, skip: int = 0, limit: int = 100):
    """Получает историю приемов пищи пользователя."""
    return db.query(models.Meal).filter(models.Meal.user_id == user_id).offset(skip).limit(limit).all()
