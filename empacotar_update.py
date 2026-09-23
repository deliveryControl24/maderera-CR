#!/usr/bin/env python3
"""
Crea una actualizacion LIVIANA (.zip con solo .py).
No compila nada: sirve para instalaciones fuente/portable
y para tener el zip en el repo sin rebuild de EXE.

Uso:
  python3.11 empacotar_update.py
  python3.11 empacotar_update.py 2.4.1 "Correccion X"
"""
import json
import os
import sys
import zipfile
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE, "updates")
ZIP_NAME = "latest.zip"
VERSION_FILE = os.path.join(BASE, "version.json")

SOURCE_FILES = [
    "app.py",
    "main.py",
    "modulos.py",
    "database.py",
    "updater.py",
    "excel_export.py",
    "themes.py",
    "utils.py",
    "config_paths.py",
    "cargar_datos_prueba.py",
]


def read_app_version():
    path = os.path.join(BASE, "config_paths.py")
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("APP_VERSION"):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return "0.0.0"


def build_zip():
    os.makedirs(OUT_DIR, exist_ok=True)
    zip_path = os.path.join(OUT_DIR, ZIP_NAME)
    added = []
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in SOURCE_FILES:
            src = os.path.join(BASE, name)
            if not os.path.exists(src):
                continue
            zf.write(src, name)
            added.append(name)
    size = os.path.getsize(zip_path)
    print(f"OK {zip_path} ({size} bytes)")
    print("archivos:", ", ".join(added))
    return zip_path, size


def update_version_json(version, changelog, kind="source"):
    data = {}
    if os.path.exists(VERSION_FILE):
        with open(VERSION_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

    data["version"] = version
    data["updated_at"] = datetime.now().strftime("%Y-%m-%d")
    data["changelog"] = changelog or data.get("changelog", "")
    data["min_size"] = 1000

    if kind == "source":
        # Portable / correr desde .py: baja zip liviano en mac/linux
        # Windows EXE sigue apuntando al binario (zip no reemplaza onefile)
        data["update_format"] = "exe"
        data["download_url"] = "updates/PINO_SYSTEM.exe"
        data["download_url_win"] = "updates/PINO_SYSTEM.exe"
        data["download_url_mac"] = f"updates/{ZIP_NAME}"
        data["download_url_linux"] = f"updates/{ZIP_NAME}"
        data["download_url_zip"] = f"updates/{ZIP_NAME}"
    else:
        data["update_format"] = "exe"
        data["download_url"] = "updates/PINO_SYSTEM.exe"
        data["download_url_win"] = "updates/PINO_SYSTEM.exe"
        data["download_url_mac"] = f"updates/{ZIP_NAME}"
        data["download_url_linux"] = f"updates/{ZIP_NAME}"

    with open(VERSION_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"OK {VERSION_FILE} -> {version} ({kind})")


def main():
    version = sys.argv[1] if len(sys.argv) > 1 else read_app_version()
    changelog = sys.argv[2] if len(sys.argv) > 2 else ""
    kind = sys.argv[3] if len(sys.argv) > 3 else "source"

    # Mantener APP_VERSION y version.json alineados
    cfg_path = os.path.join(BASE, "config_paths.py")
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = f.read()
    import re
    cfg_new = re.sub(
        r'APP_VERSION\s*=\s*["\'][^"\']+["\']',
        f'APP_VERSION = "{version}"',
        cfg,
        count=1,
    )
    if cfg_new != cfg:
        with open(cfg_path, "w", encoding="utf-8") as f:
            f.write(cfg_new)
        # sincronizar main.py si es copia de app.py
        app_path = os.path.join(BASE, "app.py")
        main_path = os.path.join(BASE, "main.py")
        if os.path.exists(app_path) and os.path.exists(main_path):
            import shutil
            shutil.copy2(app_path, main_path)
        print(f"OK APP_VERSION -> {version}")

    build_zip()
    update_version_json(version, changelog, kind)
    print("\nSiguiente: git add -A && git commit && git push")
    print("Zip: updates/latest.zip | manifest: version.json")


if __name__ == "__main__":
    main()
