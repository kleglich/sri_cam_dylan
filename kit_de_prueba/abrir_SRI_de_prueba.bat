@echo off
rem Abre el SRI con una base de PRUEBA, aparte de los datos reales.
set "KIT=%~dp0"
set "PROYECTO=%KIT%.."
if not exist "%PROYECTO%\run.bat" (
  echo La carpeta kit_de_prueba debe estar dentro de la carpeta del SRI, junto a run.bat.
  pause
  exit /b 1
)
set "SRI_DATA_DIR=%KIT%prueba\datos"
set "SRI_BACKUP_DIR=%KIT%prueba\respaldos"
set "SRI_EXPORT_DIR=%KIT%prueba\exportes"
set "SRI_CONFIG=%KIT%prueba\config.json"
if not exist "%KIT%prueba" mkdir "%KIT%prueba"
if not exist "%SRI_CONFIG%" copy "%PROYECTO%\config.json" "%SRI_CONFIG%" >nul
if not exist "%KIT%drive_de_prueba" mkdir "%KIT%drive_de_prueba"
if not exist "%KIT%usb_de_prueba" mkdir "%KIT%usb_de_prueba"
echo Modo PRUEBA: los datos se guardan en %KIT%prueba
call "%PROYECTO%\run.bat"
