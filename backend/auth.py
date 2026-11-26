"""Sessions, password hashing and the login/signup/logout API."""

import hashlib
import secrets
import sqlite3

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .database import database

router = APIRouter(prefix="/api/auth")

# session id -> {"id", "name", "role"}
sessions = {}


def current_user(request):
    return sessions.get(request.cookies.get("retinova_session"))


def require_user(request, *roles):
    user = current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Please log in first.")
    if roles and user["role"] not in roles:
        raise HTTPException(status_code=403, detail="You do not have access to this page.")
    return user


# =========================================================
# PASSWORD HASHING
# =========================================================

def hash_password(password):
    """Salted PBKDF2 password hashing."""
    salt = secrets.token_hex(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000).hex()
    return f"{salt}${password_hash}"


def check_password(password, stored_value):
    try:
        salt, saved_hash = stored_value.split("$", 1)
        test_hash = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000).hex()
        return secrets.compare_digest(test_hash, saved_hash)
    except ValueError:
        return False


# =========================================================
# API
# =========================================================

class SignupRequest(BaseModel):
    full_name: str
    email: str
    password: str
    role: str


class LoginRequest(BaseModel):
    email: str
    password: str


def start_session(user):
    session_id = secrets.token_urlsafe(32)
    sessions[session_id] = user
    response = JSONResponse({"success": True, "user": user})
    response.set_cookie("retinova_session", session_id,
                        httponly=True, samesite="lax", max_age=8 * 60 * 60)
    return response


@router.post("/signup")
def signup(data: SignupRequest):
    full_name = data.full_name.strip()
    email = data.email.strip().lower()
    role = data.role.strip().lower()

    if not full_name:
        raise HTTPException(status_code=400, detail="Full name is required.")
    if role not in {"patient", "doctor", "admin"}:
        raise HTTPException(status_code=400, detail="Invalid role.")
    if len(data.password) < 6:
        raise HTTPException(status_code=400, detail="Password must contain at least 6 characters.")

    try:
        with database() as connection:
            if connection.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone():
                raise HTTPException(status_code=409,
                                    detail="An account with this email already exists.")
            cursor = connection.execute(
                "INSERT INTO users (full_name, email, password_hash, role) VALUES (?, ?, ?, ?)",
                (full_name, email, hash_password(data.password), role))
            user_id = cursor.lastrowid
    except sqlite3.Error as exc:
        raise HTTPException(status_code=500, detail=f"Database error: {exc}")

    return start_session({"id": user_id, "name": full_name, "role": role})


@router.post("/login")
def login(data: LoginRequest):
    email = data.email.strip().lower()
    try:
        with database() as connection:
            user = connection.execute(
                "SELECT id, full_name, email, password_hash, role FROM users WHERE email = ?",
                (email,)).fetchone()
    except sqlite3.Error as exc:
        raise HTTPException(status_code=500, detail=f"Database error: {exc}")

    if not user or not check_password(data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    return start_session({"id": user["id"], "name": user["full_name"], "role": user["role"]})


@router.post("/logout")
def logout(request: Request):
    session_id = request.cookies.get("retinova_session")
    if session_id:
        sessions.pop(session_id, None)
    response = JSONResponse({"success": True})
    response.delete_cookie("retinova_session")
    return response
