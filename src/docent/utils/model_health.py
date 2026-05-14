"""Health checks for AI model providers integrated into Docent.

Two levels of checking:

- **check_opencode_server()** — fast (no model call). Verifies the OpenCode
  server is running. Used by `docent doctor` where burning tokens is unacceptable.

- **verify_opencode_model()** — makes a minimal test call to verify a specific
  model has available credits and valid auth. Raises ``OcModelError`` on failure.
  Used by preflight hooks to gate tasks before they start.

When adding a new AI provider, add a matching ``check_<provider>()`` and/or
``verify_<provider>()`` pair here, then register the check in:
  - ``cli.py`` doctor_command  (for `docent doctor` diagnostics)
  - the relevant tool's ``_preflight_*`` function  (for per-task gating)
"""
from __future__ import annotations


# Type alias matching the doctor table row format
DoctorRow = tuple[str, str, str, str]  # (label, status, version, detail)


def check_opencode_server(
    provider: str = "opencode-go",
    base_url: str | None = None,
    model: str | None = None,
) -> DoctorRow:
    """Check OpenCode server connectivity without making a model call.

    Returns a ``(label, status, version, detail)`` tuple suitable for the
    ``docent doctor`` table.  Status is ``"OK"`` or ``"FAIL"``; never blocks.
    """
    from docent.bundled_plugins.studio.oc_client import OcClient

    oc = OcClient(base_url=base_url, provider=provider)
    try:
        available = oc.is_available()
    except Exception:
        available = False

    if not available:
        return (
            "OpenCode server",
            "FAIL",
            "-",
            (
                f"Not reachable at {oc.base_url}. "
                "Start with: opencode serve --port 4096"
            ),
        )

    detail = f"Running at {oc.base_url}"
    if model:
        detail += f" | configured model: {model}"
    return "OpenCode server", "OK", "-", detail


def verify_opencode_model(
    model: str,
    provider: str = "opencode-go",
    base_url: str | None = None,
) -> None:
    """Verify a model is usable before starting a task.

    Makes a minimal test call (one "." prompt).  Results are cached for the
    lifetime of the Python process so the check is free on repeated calls.

    Raises:
        OcUnavailableError: server is not running.
        OcModelError: model has quota/auth/rate-limit issues.
    """
    from docent.bundled_plugins.studio.oc_client import OcClient

    oc = OcClient(base_url=base_url, provider=provider)
    oc.check_model(model)
