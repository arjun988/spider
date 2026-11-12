"""Probe Gemini connectivity using env key (does not print the key)."""

from __future__ import annotations

from app.core.config import settings


def main() -> None:
    key = settings.gemini_api_key or ""
    print("key_set", bool(key), "length", len(key), "prefix", repr(key[:6]) if key else None)
    print("configured_model", settings.gemini_model)
    if not key:
        return

    from google import genai

    client = genai.Client(api_key=key)
    models = [settings.gemini_model, "gemini-2.0-flash", "gemini-2.5-flash", "gemini-1.5-flash"]
    # de-dupe preserve order
    seen = set()
    ordered = []
    for m in models:
        if m and m not in seen:
            seen.add(m)
            ordered.append(m)

    for model in ordered:
        print("=== trying", model)
        try:
            response = client.models.generate_content(
                model=model,
                contents='Reply with JSON only: {"ok": true}',
                config={
                    "temperature": 0,
                    "max_output_tokens": 64,
                    "response_mime_type": "application/json",
                },
            )
            text = getattr(response, "text", None)
            print("text", repr(text))
            cands = getattr(response, "candidates", None) or []
            print("candidates", len(cands))
            if cands:
                c0 = cands[0]
                print("finish_reason", getattr(c0, "finish_reason", None))
                content = getattr(c0, "content", None)
                parts = getattr(content, "parts", None) if content else None
                print("parts", parts)
            print("prompt_feedback", getattr(response, "prompt_feedback", None))
        except Exception as exc:
            print("ERR", type(exc).__name__, str(exc)[:800])


if __name__ == "__main__":
    main()
