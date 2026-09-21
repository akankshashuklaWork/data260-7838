"""Offline authentication checks for the HW3 FastAPI routes."""

from fastapi.testclient import TestClient

from web_application import auth
from web_application.app import app


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"PASS: {message}")


with TestClient(app, base_url="https://testserver") as client:
    response = client.get("/")
    require(response.status_code == 200, "home page loads")
    require("Log in" in response.text, "home page shows login link for a signed-out user")

    response = client.get("/listings")
    require(response.status_code == 200, "existing listing page remains available")
    response = client.get("/api/listings")
    require(response.status_code == 200, "existing listing API remains available")

    response = client.get("/dashboard", follow_redirects=False)
    require(response.status_code == 303, "dashboard rejects a signed-out user")
    require(response.headers["location"] == "/login", "dashboard redirects to login")

    response = client.post("/login", data={"username": "wrong", "password": "wrong"})
    require(response.status_code == 401, "invalid credentials are rejected")
    require("Invalid username or password" in response.text, "invalid-login alert is displayed")

    response = client.post(
        "/login",
        data={"username": auth.AUTH_USERNAME, "password": auth.AUTH_PASSWORD},
        follow_redirects=False,
    )
    require(response.status_code == 303, "valid credentials are accepted")
    cookie = response.headers.get("set-cookie", "").lower()
    require("secure" in cookie, "session cookie has Secure")
    require("httponly" in cookie, "session cookie has HttpOnly")
    require("samesite=lax" in cookie, "session cookie has SameSite=Lax")

    response = client.get("/dashboard")
    require(response.status_code == 200, "signed-in user can open dashboard")
    require(auth.AUTH_USERNAME in response.text, "dashboard displays the user's name")

    original_timeout = auth.SESSION_IDLE_TIMEOUT_SECONDS
    auth.SESSION_IDLE_TIMEOUT_SECONDS = -1
    response = client.get("/dashboard", follow_redirects=False)
    auth.SESSION_IDLE_TIMEOUT_SECONDS = original_timeout
    require(response.headers["location"] == "/login?expired=true", "expired session cannot reuse dashboard")

    client.post(
        "/login",
        data={"username": auth.AUTH_USERNAME, "password": auth.AUTH_PASSWORD},
        follow_redirects=False,
    )
    old_cookie = client.cookies.get("s7838_session")
    response = client.get("/logout", follow_redirects=False)
    require(response.status_code == 303, "logout redirects")
    require(response.headers["location"] == "/", "logout redirects to home")
    response = client.get("/dashboard", follow_redirects=False)
    require(response.headers["location"] == "/login", "logged-out session cannot reuse dashboard")

    with TestClient(app, base_url="https://testserver", cookies={"s7838_session": old_cookie}) as replay:
        response = replay.get("/dashboard", follow_redirects=False)
    require(response.status_code == 303, "a session cookie copied before logout cannot be replayed")

print("\nAll HW3 authentication checks passed.")
