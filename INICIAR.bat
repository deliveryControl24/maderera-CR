@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
rem Preferir el EXE de la raiz (se reemplaza al actualizar)
if exist "PINO_SYSTEM.exe" (
  start "" "%CD%\PINO_SYSTEM.exe"
  exit /b 0
)
set "VER="
if exist current.txt (
  set /p VER=<current.txt
)
if defined VER (
  if exist "versions\%VER%\PINO_SYSTEM.exe" (
    start "" "%CD%\versions\%VER%\PINO_SYSTEM.exe"
    exit /b 0
  )
  if exist "versions\%VER%\app.py" (
    where python >nul 2>nul
    if not errorlevel 1 (
      python "versions\%VER%\app.py"
      exit /b 0
    )
    where py >nul 2>nul
    if not errorlevel 1 (
      py -3 "versions\%VER%\app.py"
      exit /b 0
    )
  )
)
if exist "app.py" (
  python app.py
  exit /b 0
)
echo No se encontro PINO SYSTEM en esta carpeta.
pause
exit /b 1
