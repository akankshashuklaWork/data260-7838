"""Constrained file and shell tools for HW7 Part 6.

All paths must remain below an explicitly configured course sandbox.  The shell
gate reports an observable allow/block reason before any command is attempted.
"""

from __future__ import annotations

import difflib
import glob
import os
import re
import shlex
import subprocess
from pathlib import Path
from typing import Any

SAFE_PREFIXES: tuple[Path, ...] = ()
_DESTRUCTIVE_PATTERNS = (
    r"\brm\s+(?:-[A-Za-z]*r[A-Za-z]*|--recursive)\b",
    r"\b(sudo|doas|su)\b",
    r"\b(chmod|chown|chgrp)\b",
    r"\b(mkfs|dd|mkdir|mktemp|touch|truncate|fallocate|install)\b",
    r"/dev/(?:disk|sd|nvme|rdisk|zero|random)",
    r">>?(?:\s*)/(?:$|[^\s])",
)


def configure_safe_prefixes(prefixes: list[Path]) -> None:
    """Set the only filesystem roots accepted by the five file tools."""
    global SAFE_PREFIXES
    SAFE_PREFIXES = tuple(path.resolve() for path in prefixes)


def _safe_path(value: str | Path) -> Path:
    path = Path(value).resolve()
    if not SAFE_PREFIXES:
        raise PermissionError("No course sandbox has been configured.")
    if not any(path.is_relative_to(prefix) for prefix in SAFE_PREFIXES):
        raise PermissionError(f"Path outside SAFE_PREFIXES: {path}")
    return path


def is_destructive(command: str) -> bool:
    """Recognize commands that require confirmation even inside a safe prefix."""
    return any(re.search(pattern, command, re.IGNORECASE) for pattern in _DESTRUCTIVE_PATTERNS)


def confirm_bash(command: str, auto_approve: bool = False) -> dict[str, Any]:
    """Return an observable policy decision; do not silently infer consent."""
    if is_destructive(command):
        return {
            "allowed": bool(auto_approve),
            "reason": "destructive command requires explicit confirmation",
        }
    if not _command_stays_in_sandbox(command):
        return {
            "allowed": False,
            "reason": "command contains shell syntax or a path outside SAFE_PREFIXES",
        }
    return {"allowed": True, "reason": "non-destructive command"}


def _command_stays_in_sandbox(command: str) -> bool:
    """Reject shell escapes before a supposedly safe command is executed.

    ``cwd`` alone is not a boundary: ``cd ..`` and relative paths can still
    reach files outside the course sandbox.  The gate therefore permits only
    simple commands whose explicit path operands resolve below a configured
    prefix.  Destructive commands are handled separately by ``is_destructive``.
    """
    if not SAFE_PREFIXES or any(marker in command for marker in (";", "|", "&", "`", "$(", "<")):
        return False
    try:
        tokens = shlex.split(command)
    except ValueError:
        return False
    if not tokens or tokens[0] in {"cd", "source", "."}:
        return False
    root = SAFE_PREFIXES[0]
    for token in tokens:
        if token.startswith("-") or "/" not in token and not token.startswith("."):
            continue
        candidate = Path(token)
        resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
        if not any(resolved.is_relative_to(prefix) for prefix in SAFE_PREFIXES):
            return False
    return True


def read_file(path: str | Path, max_lines: int = 200) -> dict[str, Any]:
    target = _safe_path(path)
    if not isinstance(max_lines, int) or not 1 <= max_lines <= 2000:
        return {"ok": False, "error": "max_lines must be an integer from 1 through 2000"}
    try:
        lines = target.read_text(encoding="utf-8").splitlines()
        return {
            "ok": True,
            "path": str(target),
            "content": "\n".join(lines[:max_lines]),
            "truncated": len(lines) > max_lines,
        }
    except OSError as exc:
        return {"ok": False, "error": str(exc)}


def write_file(path: str | Path, content: str) -> dict[str, Any]:
    target = _safe_path(path)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return {"ok": True, "path": str(target), "bytes_written": len(content.encode("utf-8"))}
    except OSError as exc:
        return {"ok": False, "error": str(exc)}


def edit_file(path: str | Path, old: str, new: str) -> dict[str, Any]:
    target = _safe_path(path)
    try:
        original = target.read_text(encoding="utf-8")
        if old not in original:
            return {"ok": False, "error": "requested text was not found"}
        updated = original.replace(old, new, 1)
        target.write_text(updated, encoding="utf-8")
        diff = "\n".join(
            difflib.unified_diff(
                original.splitlines(),
                updated.splitlines(),
                fromfile=str(target),
                tofile=str(target),
                lineterm="",
            )
        )
        return {"ok": True, "path": str(target), "diff": diff[:1000]}
    except OSError as exc:
        return {"ok": False, "error": str(exc)}


def glob_files(pattern: str) -> dict[str, Any]:
    if os.path.isabs(pattern):
        return {"ok": False, "error": "file_pattern must be relative to SAFE_PREFIXES"}
    if not SAFE_PREFIXES:
        return {"ok": False, "error": "No course sandbox has been configured."}
    found = []
    for prefix in SAFE_PREFIXES:
        found.extend(
            str(Path(path).resolve()) for path in glob.glob(str(prefix / pattern), recursive=True)
        )
    return {"ok": True, "files": sorted(set(found))}


def search_in_files(query: str, file_pattern: str = "**/*") -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    files = glob_files(file_pattern)
    if not files.get("ok"):
        return files
    for raw_path in files["files"]:
        path = Path(raw_path)
        if not path.is_file():
            continue
        try:
            for line_number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                if query in line:
                    matches.append({"path": str(path), "line": line_number, "text": line})
        except UnicodeDecodeError:
            continue
    return {"ok": True, "matches": matches}


def bash(command: str, auto_approve: bool = False) -> dict[str, Any]:
    """Run a confirmed non-destructive command after reporting the policy decision."""
    decision = confirm_bash(command, auto_approve=auto_approve)
    if not decision["allowed"]:
        return {"ok": False, **decision}
    try:
        completed = subprocess.run(
            command,
            shell=True,
            text=True,
            capture_output=True,
            timeout=5,
            cwd=str(SAFE_PREFIXES[0]) if SAFE_PREFIXES else None,
            check=False,
        )
        return {
            "ok": completed.returncode == 0,
            **decision,
            "returncode": completed.returncode,
            "stdout": completed.stdout[-2000:],
            "stderr": completed.stderr[-2000:],
        }
    except (OSError, subprocess.SubprocessError) as exc:
        return {"ok": False, **decision, "error": str(exc)}


def run_safety_demo(sandbox: Path) -> dict[str, Any]:
    """Create three temporary Python files, run the integration task, and test 5/5 gates."""
    configure_safe_prefixes([sandbox])
    sandbox.mkdir(parents=True, exist_ok=True)
    write_file(sandbox / "app.py", "DEBUG = True\nprint('app')\n")
    write_file(sandbox / "config.py", "DEBUG = False\nMODE = 'test'\n")
    write_file(sandbox / "worker.py", "def run():\n    return 'DEBUG worker'\n")
    integration = {
        "glob": glob_files("*.py"),
        "search": search_in_files("DEBUG", "*.py"),
        "read": read_file(sandbox / "app.py", max_lines=5),
    }
    allowed = [
        ("safe_read", read_file(sandbox / "app.py").get("ok") is True),
        ("safe_write", write_file(sandbox / "notes.txt", "hello\n").get("ok") is True),
        ("safe_edit", edit_file(sandbox / "notes.txt", "hello", "updated").get("ok") is True),
        ("safe_glob", glob_files("*.py").get("ok") is True),
        ("safe_bash", bash("pwd").get("ok") is True),
    ]
    blocked_commands = [
        "rm -rf .",
        "sudo ls",
        "chmod 777 app.py",
        "dd if=/dev/zero of=/dev/disk9",
        "echo x > /dev/disk9",
    ]
    blocked = [(command, confirm_bash(command)["allowed"] is False) for command in blocked_commands]
    return {
        "integration": integration,
        "allowed_tests": [{"name": name, "passed": passed} for name, passed in allowed],
        "blocked_tests": [{"command": command, "passed": passed} for command, passed in blocked],
        "false_allow_fixed": "Raw-device redirection is explicitly matched and now requires confirmation.",
    }
