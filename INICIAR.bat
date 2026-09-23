@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set "VER="
if exist current.txt (
  set /p VER=<current.txt
)
if not defined VER set "VER=__ROOT__"
set "EXE=versions\%VER%\PINO_SYSTEM.exe"
set "PY=versions\%VER%\app.py"
if exist "%EXE%" (
  start "" "%EXE%"
  exit /b 0
)
if exist "%PY%" (
  where python >nul 2>nul
  if errorlevel 1 (
    where py >nul 2>nul
    if errorlevel 1 (
      echo No se encontro Python para versions\%VER%
      pause
      exit /b 1
    )
    py -3 "%PY%"
    exit /b 0
  )
  python "%PY%"
  exit /b 0
)
if exist "PINO_SYSTEM.exe" (
  start "" "%CD%\PINO_SYSTEM.exe"
  exit /b 0
)
if exist "app.py" (
  python app.py
  exit /b 0
)
echo No se encontro PINO SYSTEM en esta carpeta.
pause
exit /b 1
