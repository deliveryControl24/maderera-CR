@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo  SUBIR MEJORAS A GITHUB (deliveryControl24)
echo ============================================
echo.
git status --short
echo.
git add .gitignore version.json updates/PINO_SYSTEM.exe updates/latest.zip
git commit -m "v2.5.0: mejoras auto-update (exe + zip + version.json)" || echo (nada nuevo que commitear)
echo.
echo Push con la cuenta deliveryControl24 / PAT con repo...
git push origin main
echo.
if errorlevel 1 (
  echo.
  echo [ERROR] Push fallido. Opciones:
  echo   1. Usar PAT de deliveryControl24 con scope repo
  echo   2. O abrir GitHub Desktop con esa cuenta
  echo.
) else (
  echo OK - subido. Verifique:
  echo https://raw.githubusercontent.com/deliveryControl24/maderera-CR/main/version.json
)
echo.
pause
