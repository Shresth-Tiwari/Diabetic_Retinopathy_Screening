"""HTML pages rendered from the Jinja2 templates in frontend/templates."""

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from .auth import current_user
from .config import TEMPLATE_DIR

router = APIRouter()
templates = Jinja2Templates(directory=TEMPLATE_DIR)


def render(request, page):
    # `page` marks the active nav link; `user` is None when logged out
    return templates.TemplateResponse(
        request, f"{page}.html", {"page": page, "user": current_user(request)})


def portal(request, role):
    """Portal pages need a login with the matching role."""
    user = current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if user["role"] != role:
        return RedirectResponse(f"/{user['role']}", status_code=303)
    return render(request, role)


@router.get("/")
def home(request: Request):
    return render(request, "index")


@router.get("/login")
def login_page(request: Request):
    return render(request, "login")


@router.get("/patient")
def patient_page(request: Request):
    return portal(request, "patient")


@router.get("/doctor")
def doctor_page(request: Request):
    return portal(request, "doctor")


@router.get("/admin")
def admin_page(request: Request):
    return portal(request, "admin")
