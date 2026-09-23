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
echo  (un solo bat - no hay PUBLICAR_26X.bat)
echo ============================================
echo.
echo IMPORTANTE: el build NO se hace en la carpeta
echo compartida (C:\Mac\Home). Se copia a local y
echo compila ahi para que el EXE salga bien.
echo.

rem ---------- 1) Push codigo + version.json + zip ----------
echo [1/4] Subir codigo + version.json + zip...
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

rem ---------- 2) Build FUERA del share ----------
set "BUILDROOT=%LOCALAPPDATA%\PinoBuild"
echo [2/4] Compilar PINO_SYSTEM.exe en %BUILDROOT% ...
if exist "%BUILDROOT%" rmdir /S /Q "%BUILDROOT%"
mkdir "%BUILDROOT%"

copy /Y "*.py" "%BUILDROOT%\" >nul
copy /Y "requirements-build.txt" "%BUILDROOT%\" >nul
if exist "pino.ico" copy /Y "pino.ico" "%BUILDROOT%\" >nul
if exist "pino_icon.png" copy /Y "pino_icon.png" "%BUILDROOT%\" >nul

pushd "%BUILDROOT%"
python -m pip install --upgrade pyinstaller pillow openpyxl --quiet
if errorlevel 1 (
  echo [ERROR] No se pudo instalar PyInstaller.
  popd
  pause
  exit /b 1
)

set "ICON_ARG=--icon=pino.ico"
if not exist "pino.ico" set "ICON_ARG="

python -m PyInstaller --noconfirm --onefile --windowed --name PINO_SYSTEM %ICON_ARG% --add-data "pino.ico;." --add-data "pino_icon.png;." --hidden-import openpyxl --hidden-import openpyxl.cell._writer --collect-all openpyxl app.py
if errorlevel 1 (
  echo [ERROR] PyInstaller fallo.
  popd
  pause
  exit /b 1
)
if not exist "dist\PINO_SYSTEM.exe" (
  echo [ERROR] No se genero dist\PINO_SYSTEM.exe
  popd
  pause
  exit /b 1
)
popd

rem ---------- 3) Copiar EXE al repo ----------
echo [3/4] Copiar EXE a updates\ ...
copy /Y "%BUILDROOT%\dist\PINO_SYSTEM.exe" "updates\PINO_SYSTEM.exe"
if not exist "updates\PINO_SYSTEM.exe" (
  echo [ERROR] No se copio el EXE
  pause
  exit /b 1
)

if not exist "paquete_pino\versions\%VER%" mkdir "paquete_pino\versions\%VER%"
copy /Y "updates\PINO_SYSTEM.exe" "paquete_pino\versions\%VER%\PINO_SYSTEM.exe" >nul
copy /Y "updates\PINO_SYSTEM.exe" "paquete_pino\PINO_SYSTEM.exe" >nul
> "paquete_pino\current.txt" echo %VER%
if exist "version.json" copy /Y "version.json" "paquete_pino\version.json" >nul
if exist "version.json" copy /Y "version.json" "paquete_pino\updates\version.json" >nul
if exist "updates\latest.zip" copy /Y "updates\latest.zip" "paquete_pino\updates\latest.zip" >nul

rem ---------- 3b) ACTUALIZADOR.exe (solo si cambio actualizador.py) ----------
echo [3b] ACTUALIZADOR.exe ...
pushd "%BUILDROOT%"
copy /Y "%~dp0actualizador.py" "actualizador.py" >nul 2>nul
python -m PyInstaller --noconfirm --onefile --windowed --name ACTUALIZADOR actualizador.py
if exist "dist\ACTUALIZADOR.exe" (
  copy /Y "dist\ACTUALIZADOR.exe" "%~dp0paquete_pino\ACTUALIZADOR.exe"
  if exist "%~dp0updates" copy /Y "dist\ACTUALIZADOR.exe" "%~dp0updates\ACTUALIZADOR.exe"
  echo   ACTUALIZADOR.exe listo
) else (
  echo   [AVISO] No se genero ACTUALIZADOR.exe
)
popd

rem ---------- 4) Push EXE ----------
echo [4/4] Subir EXE a GitHub...
git add updates/PINO_SYSTEM.exe updates/ACTUALIZADOR.exe version.json updates/latest.zip actualizador.py
git commit -m "v%VER%: EXE publicado" || echo (EXE ya era igual)
git push origin main
if errorlevel 1 (
  echo [ERROR] Push del EXE fallo.
  pause
  exit /b 1
)

echo.
echo ============================================
echo  LISTO v%VER%
echo  - version.json + EXE en GitHub
echo  - paquete_pino\ actualizado
echo.
echo Clientes: ACTUALIZADOR.exe o abrir el sistema
echo (dialogo SI, ACTUALIZAR).
echo ============================================
echo Verificar:
echo https://raw.githubusercontent.com/deliveryControl24/maderera-CR/main/version.json
pause
endlocal
