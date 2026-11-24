@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo === zhipu-tools-oss Windows 安装 ===

set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
  where python >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo 未找到 Python。请先装 Python 3.10+ 并勾选 Add to PATH。
  echo 下载：https://www.python.org/downloads/windows/
  pause
  exit /b 1
)
echo 使用：%PY%

set "VENV=%USERPROFILE%\.zhipu-tools\venv"
if not exist "%VENV%" (
  echo 创建虚拟环境 %VENV%
  %PY% -m venv "%VENV%"
)

set "WHEELS=%~dp0..\..\工具安装包\zhipu-tools-wheels-win"
if exist "%WHEELS%" (
  echo 离线安装（本地 wheel 目录）
  "%VENV%\Scripts\python.exe" -m pip install -q --no-index --find-links "%WHEELS%" -r requirements-win.txt
) else (
  echo 未找到本地 wheel 目录，改为联网安装
  "%VENV%\Scripts\python.exe" -m pip install -q -r requirements-win.txt
)

echo === 验证 ===
"%VENV%\Scripts\python.exe" -c "import fastapi,trafilatura,fitz,docx,bs4,rank_bm25;print('核心依赖 OK')"
if errorlevel 1 (
  echo 安装失败，请把上面的报错发出来。
  pause
  exit /b 1
)
echo.
echo 完成。运行 start-win.bat 启动服务。
pause