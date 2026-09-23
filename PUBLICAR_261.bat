@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo  PUBLICAR v2.6.1 - actualizacion en 1 clic
echo ============================================
echo.
echo [1/3] Subir codigo + version.json + zip...
git add config_paths.py app.py main.py modulos.py updater.py version.json updates/latest.zip PUBLICAR_261.bat PUBLICAR_260.bat PUBLICAR_251.bat AGENTS.md COMANDOS_GITHUB.txt empacotar_update.py
git commit -m "v2.6.1: actualizacion en un clic para el usuario final" || echo (ya estaba commiteado - seguimos)
git push origin main
if errorlevel 1 (
  echo.
  echo [ERROR] No se pudo push. Revise cuenta/PAT.
  pause
  exit /b 1
)
echo.
echo [2/3] Build EXE con 2.6.1 (PyInstaller)...
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
git commit -m "v2.6.1: EXE actualizado" || echo (EXE ya era igual)
git push origin main
if errorlevel 1 (
  echo [ERROR] Push del EXE fallido.
  pause
  exit /b 1
)
echo.
echo LISTO - version.json 2.6.1 y EXE 2.6.1 en GitHub
echo Verificar:
echo https://raw.githubusercontent.com/deliveryControl24/maderera-CR/main/version.json
pause
