@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo  PUBLICAR v2.5.1
echo ============================================
echo.
echo [1/3] Subir codigo + version.json + zip...
git add config_paths.py app.py main.py version.json updates/latest.zip
git commit -m "v2.5.1: publicar actualizacion"
git push origin main
if errorlevel 1 (
  echo.
  echo [ERROR] No se pudo push. Revise cuenta/PAT.
  pause
  exit /b 1
)
echo.
echo [2/3] Build EXE con 2.5.1 (PyInstaller)...
call build_exe.bat
echo.
echo [3/3] Copiar EXE a updates\...
if exist "dist\PINO_SYSTEM.exe" (
  copy /Y "dist\PINO_SYSTEM.exe" "updates\PINO_SYSTEM.exe"
  git add updates/PINO_SYSTEM.exe
  git commit -m "v2.5.1: EXE actualizado"
  git push origin main
  echo.
  echo LISTO - version.json y EXE 2.5.1 en GitHub
) else (
  echo [AVISO] No hay dist\PINO_SYSTEM.exe - suba el EXE despues
)
echo.
pause
