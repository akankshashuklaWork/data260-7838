"""Reproduce the required /compact command evidence without changing final MEMORY.md."""

import tempfile
import time
from pathlib import Path

from .config import REPOSITORY_ROOT
from .file_memory import handle_memory_command


def main() -> None:
    original = REPOSITORY_ROOT / "memory" / "MEMORY.original.md"
    output_path = REPOSITORY_ROOT / "reports" / "hw06" / "raw" / "file_memory_command_demo.txt"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="hw6-compact-") as temporary_directory:
        memory_path = Path(temporary_directory) / "MEMORY.md"
        memory_path.write_text(original.read_text(encoding="utf-8"), encoding="utf-8")
        response = handle_memory_command("/compact", [], memory_path=memory_path)
    lines = ["Akanksha Shukla | HW6 file-memory command demo", "Command: /compact", f"Result: {response}"]
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with (REPOSITORY_ROOT / "reports" / "hw06" / "RUN_LOG.txt").open("a", encoding="utf-8") as run_log:
        run_log.write(f"[{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}] /compact evidence: {response}\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
