"""Health endpoint tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    response = await client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app"] == "Spider"
    assert "version" in data


@pytest.mark.asyncio
async def test_root(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200
    assert response.json()["app"] == "Spider"


@pytest.mark.asyncio
async def test_webhook_signature_rejection():
    from app.core.security import verify_github_webhook_signature

    payload = b'{"action":"opened"}'
    secret = "test-secret"
    assert verify_github_webhook_signature(payload, None, secret) is False
    assert verify_github_webhook_signature(payload, "sha256=deadbeef", secret) is False

    import hashlib
    import hmac

    sig = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    assert verify_github_webhook_signature(payload, sig, secret) is True


@pytest.mark.asyncio
async def test_encryption_roundtrip():
    from app.core.encryption import decrypt_value, encrypt_value, mask_secret

    encrypted = encrypt_value("AIzaSyTestKey1234567890")
    assert encrypted != "AIzaSyTestKey1234567890"
    assert decrypt_value(encrypted) == "AIzaSyTestKey1234567890"
    assert mask_secret("AIzaSyTestKey1234567890").endswith("7890")
    assert "*" in mask_secret("AIzaSyTestKey1234567890")