"""Pydantic schemas for structured agent outputs."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


Severity = Literal["critical", "high", "medium", "low", "informational"]
Category = Literal["bug", "security", "test", "performance", "style", "other"]
VerificationStatus = Literal[
    "pending",
    "verified",
    "rejected",
    "confirmed_static",
    "confirmed_test",
    "unverifiable",
]


class ChangedSymbol(BaseModel):
    file_path: str
    name: str
    symbol_type: str = "function"
    start_line: int | None = None
    end_line: int | None = None


class ChangeAnalysis(BaseModel):
    summary: str
    purpose: str = ""
    categories: list[str] = Field(default_factory=list)
    risky_areas: list[str] = Field(default_factory=list)
    changed_files: list[str] = Field(default_factory=list)
    changed_symbols: list[ChangedSymbol] = Field(default_factory=list)


class FindingDraft(BaseModel):
    finding_key: str = ""
    file_path: str
    start_line: int
    end_line: int
    category: Category = "bug"
    severity: Severity = "medium"
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    title: str
    explanation: str
    failure_scenario: str
    suggested_fix: str | None = None
    supporting_evidence: dict[str, Any] | None = None
    verification_status: VerificationStatus = "pending"
    should_publish: bool = False
    rejected_reason: str | None = None


class VerificationDecision(BaseModel):
    finding_key: str
    accepted: bool
    verification_status: VerificationStatus
    reason: str
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)


class ReviewDecision(BaseModel):
    summary: str
    findings: list[FindingDraft]
    published_count: int = 0
    rejected_count: int = 0
