"""Session authorization for Analog TV.

Only the broadcast player and its read-only feed endpoints are public.
All other application routes fail closed unless local Admin login succeeded.
"""

import hmac
import re
import time
from urllib.parse import quote

from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse

from analog_tv.auth.local import configured
from analog_tv.core.config import get_settings

_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_CHANNEL_NOW = re.compile(r"^/api/channels/[0-9]+/now$")
_CHANNEL_MEDIA = re.compile(r"^/api/channels/media/[0-9]+/[0-9]+$")


def is_public(request: Request) -> bool:
    path = request.url.path
    method = request.method.upper()
    if path == "/auth/login" and method == "POST":
        return True
    if method != "GET":
        return False
    return (
        path in {"/", "/health", "/auth/login", "/api/channels", "/api/alerts/latest", "/api/weather/forecast"}
        or path.startswith("/static/") and path not in {"/static/admin.js", "/static/admin.html"}
        or bool(_CHANNEL_NOW.fullmatch(path))
        or bool(_CHANNEL_MEDIA.fullmatch(path))
    )


def get_admin(request: Request) -> dict | None:
    if not get_settings().lan_admin and not configured():
        return None
    if not get_settings().lan_admin and get_settings().cookie_secure and request.url.scheme != "https":
        return None
    sid = request.session.get("local_sid")
    if not isinstance(sid, str):
        return None
    admin = request.app.state.admin_sessions.get(sid)
    if admin and admin["expires"] > time.monotonic():
        return admin
    request.app.state.admin_sessions.pop(sid, None)
    return None


async def authorize_request(request: Request, call_next):
    path = request.url.path
    if is_public(request):
        return await call_next(request)

    admin = get_admin(request)
    if admin is None:
        if request.method == "GET" and path in {"/admin", "/docs", "/redoc", "/openapi.json"}:
            if path == "/admin" and get_settings().lan_admin:
                from analog_tv.auth.routes import login_page
                return await login_page(request)
            return RedirectResponse("/auth/login", status_code=303)
        return JSONResponse({"detail": "Admin sign-in required"}, status_code=401, headers={"Cache-Control": "no-store"})

    if request.method.upper() in _UNSAFE_METHODS:
        expected = admin["csrf_token"]
        received = request.headers.get("X-Analog-CSRF", "")
        if not expected or not hmac.compare_digest(expected.encode(), received.encode()):
            return JSONResponse({"detail": "Invalid CSRF token"}, status_code=403, headers={"Cache-Control": "no-store"})
        origin = request.headers.get("Origin")
        # Origin is supplemental CSRF defense; explicit allowed origin is authoritative
        # behind a reverse proxy. Requests with no Origin still require CSRF token.
        if origin:
            base = request.url.scheme + "://" + request.url.netloc if get_settings().lan_admin else get_settings().public_base_url
            if not base or origin.rstrip("/") != base:
                return JSONResponse({"detail": "Untrusted request origin"}, status_code=403, headers={"Cache-Control": "no-store"})

    response = await call_next(request)
    if path.startswith("/api/") or path.startswith("/auth/") or path == "/admin":
        response.headers["Cache-Control"] = "no-store"
    return response
