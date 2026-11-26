"""Screening records: follow-up advice and the JSON shape every portal uses."""

import json
from datetime import datetime, timedelta

from fastapi import HTTPException

from .config import DR_CLASSES, REFERABLE_THRESHOLD

# (advice, months until next screening or None when referred)
# Follow-up actions from the ICDR severity scale.
GRADE_ADVICE = [
    ("Re-screen in 12 months.", 12),
    ("Mild changes. Re-screen in 6 to 12 months.", 6),
    ("Refer to an ophthalmologist within 3 months.", None),
    ("Urgent referral to an ophthalmologist.", None),
    ("Immediate referral to an ophthalmologist.", None),
]


def urgency(grade, referable):
    if grade >= 3:
        return "urgent"
    if grade == 2 or referable:
        return "refer"
    if grade == 1:
        return "monitor"
    return "clear"


def follow_up(grade, referable, created_at):
    advice, months = GRADE_ADVICE[grade]
    if grade < 2 and referable:
        advice = ("The model sees a possible sign of referable DR. "
                  "A doctor should review this image.")
        months = None
    next_screening = None
    if months and created_at:
        start = datetime.strptime(created_at[:19], "%Y-%m-%d %H:%M:%S")
        next_screening = (start + timedelta(days=round(months * 30.44))).strftime("%Y-%m-%d")
    return advice, next_screening


SCREENING_QUERY = """
    SELECT s.*, p.full_name AS patient_name,
           r.final_grade, r.decision, r.comments,
           r.created_at AS reviewed_at, d.full_name AS doctor_name
    FROM screenings s
    LEFT JOIN users p ON p.id = s.patient_id
    LEFT JOIN doctor_reviews r
        ON r.id = (SELECT MAX(id) FROM doctor_reviews WHERE screening_id = s.id)
    LEFT JOIN users d ON d.id = r.doctor_id
"""


def screening_json(row):
    """Turn a SCREENING_QUERY row into the JSON shape used by every portal."""
    result = {
        "id": row["id"],
        "patient_name": row["patient_name"],
        "eye": row["eye"] or "unspecified",
        "filename": row["original_filename"],
        "file_size": row["file_size"],
        "width": row["width"],
        "height": row["height"],
        "quality": row["quality"],
        "quality_message": row["quality_message"],
        "status": row["status"],
        "created_at": row["created_at"],
        "image_url": f"/api/screenings/{row['id']}/image",
        "ai_grade": row["ai_grade"],
        "final_grade": None,
    }
    if row["ai_grade"] is None:  # retake, or saved before the AI was connected
        return result

    referable = bool(row["referable"])
    # A doctor's grade replaces the AI grade for advice and scheduling
    grade = row["final_grade"] if row["final_grade"] is not None else row["ai_grade"]
    reviewed_referable = referable if row["final_grade"] is None else grade >= 2
    advice, next_screening = follow_up(grade, reviewed_referable, row["created_at"])

    result.update({
        "ai_prediction": DR_CLASSES[row["ai_grade"]],
        "confidence": round(row["confidence"] * 100, 1),
        "referable_dr": referable,
        "referable_probability": round(row["referable_probability"] * 100, 1),
        "referable_threshold": REFERABLE_THRESHOLD,
        "probabilities": json.loads(row["probabilities"] or "[]"),
        "explanation_url": (f"/api/screenings/{row['id']}/explanation"
                            if row["explanation_filename"] else None),
        "inference_ms": row["inference_ms"],
        "final_grade": row["final_grade"],
        "grade": grade,
        "grade_name": DR_CLASSES[grade],
        "urgency": urgency(grade, reviewed_referable),
        "advice": advice,
        "next_screening": next_screening,
        "review": None if row["final_grade"] is None else {
            "doctor": row["doctor_name"],
            "decision": row["decision"],
            "comments": row["comments"],
            "reviewed_at": row["reviewed_at"],
        },
    })
    return result


def fetch_screening(connection, screening_id, user):
    row = connection.execute(SCREENING_QUERY + " WHERE s.id = ?", (screening_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Screening not found.")
    if user["role"] == "patient" and row["patient_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Screening not found.")
    return row
