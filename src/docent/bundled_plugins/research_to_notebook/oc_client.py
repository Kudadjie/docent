"""Thin OpenCode REST API client for in-process LLM calls."""
from __future__ import annotations

import datetime
import json
import urllib.error
import urllib.request
from pathlib import Path

_BASE_URL = "http://127.0.0.1:4096"
_DEFAULT_PROVIDER = "opencode-go"


def _oc_spend_file() -> Path:
    from docent.utils.paths import cache_dir
    return cache_dir() / "research" / "oc_spend.json"


def _read_oc_daily_spend() -> float:
    today = datetime.date.today().isoformat()
    try:
        data = json.loads(_oc_spend_file().read_text(encoding="utf-8"))
        if data.get("date") == today:
            return float(data.get("spend_usd", 0.0))
    except Exception:
        pass
    return 0.0


def _write_oc_daily_spend(spend: float) -> None:
    p = _oc_spend_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps({"date": datetime.date.today().isoformat(), "spend_usd": round(spend, 6)}),
        encoding="utf-8",
    )


class OcUnavailableError(RuntimeError):
    """Raised when OpenCode server is not reachable."""


class OcClient:
    """Send a prompt to the OpenCode REST API and return the response text.

    Usage:
        client = OcClient()
        text = client.call("Summarise X", model="glm-5.1")
    """

    def __init__(self, base_url: str = _BASE_URL, provider: str = _DEFAULT_PROVIDER) -> None:
        self.base_url = base_url
        self.provider = provider

    def is_available(self) -> bool:
        try:
            result = self._api("GET", "/global/health")
            return bool(result.get("healthy"))
        except Exception:
            return False

    def call(self, prompt: str, model: str = "glm-5.1", timeout: int = 300) -> str:
        """Create a session, send the prompt, return the text response."""
        session_id = self._api("POST", "/session", {})["id"]
        response = self._api(
            "POST",
            f"/session/{session_id}/message",
            {
                "parts": [{"type": "text", "text": prompt}],
                "role": "user",
                "model": {"modelID": model, "providerID": self.provider},
            },
            timeout=timeout,
        )

        try:
            cost = float((response.get("info") or {}).get("cost") or 0.0)
            if cost > 0:
                _write_oc_daily_spend(_read_oc_daily_spend() + cost)
        except Exception:
            pass

        return "\n".join(
            p["text"] for p in response.get("parts", []) if p.get("type") == "text"
        )

    def _api(self, method: str, path: str, body: dict | None = None, timeout: int = 10) -> dict:
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": "application/json"} if data else {}
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read())
        except urllib.error.URLError as e:
            raise OcUnavailableError(
                f"OpenCode server not reachable at {self.base_url}. "
                "Run: opencode serve --port 4096"
            ) from e