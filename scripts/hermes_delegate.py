"""
Delegate an implementation brief to Hermes Agent (WSL) in headless mode.

Usage:
    python scripts/hermes_delegate.py brief.md
    python scripts/hermes_delegate.py --task loop brief.md
    python scripts/hermes_delegate.py --model glm-5.1 brief.md
    cat brief.md | python scripts/hermes_delegate.py -

Task types (auto-routed to model if --model not given):
    simple    → qwen3.5-plus       (boilerplate, one-file changes)
    implement → glm-5.1            (default: multi-file implementation)
    loop      → glm-5.1            (test-fix loop — include "run pytest until green" in brief)
    reason    → deepseek-v4-pro    (design decisions, tradeoffs, debugging)
    long      → minimax-m2.7       (many/large files)

Hermes must be installed in WSL (~/.local/bin/hermes).
No server required — Hermes runs as a subprocess.

Response text → stdout. Diff summary + model info → stderr.
Brief is archived to memory/tasks/done/ with a hermes- prefix after completion.

Key advantage over oc_delegate.py: Hermes stays in a tool-calling loop (run tests,
fix failures, re-run) without Claude needing to intervene. Use --task loop for
any brief that ends with "run pytest until green."
"""

import argparse
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

HERMES_BIN = "~/.local/bin/hermes"
TEMP_BRIEF_WSL = "/tmp/docent_hermes_brief.md"
TASKS_ARCHIVE = Path(__file__).parent.parent / "memory" / "tasks" / "done"
PROJECT_ROOT = Path(__file__).parent.parent

TASK_MODELS: dict[str, str] = {
    "simple":    "qwen3.5-plus",
    "implement": "glm-5.1",
    "loop":      "deepseek-v4-pro",
    "reason":    "deepseek-v4-pro",
    "long":      "minimax-m2.7",
}

# Tasks that benefit from memory context; simple is excluded (fast, one-file).
_MEMORY_TASKS = {"implement", "loop", "reason", "long"}

# Instruction block prepended to briefs for memory-enabled tasks.
# Hermes reads the files via its own tool stack — we don't inline the content.
_MEMORY_PREAMBLE = """\
## Project context — read before starting
Use your file-reading tools to load these in order:
1. `memory/MEMORY.md` — project memory index (short; read it fully)
2. `memory/gotchas.md` — known landmines; check before writing anything similar

---

"""

_LOOP_WORDS    = {"pytest", "until green", "test-fix", "fix until", "run tests", "test loop"}
_REASON_WORDS  = {"reason", "design", "tradeoff", "architecture", "why", "debug", "diagnose", "decision"}
_SIMPLE_WORDS  = {"rename", "add field", "one file", "single file", "wire up", "typo", "constant"}


def pick_model(task: str | None, brief: str) -> str:
    if task and task in TASK_MODELS:
        return TASK_MODELS[task]
    lower = brief.lower()
    if len(lower.split()) > 1500:
        return TASK_MODELS["long"]
    if any(w in lower for w in _LOOP_WORDS):
        return TASK_MODELS["loop"]
    if any(w in lower for w in _REASON_WORDS):
        return TASK_MODELS["reason"]
    if any(w in lower for w in _SIMPLE_WORDS):
        return TASK_MODELS["simple"]
    return TASK_MODELS["implement"]


def windows_to_wsl_path(path: Path) -> str:
    """Convert an absolute Windows path to its /mnt/... WSL equivalent."""
    parts = path.resolve().parts
    drive = parts[0].rstrip(":\\").lower()        # "C:" -> "c"
    rest = "/".join(p.replace(" ", r"\ ") for p in parts[1:])
    return f"/mnt/{drive}/{rest}"


def check_hermes() -> None:
    result = subprocess.run(
        ["wsl", "bash", "-c", f"{HERMES_BIN} --version"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise SystemExit(
            f"Hermes not found at {HERMES_BIN} in WSL.\n"
            "Install it with: wsl bash -c 'curl -sSL https://hermes.ai/install | bash'"
        )


def write_brief_to_wsl(brief_text: str) -> None:
    """Write brief (with LF line endings) to the WSL temp path."""
    brief_lf = brief_text.replace("\r\n", "\n").replace("\r", "\n")
    result = subprocess.run(
        ["wsl", "bash", "-c", f"cat > {TEMP_BRIEF_WSL}"],
        input=brief_lf.encode("utf-8"),
        capture_output=True,
    )
    if result.returncode != 0:
        raise SystemExit(f"Failed to write brief to WSL: {result.stderr.decode()}")


def run_hermes(model: str, wsl_project_path: str, timeout: int) -> tuple[str, int]:
    """
    Invoke Hermes in headless mode from the project directory.

    Uses PROMPT=$(<file) to pass the brief safely — avoids shell expansion of
    special characters that would occur inside a double-quoted command substitution.
    Timeout env vars ensure long loop tasks don't stall.
    """
    env_prefix = (
        f"HERMES_API_TIMEOUT={timeout} "
        f"HERMES_STREAM_READ_TIMEOUT={timeout}"
    )
    run_cmd = (
        f"cd {wsl_project_path} && "
        f"PROMPT=$(<{TEMP_BRIEF_WSL}); "
        f"{env_prefix} {HERMES_BIN} -z \"$PROMPT\" --yolo -m {model}"
    )
    result = subprocess.run(
        ["wsl", "bash", "-c", run_cmd],
        capture_output=True,
        timeout=timeout + 30,   # outer Python timeout slightly larger than Hermes's own
    )
    output = result.stdout.decode("utf-8", errors="replace")
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace")
        # Surface stderr so the caller can diagnose failures
        sys.stderr.buffer.write(f"[hermes] stderr:\n{stderr}\n".encode())
    return output, result.returncode


def get_git_diff_summary() -> str:
    result = subprocess.run(
        ["git", "diff", "--stat", "HEAD"],
        capture_output=True, text=True,
        cwd=str(PROJECT_ROOT),
    )
    return result.stdout.strip() or "(no files changed)"


def slugify(text: str) -> str:
    words = re.sub(r"[^a-z0-9 ]", "", text.lower()).split()
    return "-".join(words[:6])


def archive_brief(brief_text: str, slug: str) -> Path:
    TASKS_ARCHIVE.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    dest = TASKS_ARCHIVE / f"{today}-hermes-{slug}.md"
    dest.write_text(brief_text, encoding="utf-8")
    return dest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Delegate a brief to Hermes Agent (WSL) in headless mode.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "brief",
        nargs="?",
        default="-",
        help="Path to brief markdown file, or '-' for stdin (default: stdin)",
    )
    parser.add_argument(
        "--task",
        choices=list(TASK_MODELS),
        help="Task type for model routing: simple|implement|loop|reason|long",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override model ID directly (e.g. deepseek-v4-pro); skips routing",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=900,
        help=(
            "Timeout in seconds (default: 900). "
            "Loop tasks may need 1800+ if the test suite is slow."
        ),
    )
    parser.add_argument(
        "--no-memory",
        action="store_true",
        help="Skip memory context injection (always skipped for --task simple).",
    )
    args = parser.parse_args()

    if args.brief == "-":
        brief_text = sys.stdin.read()
    else:
        brief_text = Path(args.brief).read_text(encoding="utf-8")

    if not brief_text.strip():
        raise SystemExit("Brief is empty.")

    model = args.model or pick_model(args.task, brief_text)
    source = f"--task {args.task}" if args.task else ("--model" if args.model else "auto")

    # Prepend memory preamble for non-simple tasks unless opted out.
    # Hermes reads the files via its tool stack — not inlined here.
    resolved_task = args.task or (
        "simple" if model == TASK_MODELS["simple"] else "other"
    )
    if not args.no_memory and resolved_task != "simple":
        brief_text = _MEMORY_PREAMBLE + brief_text

    check_hermes()
    write_brief_to_wsl(brief_text)

    wsl_project_path = windows_to_wsl_path(PROJECT_ROOT)
    memory_tag = "no-memory" if (args.no_memory or resolved_task == "simple") else "memory"
    print(
        f"[hermes] model={model}  ({source})  {memory_tag}  timeout={args.timeout}s  cwd={wsl_project_path}",
        file=sys.stderr,
    )

    try:
        output, returncode = run_hermes(model, wsl_project_path, args.timeout)
    except subprocess.TimeoutExpired:
        raise SystemExit(f"Hermes timed out after {args.timeout}s (outer guard).")

    diff_summary = get_git_diff_summary()

    first_line = brief_text.strip().splitlines()[0].lstrip("#").strip()
    slug = slugify(first_line) or "task"
    archive_path = archive_brief(brief_text, slug)

    sys.stdout.buffer.write((output + "\n").encode("utf-8", errors="replace"))
    sys.stderr.buffer.write(f"\n[hermes] exit={returncode}\n".encode())
    sys.stderr.buffer.write(f"[hermes] diff:\n{diff_summary}\n".encode())
    sys.stderr.buffer.write(f"[hermes] brief archived -> {archive_path}\n".encode())

    if returncode != 0:
        raise SystemExit(f"Hermes exited with code {returncode}.")


if __name__ == "__main__":
    main()
