@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ============================================
echo   PINO SYSTEM - Generar EXE (Windows)
echo ============================================.

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] No se encontro Python. Instale Python 3.11+ desde python.org
  echo         y marque "Add python.exe to PATH".
  pause
  exit /b 1
)

python --version
echo Instalando PyInstaller...
python -m pip install --upgrade pyinstaller pillow --quiet

if not exist pino.ico (
  echo [AVISO] No existe pino.ico - se creara sin icono personalizado.
  set ICON_ARG=
) else (
  set ICON_ARG=--icon=pino.ico
)

echo Compiliendo EXE... esto puede tardar 1-3 minutos
python -m PyInstaller ^
  --noconfirm ^
  --onefile ^
  --windowed ^
  --name PINO_SYSTEM ^
  %ICON_ARG% ^
  --add-data "pino.ico;." ^
  --add-data "pino_icon.png;." ^
  app.py

if exist "dist\PINO_SYSTEM.exe" (
  echo.
  echo ============================================
  echo   EXE listo:
  echo   %CD%\dist\PINO_SYSTEM.exe
  echo ============================================
  explorer dist
) else (
  echo [ERROR] No se genero el EXE. Revise los mensajes de error.
)

pause
endlocal
