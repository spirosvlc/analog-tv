"""Offline checks for the security boundary and verified Google ID tokens."""

import time
from urllib.parse import parse_qs, urlsplit

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from analog_tv.auth import routes
from analog_tv.auth.security import authorize_request
from analog_tv.core.config import get_settings


@pytest.fixture
def isolated_config(monkeypatch):
    monkeypatch.setenv("ANALOG_ADMIN_EMAIL", "only-owner@gmail.com")
    monkeypatch.setenv("ANALOG_GOOGLE_CLIENT_ID", "test-client.apps.googleusercontent.com")
    monkeypatch.setenv("ANALOG_GOOGLE_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("ANALOG_GOOGLE_REDIRECT_URI", "https://tv.example.com/auth/google/callback")
    monkeypatch.setenv("ANALOG_PUBLIC_BASE_URL", "https://tv.example.com")
    monkeypatch.setenv("ANALOG_SESSION_SECRET", "test-session-secret-not-used-in-production")
    monkeypatch.setenv("ANALOG_COOKIE_SECURE", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def private_app(isolated_config):
    app = FastAPI()

    @app.middleware("http")
    async def gate(request, call_next):
        return await authorize_request(request, call_next)

    app.add_middleware(SessionMiddleware,
                       secret_key="test-session-secret-not-used-in-production",
                       session_cookie="analog_admin_session", https_only=True)
    app.include_router(routes.router)

    @app.get("/admin")
    async def admin():
        return JSONResponse({"panel": "admin"})

    @app.get("/api/channels")
    async def channels():
        return JSONResponse({"channels": []})

    @app.put("/api/settings")
    async def update_settings():
        return JSONResponse({"ok": True})

    @app.get("/api/settings")
    async def read_settings():
        return JSONResponse({"secret": True})

    return app


def test_public_tv_and_private_control(private_app):
    with TestClient(private_app, base_url="https://tv.example.com") as client:
        assert client.get("/api/channels").status_code == 200
        assert client.get("/api/settings").status_code == 401
        assert client.put("/api/settings").status_code == 401
        response = client.get("/admin", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/auth/login"


def test_verifies_google_signature_nonce_and_allowlist(private_app, monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    class FakeSigningKey:
        def __init__(self):
            self.key = key.public_key()

    class FakeJwks:
        def get_signing_key_from_jwt(self, token):
            return FakeSigningKey()

    monkeypatch.setattr(routes, "_JWKS_CLIENT", FakeJwks())

    with TestClient(private_app, base_url="https://tv.example.com") as client:
        response = client.get("/auth/google/login", follow_redirects=False)
        assert response.status_code == 302
        qs = parse_qs(urlsplit(response.headers["location"]).query)
        assert qs["code_challenge_method"] == ["S256"]
        state, nonce = qs["state"][0], qs["nonce"][0]

        claims = {
            "iss": "https://accounts.google.com", "aud": "test-client.apps.googleusercontent.com",
            "exp": int(time.time()) + 600, "iat": int(time.time()),
            "sub": "12345678901234567890", "email": "only-owner@gmail.com",
            "email_verified": True, "nonce": nonce,
        }
        signed = jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test-kid"})

        class FakeResponse:
            def raise_for_status(self):
                pass
            def json(self):
                return {"id_token": signed}

        async def fake_post(self, *args, **kwargs):
            return FakeResponse()

        import httpx
        monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
        result = client.get(f"/auth/google/callback?code=example&state={state}", follow_redirects=False)
        assert result.status_code == 303
        assert result.headers["location"] == "/admin"
        csrf = client.get("/auth/me").json()["csrf_token"]
        assert client.put("/api/settings").status_code == 403
        assert client.put("/api/settings", headers={"X-Analog-CSRF": csrf,
                                                    "Origin": "https://evil.example"}).status_code == 403
        assert client.put("/api/settings", headers={"X-Analog-CSRF": csrf,
                                                    "Origin": "https://tv.example.com"}).status_code == 200
        assert client.get("/admin").status_code == 200
        assert client.post("/auth/logout", headers={"X-Analog-CSRF": csrf}).status_code == 200
        assert client.get("/api/settings").status_code == 401


def test_nonce_mismatch_fails_closed(monkeypatch, isolated_config):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    public_key = key.public_key()
    class SigningKey:
        pass
    SigningKey.key = public_key

    class FakeJwks:
        def get_signing_key_from_jwt(self, _):
            return SigningKey()

    monkeypatch.setattr(routes, "_JWKS_CLIENT", FakeJwks())
    claims = {
        "iss": "https://accounts.google.com", "aud": "test-client.apps.googleusercontent.com",
        "exp": int(time.time())+60, "iat": int(time.time()), "sub": "s",
        "email": "only-owner@gmail.com", "email_verified": True,
        "nonce": "WRONG",
    }
    signed = jwt.encode(claims, key, algorithm="RS256")
    with pytest.raises(ValueError, match="nonce"):
        routes.verify_google_identity(signed, "test-client.apps.googleusercontent.com", "correct")


def test_unverified_email_is_rejected(monkeypatch, isolated_config):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    class FakeJwks:
        def get_signing_key_from_jwt(self, _):
            class Result:
                pass
            result = Result()
            result.key = private_key.public_key()
            return result

    monkeypatch.setattr(routes, "_JWKS_CLIENT", FakeJwks())
    token = jwt.encode({
        "iss": "https://accounts.google.com",
        "aud": "test-client.apps.googleusercontent.com",
        "exp": int(time.time())+60,
        "iat": int(time.time()),
        "sub": "other",
        "email": "only-owner@gmail.com",
        "email_verified": False,
        "nonce": "nonce-123",
    }, private_key, algorithm="RS256")
    with pytest.raises(ValueError, match="unverified"):
        routes.verify_google_identity(token, "test-client.apps.googleusercontent.com", "nonce-123")
