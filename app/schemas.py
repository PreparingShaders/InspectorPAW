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
    food_item_id: int
    quantity_grams: float

class MealFoodItemCreate(MealFoodItemBase):
    pass

class MealFoodItem(MealFoodItemBase):
    id: int
    meal_id: int
    food_item: FoodItem # Включаем полную информацию о продукте

    class Config:
        from_attributes = True

# --- Meal Schemas ---
class MealBase(BaseModel):
    meal_type: Optional[str] = None # 'breakfast', 'lunch', 'dinner', 'snack'
    photo_url: Optional[str] = None

class MealCreate(MealBase):
    food_items: List[MealFoodItemCreate] = []

class Meal(MealBase):
    id: int
    user_id: int
    timestamp: datetime
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
    # Для обновления профиля пароль не обязателен
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(None, min_length=8, max_length=72)

class User(UserBase):
    id: int
    is_active: bool
    metrics: List[UserMetrics] = []
    meals: List[Meal] = [] # Добавляем приемы пищи к данным пользователя

    class Config:
        from_attributes = True
