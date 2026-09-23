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

**`PUBLICAR.bat` solo SUBE a GitHub — NO compila.** Lee `APP_VERSION`, sube código + `version.json` + `updates/latest.zip` + el EXE que ya esté en `updates\PINO_SYSTEM.exe`. Para generar el EXE aparte: `build_exe.bat` (o PyInstaller a mano) y copiar a `updates\` antes de PUBLICAR. No crear `PUBLICAR_26X.bat`.

**Si solo se sube `version.json` y NO el EXE nuevo**, el cliente “se actualiza” pero sigue corriendo el binario viejo y el aviso se repite para siempre. El EXE (compilado en Windows, no en el share de Parallels) debe estar en `updates\` y subirse en el mismo release.

Verificar despues del push:
https://raw.githubusercontent.com/deliveryControl24/maderera-CR/main/version.json

## Otros

- Fuente de verdad: `app.py` (despues de editar: `cp app.py main.py`)
- Compilar: `python3.11 -m py_compile app.py main.py modulos.py config_paths.py`
- No emojis en Tkinter (crash macOS)
- Push desde Mac falla 403 -> push desde Windows con PAT `deliveryControl24`
- Build EXE: solo en Windows local (`build_exe.bat`); PyInstaller no sirve en el share de Parallels ni en Mac
- `ACTUALIZADOR.exe` es para el **cliente** (baja updates). `PUBLICAR.bat` es para **publicar** en GitHub — sin publicar, el actualizador no tiene nada nuevo.
