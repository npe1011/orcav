@echo off
cd /d "%~dp0"
echo ORCAV を起動しています...
uv run run.py
if %ERRORLEVEL% neq 0 (
    echo.
    echo エラーが発生しました。
    pause
)
