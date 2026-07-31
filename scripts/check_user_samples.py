"""Validate user-facing sample scripts and their documentation references."""

from __future__ import annotations

import json
import py_compile
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

USER_SAMPLES = [
    "samples/basic_test.py",
    "samples/high_level_async.py",
    "samples/high_level_sync.py",
    "samples/basic_high_level_rw.py",
    "samples/config_polling.py",
    "samples/multi_plc_monitor.py",
    "samples/named_snapshot.py",
    "samples/polling_monitor.py",
    "samples/polling_reconnect.py",
]

DOC_FILES = [
    "README.md",
    "samples/README.md",
    "docsrc/user/USAGE_GUIDE.md",
]


def main() -> int:
    errors: list[str] = []

    for sample_path in sorted((ROOT / "samples").glob("*.py")):
        try:
            py_compile.compile(str(sample_path), doraise=True)
        except py_compile.PyCompileError as exc:
            errors.append(f"py_compile failed for {sample_path.relative_to(ROOT)}: {exc.msg}")

    for relative_path in USER_SAMPLES:
        sample_path = ROOT / relative_path
        if not sample_path.exists():
            errors.append(f"Missing sample file: {relative_path}")
            continue

        result = subprocess.run(
            [sys.executable, str(sample_path), "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip() or result.stdout.strip()
            errors.append(f"'--help' failed for {relative_path}: {stderr}")

    dry_run_commands = {
        "samples/config_polling.py": [
            "--config",
            "samples/config_polling.example.json",
            "--dry-run",
        ],
        "samples/multi_plc_monitor.py": [
            "--plc",
            "test=127.0.0.1,keyence:kv-8000,8501,tcp",
            "--tag",
            "value=DM100:U",
            "--dry-run",
        ],
    }
    for relative_path, arguments in dry_run_commands.items():
        result = subprocess.run(
            [sys.executable, str(ROOT / relative_path), *arguments],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip() or result.stdout.strip()
            errors.append(f"dry-run failed for {relative_path}: {stderr}")

    for json_path in sorted((ROOT / "samples").glob("*.json")):
        try:
            json.loads(json_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"JSON validation failed for {json_path.relative_to(ROOT)}: {exc}")

    combined_docs = "\n".join((ROOT / path).read_text(encoding="utf-8") for path in DOC_FILES)
    for sample_path in USER_SAMPLES:
        sample_name = Path(sample_path).name
        if sample_path not in combined_docs and sample_name not in combined_docs:
            errors.append(f"User documentation does not reference {sample_path}.")

    if errors:
        print("[ERROR] User sample validation failed.", file=sys.stderr)
        for error in errors:
            print(f" - {error}", file=sys.stderr)
        return 1

    print("[OK] User sample validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
