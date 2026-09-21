from sqlalchemy import Column, Integer, String, Boolean, Date, Float, DateTime, ForeignKey, Enum as SAEnum, JSON, Index, Text, func
from datetime import datetime, timezone
from sqlalchemy.orm import relationship, declared_attr
from .database import Base
import enum


class UserRole(enum.Enum):
    USER = "user"
    ADMIN = "admin"


class NOVAProcessingLevel(enum.Enum):
    NOVA_1 = 1
    NOVA_2 = 2
    NOVA_3 = 3
    NOVA_4 = 4


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

    # Refresh token для долгих сессий
    refresh_token = Column(String, nullable=True, unique=True)
    refresh_token_expires_at = Column(DateTime(timezone=True), nullable=True)

    # Профиль пользователя
    date_of_birth = Column(Date, nullable=True)
    gender = Column(String, nullable=True)
    height_cm = Column(Integer, nullable=True)
    activity_level = Column(String, nullable=True, default='sedentary')

    # Новые поля для цели пользователя
    goal = Column(String, nullable=True)
    goal_intensity = Column(Float, nullable=True, default=0.0)

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
    __table_args__ = (
        Index("ix_meals_user_timestamp", "user_id", "timestamp"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    meal_type = Column(String, nullable=True)
    food_name = Column(String, nullable=True)

    total_calories = Column(Float, default=0.0)
    total_protein = Column(Float, default=0.0)
    total_fat = Column(Float, default=0.0)
    total_carbohydrates = Column(Float, default=0.0)
    total_fiber = Column(Float, default=0.0)

    ai_comment = Column(String, nullable=True)
    ai_score = Column(Integer, nullable=True)

    oil_absorption_score = Column(Integer, nullable=True)
    ultra_processing_score = Column(Integer, nullable=True)
    hidden_ingredients_risk = Column(Integer, nullable=True)

    ai_analysis_details = Column(JSON, nullable=True, default=list)

    amino_acid_score = Column(Float, nullable=True)
    animal_protein_ratio = Column(Float, nullable=True)
    protein_density = Column(Float, nullable=True)
    omega6_omega3_ratio = Column(Float, nullable=True)
    trans_fat_ratio = Column(Float, nullable=True)
    saturated_fat_ratio = Column(Float, nullable=True)
    monounsaturated_fat_ratio = Column(Float, nullable=True)
    polyunsaturated_fat_ratio = Column(Float, nullable=True)
    glycemic_load = Column(Float, nullable=True)
    fiber_to_carb_ratio = Column(Float, nullable=True)
    added_sugar_ratio = Column(Float, nullable=True)
    nova_processing_level = Column(Integer, nullable=True)

    protein_ai_tip = Column(String, nullable=True)
    fat_ai_tip = Column(String, nullable=True)
    carb_ai_tip = Column(String, nullable=True)
    processing_ai_tip = Column(String, nullable=True)

    user = relationship("User", back_populates="meals")


class DailyNutritionSummary(Base):
    __tablename__ = "daily_nutrition_summaries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(Date, nullable=False)
    ai_advice = Column(String, nullable=True)
    ai_advice_model = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")


class ExerciseLibrary(Base):
    __tablename__ = "exercise_library"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    muscle_group = Column(String, nullable=True)
    equipment = Column(String, nullable=True)

    entries = relationship("WorkoutExercise", back_populates="exercise")


class WorkoutSession(Base):
    __tablename__ = "workout_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(Date, nullable=False)
    name = Column(String, nullable=True)
    duration_min = Column(Integer, nullable=True)
    feeling = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)
    is_template = Column(Boolean, default=False)
    template_id = Column(Integer, ForeignKey("workout_sessions.id"), nullable=True)
    is_completed = Column(Boolean, default=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User")
    exercises = relationship("WorkoutExercise", back_populates="session",
                             cascade="all, delete-orphan",
                             order_by="WorkoutExercise.sort_order")


class WorkoutExercise(Base):
    __tablename__ = "workout_exercises"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("workout_sessions.id"), nullable=False)
    exercise_id = Column(Integer, ForeignKey("exercise_library.id"), nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)
    rpe = Column(Float, nullable=True)

    session = relationship("WorkoutSession", back_populates="exercises")
    exercise = relationship("ExerciseLibrary", back_populates="entries")
    sets = relationship("WorkoutSet", back_populates="exercise_entry",
                        cascade="all, delete-orphan",
                        order_by="WorkoutSet.set_number")


class WorkoutSet(Base):
    __tablename__ = "workout_sets"

    id = Column(Integer, primary_key=True, index=True)
    exercise_entry_id = Column(Integer, ForeignKey("workout_exercises.id"), nullable=False)
    set_number = Column(Integer, nullable=False)
    weight_kg = Column(Float, nullable=True)
    reps = Column(Integer, nullable=True)
    rpe = Column(Float, nullable=True)
    is_warmup = Column(Boolean, default=False)
    is_done = Column(Boolean, default=False)

    exercise_entry = relationship("WorkoutExercise", back_populates="sets")


class TelegramPasswordResetToken(Base):
    __tablename__ = 'telegram_password_reset_tokens'
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    token = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(),
                        nullable=False)
    is_used = Column(Boolean, default=False, nullable=False)

    user = relationship("User")