from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc
from passlib.context import CryptContext
from datetime import date
from . import models, schemas
from typing import List, Optional

# Создаем контекст для хеширования паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def get_user_by_email(db: Session, email: str):
    """
    Получает пользователя по email с немедленной загрузкой связанных
    коллекций 'meals' и 'metrics' для предотвращения DetachedInstanceError.
    """
    return db.query(models.User).options(
        joinedload(models.User.meals),
        joinedload(models.User.metrics)
    ).filter(models.User.email == email).first()

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

def update_user(db: Session, user: models.User, user_update: schemas.UserUpdate) -> models.User:
    """Обновляет профиль пользователя."""
    db.add(user)
    update_data = user_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        if key == "password" and value:
            hashed_password = get_password_hash(value)
            setattr(user, "hashed_password", hashed_password)
        else:
            setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return user

# --- UserMetrics CRUD ---

def create_user_metric(db: Session, metric: schemas.UserMetricsCreate, user_id: int) -> models.UserMetrics:
    """Создает новую запись метрик для пользователя."""
    db_metric = models.UserMetrics(**metric.dict(), user_id=user_id)
    db.add(db_metric)
    db.commit()
    db.refresh(db_metric)
    return db_metric

def get_latest_user_weight(db: Session, user_id: int) -> Optional[float]:
    """Получает последний зафиксированный вес пользователя."""
    latest_metric = db.query(models.UserMetrics.weight_kg).filter(
        models.UserMetrics.user_id == user_id,
        models.UserMetrics.weight_kg.isnot(None)
    ).order_by(desc(models.UserMetrics.timestamp)).first()
    return latest_metric[0] if latest_metric else None

# --- Stats CRUD ---

def get_daily_stats_for_period(db: Session, user_id: int, start_date: date, end_date: date) -> List[dict]:
    """Считает и группирует статистику по дням, возвращая список словарей."""
    query = db.query(
        func.date(models.Meal.timestamp).label("date"),
        func.sum(models.Meal.total_calories).label("total_calories"),
        func.sum(models.Meal.total_protein).label("total_protein"),
        func.sum(models.Meal.total_fat).label("total_fat"),
        func.sum(models.Meal.total_carbohydrates).label("total_carbohydrates")
    ).filter(
        models.Meal.user_id == user_id,
        func.date(models.Meal.timestamp) >= start_date,
        func.date(models.Meal.timestamp) <= end_date
    ).group_by(func.date(models.Meal.timestamp)).order_by(func.date(models.Meal.timestamp))

    results = query.all()
    return [
        {
            "date": r.date,
            "total_calories": r.total_calories or 0,
            "total_protein": r.total_protein or 0,
            "total_fat": r.total_fat or 0,
            "total_carbohydrates": r.total_carbohydrates or 0,
        } for r in results
    ]

def get_user_stats_by_period(db: Session, user_id: int, start_date: date, end_date: date):
    """Считает общую сумму КБЖУ за период."""
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
    return query.first()


# --- Meal CRUD ---

def get_meal_by_id(db: Session, meal_id: int):
    """Находит прием пищи по ID."""
    return db.query(models.Meal).filter(models.Meal.id == meal_id).first()

def delete_meal(db: Session, meal_id: int):
    """Удаляет прием пищи по ID."""
    db_meal = db.query(models.Meal).filter(models.Meal.id == meal_id).first()
    if db_meal:
        db.delete(db_meal)
        db.commit()
    return db_meal

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
