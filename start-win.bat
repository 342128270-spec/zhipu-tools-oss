@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PY=%USERPROFILE%\.zhipu-tools\venv\Scripts\python.exe"
if not exist "%PY%" (
  echo 未安装，请先运行 install-win.bat
  pause
  exit /b 1
)
set "ZT_DATA=%USERPROFILE%\.zhipu-tools"
echo 工具仓 http://127.0.0.1:8088
"%PY%" serve.py --port 8088
pause