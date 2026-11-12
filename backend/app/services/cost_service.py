"""API cost aggregation and budget checks."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.settings import ModelConfiguration
from app.models.usage import ApiUsageRecord, CostRecord


def monthly_spend(db: Session, organization_id: uuid.UUID) -> float:
    now = datetime.now(timezone.utc)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    total = db.execute(
        select(func.coalesce(func.sum(ApiUsageRecord.estimated_cost_usd), 0.0)).where(
            ApiUsageRecord.organization_id == organization_id,
            ApiUsageRecord.created_at >= start,
        )
    ).scalar()
    return float(total or 0.0)


def budget_remaining(db: Session, organization_id: uuid.UUID) -> dict:
    config = db.execute(
        select(ModelConfiguration).where(ModelConfiguration.organization_id == organization_id)
    ).scalar_one_or_none()
    budget = float(config.monthly_budget_usd) if config else 100.0
    spent = monthly_spend(db, organization_id)
    return {
        "monthly_budget_usd": budget,
        "spent_usd": spent,
        "remaining_usd": max(0.0, budget - spent),
        "over_budget": spent >= budget,
        "alert": spent >= budget * (config.budget_alert_threshold if config else 0.8),
    }


def ensure_within_budget(db: Session, organization_id: uuid.UUID) -> None:
    info = budget_remaining(db, organization_id)
    if info["over_budget"]:
        raise RuntimeError(
            f"Monthly Gemini budget exceeded (${info['spent_usd']:.4f} / ${info['monthly_budget_usd']:.2f})"
        )


def aggregate_daily_costs(db: Session, organization_id: uuid.UUID) -> int:
    """Roll up usage into cost_records for the current UTC day."""
    now = datetime.now(timezone.utc)
    day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    rows = db.execute(
        select(
            ApiUsageRecord.model_name,
            func.sum(ApiUsageRecord.input_tokens),
            func.sum(ApiUsageRecord.output_tokens),
            func.sum(ApiUsageRecord.estimated_cost_usd),
            func.count(),
        ).where(
            ApiUsageRecord.organization_id == organization_id,
            ApiUsageRecord.created_at >= day,
        ).group_by(ApiUsageRecord.model_name)
    ).all()

    written = 0
    for model_name, inp, out, cost, count in rows:
        existing = db.execute(
            select(CostRecord).where(
                CostRecord.organization_id == organization_id,
                CostRecord.date == day,
                CostRecord.model_name == model_name,
            )
        ).scalar_one_or_none()
        if existing:
            existing.input_tokens = int(inp or 0)
            existing.output_tokens = int(out or 0)
            existing.total_cost_usd = float(cost or 0)
            existing.request_count = int(count or 0)
        else:
            db.add(
                CostRecord(
                    organization_id=organization_id,
                    date=day,
                    model_name=model_name,
                    input_tokens=int(inp or 0),
                    output_tokens=int(out or 0),
                    total_cost_usd=float(cost or 0),
                    request_count=int(count or 0),
                )
            )
        written += 1
    db.flush()
    return written