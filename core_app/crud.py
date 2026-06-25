from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc, asc
from passlib.context import CryptContext
from datetime import date, datetime, timedelta
from . import models, schemas, utils
from .config import settings
from typing import List, Optional
import secrets

# Создаем контекст для хеширования паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def get_user(db: Session, user_id: int):
    """
    Получает пользователя по ID.
    """
    return db.query(models.User).filter(models.User.id == user_id).first()

def get_users(db: Session, skip: int = 0, limit: int = 100):
    """
    Получает список пользователей.
    """
    return db.query(models.User).offset(skip).limit(limit).all()

def get_user_by_email(db: Session, email: str):
    """
    Получает пользователя по email. Для аутентификации не требуется загружать
    связанные коллекции 'meals' и 'metrics'.
    """
    return db.query(models.User).filter(models.User.email == email).first()

def create_user(db: Session, user: schemas.UserCreate) -> models.User:
    hashed_password = get_password_hash(user.password)
    
    # Проверяем, есть ли уже пользователи в базе данных
    is_first_user = db.query(models.User).count() == 0
    
    # Генерируем код верификации
    verification_code = utils.generate_verification_code()
    verification_expires_at = datetime.now(settings.MSK_TZ) + timedelta(minutes=15)

    db_user = models.User(
        email=user.email,
        hashed_password=hashed_password,
        is_active=False,  # Пользователь неактивен до верификации email
        is_verified=False, # Email не верифицирован
        email_verification_code=verification_code,
        email_verification_expires_at=verification_expires_at,
        date_of_birth=user.date_of_birth,
        gender=user.gender,
        height_cm=user.height_cm,
        goal=user.goal,
        goal_intensity=user.goal_intensity,
        role=models.UserRole.ADMIN if is_first_user else models.UserRole.USER # Назначаем ADMIN, если это первый пользователь
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

# --- Email Verification CRUD ---
def get_user_by_verification_code(db: Session, email: str, code: str) -> Optional[models.User]:
    """Находит неактивного пользователя по email и коду верификации."""
    return db.query(models.User).filter(
        models.User.email == email,
        models.User.email_verification_code == code,
        models.User.is_active == False
    ).first()

def activate_user(db: Session, user: models.User) -> models.User:
    """Активирует пользователя и очищает код верификации."""
    user.is_active = True
    user.is_verified = True
    user.email_verification_code = None
    user.email_verification_expires_at = None
    db.commit()
    db.refresh(user)
    return user


# --- Password Reset CRUD ---

def create_password_reset_code(db: Session, user: models.User) -> str:
    """Генерирует и сохраняет 6-значный код сброса пароля."""
    code = utils.generate_verification_code()
    user.password_reset_token = code # Используем поле токена для хранения кода
    user.password_reset_expires_at = datetime.now(settings.MSK_TZ) + timedelta(minutes=15)
    db.commit()
    return code

def get_user_by_password_reset_code(db: Session, email: str, code: str) -> Optional[models.User]:
    """Находит пользователя по email и коду сброса пароля."""
    return db.query(models.User).filter(
        models.User.email == email,
        models.User.password_reset_token == code
    ).first()

def reset_password(db: Session, user: models.User, new_password: str) -> models.User:
    """Сбрасывает пароль пользователя и удаляет токен."""
    user.hashed_password = get_password_hash(new_password)
    user.password_reset_token = None
    user.password_reset_expires_at = None
    db.commit()
    db.refresh(user)
    return user

# --- UserMetrics CRUD ---

def create_user_metric(db: Session, metric: schemas.UserMetricsCreate, user_id: int) -> models.UserMetrics:
    """Создает новую запись метрик для пользователя."""
    db_metric = models.UserMetrics(**metric.dict(), user_id=user_id, timestamp=datetime.now(settings.MSK_TZ))
    db.add(db_metric)
    db.commit()
    db.refresh(db_metric)
    return db_metric

def get_latest_user_metric(db: Session, user_id: int) -> Optional[models.UserMetrics]:
    """Получает последнюю запись метрик пользователя."""
    return db.query(models.UserMetrics).filter(
        models.UserMetrics.user_id == user_id
    ).order_by(desc(models.UserMetrics.timestamp)).first()

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
    ).group_by(func.date(models.Meal.timestamp)).order_by(desc(func.date(models.Meal.timestamp)))

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

def count_meals_today(db: Session, user_id: int) -> int:
    """Считает количество приемов пищи пользователя за текущий день."""
    today = date.today()
    return db.query(models.Meal).filter(
        models.Meal.user_id == user_id,
        func.date(models.Meal.timestamp) == today
    ).count()

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
    """Создает запись о приеме пищи с итоговыми КБЖУ и оценкой качества."""
    ai_details = None
    if meal.ai_analysis_details:
        ai_details = []
        for item in meal.ai_analysis_details:
            if hasattr(item, "model_dump"):
                ai_details.append(item.model_dump())
            elif hasattr(item, "dict"):
                ai_details.append(item.dict())
            else:
                ai_details.append(item)

    db_meal = models.Meal(
        user_id=user_id,
        meal_type=meal.meal_type,
        food_name=meal.food_name,
        total_calories=meal.total_calories,
        total_protein=meal.total_protein,
        total_fat=meal.total_fat,
        total_carbohydrates=meal.total_carbohydrates,
        total_fiber=meal.total_fiber or 0,
        ai_comment=meal.ai_comment,
        ai_score=meal.ai_score,
        oil_absorption_score=meal.oil_absorption_score,
        ultra_processing_score=meal.ultra_processing_score,
        hidden_ingredients_risk=meal.hidden_ingredients_risk,
        ai_analysis_details=ai_details,
        amino_acid_score=meal.amino_acid_score,
        animal_protein_ratio=meal.animal_protein_ratio,
        protein_density=meal.protein_density,
        omega6_omega3_ratio=meal.omega6_omega3_ratio,
        trans_fat_ratio=meal.trans_fat_ratio,
        saturated_fat_ratio=meal.saturated_fat_ratio,
        monounsaturated_fat_ratio=meal.monounsaturated_fat_ratio,
        polyunsaturated_fat_ratio=meal.polyunsaturated_fat_ratio,
        glycemic_load=meal.glycemic_load,
        fiber_to_carb_ratio=meal.fiber_to_carb_ratio,
        added_sugar_ratio=meal.added_sugar_ratio,
        nova_processing_level=meal.nova_processing_level,
        protein_ai_tip=meal.protein_ai_tip,
        fat_ai_tip=meal.fat_ai_tip,
        carb_ai_tip=meal.carb_ai_tip,
        processing_ai_tip=meal.processing_ai_tip,
        timestamp=datetime.now(settings.MSK_TZ)
    )
    db.add(db_meal)
    db.commit()
    db.refresh(db_meal)
    return db_meal

def get_meals_by_user(db: Session, user_id: int, skip: int = 0, limit: int = 100):
    """Получает историю приемов пищи пользователя за последние 7 дней."""
    seven_days_ago = datetime.now(settings.MSK_TZ) - timedelta(days=7)
    return db.query(models.Meal).filter(
        models.Meal.user_id == user_id,
        models.Meal.timestamp >= seven_days_ago
    ).order_by(models.Meal.timestamp.desc()).offset(skip).limit(limit).all()