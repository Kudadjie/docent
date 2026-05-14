"""Thin OpenCode REST API client for in-process LLM calls."""
from __future__ import annotations

import datetime
import json
import urllib.error
import urllib.request
from pathlib import Path

_BASE_URL = "http://127.0.0.1:4096"
_DEFAULT_PROVIDER = "opencode-go"


def _detect_base_url() -> str:
    """Return the OpenCode base URL.

    In WSL2, ``127.0.0.1`` points to the Linux VM — not the Windows host
    where OpenCode typically runs.  Detect WSL2 and swap in the Windows
    host IP so the client can reach the server.
    """
    # Fast path: native Linux / macOS / Windows
    try:
        proc_version = Path("/proc/version").read_text()
    except (FileNotFoundError, PermissionError):
        return _BASE_URL

    if "microsoft" not in proc_version.lower():
        return _BASE_URL

    # We're inside WSL2 — read the nameserver from resolv.conf
    try:
        for line in Path("/etc/resolv.conf").read_text().splitlines():
            line = line.strip()
            if line.startswith("nameserver"):
                host_ip = line.split(None, 1)[1]
                return f"http://{host_ip}:4096"
    except (FileNotFoundError, PermissionError, IndexError):
        pass

    return _BASE_URL


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


class OcBudgetExceededError(RuntimeError):
    """Raised when daily OC spend reaches 90% of the configured budget."""


class OcClient:
    """Send a prompt to the OpenCode REST API and return the response text.

    Usage:
        client = OcClient()
        text = client.call("Summarise X", model="glm-5.1")
    """

    def __init__(
        self,
        base_url: str | None = None,
        provider: str = _DEFAULT_PROVIDER,
        budget_usd: float = 0.0,
    ) -> None:
        self.base_url = base_url or _detect_base_url()
        self.provider = provider
        self.budget_usd = budget_usd

    def is_available(self) -> bool:
        try:
            result = self._api("GET", "/global/health")
            return bool(result.get("healthy"))
        except Exception:
            return False

    def call(self, prompt: str, model: str = "glm-5.1", timeout: int = 300) -> str:
        """Create a session, send the prompt, return the text response."""
        if self.budget_usd > 0:
            current = _read_oc_daily_spend()
            if current >= self.budget_usd * 0.9:
                raise OcBudgetExceededError(
                    f"OpenCode daily budget nearly exhausted "
                    f"(${current:.2f} of ${self.budget_usd:.2f} today). "
                    f"Increase with `docent research config-set oc_budget_usd <amount>` "
                    f"or set oc_budget_usd=0 to remove the limit."
                )

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