#!/usr/bin/env bash
# 一次性安装：建 venv、装依赖
set -euo pipefail
cd "$(dirname "$0")"
PY=${ZT_PYTHON:-python3}
VENV="${ZT_VENV:-$HOME/.zhipu-tools/venv}"
echo "==> 创建虚拟环境 $VENV"
"$PY" -m venv "$VENV"
"$VENV/bin/python" -m pip install -q --upgrade pip setuptools wheel
echo "==> 安装依赖"
"$VENV/bin/pip" install -q -r requirements.txt
echo "==> 完成"
"$VENV/bin/python" -c "import fastapi, trafilatura, fitz, docx, bs4, rank_bm25; print('核心依赖 OK')"
