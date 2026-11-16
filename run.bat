@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  set "PYTHON=.venv\Scripts\python.exe"
) else (
  set "PYTHON=python"
)
rem En un equipo nuevo instala las dependencias la primera vez (requiere Internet).
"%PYTHON%" -c "import openpyxl, xlrd, cryptography" 2>nul
if errorlevel 1 (
  echo Instalando las dependencias del SRI por primera vez...
  "%PYTHON%" -m pip install -r requirements.txt
  if errorlevel 1 (
    echo.
    echo No se pudieron instalar las dependencias. Verifique la conexion a Internet
    echo y ejecute: "%PYTHON%" -m pip install -r requirements.txt
    pause
    exit /b 1
  )
)
if not exist "datos\sri_cam_dylan.db" (
  echo Base nueva. Para cargar la demostracion ejecute: "%PYTHON%" herramientas\preparar_demo.py
)
echo Iniciando SRI - Distribuciones Cam Dylan S.A.S. ...
"%PYTHON%" main.py
if errorlevel 1 (
  echo.
  echo La aplicacion termino con errores. Revise el mensaje anterior.
  pause
)
