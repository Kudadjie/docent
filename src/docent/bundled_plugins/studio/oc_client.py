"""Thin OpenCode REST API client for in-process LLM calls."""
from __future__ import annotations

import datetime
import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

_BASE_URL = "http://127.0.0.1:4096"
_DEFAULT_PROVIDER = "opencode-go"

# Module-level model check cache: model_id → OcModelError (failed) or None (ok).
# Persists across OcClient instances within a single process.
_model_check_cache: dict[str, "OcModelError | None"] = {}


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


class OcModelError(RuntimeError):
    """Raised for upstream model-level failures (quota, auth, rate-limit).

    Check ``self.code`` for the HTTP status (0 if unknown).
    """
    def __init__(self, message: str, code: int = 0) -> None:
        self.code = code
        super().__init__(message)


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
        # Per-instance cache for check_model() results: model → OcModelError or None.
        # None means "last check passed"; an OcModelError means it failed.
        self._check_cache: dict[str, "OcModelError | None"] = {}

    def is_available(self) -> bool:
        try:
            result = self._api("GET", "/global/health")
            return bool(result.get("healthy"))
        except Exception:
            return False

    def check_model(self, model: str, timeout: int = 20) -> None:
        """Verify a model is usable by making a minimal one-token test call.

        Results are cached at module level for the lifetime of the Python
        process, so repeated calls (e.g. preflight + pipeline) cost only one
        round-trip per model.

        Raises:
            OcUnavailableError: server is not running.
            OcModelError: model has quota/auth/rate-limit issues.
            TimeoutError: model did not respond within *timeout* seconds.
        """
        if model in _model_check_cache:
            cached = _model_check_cache[model]
            if cached is not None:
                raise cached
            return

        try:
            self.call(".", model=model, timeout=timeout)
            _model_check_cache[model] = None
        except OcModelError as e:
            _model_check_cache[model] = e
            raise
        # OcUnavailableError / TimeoutError: don't cache — transient states

    def call(self, prompt: str, model: str = "glm-5.1", timeout: int = 300) -> str:
        """Create a session, send the prompt, return the text response."""
        if self.budget_usd > 0:
            current = _read_oc_daily_spend()
            if current >= self.budget_usd * 0.9:
                raise OcBudgetExceededError(
                    f"OpenCode daily budget nearly exhausted "
                    f"(${current:.2f} of ${self.budget_usd:.2f} today). "
                    f"Increase with `docent studio config-set oc_budget_usd <amount>` "
                    f"or set oc_budget_usd=0 to remove the limit."
                )

        session_id = self._api("POST", "/session", {})["id"]

        # Run the potentially long model call in a daemon thread so that
        # KeyboardInterrupt can be delivered in the main thread via the
        # 100ms polling loop below.  On Windows, a blocking socket recv()
        # inside urlopen() defers SIGINT until the C call returns, which
        # can be up to `timeout` seconds — unacceptable for interactive use.
        holder: list = [None, None]  # [response_dict, exception]
        done = threading.Event()

        def _model_call() -> None:
            try:
                holder[0] = self._api(
                    "POST",
                    f"/session/{session_id}/message",
                    {
                        "parts": [{"type": "text", "text": prompt}],
                        "role": "user",
                        "model": {"modelID": model, "providerID": self.provider},
                    },
                    timeout=timeout,
                )
            except BaseException as exc:  # noqa: BLE001
                holder[1] = exc
            finally:
                done.set()

        t = threading.Thread(target=_model_call, daemon=True)
        t.start()

        # Poll every 100ms — time.sleep(0.1) is interruptible on Windows,
        # so Ctrl+C is delivered within ~100ms regardless of socket state.
        _poll = 0.1
        _limit = float(timeout) + 5.0
        _waited = 0.0
        while not done.wait(timeout=_poll):
            _waited += _poll
            if _waited >= _limit:
                raise OcUnavailableError(
                    f"OpenCode model call timed out after {_limit:.0f}s "
                    f"at {self.base_url}."
                )

        if holder[1] is not None:
            raise holder[1]  # re-raise OcModelError / OcUnavailableError / etc.

        response = holder[0]

        # OpenCode may return HTTP 200 but with a model-level error embedded in the
        # response body (e.g. quota exhaustion, auth failure from the upstream provider).
        parts = response.get("parts") or []
        if not parts:
            err = response.get("error")
            if err:
                if isinstance(err, dict):
                    msg = err.get("message", str(err))
                    code = int(err.get("code") or 0)
                else:
                    msg = str(err)
                    code = 0
                msg_lower = msg.lower()
                if any(k in msg_lower for k in ("quota", "usage", "exhausted", "exceeded", "RESOURCE_EXHAUSTED")):
                    raise OcModelError(
                        f"Model quota/usage limit exceeded for {model!r}: {msg}\n"
                        "Add credits to your provider account, or switch models with:\n"
                        "  docent studio config-set --key oc_model_planner --value <model>",
                        code=code,
                    )
                if any(k in msg_lower for k in ("auth", "unauthorized", "forbidden", "invalid key")):
                    raise OcModelError(
                        f"Model authentication failed for {model!r}: {msg}\n"
                        "Run `feynman setup` or check your provider API keys.",
                        code=code,
                    )
                if "rate" in msg_lower or code == 429:
                    raise OcModelError(
                        f"Model rate-limited for {model!r}: {msg}\n"
                        "Wait a moment and retry, or switch models with:\n"
                        "  docent studio config-set --key oc_model_planner --value <model>",
                        code=code,
                    )
                raise OcModelError(f"Model error for {model!r} (code {code}): {msg}", code=code)

        try:
            cost = float((response.get("info") or {}).get("cost") or 0.0)
            if cost > 0:
                _write_oc_daily_spend(_read_oc_daily_spend() + cost)
        except Exception:
            pass

        return "\n".join(
            p["text"] for p in parts if p.get("type") == "text"
        )

    def _api(self, method: str, path: str, body: dict | None = None, timeout: int = 10) -> dict:
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": "application/json"} if data else {}
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            body_bytes = b""
            try:
                body_bytes = e.read()
            except Exception:
                pass
            body_str = body_bytes.decode("utf-8", errors="replace")
            if e.code == 429:
                raise OcModelError(
                    "Model rate-limited (HTTP 429). Wait a moment and retry, or "
                    "switch models with: docent studio config-set --key oc_model_planner --value <model>",
                    code=429,
                ) from e
            if e.code in (401, 403):
                raise OcModelError(
                    f"Model authentication failed (HTTP {e.code}). "
                    "Check your provider API keys or run `feynman setup`.",
                    code=e.code,
                ) from e
            raise OcUnavailableError(
                f"OpenCode server returned HTTP {e.code}: {body_str[:200]}"
            ) from e
        except urllib.error.URLError as e:
            raise OcUnavailableError(
                f"OpenCode server not reachable at {self.base_url}. "
                "Run: opencode serve --port 4096"
            ) from e