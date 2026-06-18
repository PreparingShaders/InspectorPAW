from sqlalchemy import Column, Integer, String, Boolean, Date, Float, DateTime, ForeignKey, Enum as SAEnum, JSON
from datetime import datetime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base
import enum


class UserRole(enum.Enum):
    USER = "user"
    ADMIN = "admin"


class ProcessingLevel(enum.Enum):
    WHOLE = "WHOLE"
    MINIMALLY_PROCESSED = "MINIMALLY_PROCESSED"
    ULTRA_PROCESSED = "ULTRA_PROCESSED"


class MicronutrientDensity(enum.Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    force_password_change_on_login = Column(Boolean, default=False, nullable=False)

    # Поля для верификации email
    is_verified = Column(Boolean, default=False, nullable=False)
    email_verification_code = Column(String, nullable=True)
    email_verification_expires_at = Column(DateTime(timezone=True), nullable=True)

    # Поля для ролей и премиум-статуса
    role = Column(SAEnum(UserRole), default=UserRole.USER, nullable=False)
    premium_expires_at = Column(DateTime(timezone=True), nullable=True)

    # Поля для сброса пароля
    password_reset_token = Column(String, nullable=True, unique=True)
    password_reset_expires_at = Column(DateTime(timezone=True), nullable=True)

    # Профиль пользователя
    date_of_birth = Column(Date, nullable=True)
    gender = Column(String, nullable=True)  # 'male', 'female', 'other'
    height_cm = Column(Integer, nullable=True)
    activity_level = Column(String, nullable=True,
                            default='sedentary')  # sedentary, light, moderate, active, very_active

    # Новые поля для цели пользователя
    goal = Column(String, nullable=True)  # 'fat_loss', 'maintenance', 'mass_gain'
    goal_intensity = Column(Float, nullable=True, default=0.0)  # от -1.0 до 1.0

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
    body_fat_percentage = Column(Float, nullable=True)
    active_calories = Column(Integer, nullable=True)
    sleep_hours = Column(Float, nullable=True)

    # Связь с пользователем
    user = relationship("User", back_populates="metrics")


class Meal(Base):
    __tablename__ = "meals"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    meal_type = Column(String, nullable=True)  # 'breakfast', 'lunch', 'dinner', 'snack'
    food_name = Column(String, nullable=True)

    # Итоговые КБЖУ для приема пищи
    total_calories = Column(Float, default=0.0)
    total_protein = Column(Float, default=0.0)
    total_fat = Column(Float, default=0.0)
    total_carbohydrates = Column(Float, default=0.0)
    total_fiber = Column(Float, default=0.0)  # ПРАВКА: Клетчатка

    # Оценка качества пищи от AI
    ai_comment = Column(String, nullable=True)
    ai_score = Column(Integer, nullable=True)  # Общая оценка качества (0-100)

    # ПРАВКА: Числовые шкалы от 0 до 10 для гибкого скоринга на бэкенде
    oil_absorption_score = Column(Integer, nullable=True)
    ultra_processing_score = Column(Integer, nullable=True)
    hidden_ingredients_risk = Column(Integer, nullable=True)

    # ПРАВКА: Детализация: хранение 7 пунктов по каждому ингредиенту
    ai_analysis_details = Column(JSON, nullable=True, default=list)

    # Старые поля для совместимости (не трогаем, чтобы Alembic не пытался их удалить)
    processing_level = Column(SAEnum(ProcessingLevel), nullable=True)
    satiety_index = Column(Integer, nullable=True)
    micronutrient_density = Column(SAEnum(MicronutrientDensity), nullable=True)

    user = relationship("User", back_populates="meals")


class TelegramPasswordResetToken(Base):
    __tablename__ = 'telegram_password_reset_tokens'
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    token = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(),
                        nullable=False)  # ПРАВКА: единый таймзон-дефолт базы
    is_used = Column(Boolean, default=False, nullable=False)

    user = relationship("User")