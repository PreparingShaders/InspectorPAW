from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import date, datetime

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
    # Добавляем валидацию длины пароля
    password: str = Field(..., min_length=8, max_length=72)

class UserUpdate(UserBase):
    # Для обновления профиля пароль не обязателен
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(None, min_length=8, max_length=72)

class User(UserBase):
    id: int
    is_active: bool
    # Возвращаем последние метрики вместе с данными пользователя
    metrics: List[UserMetrics] = []

    class Config:
        from_attributes = True
