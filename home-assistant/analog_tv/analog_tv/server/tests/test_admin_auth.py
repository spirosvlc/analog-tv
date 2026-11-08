"""Exercise local authentication against the real route and middleware stack."""
import re

import pytest
from fastapi.testclient import TestClient

from analog_tv.application import ApplicationFactory
from analog_tv.auth.local import derive
from analog_tv.core.config import get_settings

ORIGIN = "https://tv.example.test"
PASSWORD = "offline fixture password"


@pytest.fixture(scope="module")
def verifier():
    salt = bytes(16)
    return f"scrypt:{salt.hex()}:{derive(PASSWORD.encode(), salt).hex()}"


@pytest.fixture
def client(monkeypatch, verifier):
    for key, value in {
        "ADMIN_USERNAME": "operator", "ADMIN_PASSWORD_HASH": verifier,
        "SESSION_SECRET": "t" * 64, "COOKIE_SECURE": "true",
        "PUBLIC_BASE_URL": ORIGIN,
    }.items():
        monkeypatch.setenv("ANALOG_" + key, value)
    get_settings.cache_clear()
    with TestClient(ApplicationFactory.create(), base_url=ORIGIN, follow_redirects=False) as client:
        yield client
    get_settings.cache_clear()


def submit(client, password=PASSWORD, username="operator", origin=ORIGIN, token=None):
    page = client.get("/auth/login")
    assert page.status_code == 200
    if token is None:
        token = re.search(r'name="csrf" value="([^"]+)"', page.text)[1]
    return client.post("/auth/login", headers={"Origin": origin},
                       data={"csrf": token, "username": username, "password": password})


def test_public_and_private(client):
    for path in ("/", "/api/channels", "/api/alerts/latest"):
        assert client.get(path).status_code == 200
    # The forecast is public but needs a configured location.
    assert client.get("/api/weather/forecast").status_code == 400
    assert client.get("/admin").headers["location"] == "/auth/login"
    assert client.get("/api/settings").status_code == 401
    assert client.put("/api/settings").status_code == 401
    assert client.get("/auth/google/callback").status_code == 401


def test_login_and_revocable_logout(client):
    assert submit(client, origin="https://other.test").status_code == 403
    assert submit(client, token="bad").status_code == 403
    assert submit(client, username="another").status_code == 401
    response = submit(client)
    assert response.status_code == 303
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "secure" in cookie and "samesite=lax" in cookie
    assert client.get("/admin").status_code == 200
    identity = client.get("/auth/me").json()
    assert identity["username"] == "operator"
    headers = {"X-Analog-CSRF": identity["csrf_token"]}
    assert client.put("/api/settings", json={}).status_code == 403
    assert client.put("/api/settings", json={}, headers={**headers, "Origin": ORIGIN}).status_code == 200
    assert client.post("/auth/logout").status_code == 403
    assert client.post("/auth/logout", headers={**headers, "Origin": "https://other.test"}).status_code == 403
    saved = client.cookies.get("analog_local_admin")
    assert client.post("/auth/logout", headers=headers).status_code == 200
    client.cookies.set("analog_local_admin", saved)
    assert client.get("/api/settings").status_code == 401


def test_rate_limit(client):
    for _ in range(5):
        assert submit(client, password="wrong").status_code == 401
    assert submit(client).status_code == 429
    assert client.get("/").status_code == 200


@pytest.mark.parametrize("key,value", [
    ("ADMIN_PASSWORD_HASH", "legacy"), ("SESSION_SECRET", "short"),
    ("ADMIN_USERNAME", ""), ("COOKIE_SECURE", "invalid"),
])
def test_invalid_config_keeps_player_public(client, monkeypatch, key, value):
    monkeypatch.setenv("ANALOG_" + key, value)
    get_settings.cache_clear()
    assert client.get("/auth/login").status_code == 503
    assert client.post("/auth/login").status_code == 503
    assert client.get("/api/settings").status_code == 401
    assert client.get("/").status_code == 200


def test_http_cannot_serve_credentials_form(client):
    with TestClient(client.app, base_url="http://tv.example.test",
                    follow_redirects=False) as insecure:
        assert insecure.get("/").status_code == 200
        assert insecure.get("/auth/login").headers["location"] == ORIGIN + "/auth/login"
        assert insecure.post("/auth/login", headers={"Origin": ORIGIN}).status_code == 403


def test_session_expires(client):
    assert submit(client).status_code == 303
    session = next(iter(client.app.state.admin_sessions.values()))
    session["expires"] = 0
    assert client.get("/api/settings").status_code == 401
