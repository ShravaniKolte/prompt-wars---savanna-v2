from pydantic import BaseModel, EmailStr, Field
from typing import Optional


# ── Auth ──────────────────────────────────────────────────────────────────────

class SignupRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    email: EmailStr
    password: str = Field(..., min_length=6)
    city: Optional[str] = ""


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


# ── Daily Log ─────────────────────────────────────────────────────────────────

class LogRequest(BaseModel):
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")  # YYYY-MM-DD
    travel_kg:  float = Field(0.0, ge=0, le=20)
    food_kg:    float = Field(0.0, ge=0, le=20)
    energy_kg:  float = Field(0.0, ge=0, le=20)
    shop_kg:    float = Field(0.0, ge=0, le=20)
    deed_kg:    float = Field(0.0, ge=-5, le=0)   # offsets are negative
    travel_name: Optional[str] = ""
    food_name:   Optional[str] = ""
    energy_name: Optional[str] = ""
    shop_name:   Optional[str] = ""
    deed_name:   Optional[str] = ""


class LogResponse(BaseModel):
    id: int
    date: str
    travel_kg: float
    food_kg: float
    energy_kg: float
    shop_kg: float
    deed_kg: float
    total_kg: float
    travel_name: str
    food_name: str
    energy_name: str
    shop_name: str
    deed_name: str
    created_at: str


# ── Habit ─────────────────────────────────────────────────────────────────────

class HabitRequest(BaseModel):
    title: str = Field(..., max_length=200)


class HabitProgress(BaseModel):
    days_delta: int = Field(1, ge=1, le=7)


# ── Community / Leaderboard ───────────────────────────────────────────────────

class LeaderboardEntry(BaseModel):
    rank: int
    name: str
    avg_kg: float
    streak_days: int
    is_you: bool = False
