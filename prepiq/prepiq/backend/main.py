"""
PrepIQ Backend — FastAPI + MongoDB + Gemini
Entry point: main.py
Run: uvicorn main:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from routes import auth, profile, interview
from config.database import connect_db, close_db

app = FastAPI(
    title="PrepIQ API",
    description="AI-powered interview training platform",
    version="1.0.0",
)

# ── CORS ──────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── DB LIFECYCLE ──────────────────────────────────────────
@app.on_event("startup")
async def startup():
    await connect_db()

@app.on_event("shutdown")
async def shutdown():
    await close_db()

# ── ROUTES ────────────────────────────────────────────────
app.include_router(auth.router,      prefix="/auth",      tags=["Auth"])
app.include_router(profile.router,   prefix="/profile",   tags=["Profile"])
app.include_router(interview.router, prefix="/interview", tags=["Interview"])

# ── SERVE FRONTEND (optional static mount) ────────────────
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "pages")
if os.path.exists(frontend_path):
    app.mount("/app", StaticFiles(directory=frontend_path, html=True), name="frontend")

@app.get("/")
async def root():
    return {"message": "PrepIQ API is running 🚀", "docs": "/docs"}

@app.get("/health")
async def health():
    return {"status": "ok"}
