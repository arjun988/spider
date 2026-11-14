"""Security utilities for request authentication and webhook verification."""

from __future__ import annotations

import hashlib
import hmac
import uuid
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session


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


@dataclass
class AuthContext:
    user_id: uuid.UUID
    github_login: str
    organization_id: uuid.UUID | None
    role: str | None
    is_dev_bypass: bool = False


async def get_auth_context(
    authorization: str | None = Header(default=None),
    x_organization_id: str | None = Header(default=None, alias="X-Organization-Id"),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    db: AsyncSession = Depends(get_db_session),
) -> AuthContext:
    """Resolve JWT bearer, legacy admin token, or development bypass."""
    from app.core.config import settings
    from app.services import auth_service

    # Legacy shared secret still accepted for scripts
    if x_admin_token and hmac.compare_digest(x_admin_token, settings.secret_key):
        user, membership = await auth_service.ensure_dev_user(db)
        org_id = membership.organization_id if membership else None
        if x_organization_id:
            try:
                org_id = uuid.UUID(x_organization_id)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="Invalid X-Organization-Id") from exc
        return AuthContext(
            user_id=user.id,
            github_login=user.github_login,
            organization_id=org_id,
            role="admin",
            is_dev_bypass=True,
        )

    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        try:
            payload = auth_service.decode_access_token(token)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            ) from exc
        user = await auth_service.get_user_with_memberships(db, uuid.UUID(payload["sub"]))
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        org_id = None
        role = None
        if x_organization_id:
            try:
                wanted = uuid.UUID(x_organization_id)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="Invalid X-Organization-Id") from exc
            membership = next((m for m in user.memberships if m.organization_id == wanted), None)
            if membership is None:
                raise HTTPException(status_code=403, detail="Not a member of organization")
            org_id = membership.organization_id
            role = membership.role
        elif payload.get("org_id"):
            org_id = uuid.UUID(payload["org_id"])
            role = payload.get("role")
            membership = next((m for m in user.memberships if m.organization_id == org_id), None)
            if membership is None and user.memberships:
                org_id = user.memberships[0].organization_id
                role = user.memberships[0].role
            elif membership:
                role = membership.role
        elif user.memberships:
            org_id = user.memberships[0].organization_id
            role = user.memberships[0].role
        return AuthContext(
            user_id=user.id,
            github_login=user.github_login,
            organization_id=org_id,
            role=role,
        )

    # Dev bypass: development only, never staging/production
    allow_dev_bypass = (
        settings.app_env == "development"
        and settings.auth_disabled_in_dev
        and not settings.require_auth
        and not settings.is_production
    )
    if allow_dev_bypass:
        user, membership = await auth_service.ensure_dev_user(db)
        org_id = membership.organization_id if membership else None
        if x_organization_id:
            try:
                org_id = uuid.UUID(x_organization_id)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="Invalid X-Organization-Id") from exc
        return AuthContext(
            user_id=user.id,
            github_login=user.github_login,
            organization_id=org_id,
            role="admin",
            is_dev_bypass=True,
        )

    detail = "Authentication required"
    if settings.app_env in {"staging", "production"}:
        detail = "Sign in with GitHub SSO is required in staging/production"
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
    )


def require_role(minimum: str):
    async def _dep(auth: AuthContext = Depends(get_auth_context)) -> AuthContext:
        from app.services.auth_service import role_at_least

        if not role_at_least(auth.role, minimum):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role {minimum} or higher",
            )
        return auth

    return _dep


async def require_admin_token(
    auth: AuthContext = Depends(require_role("admin")),
) -> AuthContext:
    """Backward-compatible name — now enforces admin role (or dev bypass)."""
    return auth


async def require_member(
    auth: AuthContext = Depends(require_role("member")),
) -> AuthContext:
    return auth


async def require_user(
    auth: AuthContext = Depends(get_auth_context),
) -> AuthContext:
    return auth
