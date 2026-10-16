"""Security middleware: CORS, rate limiting, CSP headers, request logging."""
from __future__ import annotations

import logging
import time

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from .config import settings

log = logging.getLogger(__name__)


def add_security(app: FastAPI) -> None:
    """Attach all production security middleware to the app."""

    # ── CORS ───────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
        max_age=3600,
    )

    # ── Security headers ───────────────────────────────────────────────
    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if request.url.path.startswith("/api/"):
            response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        return response

    # ── Request logging ────────────────────────────────────────────────
    @app.middleware("http")
    async def request_logger(request: Request, call_next):
        start = time.perf_counter()
        response: Response = await call_next(request)
        elapsed = (time.perf_counter() - start) * 1000
        if request.url.path.startswith("/api/"):
            log.info(
                "%s %s → %d (%.0fms)",
                request.method, request.url.path, response.status_code, elapsed,
            )
        return response

    # ── Rate limiting (best-effort, single process) ────────────────────
    try:
        from slowapi import Limiter, _rate_limit_exceeded_handler
        from slowapi.errors import RateLimitExceeded
        from slowapi.util import get_remote_address

        limiter = Limiter(key_func=get_remote_address, default_limits=[settings.RATE_LIMIT])
        app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
        log.info("Rate limiting active: %s", settings.RATE_LIMIT)
    except ImportError:
        log.warning("slowapi not installed — rate limiting disabled")
