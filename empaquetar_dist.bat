@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

for /f "usebackq delims=" %%V in (`python -c "from config_paths import APP_VERSION; print(APP_VERSION)"`) do set "VER=%%V"
if "%VER%"=="" set "VER=2.6.1"
echo ============================================
echo  PINO SYSTEM - Empaquetar dist\  v%VER%
echo ============================================.

if not exist "dist\PINO_SYSTEM.exe" (
  echo [ERROR] No existe dist\PINO_SYSTEM.exe
  echo         Ejecute primero build_exe.bat
  pause
  exit /b 1
)

if not exist "dist\versions\%VER%" mkdir "dist\versions\%VER%"
if not exist "dist\updates" mkdir "dist\updates"

copy /Y "dist\PINO_SYSTEM.exe" "dist\versions\%VER%\PINO_SYSTEM.exe" >nul
copy /Y "INICIAR.bat" "dist\INICIAR.bat" >nul
> "dist\current.txt" echo %VER%

copy /Y "version.json" "dist\version.json" >nul 2>nul
copy /Y "version.json" "dist\updates\version.json" >nul 2>nul
if exist "updates\latest.zip" copy /Y "updates\latest.zip" "dist\updates\latest.zip" >nul

if exist "pino.ico" copy /Y "pino.ico" "dist\pino.ico" >nul
if exist "pino_icon.png" copy /Y "pino_icon.png" "dist\pino_icon.png" >nul

echo.
echo Listo: %CD%\dist
echo   Abrir con: dist\INICIAR.bat
echo   Version:   %VER%
echo.
explorer dist
pause
endlocal
