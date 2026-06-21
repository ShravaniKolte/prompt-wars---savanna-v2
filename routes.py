from fastapi import APIRouter, HTTPException, Depends, status
from datetime import date, timedelta, datetime
from typing import List, Optional
import random

from database import get_db
from auth import (
    hash_password, verify_password, create_access_token,
    get_current_user
)
from schemas import (
    SignupRequest, LoginRequest, TokenResponse,
    LogRequest, LogResponse,
    HabitRequest, HabitProgress,
    LeaderboardEntry,
)

PARIS_TARGET = 2.30  # kg CO₂ / day


# ══════════════════════════════════════════════════════════════════════════════
#  AUTH ROUTER
# ══════════════════════════════════════════════════════════════════════════════

auth_router = APIRouter(prefix="/auth", tags=["Auth"])


@auth_router.post("/signup", response_model=TokenResponse, status_code=201)
def signup(body: SignupRequest):
    conn = get_db()
    try:
        existing = conn.execute("SELECT id FROM users WHERE email=?", (body.email,)).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="Email already registered")

        hashed = hash_password(body.password)
        cur = conn.execute(
            "INSERT INTO users (name, email, password, city) VALUES (?,?,?,?)",
            (body.name, body.email, hashed, body.city or "")
        )
        conn.commit()
        user_id = cur.lastrowid
    finally:
        conn.close()

    token = create_access_token({"sub": str(user_id), "email": body.email, "name": body.name})
    return {"access_token": token, "user": {"id": user_id, "name": body.name, "email": body.email}}


@auth_router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest):
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM users WHERE email=?", (body.email,)).fetchone()
    finally:
        conn.close()

    if not row or not verify_password(body.password, row["password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token({"sub": str(row["id"]), "email": row["email"], "name": row["name"]})
    return {"access_token": token, "user": {"id": row["id"], "name": row["name"], "email": row["email"]}}


@auth_router.get("/me")
def me(user=Depends(get_current_user)):
    conn = get_db()
    try:
        row = conn.execute("SELECT id, name, email, city, created_at FROM users WHERE id=?", (user["id"],)).fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(404, "User not found")
    return dict(row)


# ══════════════════════════════════════════════════════════════════════════════
#  LOGS ROUTER
# ══════════════════════════════════════════════════════════════════════════════

logs_router = APIRouter(prefix="/logs", tags=["Daily Logs"])


def _row_to_log(row) -> dict:
    return {
        "id": row["id"],
        "date": row["date"],
        "travel_kg": row["travel_kg"],
        "food_kg": row["food_kg"],
        "energy_kg": row["energy_kg"],
        "shop_kg": row["shop_kg"],
        "deed_kg": row["deed_kg"],
        "total_kg": row["total_kg"],
        "travel_name": row["travel_name"] or "",
        "food_name": row["food_name"] or "",
        "energy_name": row["energy_name"] or "",
        "shop_name": row["shop_name"] or "",
        "deed_name": row["deed_name"] or "",
        "created_at": row["created_at"],
        "vs_paris": round(row["total_kg"] - PARIS_TARGET, 2),
        "on_track": row["total_kg"] <= PARIS_TARGET,
    }


@logs_router.post("/", status_code=201)
def save_log(body: LogRequest, user=Depends(get_current_user)):
    total = round(body.travel_kg + body.food_kg + body.energy_kg + body.shop_kg + body.deed_kg, 3)
    conn = get_db()
    try:
        # Upsert — one log per user per day
        existing = conn.execute(
            "SELECT id FROM logs WHERE user_id=? AND date=?", (user["id"], body.date)
        ).fetchone()

        if existing:
            conn.execute("""
                UPDATE logs SET
                    travel_kg=?, food_kg=?, energy_kg=?, shop_kg=?, deed_kg=?, total_kg=?,
                    travel_name=?, food_name=?, energy_name=?, shop_name=?, deed_name=?
                WHERE user_id=? AND date=?
            """, (
                body.travel_kg, body.food_kg, body.energy_kg, body.shop_kg, body.deed_kg, total,
                body.travel_name, body.food_name, body.energy_name, body.shop_name, body.deed_name,
                user["id"], body.date
            ))
        else:
            conn.execute("""
                INSERT INTO logs
                    (user_id, date, travel_kg, food_kg, energy_kg, shop_kg, deed_kg, total_kg,
                     travel_name, food_name, energy_name, shop_name, deed_name)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                user["id"], body.date,
                body.travel_kg, body.food_kg, body.energy_kg, body.shop_kg, body.deed_kg, total,
                body.travel_name, body.food_name, body.energy_name, body.shop_name, body.deed_name
            ))

        conn.commit()
        row = conn.execute(
            "SELECT * FROM logs WHERE user_id=? AND date=?", (user["id"], body.date)
        ).fetchone()
    finally:
        conn.close()

    return _row_to_log(row)


@logs_router.get("/")
def get_logs(limit: int = 30, user=Depends(get_current_user)):
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM logs WHERE user_id=? ORDER BY date DESC LIMIT ?",
            (user["id"], limit)
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_log(r) for r in rows]


@logs_router.get("/summary")
def get_summary(days: int = 7, user=Depends(get_current_user)):
    """Returns avg, streak, and Paris compliance for last N days."""
    since = (date.today() - timedelta(days=days)).isoformat()
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM logs WHERE user_id=? AND date>=? ORDER BY date DESC",
            (user["id"], since)
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        return {"avg_kg": None, "streak_days": 0, "days_logged": 0, "days_on_track": 0, "logs": []}

    totals = [r["total_kg"] for r in rows]
    avg = round(sum(totals) / len(totals), 2)
    on_track = sum(1 for t in totals if t <= PARIS_TARGET)

    # streak: consecutive days from today going back
    dates_logged = {r["date"] for r in rows}
    streak = 0
    d = date.today()
    while d.isoformat() in dates_logged:
        streak += 1
        d -= timedelta(days=1)

    return {
        "avg_kg": avg,
        "streak_days": streak,
        "days_logged": len(rows),
        "days_on_track": on_track,
        "paris_target": PARIS_TARGET,
        "vs_paris": round(avg - PARIS_TARGET, 2),
        "logs": [_row_to_log(r) for r in rows],
    }


@logs_router.delete("/{log_date}", status_code=204)
def delete_log(log_date: str, user=Depends(get_current_user)):
    conn = get_db()
    try:
        conn.execute("DELETE FROM logs WHERE user_id=? AND date=?", (user["id"], log_date))
        conn.commit()
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
#  HABITS ROUTER
# ══════════════════════════════════════════════════════════════════════════════

habits_router = APIRouter(prefix="/habits", tags=["Habits"])

SUGGESTED_HABITS = [
    "Trade two drive-days for the bus this week.",
    "Switch to plant-based lunches Mon–Wed.",
    "Line-dry laundry instead of tumble-drying.",
    "Walk the short commute once this week.",
    "Buy nothing new for 5 days straight.",
    "Turn off standby devices at the wall each night.",
    "Choose a local, seasonal meal three times.",
    "Take a 2-minute cold shower instead of a long hot one.",
]


@habits_router.get("/suggestions")
def get_suggestions():
    """Return all habit suggestions (no auth needed)."""
    return [{"index": i, "title": h} for i, h in enumerate(SUGGESTED_HABITS)]


@habits_router.post("/", status_code=201)
def accept_habit(body: HabitRequest, user=Depends(get_current_user)):
    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO habits (user_id, title) VALUES (?,?)",
            (user["id"], body.title)
        )
        conn.commit()
        habit_id = cur.lastrowid
        row = conn.execute("SELECT * FROM habits WHERE id=?", (habit_id,)).fetchone()
    finally:
        conn.close()
    return dict(row)


@habits_router.get("/")
def get_habits(user=Depends(get_current_user)):
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM habits WHERE user_id=? ORDER BY accepted_at DESC",
            (user["id"],)
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


@habits_router.patch("/{habit_id}/progress")
def update_habit_progress(habit_id: int, body: HabitProgress, user=Depends(get_current_user)):
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM habits WHERE id=? AND user_id=?", (habit_id, user["id"])
        ).fetchone()
        if not row:
            raise HTTPException(404, "Habit not found")
        new_days = min(row["days_done"] + body.days_delta, 7)
        conn.execute("UPDATE habits SET days_done=? WHERE id=?", (new_days, habit_id))
        conn.commit()
        row = conn.execute("SELECT * FROM habits WHERE id=?", (habit_id,)).fetchone()
    finally:
        conn.close()
    return dict(row)


@habits_router.delete("/{habit_id}", status_code=204)
def delete_habit(habit_id: int, user=Depends(get_current_user)):
    conn = get_db()
    try:
        conn.execute("DELETE FROM habits WHERE id=? AND user_id=?", (habit_id, user["id"]))
        conn.commit()
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
#  COMMUNITY / LEADERBOARD ROUTER
# ══════════════════════════════════════════════════════════════════════════════

community_router = APIRouter(prefix="/community", tags=["Community"])


@community_router.get("/leaderboard")
def leaderboard(days: int = 7, limit: int = 20, user=Depends(get_current_user)):
    """
    Returns top users by 7-day average CO₂, plus the current user's rank.
    """
    since = (date.today() - timedelta(days=days)).isoformat()
    conn = get_db()
    try:
        # All users with at least one log in the window
        rows = conn.execute("""
            SELECT u.id, u.name,
                   AVG(l.total_kg) AS avg_kg,
                   COUNT(l.id)     AS days_logged
            FROM logs l
            JOIN users u ON u.id = l.user_id
            WHERE l.date >= ?
            GROUP BY u.id
            ORDER BY avg_kg ASC
        """, (since,)).fetchall()

        # Streak for current user
        all_dates = conn.execute(
            "SELECT date FROM logs WHERE user_id=? ORDER BY date DESC",
            (user["id"],)
        ).fetchall()
    finally:
        conn.close()

    dates_set = {r["date"] for r in all_dates}
    streak = 0
    d = date.today()
    while d.isoformat() in dates_set:
        streak += 1
        d -= timedelta(days=1)

    leaderboard_list = []
    user_rank = None
    for rank, row in enumerate(rows, start=1):
        is_you = row["id"] == user["id"]
        if is_you:
            user_rank = rank
        if rank <= limit or is_you:
            leaderboard_list.append({
                "rank": rank,
                "name": row["name"] if is_you else row["name"],   # could anonymise here
                "avg_kg": round(row["avg_kg"], 2),
                "days_logged": row["days_logged"],
                "streak_days": streak if is_you else 0,
                "is_you": is_you,
            })

    return {
        "leaderboard": leaderboard_list,
        "user_rank": user_rank,
        "total_users": len(rows),
        "window_days": days,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  CARBON TWIN ROUTER
# ══════════════════════════════════════════════════════════════════════════════

twin_router = APIRouter(prefix="/twin", tags=["Carbon Twin"])

TWIN_HABITS = [
    ("COMMUTE", "Cycles two days you drive. Saves ~3.4 kg / wk."),
    ("LUNCH",   "Plant-based Monday–Wednesday, then anything."),
    ("LAUNDRY", "Cold wash, line dry. Quiet, free, lower."),
    ("HEATING", "Sets thermostat 2°C lower at night."),
    ("SHOPPING","One no-buy week per month."),
]


@twin_router.get("/")
def get_twin(user=Depends(get_current_user)):
    """
    Finds the closest matched user by lifestyle similarity (7-day avg CO₂).
    Falls back to a synthetic twin if no real match is available.
    """
    since = (date.today() - timedelta(days=7)).isoformat()
    conn = get_db()
    try:
        my_stats = conn.execute("""
            SELECT AVG(total_kg) AS avg_kg, COUNT(*) AS days
            FROM logs WHERE user_id=? AND date>=?
        """, (user["id"], since)).fetchone()

        if my_stats and my_stats["avg_kg"]:
            my_avg = my_stats["avg_kg"]
            # Find user with avg closest to (my_avg * 0.6-0.85) — "a bit better"
            target_low  = my_avg * 0.55
            target_high = my_avg * 0.90

            twin_row = conn.execute("""
                SELECT u.id, u.name, AVG(l.total_kg) AS avg_kg
                FROM logs l JOIN users u ON u.id = l.user_id
                WHERE l.date >= ? AND u.id != ?
                GROUP BY u.id
                HAVING avg_kg BETWEEN ? AND ?
                ORDER BY ABS(avg_kg - ?) ASC
                LIMIT 1
            """, (since, user["id"], target_low, target_high, my_avg * 0.75)).fetchone()
        else:
            my_avg = 3.7   # default for new users
            twin_row = None
    finally:
        conn.close()

    # Pick 3 random habit hints
    hints = random.sample(TWIN_HABITS, min(3, len(TWIN_HABITS)))

    if twin_row:
        twin_avg = round(twin_row["avg_kg"], 2)
        twin_name = "0x" + hex(twin_row["id"] * 31337)[2:].upper()[:6]
    else:
        # Synthetic twin
        twin_avg = round(max(0.9, my_avg * 0.62), 2)
        twin_name = "0x8A2F"

    gap = round(my_avg - twin_avg, 2)
    pct_better = round((gap / my_avg) * 100) if my_avg else 0

    return {
        "twin_id": twin_name,
        "your_avg_kg": round(my_avg, 2),
        "twin_avg_kg": twin_avg,
        "gap_kg": max(0, gap),
        "pct_better": pct_better,
        "habits": [{"key": k, "value": v} for k, v in hints],
        "synthetic": twin_row is None,
    }
