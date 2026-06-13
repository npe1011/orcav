# ORCAV (ORCA Output Viewer)

ORCAVは、量子化学計算プログラム [ORCA ver6](https://orcaforum.kofo.mpg.de/) の出力ファイル（`.out` ログファイル）を解析し、計算結果や分子構造、振動モード、最適化の履歴などを視覚的に確認するためのGUIアプリケーションです。
Python3系で作成しており、構造描画は3Dmol.jsを利用しています。

これはGoogle Antigravityを用いて作成しました。

## 解析できるログファイルの種類
構造最適化、スキャン、振動計算、IRC、NEBの結果を可視化します。IRCやNEBの可視化にはORCAがログとともに出力するxyzファイルが必要です。

## 使い方

Releaseから実行ファイルを配布しています。もしくは uv を用いて実行してください。
```bash
uv run orcav/app.py
```
ログファイルはドラッグドロップもしくはFileメニューから開いてください。

