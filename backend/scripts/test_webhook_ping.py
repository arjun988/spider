"""Local webhook ping/signature smoke test."""

from __future__ import annotations

import hashlib
import hmac
import json

from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import app

get_settings.cache_clear()
settings = Settings()


def main() -> None:
    body = json.dumps({"zen": "Design for failure.", "hook_id": 1}).encode()
    secret = settings.github_app_webhook_secret.encode()
    sig = "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()
    client = TestClient(app)
    response = client.post(
        "/api/webhooks/github",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "ping",
            "X-GitHub-Delivery": "script-ping-1",
            "X-Hub-Signature-256": sig,
        },
    )
    print("status", response.status_code)
    print("body", response.text)


if __name__ == "__main__":
    main()
