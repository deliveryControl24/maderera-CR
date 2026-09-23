@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

for /f "usebackq delims=" %%V in (`python -c "from config_paths import APP_VERSION; print(APP_VERSION)"`) do set "VER=%%V"
if "%VER%"=="" (
  echo [ERROR] No se pudo leer APP_VERSION
  pause
  exit /b 1
)

echo ============================================
echo  PUBLICAR PINO SYSTEM v%VER%
echo  Solo sube a GitHub - NO compila
echo ============================================
echo.

if not exist "updates\PINO_SYSTEM.exe" (
  echo [AVISO] No hay updates\PINO_SYSTEM.exe
  echo         Compile antes con build_exe.bat si hace falta
  echo         y copielo a updates\ antes de publicar.
  echo.
)

rem ---------- 1) Push codigo + version.json + zip ----------
echo [1/2] Subir codigo + version.json + zip...
rem NUNCA git add -A: PAT sin scope workflow (.github) y no subir .lnk
git reset HEAD -- .github 2>nul
git add config_paths.py app.py main.py modulos.py updater.py database.py excel_export.py themes.py utils.py cargar_datos_prueba.py actualizador.py version.json updates/latest.zip PUBLICAR.bat SUBIR.bat build_exe.bat empaquetar_dist.bat empacotar_update.py AGENTS.md COMANDOS_GITHUB.txt .gitignore
git commit -m "v%VER%: actualizacion" || echo (ya estaba commiteado)
git push origin main
if errorlevel 1 (
  echo.
  echo [ERROR] Push de codigo fallo. Revise PAT/cuenta.
  echo         No debe haber archivos .github en el commit.
  git status -sb
  pause
  exit /b 1
)

rem ---------- 2) Subir EXE ya compilados (sin PyInstaller) ----------
echo [2/2] Subir EXE existentes + version.json...
if exist "updates\PINO_SYSTEM.exe" (
  if not exist "paquete_pino\versions\%VER%" mkdir "paquete_pino\versions\%VER%"
  copy /Y "updates\PINO_SYSTEM.exe" "paquete_pino\versions\%VER%\PINO_SYSTEM.exe" >nul
  copy /Y "updates\PINO_SYSTEM.exe" "paquete_pino\PINO_SYSTEM.exe" >nul
)
> "paquete_pino\current.txt" echo %VER%
if exist "version.json" (
  if not exist "paquete_pino" mkdir "paquete_pino"
  copy /Y "version.json" "paquete_pino\version.json" >nul
  if not exist "paquete_pino\updates" mkdir "paquete_pino\updates"
  copy /Y "version.json" "paquete_pino\updates\version.json" >nul
)
if exist "updates\latest.zip" (
  if not exist "paquete_pino\updates" mkdir "paquete_pino\updates"
  copy /Y "updates\latest.zip" "paquete_pino\updates\latest.zip" >nul
)
if exist "updates\ACTUALIZADOR.exe" (
  copy /Y "updates\ACTUALIZADOR.exe" "paquete_pino\ACTUALIZADOR.exe" >nul
)

git add updates/PINO_SYSTEM.exe updates/ACTUALIZADOR.exe version.json updates/latest.zip actualizador.py 2>nul
git commit -m "v%VER%: EXE publicado" || echo (EXE ya era igual o no hay cambios)
git push origin main
if errorlevel 1 (
  echo [ERROR] Push del EXE fallo.
  pause
  exit /b 1
)

echo.
echo ============================================
echo  LISTO v%VER%
echo  - Subido a GitHub SIN compilar
echo  - paquete_pino\ actualizado
if not exist "updates\PINO_SYSTEM.exe" (
  echo  - AVISO: no había EXE en updates\
)
echo.
echo Verificar:
echo https://raw.githubusercontent.com/deliveryControl24/maderera-CR/main/version.json
echo ============================================
pause
endlocal
