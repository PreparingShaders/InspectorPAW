from sqlalchemy import Column, Integer, String, Boolean, Date, Float, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base
import enum

class UserRole(enum.Enum):
    USER = "user"
    ADMIN = "admin"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)

    # Новые поля для ролей и премиум-статуса
    role = Column(Enum(UserRole), default=UserRole.USER, nullable=False)
    is_premium = Column(Boolean, default=False)

    # Поля для отслеживания лимитов бесплатных пользователей
    photo_uploads_today = Column(Integer, default=0, nullable=False)
    last_upload_date = Column(Date, server_default=func.current_date(), nullable=False) # Изменено с func.now() на func.current_date()

    # Профиль пользователя
    date_of_birth = Column(Date, nullable=True)
    gender = Column(String, nullable=True) # 'male', 'female', 'other'
    height_cm = Column(Integer, nullable=True)
    activity_level = Column(String, nullable=True, default='sedentary') # sedentary, light, moderate, active, very_active

    # Новые поля для цели пользователя
    goal = Column(String, nullable=True) # 'fat_loss', 'maintenance', 'mass_gain'
    goal_intensity = Column(Float, nullable=True, default=0.0) # от -1.0 до 1.0

    # Связь с метриками пользователя
    metrics = relationship("UserMetrics", back_populates="user")

    # Связь с приемами пищи
    meals = relationship("Meal", back_populates="user")

class UserMetrics(Base):
    __tablename__ = "user_metrics"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    weight_kg = Column(Float, nullable=True)
    body_fat_percentage = Column(Float, nullable=True) # Процент жира в организме
    active_calories = Column(Integer, nullable=True)
    sleep_hours = Column(Float, nullable=True)

    # Связь с пользователем
    user = relationship("User", back_populates="metrics")

class Meal(Base):
    __tablename__ = "meals"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    meal_type = Column(String, nullable=True) # 'breakfast', 'lunch', 'dinner', 'snack'
    food_name = Column(String, nullable=True) # Добавлено поле для названия блюда
    
    # Итоговые КБЖУ для приема пищи
    total_calories = Column(Float, default=0.0)
    total_protein = Column(Float, default=0.0)
    total_fat = Column(Float, default=0.0)
    total_carbohydrates = Column(Float, default=0.0)

    user = relationship("User", back_populates="meals")
