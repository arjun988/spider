"""GitHub App JWT and installation access token generation."""

from __future__ import annotations

import time
from pathlib import Path

import httpx
import jwt

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_token_cache: dict[int, tuple[str, float]] = {}


def load_private_key() -> str:
    path = Path(settings.github_app_private_key_path)
    if not path.exists():
        raise FileNotFoundError(
            f"GitHub App private key not found at {path}. "
            "Place the .pem file under secrets/ and set GITHUB_APP_PRIVATE_KEY_PATH."
        )
    return path.read_text(encoding="utf-8")


def create_app_jwt() -> str:
    if not settings.github_app_id:
        raise ValueError("GITHUB_APP_ID is not configured")
    now = int(time.time())
    payload = {
        "iat": now - 60,
        "exp": now + (9 * 60),
        "iss": settings.github_app_id,
    }
    return jwt.encode(payload, load_private_key(), algorithm="RS256")


def get_installation_token(installation_id: int) -> str:
    """Return a cached installation access token (never expose to frontend)."""
    cached = _token_cache.get(installation_id)
    if cached and cached[1] > time.time() + 60:
        return cached[0]

    app_jwt = create_app_jwt()
    url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            url,
            headers={
                "Authorization": f"Bearer {app_jwt}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        response.raise_for_status()
        data = response.json()

    token = data["token"]
    # GitHub tokens expire in ~1 hour; cache conservatively
    expires_at = time.time() + 50 * 60
    _token_cache[installation_id] = (token, expires_at)
    logger.info("installation_token_issued", installation_id=installation_id)
    return token


def clear_token_cache(installation_id: int | None = None) -> None:
    if installation_id is None:
        _token_cache.clear()
    else:
        _token_cache.pop(installation_id, None)