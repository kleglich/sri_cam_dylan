@echo off
echo Se borrara la base de PRUEBA y sus respaldos (carpetas prueba, drive_de_prueba y usb_de_prueba).
echo Los datos reales del SRI no se tocan. Cierre antes la ventana del SRI de prueba.
choice /M "Desea borrar la prueba"
if errorlevel 2 exit /b 0
for %%C in (prueba drive_de_prueba usb_de_prueba) do if exist "%~dp0%%C" rmdir /s /q "%~dp0%%C"
echo Listo. Abra de nuevo abrir_SRI_de_prueba.bat para empezar de cero.
pause
