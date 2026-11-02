@echo off
REM Scripts batch pour clipforge (Windows)

if "%1"=="install" (
    pip install -e .[dev]
) else if "%1"=="lint" (
    ruff check src/ tests/
) else if "%1"=="format" (
    ruff format src/ tests/
) else if "%1"=="test" (
    pytest
) else if "%1"=="test-cov" (
    pytest --cov=clipforge --cov-report=html
) else if "%1"=="clean" (
    if exist build rmdir /s /q build
    if exist dist rmdir /s /q dist
    for /d %%d in (*.egg-info) do rmdir /s /q "%%d"
    if exist .pytest_cache rmdir /s /q .pytest_cache
    if exist htmlcov rmdir /s /q htmlcov
    if exist .coverage del /q .coverage
    if exist .ruff_cache rmdir /s /q .ruff_cache
    for /d /r . %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d"
) else (
    echo Utilisation: scripts.bat [install^|lint^|format^|test^|test-cov^|clean]
)
