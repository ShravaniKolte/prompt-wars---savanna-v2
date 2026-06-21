# SAVANNA Backend API

FastAPI + SQLite backend for the SAVANNA carbon tracking app.

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the server
uvicorn main:app --reload --port 8000
```

Open **http://localhost:8000/docs** for the interactive Swagger UI.

---

## Environment Variables

| Variable     | Default                          | Description                          |
|--------------|----------------------------------|--------------------------------------|
| `SECRET_KEY` | `savanna-super-secret-...`       | JWT signing key — **change this!**   |
| `DB_PATH`    | `savanna.db`                     | Path to the SQLite database file     |

```bash
# Example
export SECRET_KEY="my-very-long-random-secret-key-2026"
export DB_PATH="/data/savanna.db"
uvicorn main:app --host 0.0.0.0 --port 8000
```

---

## API Overview

### Auth

| Method | Endpoint       | Auth? | Description         |
|--------|---------------|-------|---------------------|
| POST   | /auth/signup  | ✗     | Create account      |
| POST   | /auth/login   | ✗     | Login → JWT token   |
| GET    | /auth/me      | ✓     | Current user info   |

**Signup**
```json
POST /auth/signup
{
  "name": "Alex",
  "email": "alex@example.com",
  "password": "secure123",
  "city": "Pune"
}
```

**Login**
```json
POST /auth/login
{ "email": "alex@example.com", "password": "secure123" }
```

Returns:
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "user": { "id": 1, "name": "Alex", "email": "alex@example.com" }
}
```

All authenticated endpoints need:
```
Authorization: Bearer <access_token>
```

---

### Daily Logs

| Method | Endpoint          | Description                          |
|--------|------------------|--------------------------------------|
| POST   | /logs/           | Save / update today's log (upsert)   |
| GET    | /logs/           | Get all logs (last 30 by default)    |
| GET    | /logs/summary    | 7-day avg, streak, Paris compliance  |
| DELETE | /logs/{date}     | Delete a log by date (YYYY-MM-DD)    |

**Save a log**
```json
POST /logs/
{
  "date": "2026-06-21",
  "travel_kg": 0.0,
  "food_kg": 0.6,
  "energy_kg": 0.4,
  "shop_kg": 0.0,
  "deed_kg": -0.3,
  "travel_name": "Walked or cycled",
  "food_name": "Plant-forward",
  "energy_name": "Quiet home",
  "shop_name": "Bought nothing",
  "deed_name": "Planted or composted"
}
```

Response includes `total_kg`, `vs_paris`, and `on_track` fields.

---

### Habits

| Method | Endpoint                       | Description                    |
|--------|-------------------------------|--------------------------------|
| GET    | /habits/suggestions           | List all habit suggestions     |
| POST   | /habits/                      | Accept a habit                 |
| GET    | /habits/                      | List your habits               |
| PATCH  | /habits/{id}/progress         | Increment days_done            |
| DELETE | /habits/{id}                  | Remove a habit                 |

---

### Community Leaderboard

| Method | Endpoint              | Description                        |
|--------|-----------------------|------------------------------------|
| GET    | /community/leaderboard | 7-day rolling leaderboard + your rank |

Query params: `?days=7&limit=20`

Response:
```json
{
  "leaderboard": [
    { "rank": 1, "name": "leite_quente", "avg_kg": 1.10, "is_you": false },
    { "rank": 2, "name": "you",          "avg_kg": 2.30, "is_you": true  }
  ],
  "user_rank": 2,
  "total_users": 3418,
  "window_days": 7
}
```

---

### Carbon Twin

| Method | Endpoint | Description                             |
|--------|----------|-----------------------------------------|
| GET    | /twin/   | Get your matched Carbon Twin + habits   |

Response:
```json
{
  "twin_id": "0x8A2F",
  "your_avg_kg": 3.70,
  "twin_avg_kg": 2.29,
  "gap_kg": 1.41,
  "pct_better": 38,
  "habits": [
    { "key": "COMMUTE", "value": "Cycles two days you drive. Saves ~3.4 kg / wk." },
    { "key": "LUNCH",   "value": "Plant-based Monday–Wednesday, then anything." },
    { "key": "LAUNDRY", "value": "Cold wash, line dry. Quiet, free, lower." }
  ],
  "synthetic": true
}
```

---

## Connecting to the Frontend

Replace the `localStorage` calls in the frontend JS with `fetch()` to this API.

```js
// Login
const res = await fetch('http://localhost:8000/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ email, password })
});
const { access_token, user } = await res.json();
localStorage.setItem('savanna_token', access_token);

// Save a log
await fetch('http://localhost:8000/logs/', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${localStorage.getItem('savanna_token')}`
  },
  body: JSON.stringify({ date: '2026-06-21', travel_kg: 0, food_kg: 0.6, ... })
});
```

---

## Project Structure

```
savanna/
├── main.py          ← FastAPI app, CORS, startup
├── database.py      ← SQLite init & connection helper
├── auth.py          ← JWT + bcrypt password utilities
├── schemas.py       ← Pydantic request/response models
├── routes.py        ← All route handlers (auth, logs, habits, community, twin)
├── requirements.txt
└── README.md
```

---

## Production Checklist

- [ ] Set a strong `SECRET_KEY` env variable
- [ ] Set `allow_origins` in CORS to your actual frontend domain
- [ ] Use a process manager: `gunicorn -k uvicorn.workers.UvicornWorker main:app`
- [ ] Mount `DB_PATH` on a persistent volume (not ephemeral storage)
- [ ] Add HTTPS via nginx / Caddy reverse proxy
