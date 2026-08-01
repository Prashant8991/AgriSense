"""
Pages router — serves the single-page HTML shell for every frontend route.
All navigation is handled client-side via JavaScript.
"""
from fastapi import APIRouter
from fastapi.responses import FileResponse
import os

router = APIRouter()

TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")


@router.get("/")
async def index():
    return FileResponse(os.path.join(TEMPLATES_DIR, "index.html"))


@router.get("/{full_path:path}")
async def catch_all(full_path: str):
    # Return the SPA shell; JS handles routing
    return FileResponse(os.path.join(TEMPLATES_DIR, "index.html"))
