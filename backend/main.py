"""
RETINOVA backend.

Patients upload fundus photos; each one is quality-checked, graded on the
ICDR scale (0-4) with a Grad-CAM heatmap, and stored for doctor review.
Doctors confirm or override the AI grade; admins see system usage.

Run from the project folder:
    python -m uvicorn backend.main:app --reload

Modules:
    config.py      paths and settings
    database.py    SQLite connection and schema
    ai.py          image quality check, ResNet18 grading, Grad-CAM
    auth.py        sessions, password hashing, login/signup/logout API
    screenings.py  follow-up advice and screening JSON
    api.py         upload and portal data API
    pages.py       HTML pages (Jinja2 templates)
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from . import api, auth, pages
from .config import STATIC_DIR
from .database import setup_database


@asynccontextmanager
async def lifespan(app):
    setup_database()
    yield


app = FastAPI(title="RETINOVA", lifespan=lifespan)
app.include_router(auth.router)
app.include_router(api.router)
app.include_router(pages.router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
