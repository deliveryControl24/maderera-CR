import os
import sys
import json
import ctypes
import tempfile
import shutil

# Base app name
APP_NAME = "PinoSystem"
APP_VERSION = "2.5.0"

def get_app_data_dir():
    """Obtiene la carpeta de datos de la aplicación (AppData Local)"""
    if sys.platform == "win32":
        appdata = os.environ.get("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local"))
    elif sys.platform == "darwin":
        appdata = os.path.expanduser("~/Library/Application Support")
    else:
        appdata = os.path.expanduser("~/.local/share")
    
    data_dir = os.path.join(appdata, APP_NAME)
    os.makedirs(data_dir, exist_ok=True)
    return data_dir

def get_datos_dir():
    """Carpeta donde se guardan base de datos, configuración, reportes"""
    datos_dir = os.path.join(get_app_data_dir(), "datos")
    os.makedirs(datos_dir, exist_ok=True)
    # Crear subcarpetas
    os.makedirs(os.path.join(datos_dir, "reportes"), exist_ok=True)
    os.makedirs(os.path.join(datos_dir, "respaldos"), exist_ok=True)
    return datos_dir

def get_updates_dir():
    """Carpeta donde se descargan actualizaciones"""
    updates_dir = os.path.join(get_app_data_dir(), "updates")
    os.makedirs(updates_dir, exist_ok=True)
    return updates_dir

def get_db_path():
    """Ruta completa de la base de datos"""
    return os.path.join(get_datos_dir(), "pino_system.db")

def get_config_path():
    """Ruta del archivo de configuración"""
    return os.path.join(get_datos_dir(), "config.json")

def get_executable_dir():
    """Directorio donde está el ejecutable o script"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))


def get_install_root():
    """
    Raiz de instalacion (donde viven versions\\ y current.txt).
    Si el codigo/exe esta en versions\\X\\, la raiz es el padre de versions.
    """
    code_dir = get_executable_dir()
    parent = os.path.dirname(code_dir)
    if os.path.basename(parent).lower() == "versions":
        return os.path.dirname(parent)
    if os.path.basename(code_dir).lower() == "versions":
        return parent
    return code_dir


def get_versions_dir():
    path = os.path.join(get_install_root(), "versions")
    os.makedirs(path, exist_ok=True)
    return path


def get_current_pointer_path():
    return os.path.join(get_install_root(), "current.txt")


def read_current_version():
    path = get_current_pointer_path()
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip() or None
    except Exception:
        return None


def write_current_version(version):
    """Escribe el puntero de forma atomica (.tmp + replace)."""
    root = get_install_root()
    os.makedirs(root, exist_ok=True)
    path = os.path.join(root, "current.txt")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(str(version).strip() + "\n")
    os.replace(tmp, path)
    return path


def version_dir(version):
    return os.path.join(get_install_root(), "versions", str(version))


LAUNCHER_BAT = r'''@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set "VER="
if exist current.txt (
  set /p VER=<current.txt
)
if not defined VER set "VER=__ROOT__"
set "EXE=versions\%VER%\PINO_SYSTEM.exe"
set "PY=versions\%VER%\app.py"
if exist "%EXE%" (
  start "" "%EXE%"
  exit /b 0
)
if exist "%PY%" (
  where python >nul 2>nul
  if errorlevel 1 (
    where py >nul 2>nul
    if errorlevel 1 (
      echo No se encontro Python para versions\%VER%
      pause
      exit /b 1
    )
    py -3 "%PY%"
    exit /b 0
  )
  python "%PY%"
  exit /b 0
)
REM fallback: raiz tipica (primera instalacion)
if exist "PINO_SYSTEM.exe" (
  start "" "%CD%\PINO_SYSTEM.exe"
  exit /b 0
)
if exist "app.py" (
  python app.py
  exit /b 0
)
echo No se encontro PINO SYSTEM en esta carpeta.
pause
exit /b 1
'''


def ensure_launcher():
    """Crea INICIAR.bat en la raiz si no existe."""
    root = get_install_root()
    path = os.path.join(root, "INICIAR.bat")
    try:
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8", newline="\r\n") as f:
                f.write(LAUNCHER_BAT)
        return path
    except Exception:
        return None


def cleanup_old_versions(keep_previous=1, current=None):
    """
    Borra versiones viejas dejando la actual + keep_previous anteriores.
    Nunca borra la version que esta corriendo.
    """
    root = get_install_root()
    vdir = os.path.join(root, "versions")
    if not os.path.isdir(vdir):
        return []

    cur = current or read_current_version() or APP_VERSION
    running = None
    if getattr(sys, "frozen", False):
        # .../versions/X/PINO_SYSTEM.exe -> X
        running = os.path.basename(get_executable_dir())
    else:
        code = get_executable_dir()
        if os.path.basename(os.path.dirname(code)).lower() == "versions":
            running = os.path.basename(code)

    def vkey(name):
        parts = []
        for p in name.replace("-", ".").split("."):
            parts.append(int(p) if p.isdigit() else 0)
        return tuple(parts)

    entries = []
    for name in os.listdir(vdir):
        full = os.path.join(vdir, name)
        if os.path.isdir(full):
            entries.append(name)
    entries.sort(key=vkey)

    keep = set()
    keep.add(str(cur))
    if running:
        keep.add(str(running))
    # ultimas N versiones por orden
    for name in reversed(entries):
        if len(keep) >= keep_previous + 2:  # actual + running + extras
            break
        keep.add(name)

    removed = []
    for name in entries:
        if name in keep:
            continue
        full = os.path.join(vdir, name)
        try:
            shutil.rmtree(full, ignore_errors=True)
            removed.append(name)
        except Exception:
            pass
    return removed

def ensure_data_migration():
    """Migra datos si existe una instalación antigua (carpeta del exe)"""
    old_locations = [
        os.path.join(get_executable_dir(), "pino_system.db"),
        os.path.join(get_executable_dir(), "datos", "pino_system.db"),
    ]
    
    new_db = get_db_path()
    
    # Solo migrar si la DB nueva no existe pero la vieja sí
    if not os.path.exists(new_db):
        for old_path in old_locations:
            if os.path.exists(old_path):
                shutil.copy2(old_path, new_db)
                print(f"Migrado: {old_path} -> {new_db}")
                break
    
    return new_db

def load_config():
    """Carga configuración desde config.json"""
    config_path = get_config_path()
    defaults = {
        "version": "2.1.0",
        "exchange_rate": 520.0,
        "iva_percent": 12.0,
        "company_name": "PINO SYSTEM",
        "auto_update": True,
        "update_url": "https://github.com/deliveryControl24/maderera-CR",
        "update_type": "github",
        "google_drive_url": "",
        "last_update_check": "",
        "currency": "CRC",
        "theme": "claro"
    }
    
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                saved = json.load(f)
                defaults.update(saved)
        except:
            pass
    
    return defaults

def save_config(config):
    """Guarda configuración en config.json"""
    config_path = get_config_path()
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error guardando config: {e}")
        return False

def get_version():
    """Obtiene la versión actual de la app (version del codigo)."""
    return APP_VERSION
