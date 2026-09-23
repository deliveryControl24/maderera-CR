import os
import sys
import json
import ctypes
import tempfile
import shutil

# Base app name
APP_NAME = "PinoSystem"
APP_VERSION = "2.4.0"

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
