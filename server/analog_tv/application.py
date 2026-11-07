"""Analog TV FastAPI application and authorization boundary."""
import secrets

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from analog_tv.api.routes.alerts import router as alerts_router
from analog_tv.api.routes.channels import router as channels_router
from analog_tv.api.routes.pages import router as pages_router
from analog_tv.api.routes.settings import router as settings_router
from analog_tv.api.routes.youtube import router as youtube_router
from analog_tv.api.routes.weather_channel import router as weather_router
from analog_tv.auth.routes import router as auth_router
from analog_tv.auth.security import authorize_request
from analog_tv.core.config import get_settings
from analog_tv.core.lifespan import application_lifespan


class ApplicationFactory:
    @staticmethod
    def create() -> FastAPI:
        settings = get_settings()
        application = FastAPI(title=settings.app_name, version="2.1.0", lifespan=application_lifespan)

        @application.middleware("http")
        async def security_gate(request, call_next):
            response = await authorize_request(request, call_next)
            if request.url.path in {"/", "/admin"} or request.url.path.startswith("/static/"):
                response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
                response.headers["Pragma"] = "no-cache"
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            response.headers["X-Frame-Options"] = "DENY"
            return response

        # SessionMiddleware MUST wrap the security gate so request.session exists.
        # When authentication is unconfigured, random ephemeral signing key is used,
        # but Google login still fails closed until all credentials are configured.
        application.add_middleware(
            SessionMiddleware,
            secret_key=settings.session_secret or secrets.token_urlsafe(48),
            session_cookie="analog_admin_session",
            max_age=8 * 3600,
            same_site="lax",  # required for Google OAuth redirect
            https_only=settings.cookie_secure,
        )

        application.mount("/static", StaticFiles(directory="analog_tv/static"), name="static")
        application.include_router(auth_router)
        application.include_router(pages_router)
        application.include_router(channels_router, prefix="/api")
        application.include_router(alerts_router, prefix="/api")
        application.include_router(settings_router, prefix="/api")
        application.include_router(youtube_router, prefix="/api")
        application.include_router(weather_router, prefix="/api")

        @application.get("/health", include_in_schema=False)
        async def health():
            return {"status": "ok", "app": "Analog TV"}

        return application
