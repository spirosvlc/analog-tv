"""Google OpenID Connect sign-in for the private Analog TV control center.

Authorization-code + PKCE, state and nonce; the ID token is checked against
Google's JWKS with PyJWT (RSA signature, issuer, audience and expiry).
"""

import asyncio
import base64
import hashlib
import hmac
import logging
import secrets
import time
from html import escape
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from analog_tv.auth.security import get_admin
from analog_tv.core.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["authentication"], include_in_schema=False)
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
_JWKS_CLIENT = jwt.PyJWKClient(GOOGLE_JWKS_URL, cache_jwk_set=True, lifespan=3600)


def configured():
    s = get_settings()
    return all((s.google_client_id, s.google_client_secret, s.google_redirect_uri,
                s.admin_email, s.session_secret, s.public_base_url))


@router.get("/auth/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if get_admin(request):
        return RedirectResponse("/admin", status_code=303)
    active = configured()
    title = "GOOGLE ACCOUNT REQUIRED" if active else "ADMIN LOGIN NOT CONFIGURED"
    message = ("Only the configured Analog TV administrator may access Broadcast Control."
               if active else "Set the private Google OAuth settings in auth.env and restart Analog TV. The player remains available.")
    action = '<a class="button" href="/auth/google/login">SIGN IN WITH GOOGLE</a>' if active else '<p>See README.md for Google sign-in setup.</p>'
    return HTMLResponse(f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Analog TV // Secure Control</title><link rel="stylesheet" href="/static/style.css"></head><body class="admin-body" style="min-height:100vh;display:grid;place-items:center;background:#040b05;color:#8afc7f"><main class="panel" style="max-width:580px;padding:38px;border:1px solid #6dbb65"><span class="eyebrow">ANALOG TV / RESTRICTED AREA</span><h1>BROADCAST CONTROL</h1><h2>{escape(title)}</h2><p>{escape(message)}</p>{action}<p><a href="/">RETURN TO LIVE TV</a></p></main></body></html>''', headers={"Cache-Control": "no-store", "Content-Security-Policy": "default-src 'self'; style-src 'self' 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'"})


@router.get("/auth/google/login")
async def start_google_login(request: Request):
    if not configured():
        return RedirectResponse("/auth/login", status_code=303)
    s = get_settings()
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    request.session["oidc_pending"] = {"state": state, "nonce": nonce, "verifier": verifier, "created": int(time.time())}
    params = {
        "client_id": s.google_client_id,
        "redirect_uri": s.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "nonce": nonce,
        "code_challenge_method": "S256",
        "code_challenge": challenge,
        "prompt": "select_account",
    }
    return RedirectResponse(GOOGLE_AUTH_URL + "?" + urlencode(params), status_code=302)


def verify_google_identity(id_token: str, client_id: str, expected_nonce: str) -> dict:
    """Cryptographically verify Google's ID token; fail closed on any mismatch."""
    key = _JWKS_CLIENT.get_signing_key_from_jwt(id_token)
    claims = jwt.decode(
        id_token,
        key.key,
        algorithms=["RS256"],
        audience=client_id,
        issuer=["https://accounts.google.com", "accounts.google.com"],
        options={"require": ["exp", "iat", "iss", "aud", "sub", "nonce", "email", "email_verified"]},
        leeway=30,
    )
    nonce = str(claims.get("nonce", ""))
    if not nonce or not hmac.compare_digest(nonce, expected_nonce):
        raise ValueError("Invalid Google login nonce")
    if claims.get("email_verified") is not True or not claims.get("sub"):
        raise ValueError("Google email is unverified or subject missing")
    return claims


@router.get("/auth/google/callback")
async def finish_google_login(request: Request):
    s = get_settings()
    pending = request.session.pop("oidc_pending", None)
    code = request.query_params.get("code", "")
    received_state = request.query_params.get("state", "")
    if not configured() or not isinstance(pending, dict) or not code or not received_state:
        request.session.clear()
        return HTMLResponse("Analog TV: invalid or expired login attempt.", status_code=400)
    expected_state = str(pending.get("state", ""))
    if not expected_state or not hmac.compare_digest(received_state, expected_state) or time.time() - int(pending.get("created", 0)) > 600:
        request.session.clear()
        return HTMLResponse("Analog TV: invalid or expired login state.", status_code=400)
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(GOOGLE_TOKEN_URL, data={
                "client_id": s.google_client_id,
                "client_secret": s.google_client_secret,
                "code": code,
                "redirect_uri": s.google_redirect_uri,
                "code_verifier": str(pending["verifier"]),
                "grant_type": "authorization_code",
            })
            response.raise_for_status()
            id_token = response.json().get("id_token", "")
        if not id_token:
            raise ValueError("Google did not supply an ID token")
        claims = await asyncio.to_thread(verify_google_identity, id_token, s.google_client_id, str(pending["nonce"]))
        email = str(claims["email"])
        if email.casefold() != s.admin_email.strip().casefold():
            logger.warning("Denied Google admin sign-in for non-allowlisted account")
            request.session.clear()
            return HTMLResponse("Analog TV: this Google account is not authorized.", status_code=403)
        request.session.clear()
        request.session["analog_admin"] = {"email": email, "sub": str(claims["sub"])}
        request.session["analog_login_at"] = int(time.time())
        request.session["analog_csrf"] = secrets.token_urlsafe(32)
        return RedirectResponse("/admin", status_code=303)
    except (httpx.HTTPError, jwt.PyJWTError, KeyError, ValueError) as exc:
        logger.warning("Google sign-in failed: %s", type(exc).__name__)
        request.session.clear()
        return HTMLResponse("Analog TV Google sign-in failed. Return to /auth/login.", status_code=400)


@router.get("/auth/me")
async def authenticated_user(request: Request):
    admin = get_admin(request)
    if not admin:
        raise HTTPException(401, "Google admin sign-in required")
    return JSONResponse({"email": admin["email"], "csrf_token": request.session["analog_csrf"]}, headers={"Cache-Control": "no-store"})


@router.post("/auth/logout")
async def logout(request: Request):
    request.session.clear()
    return JSONResponse({"ok": True}, headers={"Cache-Control": "no-store"})
