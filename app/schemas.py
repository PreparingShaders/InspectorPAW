from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import date, datetime

# --- Token Schemas ---
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

# --- Stats Schemas ---
class StatsSummary(BaseModel):
    total_calories: float = 0
    total_protein: float = 0
    total_fat: float = 0
    total_carbohydrates: float = 0
    start_date: date
    end_date: date

# --- FoodItem Schemas ---
class FoodItemBase(BaseModel):
    name: str
    calories: float
    protein: float
    fat: float
    carbohydrates: float

class FoodItemCreate(FoodItemBase):
    pass

class FoodItem(FoodItemBase):
    id: int

    class Config:
        from_attributes = True

# --- MealFoodItem Schemas ---
class MealFoodItemBase(BaseModel):
    # Используется для создания и подтверждения
    name: str
    quantity_grams: float
    # Поля КБЖУ опциональны, т.к. при создании они могут быть неизвестны
    calories: Optional[float] = None
    protein: Optional[float] = None
    fat: Optional[float] = None
    carbohydrates: Optional[float] = None

class MealFoodItemCreate(MealFoodItemBase):
    pass

class MealFoodItem(MealFoodItemBase):
    id: int
    meal_id: int
    food_item: FoodItem # Включаем полную информацию о продукте

    class Config:
        from_attributes = True

# --- Analysis Schemas ---
class AnalysisConfirmation(BaseModel):
    # Схема для подтверждения финального списка продуктов
    items: List[MealFoodItemCreate]

# --- Meal Schemas ---
class MealBase(BaseModel):
    meal_type: Optional[str] = None # 'breakfast', 'lunch', 'dinner', 'snack'
    description: Optional[str] = None

class MealCreate(MealBase):
    # При создании приема пищи список продуктов пуст
    pass

class Meal(MealBase):
    id: int
    user_id: int
    timestamp: datetime
    status: str
    photo_url: Optional[str] = None
    
    # Денормализованные поля
    total_calories: float
    total_protein: float
    total_fat: float
    total_carbohydrates: float

    food_items: List[MealFoodItem] = []

    class Config:
        from_attributes = True

# --- UserMetrics Schemas ---
class UserMetricsBase(BaseModel):
    weight_kg: Optional[float] = None
    active_calories: Optional[int] = None
    sleep_hours: Optional[float] = None

class UserMetricsCreate(UserMetricsBase):
    pass

class UserMetrics(UserMetricsBase):
    id: int
    user_id: int
    timestamp: datetime

    class Config:
        from_attributes = True

# --- User Schemas ---
class UserBase(BaseModel):
    email: EmailStr
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    height_cm: Optional[int] = None
    goal: Optional[str] = None # 'fat_loss', 'maintenance', 'mass_gain'
    goal_intensity: Optional[float] = Field(None, ge=-1.0, le=1.0) # Валидация диапазона

class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=72)

class UserUpdate(UserBase):
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(None, min_length=8, max_length=72)

class User(UserBase):
    id: int
    is_active: bool
    metrics: List[UserMetrics] = []
    meals: List[Meal] = []

    class Config:
        from_attributes = True
