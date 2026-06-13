@echo off
cd /d "%~dp0"

where uv >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo Error: 'uv' is not installed or not found in PATH.
    echo Please install 'uv' first to run this application.
    echo Visit: https://docs.astral.sh/uv/
    echo.
    pause
    exit /b 1
)

:: GUIアプリとして非同期起動（pythonwを使用）し、このコマンドプロンプト画面は即座に閉じる
start "" uv run pythonw run.py
