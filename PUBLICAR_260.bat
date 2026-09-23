@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo  PUBLICAR v2.6.0
echo ============================================
echo.
echo [1/3] Subir codigo + version.json + zip...
git add config_paths.py app.py main.py modulos.py version.json updates/latest.zip PUBLICAR_251.bat
git commit -m "v2.6.0: version visible + modulos ocultables" || echo (ya estaba commiteado - seguimos)
git push origin main
if errorlevel 1 (
  echo.
  echo [ERROR] No se pudo push. Revise cuenta/PAT.
  pause
  exit /b 1
)
echo.
echo [2/3] Build EXE con 2.6.0 (PyInstaller)...
call build_exe.bat
if not exist "dist\PINO_SYSTEM.exe" (
  echo [ERROR] No se genero dist\PINO_SYSTEM.exe
  pause
  exit /b 1
)
echo.
echo [3/3] Copiar EXE a updates\ y subir...
copy /Y "dist\PINO_SYSTEM.exe" "updates\PINO_SYSTEM.exe"
git add updates/PINO_SYSTEM.exe
git commit -m "v2.6.0: EXE actualizado" || echo (EXE ya era igual)
git push origin main
if errorlevel 1 (
  echo [ERROR] Push del EXE fallido.
  pause
  exit /b 1
)
echo.
echo LISTO - version.json 2.6.0 y EXE 2.6.0 en GitHub
pause
