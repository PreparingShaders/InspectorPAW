from sqlalchemy import Column, Integer, String, Boolean, Date, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)

    # Профиль пользователя
    date_of_birth = Column(Date, nullable=True)
    gender = Column(String, nullable=True) # 'male', 'female', 'other'
    height_cm = Column(Integer, nullable=True)

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
    photo_url = Column(String, nullable=True)
    
    # Новые поля для интерактивного анализа и денормализации
    description = Column(String, nullable=True)
    status = Column(String, default='created', nullable=False) # created, pending_confirmation, confirmed
    
    # Денормализованные итоговые КБЖУ для быстрой статистики
    total_calories = Column(Float, default=0.0)
    total_protein = Column(Float, default=0.0)
    total_fat = Column(Float, default=0.0)
    total_carbohydrates = Column(Float, default=0.0)

    user = relationship("User", back_populates="meals")
    food_items = relationship("MealFoodItem", back_populates="meal", cascade="all, delete-orphan")

class FoodItem(Base):
    __tablename__ = "food_items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    calories = Column(Float, nullable=False)
    protein = Column(Float, nullable=False)
    fat = Column(Float, nullable=False)
    carbohydrates = Column(Float, nullable=False)

    meals = relationship("MealFoodItem", back_populates="food_item")

class MealFoodItem(Base):
    __tablename__ = "meal_food_items"

    id = Column(Integer, primary_key=True, index=True)
    meal_id = Column(Integer, ForeignKey("meals.id"), nullable=False)
    food_item_id = Column(Integer, ForeignKey("food_items.id"), nullable=False)
    quantity_grams = Column(Float, nullable=False)

    meal = relationship("Meal", back_populates="food_items")
    food_item = relationship("FoodItem", back_populates="meals")
