from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db
from routes import auth_router, logs_router, habits_router, community_router, twin_router

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="SAVANNA API",
    description="Backend for SAVANNA — A Field Journal of Small Decisions",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ─────────────────────────────────────────────────────────────────────
# Allow your frontend origin. In production, replace "*" with your domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Startup ───────────────────────────────────────────────────────────────────

@app.on_event("startup")
def on_startup():
    init_db()


# ── Routes ────────────────────────────────────────────────────────────────────

app.include_router(auth_router)
app.include_router(logs_router)
app.include_router(habits_router)
app.include_router(community_router)
app.include_router(twin_router)


@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "service": "SAVANNA API", "version": "1.0.0"}


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}
