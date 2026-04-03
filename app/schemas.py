from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import date, datetime

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
    consumed_protein: float = 0  # Добавлено
    consumed_fat: float = 0      # Добавлено
    consumed_carbohydrates: float = 0 # Добавлено
    target_calories: float
    status: str

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
    total_calories: float = 0
    total_protein: float = 0
    total_fat: float = 0
    total_carbohydrates: float = 0

# --- Analysis Schemas ---
class AnalysisResponse(BaseModel):
    suggested_totals: MealTotals
    ai_response_text: str

# --- Meal Schemas ---
class MealBase(BaseModel):
    meal_type: Optional[str] = None

class MealCreate(MealBase, MealTotals):
    pass

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
    goal_intensity: Optional[float] = Field(None, ge=-1.0, le=1.0)

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

class UserWithTargets(User):
    calculated_targets: Optional[CalculatedTargets] = None
