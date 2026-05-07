"""
Delegate an implementation brief to OpenCode (Go sub) via its REST API.

Usage:
    python scripts/oc_delegate.py brief.md
    python scripts/oc_delegate.py --task simple brief.md
    python scripts/oc_delegate.py --model deepseek-v4-pro brief.md
    cat brief.md | python scripts/oc_delegate.py -

Task types (auto-routed to model if --model not given):
    simple    → qwen3.5-plus   (rename, add field, one-file change)
    implement → kimi-k2.6      (default: multi-file, follow existing pattern)
    reason    → deepseek-v4-pro (design decisions, tradeoffs, debugging)
    long      → minimax-m2.7   (needs to read many/large files)

The OpenCode server must already be running:
    opencode serve --port 4096

Response text goes to stdout. Diff summary goes to stderr.
Brief is archived to memory/tasks/done/ after completion.
"""

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

BASE_URL = "http://127.0.0.1:4096"
DEFAULT_PROVIDER = "opencode-go"
TASKS_ARCHIVE = Path(__file__).parent.parent / "memory" / "tasks" / "done"

TASK_MODELS = {
    "simple": "qwen3.5-plus",
    "implement": "glm-5.1",       # preferred default for multi-file implementation
    "reason": "deepseek-v4-pro",
    "long": "minimax-m2.7",
}

_REASON_WORDS = {"reason", "design", "tradeoff", "architecture", "why", "debug", "diagnose", "decision"}
_SIMPLE_WORDS = {"rename", "add field", "one file", "single file", "wire up", "typo", "constant"}


def pick_model(task: str | None, brief: str) -> str:
    """Return model ID: explicit task wins, then heuristics, then default."""
    if task and task in TASK_MODELS:
        return TASK_MODELS[task]

    lower = brief.lower()
    word_count = len(lower.split())

    if word_count > 1500:
        return TASK_MODELS["long"]
    if any(w in lower for w in _REASON_WORDS):
        return TASK_MODELS["reason"]
    if any(w in lower for w in _SIMPLE_WORDS):
        return TASK_MODELS["simple"]
    return TASK_MODELS["implement"]


def api(method: str, path: str, body: dict | None = None, timeout: int = 10) -> dict:
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode()
        raise SystemExit(f"API error {e.code} {path}: {body_text}") from e
    except urllib.error.URLError as e:
        raise SystemExit(
            f"Cannot reach OpenCode server at {BASE_URL}.\n"
            f"Start it with: opencode serve --port 4096\n"
            f"Error: {e.reason}"
        ) from e


def health_check() -> None:
    try:
        result = api("GET", "/global/health")
        if not result.get("healthy"):
            raise SystemExit("OpenCode server reports unhealthy.")
    except SystemExit as e:
        if "Cannot reach" in str(e):
            raise
        raise SystemExit(
            f"OpenCode server at {BASE_URL} is not running.\n"
            "Start it with: opencode serve --port 4096"
        ) from e


def create_session() -> str:
    result = api("POST", "/session", {})
    return result["id"]


def send_brief(session_id: str, text: str, model: str, provider: str) -> dict:
    return api(
        "POST",
        f"/session/{session_id}/message",
        {
            "parts": [{"type": "text", "text": text}],
            "role": "user",
            "model": {"modelID": model, "providerID": provider},
        },
        timeout=600,  # model generation can take several minutes for complex briefs
    )


def extract_text(response: dict) -> str:
    return "\n".join(
        p["text"] for p in response.get("parts", []) if p.get("type") == "text"
    )


def get_diff(session_id: str) -> list[dict]:
    return api("GET", f"/session/{session_id}/diff")


def format_diff_summary(diff: list[dict]) -> str:
    if not diff:
        return "(no files changed)"
    lines = []
    for entry in diff:
        path = entry.get("file", entry.get("path", "?"))
        adds = entry.get("additions", 0)
        dels = entry.get("deletions", 0)
        lines.append(f"  {path}  +{adds}/-{dels}")
    return "\n".join(lines)


def slugify(text: str) -> str:
    words = re.sub(r"[^a-z0-9 ]", "", text.lower()).split()
    return "-".join(words[:6])


def archive_brief(brief_text: str, slug: str) -> Path:
    TASKS_ARCHIVE.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    dest = TASKS_ARCHIVE / f"{today}-{slug}.md"
    dest.write_text(brief_text, encoding="utf-8")
    return dest


def main() -> None:
    parser = argparse.ArgumentParser(description="Delegate a brief to OpenCode.")
    parser.add_argument(
        "brief",
        nargs="?",
        default="-",
        help="Path to brief markdown file, or '-' for stdin (default: stdin)",
    )
    parser.add_argument(
        "--task",
        choices=list(TASK_MODELS),
        help="Task type for model routing: simple|implement|reason|long",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override model ID directly (skips routing)",
    )
    parser.add_argument(
        "--provider",
        default=DEFAULT_PROVIDER,
        help=f"Provider ID (default: {DEFAULT_PROVIDER})",
    )
    args = parser.parse_args()

    if args.brief == "-":
        brief_text = sys.stdin.read()
    else:
        brief_text = Path(args.brief).read_text(encoding="utf-8")

    if not brief_text.strip():
        raise SystemExit("Brief is empty.")

    model = args.model or pick_model(args.task, brief_text)

    health_check()

    session_id = create_session()
    source = f"--task {args.task}" if args.task else ("--model" if args.model else "auto")
    print(f"[oc] session {session_id}  model {model}  ({source})", file=sys.stderr)

    response = send_brief(session_id, brief_text, model, args.provider)
    info = response.get("info", {})
    tokens = info.get("tokens", {})
    cost = info.get("cost", 0)
    model_used = info.get("modelID", args.model)

    text = extract_text(response)
    diff = get_diff(session_id)
    diff_summary = format_diff_summary(diff)

    # Archive brief
    first_line = brief_text.strip().splitlines()[0].lstrip("#").strip()
    slug = slugify(first_line) or "task"
    archive_path = archive_brief(brief_text, slug)

    # Output
    print(text)

    print(
        f"\n[oc] model={model_used}  tokens={tokens.get('total', '?')}  cost=${cost:.5f}",
        file=sys.stderr,
    )
    print(f"[oc] diff:\n{diff_summary}", file=sys.stderr)
    print(f"[oc] brief archived → {archive_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
