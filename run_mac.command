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

uv run run.py
