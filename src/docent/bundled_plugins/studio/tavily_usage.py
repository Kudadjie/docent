"""Tavily API usage helper — fetch live credit consumption."""
from __future__ import annotations


def fetch_tavily_usage(api_key: str, timeout: float = 5.0) -> dict:
    """Call GET https://api.tavily.com/usage and return the parsed JSON.

    Raises on network/HTTP failure. Caller is responsible for handling errors.
    """
    import httpx

    with httpx.Client(timeout=timeout) as client:
        r = client.get(
            "https://api.tavily.com/usage",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        r.raise_for_status()
        return r.json()
