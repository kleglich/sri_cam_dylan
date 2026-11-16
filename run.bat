@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  set "PYTHON=.venv\Scripts\python.exe"
) else (
  set "PYTHON=python"
)
echo Iniciando SRI - Distribuciones Cam Dylan S.A.S. ...
"%PYTHON%" main.py
if errorlevel 1 (
  echo.
  echo La aplicacion termino con errores. Revise el mensaje anterior.
  pause
)
