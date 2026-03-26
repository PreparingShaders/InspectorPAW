from sqlalchemy.orm import Session
from passlib.context import CryptContext
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
    # Хешируем пароль перед сохранением
    hashed_password = get_password_hash(user.password) # Используем новую функцию
    
    # Создаем объект модели SQLAlchemy
    db_user = models.User(
        email=user.email, 
        hashed_password=hashed_password,
        # Мы можем добавить сюда и другие поля из UserCreate, если они там будут
        date_of_birth=user.date_of_birth,
        gender=user.gender,
        height_cm=user.height_cm,
        goal=user.goal,
        goal_intensity=user.goal_intensity
    )
    
    # Добавляем пользователя в сессию и сохраняем в базу
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user
