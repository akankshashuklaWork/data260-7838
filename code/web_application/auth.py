"""Authentication routes for the DATA 260 rental housing application."""

import os
import secrets
import time
from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

APP_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=APP_DIR / "templates")

router = APIRouter()

AUTH_USERNAME = os.getenv("APP_LOGIN_USERNAME", "akanksha")
AUTH_PASSWORD = os.getenv("APP_LOGIN_PASSWORD", "data260")
SESSION_IDLE_TIMEOUT_SECONDS = int(os.getenv("SESSION_IDLE_TIMEOUT_SECONDS", "900"))

# The signed cookie alone can be copied and replayed, so the server keeps its own
# record of live sessions (id -> last activity). Logout and expiry delete the id.
ACTIVE_SESSIONS: dict[str, float] = {}


def _active_user(request: Request, *, refresh: bool = True) -> tuple[str | None, bool]:
    user = request.session.get("user")
    session_id = request.session.get("sid")
    last_activity = ACTIVE_SESSIONS.get(session_id)
    if not user or last_activity is None:
        request.session.clear()
        return None, False

    now = time.time()
    if now - last_activity > SESSION_IDLE_TIMEOUT_SECONDS:
        ACTIVE_SESSIONS.pop(session_id, None)
        request.session.clear()
        return None, True

    if refresh:
        ACTIVE_SESSIONS[session_id] = now
    return str(user), False


@router.get("/", response_class=HTMLResponse, name="home")
def home(request: Request) -> HTMLResponse:
    user, _ = _active_user(request)
    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={"user": user},
    )


@router.get("/login", response_class=HTMLResponse, name="login_page")
def login_page(request: Request, expired: bool = False, logged_out: bool = False) -> HTMLResponse:
    user, session_expired = _active_user(request)
    if user:
        return RedirectResponse(url="/dashboard", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "user": None,
            "invalid_credentials": False,
            "expired": expired or session_expired,
            "logged_out": logged_out,
        },
    )


@router.post("/login", response_class=HTMLResponse, name="login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
) -> HTMLResponse:
    username_matches = secrets.compare_digest(username, AUTH_USERNAME)
    password_matches = secrets.compare_digest(password, AUTH_PASSWORD)
    if not (username_matches and password_matches):
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "user": None,
                "invalid_credentials": True,
                "expired": False,
                "logged_out": False,
            },
            status_code=401,
        )

    request.session.clear()
    session_id = secrets.token_urlsafe(16)
    ACTIVE_SESSIONS[session_id] = time.time()
    request.session.update({"user": AUTH_USERNAME, "sid": session_id})
    return RedirectResponse(url="/dashboard", status_code=303)


@router.get("/dashboard", response_class=HTMLResponse, name="dashboard")
def dashboard(request: Request) -> HTMLResponse:
    user, expired = _active_user(request)
    if not user:
        target = "/login?expired=true" if expired else "/login"
        return RedirectResponse(url=target, status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"user": user, "idle_timeout_minutes": SESSION_IDLE_TIMEOUT_SECONDS // 60},
    )


@router.get("/logout", name="logout")
def logout(request: Request) -> RedirectResponse:
    ACTIVE_SESSIONS.pop(request.session.get("sid"), None)
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)
