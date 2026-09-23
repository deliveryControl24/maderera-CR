@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo  SUBIR CAMBIOS - PINO SYSTEM
echo ============================================
echo.

git status -sb
echo.
set /p MSG=Mensaje del commit (Enter = "cambios locales"): 

if "%MSG%"=="" set MSG=cambios locales

git add -A
git commit -m "%MSG%"
if errorlevel 1 (
  echo.
  echo (nada para commitear o ya estaba todo guardado)
) else (
  echo.
  echo Commit listo.
)

echo.
echo Push a GitHub...
git push origin main
if errorlevel 1 (
  echo.
  echo [ERROR] Push fallido. Revise PAT / cuenta en Windows.
  pause
  exit /b 1
)

echo.
echo LISTO - subido a GitHub
git status -sb
pause
