# Release Guide

This is the minimum release checklist for this repository.

## 1. Update the Human-Facing Files

Check these before tagging:

- [Usage Guide](../../docsrc/user/USAGE_GUIDE.md)
- [CHANGELOG](../../CHANGELOG.md)

## 2. Run Local Verification

```powershell
call run_ci.bat
python -m build
python -m twine check dist/*
```

Expected result:

- all checks and the complete pytest suite in `run_ci.bat` pass
- `dist/` contains a source distribution and wheel
- `twine check` accepts both artifacts

## 3. Run the Minimum Live Check

If the release changes live behavior, perform the separately approved focused
check on a controlled test PLC. Record the exact profile, endpoint, device,
read/write intent, and test purpose before communication. Build or select a
focused probe for the behavior under test rather than assuming a generic live
check exists.

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

Then:

- push the release commit and tag to the repository
- let the tag workflow create the GitHub release entry, or manually dispatch it
  with the version of an existing `v*` tag
- upload `dist/` artifacts if distributing release packages outside the repository
