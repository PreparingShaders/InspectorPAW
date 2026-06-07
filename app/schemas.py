from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List, Dict, Any
from datetime import date, datetime
import re
from .models import UserRole

# --- AI Hub Chat Schema ---
class AIChatRequest(BaseModel):
    model: str
    prompt: str
    history: List[Dict[str, str]]

class AIModel(BaseModel):
    id: str
    name: Optional[str] = None

# --- Target Calculation Schemas ---
class CalculatedTargets(BaseModel):
    target_calories: int
    target_protein: int
    target_fat: int
    target_carbohydrates: int

class TargetCalculationRequest(BaseModel):
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    height_cm: Optional[int] = None
    weight_kg: Optional[float] = None
    body_fat_percentage: Optional[float] = None
    activity_level: Optional[str] = None
    goal: Optional[str] = None
    goal_intensity: Optional[float] = None

# --- Token Schemas ---
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

# --- New Weekly Summary Schemas ---
class DailyStatDetail(BaseModel):
    date: date
    consumed_calories: float
    consumed_protein: float = 0
    consumed_fat: float = 0
    consumed_carbohydrates: float = 0
    target_calories: float
    target_protein: float = 0
    target_fat: float = 0
    target_carbohydrates: float = 0
    status: str
    # Новые поля для ProgressLab Score
    daily_score: Optional[int] = None
    status_color: Optional[str] = None
    status_message: Optional[Dict[str, Any]] = None
    y_axis_pos: Optional[int] = None
    time_progress: Optional[float] = None


class AverageSummary(BaseModel):
    avg_calories: float
    avg_protein: float
    avg_fat: float
    avg_carbohydrates: float
    target_calories: float
    target_protein: float
    target_fat: float
    target_carbohydrates: float

class WeeklySummaryResponse(BaseModel):
    daily_breakdown: List[DailyStatDetail]
    period_summary: AverageSummary
    progress_lab_summary: Optional[Dict[str, Any]] = None

# --- Stats Schemas ---
class DailyStat(BaseModel):
    date: date
    total_calories: float = 0
    total_protein: float = 0
    total_fat: float = 0
    total_carbohydrates: float = 0

class PeriodSummary(BaseModel):
    total_calories: float = 0
    total_protein: float = 0
    total_fat: float = 0
    total_carbohydrates: float = 0
    average_daily_calories: float = 0
    average_daily_protein: float = 0
    average_daily_fat: float = 0
    average_daily_carbohydrates: float = 0

class StatsResponse(BaseModel):
    period_summary: PeriodSummary
    daily_breakdown: List[DailyStat]

class StatsSummary(BaseModel):
    total_calories: float
    total_protein: float
    total_fat: float
    total_carbohydrates: float
    start_date: date
    end_date: date

# --- Dashboard Stats Schema ---
class DashboardStats(BaseModel):
    target_calories: float
    target_protein: float
    target_fat: float
    target_carbohydrates: float
    consumed_calories: float
    consumed_protein: float
    consumed_fat: float
    consumed_carbohydrates: float

# --- Meal Totals Schema (для передачи КБЖУ) ---
class MealTotals(BaseModel):
    food_name: Optional[str] = None
    total_calories: float = 0
    total_protein: float = 0
    total_fat: float = 0
    total_carbohydrates: float = 0

# --- Analysis Schemas ---
class AnalysisResponse(BaseModel):
    suggested_totals: MealTotals
    ai_response_text: str
    ai_coach_advice: Optional[str] = None
    nutrition_model_used: Optional[str] = None # Модель для анализа КБЖУ
    coach_model_used: Optional[str] = None      # Модель для совета

# --- Meal Schemas ---
class MealBase(BaseModel):
    meal_type: Optional[str] = None
    food_name: Optional[str] = None

class MealCreate(MealBase, MealTotals):
    ai_coach_advice: Optional[str] = None

class Meal(MealBase, MealTotals):
    id: int
    user_id: int
    timestamp: datetime
    class Config:
        from_attributes = True

# --- UserMetrics Schemas ---
class UserMetricsBase(BaseModel):
    weight_kg: Optional[float] = None
    body_fat_percentage: Optional[float] = None
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
    activity_level: Optional[str] = None
    goal: Optional[str] = None
    goal_intensity: Optional[float] = Field(None, ge=-3.0, le=3.0)

class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=72)
    password_confirm: str = Field(..., min_length=8, max_length=72)

    @validator('password')
    def validate_password_strength(cls, v):
        if not re.search(r'[A-Z]', v):
            raise ValueError('Пароль должен содержать хотя бы одну заглавную букву')
        if not re.search(r'[a-z]', v):
            raise ValueError('Пароль должен содержать хотя бы одну строчную букву')
        if not re.search(r'\d', v):
            raise ValueError('Пароль должен содержать хотя бы одну цифру')
        return v

    @validator('password_confirm')
    def passwords_match(cls, v, values, **kwargs):
        if 'password' in values and v != values['password']:
            raise ValueError('Пароли не совпадают')
        return v

class UserUpdate(UserBase):
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(None, min_length=8, max_length=72)

class User(UserBase):
    id: int
    is_active: bool
    is_verified: bool # Добавлено
    verification_token: Optional[str] = None # Добавлено
    verification_token_expires_at: Optional[datetime] = None # Добавлено
    role: UserRole
    premium_expires_at: Optional[datetime] = None # Изменено с is_premium на premium_expires_at
    force_password_change_on_login: bool = False
    metrics: List[UserMetrics] = []
    meals: List[Meal] = []
    class Config:
        from_attributes = True

class UserWithTargets(User):
    calculated_targets: Optional[CalculatedTargets] = None

# --- Admin Schemas ---
class UserAdminView(User):
    pass

class UserUpdateAdmin(BaseModel):
    role: Optional[UserRole] = None
    premium_expires_at: Optional[datetime] = None
    is_active: Optional[bool] = None

class PasswordResetRequest(BaseModel):
    user_id: int
    new_password: str = Field(..., min_length=8, max_length=72)

# --- Password Reset Schemas ---
class PasswordResetRequestPayload(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8, max_length=72)

class PasswordResetTokenResponse(BaseModel):
    email: EmailStr
    reset_token: str
    expires_at: datetime

# --- Email Verification Schemas ---
class EmailVerificationResponse(BaseModel):
    message: str