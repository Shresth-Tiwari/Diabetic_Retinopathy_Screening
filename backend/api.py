"""JSON API: upload and grading, screening records, and portal data."""

import json
import os
import re
import sqlite3
import time
import uuid
from datetime import datetime
from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field

from .ai import AI_DEVICE, analyze_image, check_image_quality
from .auth import require_user
from .config import (ALLOWED_EXTENSIONS, ALLOWED_TYPES, DATABASE_PATH, DR_CLASSES, EXPLANATION_DIR,
                     EYES, MAX_FILE_SIZE, METRICS_PATH, MODEL_PATH, REFERABLE_THRESHOLD, UPLOAD_DIR)
from .database import database
from .screenings import SCREENING_QUERY, fetch_screening, screening_json

router = APIRouter(prefix="/api")


class ReviewRequest(BaseModel):
    final_grade: int = Field(ge=0, le=4)
    comments: str = Field(default="", max_length=2000)


@router.get("/health")
def health():
    return {"status": "online", "project": "RETINOVA", "ai_status": "connected",
            "ai_device": str(AI_DEVICE)}


# =========================================================
# IMAGE UPLOAD + AI
# =========================================================

def clean_filename(filename):
    filename = os.path.basename(filename or "image")
    return re.sub(r"[^A-Za-z0-9_.-]", "_", filename)


# A plain `def` endpoint runs in FastAPI's thread pool, so model inference
# does not block other requests.
@router.post("/upload")
def upload_image(request: Request, file: UploadFile = File(...), eye: str = Form("unspecified")):
    user = require_user(request, "patient")

    original_name = clean_filename(file.filename)
    extension = Path(original_name).suffix.lower()
    eye = eye.strip().lower() if eye.strip().lower() in EYES else "unspecified"

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Accepted formats: JPG, JPEG, PNG.")
    if file.content_type and file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400,
                            detail="The uploaded file is not a JPG, JPEG or PNG image.")

    contents = file.file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Image is too large. Maximum size is 10 MB.")

    try:
        Image.open(BytesIO(contents)).verify()
        image = Image.open(BytesIO(contents))
        width, height = image.size
        quality = check_image_quality(image)
    except (UnidentifiedImageError, OSError):
        raise HTTPException(status_code=400, detail="The file is not a valid image.")

    safe_name = f"{uuid.uuid4().hex}{extension}"
    save_path = UPLOAD_DIR / safe_name
    save_path.write_bytes(contents)

    record = {
        "patient_id": user["id"], "eye": eye,
        "original_filename": original_name, "saved_filename": safe_name,
        "file_size": len(contents), "width": width, "height": height,
        "quality": quality["quality"], "quality_message": quality["message"],
        "status": "retake",
    }

    # Poor images are stored but not graded: the patient is asked to retake.
    if quality["quality"] != "poor":
        explanation_name = f"{save_path.stem}_gradcam.jpg"
        start = time.perf_counter()
        try:
            ai = analyze_image(save_path, EXPLANATION_DIR / explanation_name)
        except Exception as exc:
            print("AI prediction failed:", exc)
            save_path.unlink(missing_ok=True)
            raise HTTPException(status_code=500, detail=f"AI analysis failed: {exc}")

        record.update({
            "status": "pending",
            "ai_grade": ai["grade"],
            "confidence": ai["confidence"],
            "referable": int(ai["referable"]),
            "referable_probability": ai["referable_probability"],
            "probabilities": json.dumps(ai["probabilities"]),
            "explanation_filename": explanation_name,
            "inference_ms": round((time.perf_counter() - start) * 1000),
        })

    try:
        with database() as connection:
            cursor = connection.execute(
                f"INSERT INTO screenings ({', '.join(record)}) "
                f"VALUES ({', '.join('?' * len(record))})",
                tuple(record.values()))
            row = fetch_screening(connection, cursor.lastrowid, user)
    except sqlite3.Error as exc:
        raise HTTPException(status_code=500, detail=f"Could not save the screening: {exc}")

    return {"success": True, **screening_json(row)}


# =========================================================
# SCREENING DETAILS AND IMAGES
# =========================================================

@router.get("/screenings/{screening_id}")
def get_screening(screening_id: int, request: Request):
    user = require_user(request)
    with database() as connection:
        return screening_json(fetch_screening(connection, screening_id, user))


@router.get("/screenings/{screening_id}/image")
def screening_image(screening_id: int, request: Request):
    user = require_user(request)
    with database() as connection:
        row = fetch_screening(connection, screening_id, user)
    path = UPLOAD_DIR / row["saved_filename"]
    if not path.exists():
        raise HTTPException(status_code=404, detail="Image file is missing.")
    return FileResponse(path)


@router.get("/screenings/{screening_id}/explanation")
def screening_explanation(screening_id: int, request: Request):
    user = require_user(request)
    with database() as connection:
        row = fetch_screening(connection, screening_id, user)
    if not row["explanation_filename"]:
        raise HTTPException(status_code=404, detail="No explanation for this screening.")
    path = EXPLANATION_DIR / row["explanation_filename"]
    if not path.exists():
        raise HTTPException(status_code=404, detail="Explanation file is missing.")
    return FileResponse(path)


# =========================================================
# PATIENT PORTAL
# =========================================================

@router.get("/patient/screenings")
def patient_screenings(request: Request):
    user = require_user(request, "patient")
    with database() as connection:
        rows = connection.execute(
            SCREENING_QUERY + " WHERE s.patient_id = ? ORDER BY s.id DESC",
            (user["id"],)).fetchall()
    history = [screening_json(row) for row in rows]
    graded = [s for s in history if s["ai_grade"] is not None]
    return {"latest": graded[0] if graded else None, "history": history}


# =========================================================
# DOCTOR PORTAL
# =========================================================

URGENCY_ORDER = {"urgent": 0, "refer": 1, "monitor": 2, "clear": 3}


@router.get("/doctor/queue")
def doctor_queue(request: Request):
    require_user(request, "doctor")
    with database() as connection:
        pending = [screening_json(row) for row in connection.execute(
            SCREENING_QUERY + " WHERE s.status = 'pending' AND s.ai_grade IS NOT NULL")]
        recent = [screening_json(row) for row in connection.execute(
            SCREENING_QUERY + " WHERE s.status = 'reviewed' ORDER BY r.created_at DESC LIMIT 10")]
        reviews = connection.execute("""
            SELECT COUNT(*) AS total,
                   SUM(r.final_grade = s.ai_grade) AS agreed,
                   SUM(date(r.created_at) = date('now')) AS today
            FROM doctor_reviews r JOIN screenings s ON s.id = r.screening_id""").fetchone()

    pending.sort(key=lambda s: (URGENCY_ORDER[s["urgency"]], -s["referable_probability"]))
    return {
        "stats": {
            "awaiting": len(pending),
            "urgent": sum(s["urgency"] == "urgent" for s in pending),
            "signed_today": reviews["today"] or 0,
            "agreement": (round(100 * reviews["agreed"] / reviews["total"], 1)
                          if reviews["total"] else None),
        },
        "pending": pending,
        "recent": recent,
    }


@router.post("/screenings/{screening_id}/review")
def review_screening(screening_id: int, data: ReviewRequest, request: Request):
    user = require_user(request, "doctor")
    with database() as connection:
        row = fetch_screening(connection, screening_id, user)
        if row["ai_grade"] is None:
            raise HTTPException(status_code=400, detail="This image was not graded by the AI.")
        decision = "confirmed" if data.final_grade == row["ai_grade"] else "overridden"
        connection.execute(
            "INSERT INTO doctor_reviews (screening_id, doctor_id, decision, comments, final_grade) "
            "VALUES (?, ?, ?, ?, ?)",
            (screening_id, user["id"], decision, data.comments.strip(), data.final_grade))
        connection.execute("UPDATE screenings SET status = 'reviewed' WHERE id = ?",
                           (screening_id,))
        return screening_json(fetch_screening(connection, screening_id, user))


# =========================================================
# ADMIN PORTAL
# =========================================================

def folder_size(folder):
    return sum(f.stat().st_size for f in folder.iterdir() if f.is_file())


@router.get("/admin/overview")
def admin_overview(request: Request):
    require_user(request, "admin")
    with database() as connection:
        roles = dict(connection.execute(
            "SELECT role, COUNT(*) FROM users GROUP BY role").fetchall())
        scans = connection.execute("""
            SELECT COUNT(*) AS total,
                   SUM(status = 'pending' AND ai_grade IS NOT NULL) AS pending,
                   SUM(status = 'reviewed') AS reviewed,
                   SUM(status = 'retake') AS retake,
                   SUM(referable = 1) AS referable,
                   AVG(inference_ms) AS inference_ms
            FROM screenings""").fetchone()
        grades = dict(connection.execute(
            "SELECT ai_grade, COUNT(*) FROM screenings "
            "WHERE ai_grade IS NOT NULL GROUP BY ai_grade").fetchall())
        users = connection.execute("""
            SELECT u.full_name, u.email, u.role, u.created_at,
                   COUNT(DISTINCT s.id) AS screenings,
                   COUNT(DISTINCT r.id) AS reviews,
                   MAX(COALESCE(r.created_at, s.created_at)) AS last_active
            FROM users u
            LEFT JOIN screenings s ON s.patient_id = u.id
            LEFT JOIN doctor_reviews r ON r.doctor_id = u.id
            GROUP BY u.id ORDER BY u.created_at DESC""").fetchall()

    metrics = json.loads(METRICS_PATH.read_text()) if METRICS_PATH.exists() else None
    return {
        "users": {"total": sum(roles.values()), **{r: roles.get(r, 0)
                                                   for r in ("patient", "doctor", "admin")}},
        "screenings": {key: scans[key] or 0
                       for key in ("total", "pending", "reviewed", "retake", "referable")},
        "grade_counts": [grades.get(g, 0) for g in range(len(DR_CLASSES))],
        "service": {
            "ai_device": str(AI_DEVICE),
            "avg_inference_ms": round(scans["inference_ms"]) if scans["inference_ms"] else None,
            "database_mb": round(DATABASE_PATH.stat().st_size / 1e6, 2),
            "uploads_mb": round(folder_size(UPLOAD_DIR) / 1e6, 1),
            "explanations_mb": round(folder_size(EXPLANATION_DIR) / 1e6, 1),
        },
        "model": {
            "file": MODEL_PATH.name,
            "size_mb": round(MODEL_PATH.stat().st_size / 1e6, 1),
            "updated": datetime.fromtimestamp(MODEL_PATH.stat().st_mtime).strftime("%Y-%m-%d"),
            "referable_threshold": REFERABLE_THRESHOLD,
            "metrics": metrics,
        },
        "user_list": [dict(u) for u in users],
    }
