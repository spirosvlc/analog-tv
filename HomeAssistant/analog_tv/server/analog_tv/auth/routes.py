"""Password login, identity and revocable logout."""
import asyncio
import hmac
import secrets
import time
from urllib.parse import parse_qs

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from analog_tv.auth.accounts import create_account, read_account
from analog_tv.auth.local import USERNAME, HASH, SESSION_AGE, configured, derive
from analog_tv.auth.security import get_admin
from analog_tv.core.config import get_settings

router = APIRouter(tags=["authentication"], include_in_schema=False)
HEADERS = {
    "Cache-Control": "no-store",
    "Content-Security-Policy": "default-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'",
}


def page(message, status=200, form=""):
    return HTMLResponse(f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Analog TV // Broadcast Control</title><link rel="stylesheet" href="/static/style.css">
</head><body class="admin-body"><main class="panel"><h1>Broadcast Control</h1>
<p>{message}</p>{form}<p><a href="/">Return to Live TV</a></p></main></body></html>""",
                        status_code=status, headers=HEADERS)


@router.get("/auth/login")
async def login_page(request: Request):
    if get_admin(request):
        return RedirectResponse("/admin", status_code=303, headers=HEADERS)
    settings = get_settings()
    setup = settings.lan_admin and await asyncio.to_thread(read_account) is None
    if setup and not settings.allow_admin_setup:
        return page("Enable Allow Admin Setup in the Home Assistant add-on configuration and restart.", 503)
    if not settings.lan_admin and not configured():
        return page("Admin login is locked. See the setup instructions.", 503)
    if not settings.lan_admin and settings.cookie_secure and request.url.scheme != "https":
        return RedirectResponse(settings.public_base_url + "/auth/login", status_code=303,
                                headers=HEADERS)
    token = secrets.token_urlsafe(32)
    request.session.clear()
    request.session.update(login_token=token, login_expires=time.time() + 600, setup=setup)
    action = "Create Admin account" if setup else "Sign in"
    autocomplete = "new-password" if setup else "current-password"
    confirmation = ('<label>Confirm password <input name="confirm" type="password" '
                    'autocomplete="new-password" required></label>') if setup else ""
    message = ("Choose a username and a password of at least 16 characters."
               if setup else "Sign in with your local Admin account.")
    return page(message, form=f"""
<form action="/auth/login" method="post">
<input type="hidden" name="csrf" value="{token}">
<label>Username <input name="username" autocomplete="username" required maxlength="64"></label>
<label>Password <input name="password" type="password" autocomplete="{autocomplete}" required></label>
{confirmation}
<button class="button" type="submit">{action}</button></form>""")


@router.post("/auth/login")
async def login(request: Request):
    s = get_settings()
    if not s.lan_admin and not configured():
        return page("Admin login is locked.", 503)
    if not s.lan_admin and s.cookie_secure and request.url.scheme != "https":
        return page("Admin login requires HTTPS.", 403)
    origin = request.url.scheme + "://" + request.url.netloc if s.lan_admin else s.public_base_url
    if request.headers.get("origin") != origin:
        return page("Untrusted login origin.", 403)
    if request.headers.get("content-type", "").split(";")[0] != "application/x-www-form-urlencoded":
        return page("Invalid login form.", 415)
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > 8192:
            return page("Login form too large.", 413)
        body.extend(chunk)
    try:
        form = parse_qs(body.decode("ascii"), max_num_fields=4, errors="strict")
    except ValueError:
        return page("Invalid login form.", 400)
    token = request.session.get("login_token", "")
    if (not token or request.session.get("login_expires", 0) < time.time()
            or not hmac.compare_digest(token.encode(), form.get("csrf", [""])[0].encode())):
        return page('Login expired. <a href="/auth/login">Start again</a>.', 403)
    state = request.app.state
    now = time.monotonic()
    ip = request.client.host if request.client else "unknown"
    for key, (until, _) in list(state.login_attempts.items()):
        if until <= now:
            del state.login_attempts[key]
    keys = [(ip, 5), ("*", 30)]
    if (state.login_busy or len(state.login_attempts) >= 1024 or
            any(state.login_attempts.get(key, (0, 0))[1] >= limit for key, limit in keys)):
        return HTMLResponse('Too many attempts. Try again in 60 seconds.', status_code=429,
                            headers={**HEADERS, "Retry-After": "60"})
    for key, _ in keys:
        until, count = state.login_attempts.get(key, (now + 60, 0))
        state.login_attempts[key] = (until, count + 1)
    password_text = form.get("password", [""])[0]
    password = password_text.encode()
    username = form.get("username", [""])[0]
    state.login_busy = True
    try:
        account = (await asyncio.to_thread(read_account) if s.lan_admin else
                   (s.admin_username, s.admin_password_hash))
        if account is None:
            if not s.allow_admin_setup or request.session.get("setup") is not True:
                return page('Account setup is locked. <a href="/admin">Return to Admin</a>.', 403)
            if (not USERNAME.fullmatch(username) or not 16 <= len(password_text)
                    or len(password) > 1024 or password_text != form.get("confirm", [""])[0]):
                return page('Use a valid username and matching passwords of at least 16 characters. '
                            '<a href="/admin">Try again</a>.', 400)
            salt = secrets.token_bytes(16)
            digest = await asyncio.to_thread(derive, password, salt)
            if not await asyncio.to_thread(create_account, username, f"scrypt:{salt.hex()}:{digest.hex()}"):
                return page('Account already created. <a href="/admin">Sign in</a>.', 409)
            request.session.clear()
            return RedirectResponse("/admin", status_code=303, headers=HEADERS)
        if request.session.get("setup"):
            return page('Account already created. <a href="/admin">Sign in</a>.', 409)
        admin_username, verifier = account
        match = HASH.fullmatch(verifier)
        if match is None:
            return page("Stored credentials are invalid.", 503)
        salt, digest = match.groups()
        valid = hmac.compare_digest(
            await asyncio.to_thread(derive, password[:1024], bytes.fromhex(salt)),
            bytes.fromhex(digest),
        )
    finally:
        state.login_busy = False
    request.session.clear()
    if not (valid and len(password) <= 1024 and hmac.compare_digest(username.encode(), admin_username.encode())):
        return page('Invalid username or password. <a href="/admin">Try again</a>.', 401)
    # One administrator, one active session. Replace the identifier at login.
    sid = secrets.token_urlsafe(32)
    state.admin_sessions.clear()
    state.admin_sessions[sid] = dict(username=admin_username, csrf_token=secrets.token_urlsafe(32),
                                    expires=time.monotonic() + SESSION_AGE)
    request.session["local_sid"] = sid
    return RedirectResponse("/admin", status_code=303, headers=HEADERS)


@router.get("/auth/me")
async def identity(request: Request):
    admin = get_admin(request)
    if not admin:
        return JSONResponse({"detail": "Admin sign-in required"}, status_code=401, headers=HEADERS)
    return JSONResponse({key: admin[key] for key in ("username", "csrf_token")}, headers=HEADERS)


@router.post("/auth/logout")
async def logout(request: Request):
    request.app.state.admin_sessions.pop(request.session.get("local_sid"), None)
    request.session.clear()
    return JSONResponse({"ok": True}, headers=HEADERS)
