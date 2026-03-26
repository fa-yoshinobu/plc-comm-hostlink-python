@echo off
setlocal
set PUBLISH_DIR=.\publish

echo ===================================================
echo [CI] Starting Python Quality Checks and CLI EXE Build...
echo ===================================================

set RUFF_TARGETS=src tests scripts samples

echo [1/6] Running Ruff (Linting)...
python -m ruff check %RUFF_TARGETS%
if %errorlevel% neq 0 (
    echo [ERROR] Ruff check failed.
    exit /b %errorlevel%
)

echo [2/6] Running Ruff (Formatting Check)...
python -m ruff format --check %RUFF_TARGETS%
if %errorlevel% neq 0 (
    echo [ERROR] Code is not formatted.
    exit /b %errorlevel%
)

echo [3/6] Running Mypy (Type Checking core library)...
python -m mypy src
if %errorlevel% neq 0 (
    echo [ERROR] Mypy type check failed.
    exit /b %errorlevel%
)

echo [4/6] Validating high-level docs coverage...
python scripts\check_high_level_docs.py
if %errorlevel% neq 0 (
    echo [ERROR] High-level docs coverage check failed.
    exit /b %errorlevel%
)

echo [5/6] Validating user-facing samples...
python scripts\check_user_samples.py
if %errorlevel% neq 0 (
    echo [ERROR] User-facing sample validation failed.
    exit /b %errorlevel%
)

echo [6/6] Running Tests...
set PYTHONPATH=src
python -m pytest tests
if %errorlevel% neq 0 (
    echo [ERROR] Tests failed.
    exit /b %errorlevel%
)

echo ===================================================
echo [SUCCESS] CI passed.
echo ===================================================
endlocal

