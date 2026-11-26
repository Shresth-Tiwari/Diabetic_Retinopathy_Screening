"""Paths and settings shared by the backend."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Frontend
TEMPLATE_DIR = BASE_DIR / "frontend" / "templates"
STATIC_DIR = BASE_DIR / "frontend" / "static"

# App data: database, uploaded photos and Grad-CAM overlays
STORAGE_DIR = BASE_DIR / "storage"
DATABASE_PATH = Path(os.getenv("RETINOVA_DB_PATH", str(STORAGE_DIR / "retinova.db")))
UPLOAD_DIR = STORAGE_DIR / "uploads"
EXPLANATION_DIR = STORAGE_DIR / "explanations"
for folder in (UPLOAD_DIR, EXPLANATION_DIR):
    folder.mkdir(parents=True, exist_ok=True)

# Model and its evaluation (written by `python train.py --evaluate ...`)
MODEL_PATH = BASE_DIR / "models" / "retinova_resnet18.pth"
METRICS_PATH = BASE_DIR / "results" / f"{MODEL_PATH.stem}_metrics.json"

# Uploads
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}
ALLOWED_TYPES = {"image/jpeg", "image/jpg", "image/png"}
MAX_FILE_SIZE = 10 * 1024 * 1024
MIN_WIDTH = 512
MIN_HEIGHT = 512
EYES = {"left", "right", "unspecified"}

# ICDR grades
DR_CLASSES = ["No DR", "Mild", "Moderate", "Severe", "Proliferative"]

# P(grade 2-4) at or above this flags referable DR.
# Selected on the validation set: 98.7% sensitivity, 82.5% specificity.
REFERABLE_THRESHOLD = 0.05
