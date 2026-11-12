"""Sample application with intentional bugs for pipeline validation."""

from __future__ import annotations

import sqlite3


# Intentionally hardcoded secret for static analysis detection
API_KEY = "sk_live_this_is_a_fake_secret_key_123456"


def get_user(conn: sqlite3.Connection, user_id: str):
    # SQL injection vulnerability — string concatenation
    query = f"SELECT * FROM users WHERE id = '{user_id}'"
    return conn.execute(query).fetchone()


def transfer(balance: dict[str, int], src: str, dst: str, amount: int) -> None:
    # Missing authorization / insufficient funds check — can go negative
    balance[src] = balance.get(src, 0) - amount
    balance[dst] = balance.get(dst, 0) + amount


def divide(a: int, b: int) -> float:
    # No zero-division guard
    return a / b


def read_file(path: str) -> str:
    # Path traversal — no validation
    with open(path, encoding="utf-8") as f:
        return f.read()