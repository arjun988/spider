"""Security utilities for request authentication and webhook verification."""

from __future__ import annotations

import hashlib
import hmac

from fastapi import Header, HTTPException, status


def verify_github_webhook_signature(
    payload: bytes,
    signature_header: str | None,
    secret: str,
) -> bool:
    """Verify GitHub webhook HMAC-SHA256 signature (X-Hub-Signature-256)."""
    if not signature_header or not secret:
        return False
    if not signature_header.startswith("sha256="):
        return False

    expected = hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()
    received = signature_header.removeprefix("sha256=")
    return hmac.compare_digest(expected, received)


def require_admin_token(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> None:
    """Simple shared-secret gate for internal admin API (Phase 1)."""
    from app.core.config import settings

    if settings.app_env == "development" and not settings.is_production:
        # In development allow missing token when secret_key is default
        if x_admin_token is None:
            return

    expected = settings.secret_key
    if not x_admin_token or not hmac.compare_digest(x_admin_token, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin token",
        )