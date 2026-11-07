"""Session authorization for Analog TV.

Only the broadcast player and its read-only feed endpoints are public.
All other application routes fail closed unless Google OIDC login succeeded.
"""

import hmac
import re
import time
from urllib.parse import quote

from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse

from analog_tv.core.config import get_settings

_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_CHANNEL_NOW = re.compile(r"^/api/channels/[0-9]+/now$")
_CHANNEL_MEDIA = re.compile(r"^/api/channels/media/[0-9]+/[0-9]+$")


def is_public(request: Request) -> bool:
    path = request.url.path
    method = request.method.upper()
    if method != "GET":
        return False
    return (
        path in {"/", "/health", "/auth/login", "/auth/google/login", "/auth/google/callback", "/api/channels", "/api/alerts/latest", "/api/weather/forecast"}
        or path.startswith("/static/") and path not in {"/static/admin.js", "/static/admin.html"}
        or bool(_CHANNEL_NOW.fullmatch(path))
        or bool(_CHANNEL_MEDIA.fullmatch(path))
    )


def get_admin(request: Request) -> dict | None:
    session = request.session
    user = session.get("analog_admin")
    if not isinstance(user, dict):
        return None
    try:
        logged_at = float(session.get("analog_login_at", 0))
    except (TypeError, ValueError):
        return None
    email = user.get("email")
    subject = user.get("sub")
    allowed = get_settings().admin_email.strip().casefold()
    if (
        not allowed
        or not isinstance(email, str)
        or not isinstance(subject, str)
        or not subject
        or email.casefold() != allowed
        or logged_at <= 0
        or time.time() - logged_at > 8 * 3600
    ):
        return None
    return user


async def authorize_request(request: Request, call_next):
    path = request.url.path
    if is_public(request):
        return await call_next(request)

    # This endpoint is public for a no-login, health-check-only response.
    if path == "/auth/login" and request.method == "GET":
        return await call_next(request)

    admin = get_admin(request)
    if admin is None:
        if request.method == "GET" and path in {"/admin", "/docs", "/redoc", "/openapi.json"}:
            return RedirectResponse("/auth/login", status_code=303)
        return JSONResponse({"detail": "Google admin sign-in required"}, status_code=401, headers={"Cache-Control": "no-store"})

    if request.method.upper() in _UNSAFE_METHODS:
        expected = str(request.session.get("analog_csrf", ""))
        received = request.headers.get("X-Analog-CSRF", "")
        if not expected or not hmac.compare_digest(expected, received):
            return JSONResponse({"detail": "Invalid CSRF token"}, status_code=403, headers={"Cache-Control": "no-store"})
        origin = request.headers.get("Origin")
        # Origin is supplemental CSRF defense; explicit allowed origin is authoritative
        # behind a reverse proxy. Requests with no Origin still require CSRF token.
        if origin:
            base = get_settings().public_base_url.rstrip("/")
            if not base or origin.rstrip("/") != base:
                return JSONResponse({"detail": "Untrusted request origin"}, status_code=403, headers={"Cache-Control": "no-store"})

    response = await call_next(request)
    if path.startswith("/api/") or path.startswith("/auth/") or path == "/admin":
        response.headers["Cache-Control"] = "no-store"
    return response
