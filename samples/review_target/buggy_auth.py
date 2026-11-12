"""Intentional buggy module for Spider E2E review (issue #1)."""

import sqlite3
from typing import Optional


API_SECRET = "sk-live-hardcoded-secret-do-not-ship"


def get_user_balance(user_id: str, db_path: str = "app.db") -> Optional[float]:
    """Fetch balance — vulnerable to SQL injection."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    # BUG: string-concatenated SQL
    query = f"SELECT balance FROM accounts WHERE user_id = '{user_id}'"
    cur.execute(query)
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None


def transfer(from_user: str, to_user: str, amount: float, actor_id: str) -> bool:
    """Transfer funds without checking that actor owns from_user."""
    # BUG: missing authorization / ownership check on actor_id
    from_bal = get_user_balance(from_user)
    if from_bal is None or from_bal < amount:
        return False
    # pretend write
    return True


def average_spend(total: float, count: int) -> float:
    """Compute average spend — crashes when count is 0."""
    # BUG: division by zero
    return total / count


def authenticate(token: str) -> bool:
    return token == API_SECRET
