"""Validate user-facing sample scripts and their documentation references."""

from __future__ import annotations

import py_compile
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

USER_SAMPLES = [
    "samples/high_level_async.py",
    "samples/high_level_sync.py",
    "samples/basic_high_level_rw.py",
    "samples/named_snapshot.py",
    "samples/polling_monitor.py",
]

DOC_FILES = [
    "README.md",
    "samples/README.md",
    "docsrc/user/USER_GUIDE.md",
]


def main() -> int:
    errors: list[str] = []

    for relative_path in USER_SAMPLES:
        sample_path = ROOT / relative_path
        if not sample_path.exists():
            errors.append(f"Missing sample file: {relative_path}")
            continue

        try:
            py_compile.compile(str(sample_path), doraise=True)
        except py_compile.PyCompileError as exc:
            errors.append(f"py_compile failed for {relative_path}: {exc.msg}")

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

    for doc_relative_path in DOC_FILES:
        doc_text = (ROOT / doc_relative_path).read_text(encoding="utf-8")
        for sample_path in USER_SAMPLES:
            sample_name = Path(sample_path).name
            if sample_path not in doc_text and sample_name not in doc_text:
                errors.append(f"{doc_relative_path} does not reference {sample_path}.")

    if errors:
        print("[ERROR] User sample validation failed.", file=sys.stderr)
        for error in errors:
            print(f" - {error}", file=sys.stderr)
        return 1

    print("[OK] User sample validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
