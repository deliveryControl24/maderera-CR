# Reglas del proyecto - PINO SYSTEM

## REGLA: version.json SIEMPRE en cada actualizacion

Despues de **cada** actualizacion (bugfix, feature, EXE, zip), hay que:

1. Bump de `APP_VERSION` en `config_paths.py`
2. Regenerar y **subir `version.json`** (nunca omitirlo)
3. Subir el paquete de la actualizacion (`updates/latest.zip` y/o `updates/PINO_SYSTEM.exe`)
4. `git add` de esos archivos + commit + push

Sin `version.json` con version **mayor** en GitHub, el cliente **no ve** la actualizacion ni el changelog de bugs.

Comando rapido (genera zip + version.json alineados):

```bash
python3.11 empacotar_update.py <NUEVA_VERSION> "Lista de cambios / bugs corregidos"
git add config_paths.py app.py main.py modulos.py version.json updates/latest.zip
git commit -m "v<NUEVA_VERSION>: descripcion"
git push origin main
```

Si hay EXE Windows, ademas rebuild + subir `updates/PINO_SYSTEM.exe` (ej. `PUBLICAR_260.bat` o equivalente de la version actual).

Verificar despues del push:
https://raw.githubusercontent.com/deliveryControl24/maderera-CR/main/version.json

## Otros

- Fuente de verdad: `app.py` (despues de editar: `cp app.py main.py`)
- Compilar: `python3.11 -m py_compile app.py main.py modulos.py config_paths.py`
- No emojis en Tkinter (crash macOS)
- Push desde Mac falla 403 -> push desde Windows con PAT `deliveryControl24`
