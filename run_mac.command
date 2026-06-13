#!/bin/bash
cd "$(dirname "$0")"
echo "ORCAV を起動しています..."
uv run run.py
if [ $? -ne 0 ]; then
    echo ""
    echo "エラーが発生しました。エンターキーを押して終了してください。"
    read
fi
