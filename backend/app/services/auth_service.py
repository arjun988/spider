"""GitHub OAuth SSO and JWT session helpers."""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.github import GitHubInstallation
from app.models.organization import Organization
from app.models.user import OAuthState, OrgMembership, User

GITHUB_AUTHORIZE = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN = "https://github.com/login/oauth/access_token"
GITHUB_API = "https://api.github.com"
ROLE_RANK = {"viewer": 1, "member": 2, "admin": 3}


def create_access_token(
    user_id: uuid.UUID,
    *,
    org_id: uuid.UUID | None = None,
    role: str | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "org_id": str(org_id) if org_id else None,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=settings.auth_jwt_ttl_hours)).timestamp()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.secret_key, algorithms=["HS256"])


async def begin_oauth(db: AsyncSession, redirect_uri: str | None = None) -> str:
    state = secrets.token_urlsafe(24)
    db.add(
        OAuthState(
            id=uuid.uuid4(),
            state=state,
            redirect_uri=redirect_uri or f"{settings.frontend_url}/auth/callback",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        )
    )
    await db.flush()
    params = {
        "client_id": settings.github_app_client_id,
        "redirect_uri": f"{settings.frontend_url}/auth/callback",
        "scope": "read:user user:email read:org",
        "state": state,
    }
    return f"{GITHUB_AUTHORIZE}?{urlencode(params)}"


async def exchange_code(code: str) -> str:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            GITHUB_TOKEN,
            headers={"Accept": "application/json"},
            data={
                "client_id": settings.github_app_client_id,
                "client_secret": settings.github_app_client_secret,
                "code": code,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        token = data.get("access_token")
        if not token:
            raise ValueError(data.get("error_description") or "OAuth token exchange failed")
        return token


async def fetch_github_user(access_token: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        user_resp = await client.get(f"{GITHUB_API}/user", headers=headers)
        user_resp.raise_for_status()
        user = user_resp.json()
        email = user.get("email")
        if not email:
            emails_resp = await client.get(f"{GITHUB_API}/user/emails", headers=headers)
            if emails_resp.status_code == 200:
                emails = emails_resp.json()
                primary = next((e for e in emails if e.get("primary") and e.get("verified")), None)
                email = (primary or (emails[0] if emails else {})).get("email")
        user["email"] = email
        orgs_resp = await client.get(f"{GITHUB_API}/user/orgs", headers=headers)
        org_logins: list[str] = []
        if orgs_resp.status_code == 200:
            org_logins = [o.get("login") for o in orgs_resp.json() if o.get("login")]
        user["_org_logins"] = org_logins
        return user


async def upsert_user_from_github(db: AsyncSession, gh_user: dict[str, Any]) -> User:
    github_id = str(gh_user["id"])
    result = await db.execute(select(User).where(User.github_id == github_id))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(
            id=uuid.uuid4(),
            github_id=github_id,
            github_login=gh_user["login"],
            email=gh_user.get("email"),
            name=gh_user.get("name"),
            avatar_url=gh_user.get("avatar_url"),
        )
        db.add(user)
    else:
        user.github_login = gh_user["login"]
        user.email = gh_user.get("email") or user.email
        user.name = gh_user.get("name") or user.name
        user.avatar_url = gh_user.get("avatar_url") or user.avatar_url
    user.last_login_at = datetime.now(timezone.utc)
    await db.flush()
    return user


async def sync_memberships(db: AsyncSession, user: User, org_logins: list[str]) -> list[OrgMembership]:
    """Attach user to Spider orgs matching GitHub installations / org logins."""
    inst_q = await db.execute(
        select(GitHubInstallation).where(GitHubInstallation.is_active.is_(True))
    )
    installations = list(inst_q.scalars().all())
    logins = {login.lower() for login in org_logins}
    logins.add(user.github_login.lower())

    memberships: list[OrgMembership] = []
    for inst in installations:
        if inst.account_login.lower() not in logins and inst.account_type == "Organization":
            # User orgs don't include this install account
            if user.github_login.lower() != inst.account_login.lower():
                continue
        existing = await db.execute(
            select(OrgMembership).where(
                OrgMembership.user_id == user.id,
                OrgMembership.organization_id == inst.organization_id,
            )
        )
        membership = existing.scalar_one_or_none()
        if membership is None:
            # First member of an org becomes admin
            count_q = await db.execute(
                select(OrgMembership).where(OrgMembership.organization_id == inst.organization_id)
            )
            is_first = count_q.scalars().first() is None
            membership = OrgMembership(
                id=uuid.uuid4(),
                user_id=user.id,
                organization_id=inst.organization_id,
                role="admin" if is_first else "member",
            )
            db.add(membership)
        memberships.append(membership)

    # If no installations matched but orgs exist, bootstrap first org as admin for first user
    if not memberships:
        org_q = await db.execute(select(Organization).order_by(Organization.created_at.asc()).limit(1))
        org = org_q.scalar_one_or_none()
        if org:
            existing = await db.execute(
                select(OrgMembership).where(
                    OrgMembership.user_id == user.id,
                    OrgMembership.organization_id == org.id,
                )
            )
            membership = existing.scalar_one_or_none()
            if membership is None:
                count_q = await db.execute(
                    select(OrgMembership).where(OrgMembership.organization_id == org.id)
                )
                is_first = count_q.scalars().first() is None
                membership = OrgMembership(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    organization_id=org.id,
                    role="admin" if is_first else "member",
                )
                db.add(membership)
            memberships.append(membership)

    await db.flush()
    return memberships


async def consume_oauth_state(db: AsyncSession, state: str) -> OAuthState | None:
    result = await db.execute(select(OAuthState).where(OAuthState.state == state))
    row = result.scalar_one_or_none()
    if row is None:
        return None
    if row.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        await db.delete(row)
        return None
    await db.delete(row)
    await db.flush()
    return row


async def get_user_with_memberships(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    result = await db.execute(
        select(User)
        .where(User.id == user_id)
        .options(selectinload(User.memberships).selectinload(OrgMembership.organization))
    )
    return result.scalar_one_or_none()


def role_at_least(role: str | None, minimum: str) -> bool:
    return ROLE_RANK.get(role or "", 0) >= ROLE_RANK.get(minimum, 99)


async def ensure_dev_user(db: AsyncSession) -> tuple[User, OrgMembership | None]:
    """Development bypass identity when auth is disabled."""
    result = await db.execute(select(User).where(User.github_id == "dev-local"))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(
            id=uuid.uuid4(),
            github_id="dev-local",
            github_login="dev",
            name="Local Dev",
            email="dev@localhost",
        )
        db.add(user)
        await db.flush()
    org_q = await db.execute(select(Organization).order_by(Organization.created_at.asc()).limit(1))
    org = org_q.scalar_one_or_none()
    membership = None
    if org:
        mem_q = await db.execute(
            select(OrgMembership).where(
                OrgMembership.user_id == user.id,
                OrgMembership.organization_id == org.id,
            )
        )
        membership = mem_q.scalar_one_or_none()
        if membership is None:
            membership = OrgMembership(
                id=uuid.uuid4(),
                user_id=user.id,
                organization_id=org.id,
                role="admin",
            )
            db.add(membership)
            await db.flush()
    return user, membership
