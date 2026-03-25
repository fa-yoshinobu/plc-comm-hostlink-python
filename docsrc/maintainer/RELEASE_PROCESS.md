# Release Guide

This is the minimum release checklist for this repository.

## 1. Update the Human-Facing Files

Check these before tagging:

- [User Guide](../user/USER_GUIDE.md)
- [CHANGELOG](../CHANGELOG.md)
- [Protocol Spec](PROTOCOL_SPEC.md)

## 2. Run Local Verification

Clean old packaging artifacts first:

```powershell
Remove-Item -Recurse -Force build, dist, *.egg-info
```

```powershell
python -m unittest discover -s tests -v
python -m ruff check .
python -m mypy src scripts
python -m build
```

Expected result:

- tests pass
- `ruff` passes
- `mypy` passes
- `dist/` contains a source distribution and wheel

## 3. Run the Minimum Live Check

If the release changes live behavior, run the focused script for that area.

Typical examples:

- `scripts/connection_check.py --host <host> --port <port>`

## 4. Artifact Policy

- do not commit build artifacts from `dist/`
- do not commit packet captures or raw communication logs

## 5. Tagging Flow

1. update `version` in `pyproject.toml`
2. update `CHANGELOG.md`
3. finish local and live verification
4. create a normal release commit
5. create the tag

## 6. Publish

If you are publishing artifacts:

```powershell
python -m twine check dist/*
```

Then:

- push the release commit and tag to the repository
- create the GitHub release entry
- upload `dist/` artifacts if distributing release packages outside the repository
