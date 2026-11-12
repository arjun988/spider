"""Smoke-test installation.created webhook handling."""

from __future__ import annotations

import hashlib
import hmac
import json
import time

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.config import Settings, get_settings
from app.database.session import get_sync_session_factory
from app.main import app

get_settings.cache_clear()
settings = Settings()


def main() -> None:
    payload = {
        "action": "created",
        "installation": {
            "id": 181374825,
            "account": {"login": "arjun988", "id": 95240136, "type": "User"},
            "permissions": {"contents": "read", "pull_requests": "write"},
            "repository_selection": "selected",
        },
        "repositories": [
            {
                "id": 1445943099,
                "name": "ArjunShuklaPortfolio",
                "full_name": "arjun988/ArjunShuklaPortfolio",
                "private": True,
                "owner": {"login": "arjun988"},
            },
            {
                "id": 1455734925,
                "name": "spider",
                "full_name": "arjun988/spider",
                "private": True,
                "owner": {"login": "arjun988"},
            },
        ],
        "sender": {"login": "arjun988", "id": 95240136},
    }
    body = json.dumps(payload).encode()
    sig = "sha256=" + hmac.new(
        settings.github_app_webhook_secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    client = TestClient(app)
    response = client.post(
        "/api/webhooks/github",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "installation",
            "X-GitHub-Delivery": "script-install-2",
            "X-Hub-Signature-256": sig,
        },
    )
    print("status", response.status_code)
    print("body", response.text)
    time.sleep(1.5)
    db = get_sync_session_factory()()
    rows = db.execute(
        text(
            "select event_type, action, status from webhook_events "
            "order by created_at desc limit 5"
        )
    ).all()
    print("webhooks", rows)
    db.close()


if __name__ == "__main__":
    main()
