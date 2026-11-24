#!/usr/bin/env bash
# 启动服务（默认 127.0.0.1:8088）
set -euo pipefail
cd "$(dirname "$0")"
VENV="${ZT_VENV:-$HOME/.zhipu-tools/venv}"
if [ ! -x "$VENV/bin/python" ]; then
  echo "未安装依赖，先跑 ./install.sh" >&2
  exit 1
fi
export ZT_DATA="${ZT_DATA:-$HOME/.zhipu-tools}"
exec "$VENV/bin/python" serve.py --port "${ZT_PORT:-8088}" --host "${ZT_HOST:-127.0.0.1}"
