#!/bin/bash
cd "$(dirname "$0")"

if ! command -v uv &> /dev/null; then
    echo "Error: 'uv' is not installed or not found in PATH."
    echo "Please install 'uv' first to run this application."
    echo "Visit: https://docs.astral.sh/uv/"
    echo ""
    echo "Press Enter to exit..."
    read
    exit 1
fi

echo "ORCAV を起動しています..."
uv run run.py
if [ $? -ne 0 ]; then
    echo ""
    echo "エラーが発生しました。エンターキーを押して終了してください。"
    read
fi
