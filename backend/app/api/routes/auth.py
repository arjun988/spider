"""GitHub OAuth SSO routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.core.config import settings
from app.core.security import AuthContext, require_user
from app.services import auth_service
from app.services.audit import emit_audit

router = APIRouter(prefix="/auth", tags=["auth"])


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict
    organizations: list[dict]


@router.get("/github/login")
async def github_login(db: AsyncSession = Depends(get_db_session)):
    if not settings.github_app_client_id:
        raise HTTPException(status_code=400, detail="GITHUB_APP_CLIENT_ID not configured")
    url = await auth_service.begin_oauth(db)
    return {"authorize_url": url}


@router.get("/github/callback")
async def github_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db_session),
):
    row = await auth_service.consume_oauth_state(db, state)
    if row is None:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")
    try:
        gh_token = await auth_service.exchange_code(code)
        gh_user = await auth_service.fetch_github_user(gh_token)
        user = await auth_service.upsert_user_from_github(db, gh_user)
        memberships = await auth_service.sync_memberships(
            db, user, gh_user.get("_org_logins") or []
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    org_id = memberships[0].organization_id if memberships else None
    role = memberships[0].role if memberships else None
    token = auth_service.create_access_token(user.id, org_id=org_id, role=role)
    await emit_audit(
        db,
        action="auth.login",
        actor_user_id=user.id,
        organization_id=org_id,
        resource_type="user",
        resource_id=str(user.id),
        metadata={"login": user.github_login},
    )
    # Redirect to frontend with token fragment for SPA pickup
    redirect = f"{settings.frontend_url}/auth/callback#access_token={token}"
    return RedirectResponse(redirect)


@router.post("/logout")
async def logout(auth: AuthContext = Depends(require_user)):
    return {"status": "ok", "user_id": str(auth.user_id)}


@router.get("/me")
async def me(
    auth: AuthContext = Depends(require_user),
    db: AsyncSession = Depends(get_db_session),
):
    user = await auth_service.get_user_with_memberships(db, auth.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    orgs = [
        {
            "id": str(m.organization_id),
            "role": m.role,
            "name": m.organization.name if m.organization else None,
            "slug": m.organization.slug if m.organization else None,
            "github_org_login": m.organization.github_org_login if m.organization else None,
        }
        for m in user.memberships
    ]
    return {
        "id": str(user.id),
        "github_login": user.github_login,
        "email": user.email,
        "name": user.name,
        "avatar_url": user.avatar_url,
        "organization_id": str(auth.organization_id) if auth.organization_id else None,
        "role": auth.role,
        "organizations": orgs,
        "dev_bypass": auth.is_dev_bypass,
    }


@router.post("/switch-org")
async def switch_org(
    organization_id: str,
    auth: AuthContext = Depends(require_user),
    db: AsyncSession = Depends(get_db_session),
):
    user = await auth_service.get_user_with_memberships(db, auth.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    wanted = uuid.UUID(organization_id)
    membership = next((m for m in user.memberships if m.organization_id == wanted), None)
    if membership is None:
        raise HTTPException(status_code=403, detail="Not a member of organization")
    token = auth_service.create_access_token(
        user.id, org_id=membership.organization_id, role=membership.role
    )
    return {
        "access_token": token,
        "organization_id": str(membership.organization_id),
        "role": membership.role,
    }
