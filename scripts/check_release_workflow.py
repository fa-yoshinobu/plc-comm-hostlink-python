"""Guard release workflow identity checks against accidental regression."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"


def main() -> int:
    text = WORKFLOW.read_text(encoding="utf-8")
    required = (
        "refs/tags/v{0}",
        "git describe --tags --exact-match HEAD",
        "pyproject.toml",
        "hostlink.__version__",
        "RELEASE_VERSION",
        "--verify-tag",
    )
    forbidden = ("v0.1.2", "--target main")
    missing = [token for token in required if token not in text]
    present = [token for token in forbidden if token in text]
    if missing or present:
        raise AssertionError(f"release workflow identity guard failed; missing={missing}, forbidden={present}")
    print("validated release workflow tag, source, runtime, and artifact identity guards")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
