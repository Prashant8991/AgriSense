"""
AgriSense Pro — FastAPI Application Factory
"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from routes.auth import router as auth_router
from routes.farm import router as farm_router
from routes.detection import router as detection_router
from routes.dashboard import router as dashboard_router
from routes.history import router as history_router
from routes.report import router as report_router
from routes.pages import router as pages_router

import os

app = FastAPI(title="AgriSense Pro", version="2.0.0")

# ── Middleware ──────────────────────────────────────────────────────────────
app.add_middleware(SessionMiddleware, secret_key="agrisense-secret-key-2024")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Static files / uploaded images ─────────────────────────────────────────
os.makedirs("static", exist_ok=True)
os.makedirs("static/uploads", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# ── Routers ─────────────────────────────────────────────────────────────────
# ⚠️  API routers MUST be registered before pages_router because
#     pages_router contains a catch-all /{full_path:path} route.
app.include_router(auth_router,      prefix="/api/auth")
app.include_router(farm_router,      prefix="/api/farm")
app.include_router(detection_router, prefix="/api/detection")
app.include_router(dashboard_router, prefix="/api/dashboard")
app.include_router(history_router,   prefix="/api/history")
app.include_router(report_router,    prefix="/api/report")
app.include_router(pages_router)      # catch-all SPA shell — must be LAST
