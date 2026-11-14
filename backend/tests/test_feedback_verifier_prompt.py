"""Feedback signals are injected into verifier guidance text."""

from __future__ import annotations

from app.services.feedback_signals import format_verifier_guidance


def test_format_verifier_guidance_includes_fp_rates_and_examples():
    text = format_verifier_guidance(
        {
            "category_fp_rate": {"security": 0.5, "bug": 0.35},
            "path_fp_rate": {"src/legacy": 0.6},
            "confidence_bumps": {"security": 0.2},
            "prompt_hints": ["Category `security` has 50% recent false-positive feedback"],
            "fp_examples": [
                {
                    "category": "security",
                    "title": "Possible hardcoded secret",
                    "file_path": "src/legacy/config.py",
                }
            ],
        }
    )
    assert "security: 50% FP" in text
    assert "confidence bump" in text
    assert "src/legacy/" in text
    assert "Possible hardcoded secret" in text
    assert "concrete failure" in text.lower()


def test_format_verifier_guidance_empty():
    assert format_verifier_guidance(None) == ""
    assert "Not enough category feedback" in format_verifier_guidance({})
