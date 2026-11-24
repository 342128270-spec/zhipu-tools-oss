#!/usr/bin/env bash
# 离线安装：不联网，全部从本地 wheel 目录装
set -euo pipefail
cd "$(dirname "$0")"
PY="${ZT_PYTHON:-python3}"
VENV="${ZT_VENV:-$HOME/.zhipu-tools/venv}"

# wheel 目录：优先环境变量，其次同级 ../../工具安装包/zhipu-tools-wheels
WHEELS="${ZT_WHEELS:-}"
if [ -z "$WHEELS" ]; then
  for cand in \
    "$(cd .. && pwd)/../工具安装包/zhipu-tools-wheels" \
    "$(cd .. && pwd)/工具安装包/zhipu-tools-wheels" \
    "$HOME/.zhipu-tools/wheels"; do
    if [ -d "$cand" ]; then WHEELS="$cand"; break; fi
  done
fi
if [ -z "$WHEELS" ] || [ ! -d "$WHEELS" ]; then
  echo "找不到本地 wheel 目录。设 ZT_WHEELS 指向它，或改用 ./install.sh 联网安装。" >&2
  exit 1
fi

echo "wheel 目录: $WHEELS"
echo "==> 创建虚拟环境 $VENV"
"$PY" -m venv "$VENV"
# 引导包（pip/setuptools/wheel）有就装，没有就跳过，不影响主依赖
"$VENV/bin/python" -m pip install -q --upgrade pip setuptools wheel --no-index --find-links "$WHEELS" 2>/dev/null || true
echo "==> 离线安装依赖"
"$VENV/bin/pip" install -q --no-index --find-links "$WHEELS" -r requirements.txt
echo "==> 完成"
"$VENV/bin/python" -c "import fastapi, trafilatura, fitz, docx, bs4, rank_bm25; print('核心依赖 OK（离线）')"