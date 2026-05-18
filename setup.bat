@echo off
REM ContextWeave Bootstrap Script for Windows

echo Initializing ContextWeave environment...

REM Check for uv
where uv >nul 2>nul
if %errorlevel% neq 0 (
    echo [!] uv is not installed. Installing via pip...
    pip install uv
)

REM Sync dependencies and install the package
echo [1/3] Syncing dependencies...
uv sync --quiet

REM Initialize configuration if it doesn't exist
if not exist "%USERPROFILE%\.contextweave\config.toml" (
    echo [2/3] First-time setup: Initializing configuration...
    uv run contextweave init contextweave
) else (
    echo [2/3] Configuration found. Skipping init.
)

echo [3/3] System Ready!
echo.
echo ============================================================
echo SETUP COMPLETE
echo ============================================================
echo You can now use the 'cw' command in this folder.
echo.
echo 1. Close this window.
echo 2. Open your terminal (PowerShell/CMD) in this folder.
echo 3. Type 'cw --help' to get started.
echo ============================================================
echo.
pause
