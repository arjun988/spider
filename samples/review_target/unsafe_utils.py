"""Companion helpers with more review bait."""

def parse_config(raw: str) -> dict:
    # BUG: unsafe eval of untrusted input
    return eval(raw)


def fetch_url(url: str) -> str:
    import urllib.request
    # BUG: SSRF — no allowlist / scheme check
    with urllib.request.urlopen(url) as resp:
        return resp.read().decode("utf-8")
