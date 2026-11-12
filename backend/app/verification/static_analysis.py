"""Lightweight static checks to supplement AI findings."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class StaticFinding:
    file_path: str
    line: int
    rule: str
    message: str
    severity: str = "medium"


SECRET_PATTERNS = [
    (re.compile(r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*['\"][^'\"]{12,}['\"]"), "hardcoded_secret"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "aws_access_key"),
    (re.compile(r"-----BEGIN (RSA |EC )?PRIVATE KEY-----"), "private_key"),
]

SQL_CONCAT = re.compile(r"(?i)(execute|executemany|raw)\s*\(.*\+|f[\"'].*SELECT|cursor\.execute\s*\(\s*[f\"']")


def scan_patch(file_path: str, patch: str | None) -> list[StaticFinding]:
    if not patch:
        return []
    findings: list[StaticFinding] = []
    new_line = 0
    for raw in patch.splitlines():
        if raw.startswith("@@"):
            try:
                plus = raw.split("+")[1].split(" ")[0]
                new_line = int(plus.split(",")[0]) - 1
            except (IndexError, ValueError):
                continue
            continue
        if raw.startswith("+") and not raw.startswith("+++"):
            new_line += 1
            content = raw[1:]
            for pattern, rule in SECRET_PATTERNS:
                if pattern.search(content):
                    findings.append(
                        StaticFinding(
                            file_path=file_path,
                            line=new_line,
                            rule=rule,
                            message=f"Possible secret committed ({rule})",
                            severity="critical",
                        )
                    )
            if SQL_CONCAT.search(content):
                findings.append(
                    StaticFinding(
                        file_path=file_path,
                        line=new_line,
                        rule="sql_concatenation",
                        message="Possible SQL injection via string concatenation",
                        severity="high",
                    )
                )
        elif raw.startswith("-") and not raw.startswith("---"):
            continue
        elif raw.startswith("\\"):
            continue
        else:
            # context
            if raw.startswith(" "):
                new_line += 1
    return findings


def scan_files(files: list[dict[str, Any]]) -> list[StaticFinding]:
    out: list[StaticFinding] = []
    for f in files:
        out.extend(scan_patch(f.get("filename") or "", f.get("patch")))
    return out