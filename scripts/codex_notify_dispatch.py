import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

JESKO = ROOT / ".venv" / "Scripts" / "jesko.exe"

LOG = Path(os.environ.get("TEMP", str(ROOT))) / "jesko-codex-dispatch.log"


def log(message):
    try:
        with LOG.open("a", encoding="utf-8") as f:
            f.write(
                f"{datetime.now().isoformat()} | {message}\n"
            )
    except OSError:
        pass


def main():
    log("Dispatcher invoked")

    if len(sys.argv) != 2:
        log("Invalid argument count")
        return 2

    try:
        event = json.loads(sys.argv[1])
    except json.JSONDecodeError:
        log("Invalid JSON payload")
        return 2

    if not isinstance(event, dict):
        log("Invalid event object")
        return 2

    if event.get("type") != "agent-turn-complete":
        log("Unsupported event type")
        return 0

    if not JESKO.is_file():
        log("JESKO executable not found")
        return 1

    try:
        result = subprocess.run(
            [str(JESKO), "codex-notify", sys.argv[1]],
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
            check=False,
            creationflags=getattr(
                subprocess, "CREATE_NO_WINDOW", 0
            ),
        )

        log(f"JESKO exit code: {result.returncode}")
        log(f"JESKO result: {result.stdout.strip()[:100]}")

        return result.returncode

    except Exception as exc:
        log(f"JESKO error: {type(exc).__name__}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())