import os
import sys
import json
import urllib.request
import urllib.error
import hashlib
import subprocess
import shutil
import threading
import zipfile
import tkinter as tk
from tkinter import messagebox, ttk
from datetime import datetime

from config_paths import (
    get_updates_dir, get_version, save_config,
    load_config, get_executable_dir, get_datos_dir, APP_NAME,
    get_install_root, get_versions_dir, version_dir,
    write_current_version, read_current_version, ensure_launcher,
    cleanup_old_versions, APP_VERSION
)

GITHUB_REPO_DEFAULT = "https://github.com/deliveryControl24/maderera-CR"


def format_changelog(texto):
    """Devuelve (titulo, lineas) legibles para el changelog."""
    raw = (texto or "").replace("\\n", "\n").strip()
    if not raw:
        return "Actualizacion del sistema", ["Correcciones de errores y mejoras"]
    lineas = [ln.strip() for ln in raw.split("\n") if ln.strip()]
    titulo = lineas[0] if lineas else "Novedades"
    resto = lineas[1:] if len(lineas) > 1 else lineas
    items = []
    for ln in resto:
        s = ln.lstrip("-*• ").strip()
        items.append(s if s else ln)
    if not items:
        items = ["Correcciones de errores y mejoras"]
    return titulo, items


class AutoUpdater:
    """Sistema de auto-actualizacion multi-servidor (GitHub, Dropbox, HTTP...)"""

    def __init__(self):
        self.config = load_config()
        self.current_version = get_version()
        self.updates_dir = get_updates_dir()
        self.update_url = self.config.get("update_url", "") or GITHUB_REPO_DEFAULT
        self.update_type = self.config.get("update_type", "github")

    def set_update_server(self, url, update_type="github"):
        """Configura el servidor de actualizaciones"""
        self.update_url = url
        self.update_type = update_type
        self.config["update_url"] = url
        self.config["update_type"] = update_type
        save_config(self.config)

    @staticmethod
    def parse_github_repo(url):
        """Devuelve (owner, repo, branch) o None si no es un repo GitHub."""
        if not url:
            return None
        s = url.strip().rstrip("/")
        s = s.split("?")[0]
        if s.endswith(".git"):
            s = s[:-4]
        for prefix in (
            "https://github.com/",
            "http://github.com/",
            "https://www.github.com/",
            "github.com/",
        ):
            if s.startswith(prefix):
                s = s[len(prefix):]
                break
        else:
            if "github.com/" not in url and "/" not in s:
                return None
            if not s.count("/") >= 1:
                return None

        parts = [p for p in s.split("/") if p]
        if len(parts) < 2:
            return None
        owner, repo = parts[0], parts[1]
        branch = "main"
        if len(parts) >= 4 and parts[2] in ("tree", "blob", "raw"):
            branch = parts[3]
        return owner, repo, branch

    def is_github(self, url=None):
        if url is None:
            url = self.update_url or ""
        if self.update_type == "github":
            return True
        return "github.com/" in (url or "")

    @staticmethod
    def github_raw(owner, repo, branch, path=""):
        base = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}"
        if path:
            base += "/" + path.lstrip("/")
        return base

    def _version_json_url(self):
        """URL absoluta del version.json segun el servidor configurado."""
        if not self.update_url:
            return None

        gh = self.parse_github_repo(self.update_url)
        if gh and self.is_github():
            return self.github_raw(*gh, "version.json")

        version_url = self.update_url.rstrip("/")
        if version_url.endswith("version.json"):
            return version_url
        if not version_url.endswith("/"):
            version_url += "/"
        return version_url + "version.json"

    def _resolve_download_url(self, download_url, remote_data=None):
        """Resuelve download_url (relativa o GitHub) a URL directa."""
        if not download_url:
            return ""

        data = remote_data or {}
        if sys.platform.startswith("win"):
            download_url = data.get("download_url_win") or download_url
        elif sys.platform == "darwin":
            download_url = data.get("download_url_mac") or download_url
        elif sys.platform.startswith("linux"):
            download_url = data.get("download_url_linux") or download_url

        download_url = download_url.strip()

        # Ruta relativa dentro del repo GitHub
        if self.is_github() and not download_url.startswith(("http://", "https://")):
            gh = self.parse_github_repo(self.update_url)
            if gh:
                return self.github_raw(*gh, download_url)
            return download_url

        # https://github.com/owner/repo/blob/main/archivo -> raw
        if "github.com/" in download_url and "/blob/" in download_url:
            gh = self.parse_github_repo(download_url)
            if gh:
                owner, repo, branch = gh
                rest = download_url.split("/blob/", 1)[1]
                # rest = branch/path/to/file
                path = "/".join(rest.split("/")[1:])
                return self.github_raw(owner, repo, branch, path)

        # https://github.com/owner/repo/raw/main/archivo -> raw
        if "github.com/" in download_url and "/raw/" in download_url:
            gh = self.parse_github_repo(download_url)
            if gh:
                owner, repo, branch = gh
                rest = download_url.split("/raw/", 1)[1]
                path = "/".join(rest.split("/")[1:])
                return self.github_raw(owner, repo, branch, path)

        return self._get_direct_download_url(download_url)

    def _get_direct_download_url(self, url):
        """Convierte URL a enlace de descarga directa segun tipo"""
        if not url:
            return None

        # Dropbox: convertir a enlace directo
        if "dropbox.com" in url:
            if "?dl=0" in url:
                return url.replace("?dl=0", "?dl=1")
            elif "?dl=" not in url:
                return url + "?dl=1"
            return url

        # Google Drive: convertir a enlace directo
        elif "drive.google.com" in url:
            if "/file/d/" in url:
                file_id = url.split("/file/d/")[1].split("/")[0]
                return f"https://drive.google.com/uc?export=download&id={file_id}"
            elif "id=" in url:
                file_id = url.split("id=")[1].split("&")[0]
                return f"https://drive.google.com/uc?export=download&id={file_id}"
            return url

        # Mega.nz: extraer enlace de descarga
        elif "mega.nz" in url:
            return url

        # URL directa (HTTP/HTTPS)
        elif url.startswith("http://") or url.startswith("https://"):
            return url

        # FTP
        elif url.startswith("ftp://"):
            return url

        return url
    
    def _download_file(self, url, dest_path, progress_callback=None):
        """Descarga un archivo con manejo de errores mejorado"""
        try:
            direct_url = self._get_direct_download_url(url)
            if not direct_url:
                raise Exception("URL de descarga no valida")

            if progress_callback:
                progress_callback("Conectando con servidor...")

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            # GitHub raw / API agradecen Accept
            if "raw.githubusercontent.com" in direct_url or "github.com" in direct_url:
                headers['Accept'] = '*/*'

            req = urllib.request.Request(direct_url, headers=headers)
            
            response = urllib.request.urlopen(req, timeout=30)
            
            # Obtener tamano total
            total_size = response.headers.get('content-length')
            total_size = int(total_size) if total_size else 0
            
            if progress_callback:
                if total_size > 0:
                    progress_callback(f"Descargando: 0/{total_size // 1024} KB")
                else:
                    progress_callback("Descargando archivo...")
            
            # Descargar
            downloaded = 0
            block_size = 8192
            
            with open(dest_path, 'wb') as f:
                while True:
                    chunk = response.read(block_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    if progress_callback and total_size > 0:
                        pct = (downloaded / total_size) * 100
                        progress_callback(f"Descargando: {downloaded // 1024}/{total_size // 1024} KB ({pct:.0f}%)")
            
            # Verificar que el archivo no este vacio
            if os.path.getsize(dest_path) == 0:
                raise Exception("Archivo descargado vacio")
            
            return True

        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise Exception(
                    "Archivo no encontrado en el servidor (404).\n"
                    "Verifique que updates/latest.zip o updates/PINO_SYSTEM.exe "
                    "este subido a GitHub (o el asset del Release)."
                )
            elif e.code == 403:
                raise Exception("Acceso denegado al archivo (403)")
            else:
                raise Exception(f"Error HTTP {e.code}: {str(e)}")
        except urllib.error.URLError as e:
            raise Exception(f"Error de conexion: {str(e)}")
        except Exception as e:
            raise Exception(f"Error descargando: {str(e)}")
    
    def check_for_updates(self, silent=True):
        """Verifica si hay actualizaciones disponibles"""
        version_url = self._version_json_url()
        if not version_url:
            if not silent:
                return {"update_available": False, "message": "No hay servidor configurado"}
            return None

        try:
            if not silent:
                print(f"Verificando en: {version_url}")

            req = urllib.request.Request(version_url, headers={
                'User-Agent': 'PinoSystem-Updater/2.1'
            })
            response = urllib.request.urlopen(req, timeout=8)
            data = json.loads(response.read().decode('utf-8'))

            remote_version = data.get("version", "0.0.0")
            download_url = self._resolve_download_url(
                data.get("download_url", ""), data)
            # Formato por URL resuelta (zip = .py liviano, resto = exe)
            url_path = (download_url or "").split("?")[0].lower()
            update_format = (data.get("update_format") or "").lower()
            if url_path.endswith(".zip"):
                update_format = "zip"
            elif url_path.endswith((".exe", ".bin", ".app")):
                update_format = "exe"
            elif not update_format:
                update_format = "zip" if url_path.endswith(".zip") else "exe"
            changelog = data.get("changelog", "Sin detalles")
            checksum = data.get("checksum", "")
            min_size = data.get("min_size", 0)

            if self._version_compare(remote_version, self.current_version) > 0:
                return {
                    "update_available": True,
                    "remote_version": remote_version,
                    "download_url": download_url,
                    "update_format": update_format,
                    "changelog": changelog,
                    "checksum": checksum,
                    "min_size": min_size
                }
            else:
                if not silent:
                    return {"update_available": False, "message": "Estas en la ultima version"}
                return None

        except urllib.error.HTTPError as e:
            if e.code == 404 and "version.json" in (version_url or "") and not silent:
                return {
                    "update_available": False,
                    "message": f"No se encontro version.json (404) en:\n{version_url}"
                }
            if e.code == 404 and not silent:
                return {
                    "update_available": False,
                    "message": (
                        "El archivo no existe en GitHub (404).\n"
                        "Verifique que updates/PINO_SYSTEM.exe este subido al repo."
                    )
                }
            if not silent:
                return {"update_available": False, "message": f"Error HTTP {e.code}"}
            return None
        except urllib.error.URLError as e:
            if not silent:
                return {"update_available": False, "message": f"Error de conexion: {str(e)}"}
            return None
        except Exception as e:
            if not silent:
                return {"update_available": False, "message": f"Error: {str(e)}"}
            return None
    
    def _version_compare(self, v1, v2):
        """Compara versiones: retorna 1 si v1>v2, -1 si v1<v2, 0 si iguales"""
        try:
            parts1 = [int(x) for x in v1.split(".")]
            parts2 = [int(x) for x in v2.split(".")]
            
            for i in range(max(len(parts1), len(parts2))):
                p1 = parts1[i] if i < len(parts1) else 0
                p2 = parts2[i] if i < len(parts2) else 0
                if p1 > p2:
                    return 1
                elif p1 < p2:
                    return -1
            return 0
        except:
            return 0
    
    def _verify_checksum(self, filepath, expected_checksum):
        """Verifica el checksum del archivo descargado"""
        if not expected_checksum:
            return True  # Si no hay checksum, asumir valido
        
        try:
            sha256_hash = hashlib.sha256()
            with open(filepath, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            
            file_checksum = sha256_hash.hexdigest()
            return file_checksum.lower() == expected_checksum.lower()
        except:
            return False
    
    def _create_backup(self):
        """Crea backup del ejecutable actual antes de actualizar"""
        current_exe = sys.executable if getattr(sys, 'frozen', False) else None
        
        if not current_exe or not os.path.exists(current_exe):
            return None
        
        backup_dir = os.path.join(get_datos_dir(), "backups")
        os.makedirs(backup_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{APP_NAME}_{timestamp}.exe"
        backup_path = os.path.join(backup_dir, backup_name)
        
        try:
            shutil.copy2(current_exe, backup_path)
            return backup_path
        except:
            return None
    
    def _restore_backup(self, backup_path):
        """Restaura desde backup"""
        current_exe = sys.executable if getattr(sys, 'frozen', False) else None
        
        if not current_exe or not os.path.exists(backup_path):
            return False
        
        try:
            shutil.copy2(backup_path, current_exe)
            return True
        except:
            return False
    
    def _app_code_dir(self):
        """Carpeta donde viven los .py de la aplicacion."""
        if getattr(sys, "frozen", False):
            return get_executable_dir()
        return os.path.dirname(os.path.abspath(__file__))

    def _extract_py_from_zip(self, zip_path, dest_dir):
        """Extrae solo .py seguros del zip a dest_dir."""
        if not zipfile.is_zipfile(zip_path):
            raise Exception("El archivo descargado no es un zip valido")

        extracted = []
        os.makedirs(dest_dir, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as zf:
            for info in zf.infolist():
                name = info.filename.replace("\\", "/")
                if not name.endswith(".py"):
                    continue
                if name.startswith("/") or ".." in name.split("/"):
                    continue
                if name.startswith("datos/"):
                    continue
                dest = os.path.join(dest_dir, *name.split("/"))
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with zf.open(info) as src, open(dest, "wb") as out:
                    shutil.copyfileobj(src, out)
                extracted.append(name)
        if not extracted:
            raise Exception("El zip no contiene archivos .py")
        pyc = os.path.join(dest_dir, "__pycache__")
        if os.path.isdir(pyc):
            shutil.rmtree(pyc, ignore_errors=True)
        return extracted

    def apply_zip_update(self, zip_path, new_version=None):
        """
        Actualizacion LIVIANA en carpeta NUEVA:
          versions/<nueva>/*.py  + current.txt  -> relanzar nuevo
        No pisa la version que esta corriendo.
        """
        if getattr(sys, "frozen", False):
            raise Exception(
                "Esta version esta empaquetada como EXE.\n"
                "Un zip de .py no puede reemplazar el binario.\n"
                "Use actualizacion .exe (GitHub Actions genera el EXE)."
            )

        root = get_install_root()
        ver = str(new_version or "").strip() or f"src_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        dest = version_dir(ver)
        # Si la version destino es la que corre, usar sufijo
        running = os.path.basename(get_executable_dir())
        if os.path.basename(os.path.dirname(get_executable_dir())).lower() == "versions":
            if ver == running:
                ver = f"{running}_new"

        dest = version_dir(ver)
        extracted = self._extract_py_from_zip(zip_path, dest)

        # Copiar assets no-.py utiles si existen en la raiz y faltan en dest
        root_src = get_executable_dir()
        for asset in ("pino.ico", "pino_icon.png"):
            src = os.path.join(root_src, asset)
            dst = os.path.join(dest, asset)
            if os.path.exists(src) and not os.path.exists(dst):
                try:
                    shutil.copy2(src, dst)
                except Exception:
                    pass

        write_current_version(ver)
        ensure_launcher()

        # Lanzar la NUEVA version (proceso nuevo); este se cierra despues
        app_path = os.path.join(dest, "app.py")
        if not os.path.exists(app_path):
            raise Exception(f"No se genero {app_path}")

        python = sys.executable or "python3"
        popen_kwargs = {"cwd": dest}
        if not sys.platform.startswith("win"):
            popen_kwargs["start_new_session"] = True
        subprocess.Popen([python, app_path], **popen_kwargs)

        # Limpieza diferida de versiones viejas (no la que corre)
        try:
            cleanup_old_versions(keep_previous=1, current=ver)
        except Exception:
            pass

        return {"version": ver, "target": dest, "extracted": extracted}

    def apply_exe_side_by_side(self, new_exe_path, new_version):
        """
        Copia el EXE nuevo a versions/<nueva>/ SIN tocar el que corre,
        escribe current.txt y lanza el nuevo.
        """
        if not os.path.isfile(new_exe_path):
            raise Exception("No se encontro el binario descargado")

        root = get_install_root()
        ver = str(new_version or "").strip()
        if not ver:
            raise Exception("Falta la version destino")

        dest_dir = version_dir(ver)
        # Si destino es el mismo exe que corre, usar sufijo temporal
        current_exe = os.path.abspath(sys.executable) if getattr(sys, "frozen", False) else ""
        dest_exe = os.path.join(dest_dir, "PINO_SYSTEM.exe")
        if current_exe and os.path.abspath(dest_exe) == current_exe:
            dest_dir = version_dir(f"{ver}_new")
            dest_exe = os.path.join(dest_dir, "PINO_SYSTEM.exe")

        os.makedirs(dest_dir, exist_ok=True)

        src = os.path.abspath(new_exe_path)
        dst = os.path.abspath(dest_exe)
        if src != dst:
            # copia atomica: tmp -> rename
            tmp = dst + ".tmp"
            shutil.copy2(src, tmp)
            os.replace(tmp, dst)
        if not os.path.isfile(dst) or os.path.getsize(dst) < 1024:
            raise Exception("El binario copiado esta vacio o corrupto")

        if sys.platform != "win32":
            try:
                os.chmod(dst, 0o755)
            except Exception:
                pass

        write_current_version(os.path.basename(dest_dir))
        ensure_launcher()

        popen_kwargs = {"cwd": dest_dir}
        if not sys.platform.startswith("win"):
            popen_kwargs["start_new_session"] = True
        subprocess.Popen([dst], **popen_kwargs)

        try:
            cleanup_old_versions(keep_previous=1, current=os.path.basename(dest_dir))
        except Exception:
            pass

        return {"version": ver, "target": dest_exe}

    def apply_zip_update_inplace(self, zip_path):
        """
        (Legacy/fallback) extrae .py encima de la carpeta actual.
        Solo si side-by-side falla.
        """
        target = self._app_code_dir()
        backup_root = os.path.join(get_datos_dir(), "backups")
        os.makedirs(backup_root, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = os.path.join(backup_root, f"src_{stamp}")
        os.makedirs(backup_dir, exist_ok=True)

        if not zipfile.is_zipfile(zip_path):
            raise Exception("El archivo descargado no es un zip valido")

        extracted = []
        with zipfile.ZipFile(zip_path, "r") as zf:
            for info in zf.infolist():
                name = info.filename.replace("\\", "/")
                if not name.endswith(".py"):
                    continue
                if name.startswith("/") or ".." in name.split("/"):
                    continue
                if name.startswith("datos/"):
                    continue
                dest = os.path.join(target, *name.split("/"))
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                if os.path.exists(dest):
                    bak = os.path.join(backup_dir, *name.split("/"))
                    os.makedirs(os.path.dirname(bak), exist_ok=True)
                    shutil.copy2(dest, bak)
                with zf.open(info) as src, open(dest, "wb") as out:
                    shutil.copyfileobj(src, out)
                extracted.append(name)

        if not extracted:
            raise Exception("El zip no contiene archivos .py")

        pyc = os.path.join(target, "__pycache__")
        if os.path.isdir(pyc):
            shutil.rmtree(pyc, ignore_errors=True)
        return {"extracted": extracted, "backup_dir": backup_dir, "target": target}

    def apply_update(self, update_exe_path, update_format="exe", new_version=None):
        """
        Aplica actualizacion:
          - zip: extrae a versions/<nueva>/ y relanza (fuente)
          - exe: copia a versions/<nueva>/ y relanza (side-by-side)
        Nunca pisa el binario en uso. Retorna info del swap.
        """
        if update_format == "zip":
            try:
                return self.apply_zip_update(update_exe_path, new_version)
            except Exception:
                # fallback inplace + reinicio del mismo proceso
                self.apply_zip_update_inplace(update_exe_path)
                python = sys.executable or "python3"
                subprocess.Popen(
                    [python] + sys.argv,
                    cwd=os.path.dirname(os.path.abspath(sys.argv[0] or ".")),
                    start_new_session=not sys.platform.startswith("win"),
                )
                return {"mode": "inplace"}

        if getattr(sys, "frozen", False):
            # Preferir side-by-side (carpeta nueva)
            try:
                return self.apply_exe_side_by_side(update_exe_path, new_version)
            except Exception as e_side:
                # Fallback legado: copia via script (puede fallar si EXE en uso)
                current_exe = sys.executable
                if not current_exe or not os.path.exists(current_exe):
                    raise e_side

                if sys.platform.startswith("win"):
                    bat_content = f'''@echo off
timeout /t 2 /nobreak >nul
copy /Y "{update_exe_path}" "{current_exe}"
echo Actualizacion completada
start "" "{current_exe}"
del "%~f0"
'''
                    bat_path = os.path.join(self.updates_dir, "update.bat")
                    with open(bat_path, "w") as f:
                        f.write(bat_content)
                    subprocess.Popen([bat_path], shell=True)
                    return {"mode": "legacy_copy", "error_side_by_side": str(e_side)}

                sh_content = f'''#!/bin/sh
sleep 2
cp -f "{update_exe_path}" "{current_exe}" || exit 1
chmod +x "{current_exe}"
nohup "{current_exe}" >/dev/null 2>&1 &
'''
                sh_path = os.path.join(self.updates_dir, "update.sh")
                with open(sh_path, "w") as f:
                    f.write(sh_content)
                os.chmod(sh_path, 0o755)
                subprocess.Popen(["/bin/sh", sh_path], start_new_session=True)
                return {"mode": "legacy_copy", "error_side_by_side": str(e_side)}

        # modo desarrollo con formato exe: no hay binario
        raise Exception("Ejecutable no encontrado (modo desarrollo)")
    
    def create_version_file(self, version, download_url, changelog="", checksum=""):
        """Crea archivo version.json para subir al servidor"""
        data = {
            "version": version,
            "download_url": download_url,
            "changelog": changelog,
            "checksum": checksum,
            "updated_at": datetime.now().isoformat(),
            "min_size": 1024 * 1024  # 1MB minimo
        }
        
        filepath = os.path.join(self.updates_dir, "version.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return filepath


class UpdateDialog:
    """Dialogos de actualizacion claros y agradables para el usuario."""

    BG = "#F7F9FC"
    HEADER = "#1565C0"
    OK = "#2E7D32"
    CARD = "#FFFFFF"
    MUTED = "#546E7A"
    TEXT = "#263238"

    def __init__(self, parent, updater):
        self.parent = parent
        self.updater = updater
        self.dialog = None

    def _center(self, win, w, h):
        win.update_idletasks()
        x = (win.winfo_screenwidth() // 2) - (w // 2)
        y = (win.winfo_screenheight() // 2) - (h // 2)
        win.geometry(f"{w}x{h}+{x}+{y}")

    def _mk_btn(self, parent, text, color, command, width=16):
        cont = tk.Frame(parent, bg=color, padx=2, pady=2)
        cont.pack(side=tk.LEFT, padx=6)
        b = tk.Button(cont, text=text, bg="#F0F0F0", fg="#212121",
                      font=("Helvetica", 10, "bold"), width=width,
                      command=command, relief=tk.FLAT, cursor="hand2")
        b.pack()
        return b

    def show_checking(self):
        """Dialogo limpio mientras verifica."""
        if self.dialog:
            try:
                self.dialog.destroy()
            except tk.TclError:
                pass
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Buscando actualizaciones")
        self.dialog.configure(bg=self.BG)
        self.dialog.resizable(False, False)
        self.dialog.transient(self.parent)
        self.dialog.grab_set()
        self._center(self.dialog, 380, 150)

        header = tk.Frame(self.dialog, bg=self.HEADER)
        header.pack(fill=tk.X)
        tk.Label(header, text="BUSCANDO ACTUALIZACIONES",
                 bg=self.HEADER, fg="white",
                 font=("Helvetica", 11, "bold")).pack(pady=10)

        tk.Label(self.dialog, text="Un momento, por favor...",
                 bg=self.BG, fg=self.TEXT,
                 font=("Helvetica", 12)).pack(pady=(18, 6))
        self.status_label = tk.Label(
            self.dialog, text="Conectando con el servidor...",
            bg=self.BG, fg=self.MUTED, font=("Helvetica", 10))
        self.status_label.pack()
        bar = ttk.Progressbar(self.dialog, length=280, mode="indeterminate")
        bar.pack(pady=14)
        try:
            bar.start(12)
        except Exception:
            pass
        self.dialog.update()
        return self.dialog

    def show_update_available(self, info):
        """Dialogo agradable cuando hay una version nueva."""
        if self.dialog:
            try:
                self.dialog.destroy()
            except tk.TclError:
                pass

        dialog = tk.Toplevel(self.parent)
        dialog.title("Nueva version disponible")
        dialog.configure(bg=self.BG)
        dialog.resizable(False, False)
        dialog.transient(self.parent)
        dialog.grab_set()
        self._center(dialog, 480, 420)
        self.dialog = dialog

        header = tk.Frame(dialog, bg=self.HEADER)
        header.pack(fill=tk.X)
        tk.Label(header, text="HAY UNA ACTUALIZACION DISPONIBLE",
                 bg=self.HEADER, fg="white",
                 font=("Helvetica", 13, "bold")).pack(pady=(12, 4))
        tk.Label(header, text="Un clic y listo. No hace falta saber de computacion.",
                 bg=self.HEADER, fg="#BBDEFB",
                 font=("Helvetica", 9)).pack(pady=(0, 10))

        body = tk.Frame(dialog, bg=self.BG)
        body.pack(fill=tk.BOTH, expand=True, padx=16, pady=12)

        # Chips de version
        chips = tk.Frame(body, bg=self.BG)
        chips.pack(fill=tk.X, pady=(0, 10))
        for label, valor, bg, fg in (
            ("Tienes", str(self.updater.current_version), "#ECEFF1", self.TEXT),
            ("Nueva", str(info.get("remote_version", "?")), self.OK, "white"),
        ):
            card = tk.Frame(chips, bg=bg, padx=12, pady=6)
            card.pack(side=tk.LEFT, padx=(0, 10))
            tk.Label(card, text=label, bg=bg, fg=fg,
                     font=("Helvetica", 8)).pack()
            tk.Label(card, text=valor, bg=bg, fg=fg,
                     font=("Helvetica", 14, "bold")).pack()

        # Card changelog
        card = tk.Frame(body, bg=self.CARD, highlightthickness=1,
                        highlightbackground="#CFD8DC")
        card.pack(fill=tk.BOTH, expand=True)
        titulo, items = format_changelog(info.get("changelog", ""))
        tk.Label(card, text=titulo, bg=self.CARD, fg=self.HEADER,
                 font=("Helvetica", 11, "bold"), anchor="w",
                 padx=12, pady=(10, 4)).pack(fill=tk.X)

        txt = tk.Text(card, height=8, width=52, font=("Helvetica", 10),
                      bg=self.CARD, fg=self.TEXT, relief=tk.FLAT,
                      padx=8, pady=4, wrap=tk.WORD)
        txt.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        txt.tag_configure("item", lmargin1=8, lmargin2=22, spacing3=4)
        for it in items:
            txt.insert(tk.END, f"  {it}\n", "item")
        txt.config(state="disabled")

        btns = tk.Frame(body, bg=self.BG)
        btns.pack(fill=tk.X, pady=(12, 0))

        def on_update():
            dialog.destroy()
            self._start_update(
                info["download_url"],
                info.get("checksum", ""),
                info.get("update_format", "exe"),
                info.get("remote_version"),
            )

        def on_cancel():
            dialog.destroy()

        self._mk_btn(btns, "SI, ACTUALIZAR", self.OK, on_update, width=18)
        self._mk_btn(btns, "AHORA NO", "#78909C", on_cancel, width=12)

    def show_no_updates(self):
        """Confirmacion amable de que esta al dia."""
        if self.dialog:
            try:
                self.dialog.destroy()
            except tk.TclError:
                pass
        dialog = tk.Toplevel(self.parent)
        dialog.title("Version al dia")
        dialog.configure(bg=self.BG)
        dialog.resizable(False, False)
        dialog.transient(self.parent)
        dialog.grab_set()
        self._center(dialog, 400, 200)
        self.dialog = dialog

        header = tk.Frame(dialog, bg=self.OK)
        header.pack(fill=tk.X)
        tk.Label(header, text="TODO ESTA ACTUALIZADO",
                 bg=self.OK, fg="white",
                 font=("Helvetica", 12, "bold")).pack(pady=12)

        tk.Label(dialog, text=f"Version actual: {self.updater.current_version}",
                 bg=self.BG, fg=self.TEXT,
                 font=("Helvetica", 12, "bold")).pack(pady=(20, 4))
        tk.Label(dialog,
                 text="Tienes la ultima version.\nNo hay nada que instalar.",
                 bg=self.BG, fg=self.MUTED,
                 font=("Helvetica", 10), justify=tk.CENTER).pack(pady=4)

        btns = tk.Frame(dialog, bg=self.BG)
        btns.pack(pady=18)
        self._mk_btn(btns, "ENTENDIDO", self.OK,
                     lambda: dialog.destroy(), width=14)

    def show_error(self, message):
        """Error legible (sin tecnicismos raros)."""
        if self.dialog:
            try:
                self.dialog.destroy()
            except tk.TclError:
                pass
        dialog = tk.Toplevel(self.parent)
        dialog.title("No se pudo verificar")
        dialog.configure(bg=self.BG)
        dialog.resizable(False, False)
        dialog.transient(self.parent)
        dialog.grab_set()
        self._center(dialog, 420, 220)
        self.dialog = dialog

        header = tk.Frame(dialog, bg="#E64A19")
        header.pack(fill=tk.X)
        tk.Label(header, text="NO SE PUDO VERIFICAR",
                 bg="#E64A19", fg="white",
                 font=("Helvetica", 12, "bold")).pack(pady=12)

        txt = tk.Text(dialog, height=5, width=48, font=("Helvetica", 10),
                      bg=self.CARD, relief=tk.FLAT, wrap=tk.WORD)
        txt.pack(padx=16, pady=14, fill=tk.X)
        friendly = message or "Error desconocido"
        low = friendly.lower()
        if "conexion" in low or "urlerror" in low or "network" in low:
            friendly = ("No hay internet o el servidor no responde.\n"
                        "Revise su conexion e intente de nuevo.")
        elif "404" in low:
            friendly = ("No se encontro la actualizacion en el servidor.\n"
                        "Contacte al administrador del sistema.")
        txt.insert("1.0", friendly)
        txt.config(state="disabled")

        btns = tk.Frame(dialog, bg=self.BG)
        btns.pack(pady=(0, 14))
        self._mk_btn(btns, "CERRAR", "#78909C",
                     lambda: dialog.destroy(), width=12)

    def show_changelog(self, remote_version, changelog, local_version=None):
        """Muestra novedades / lista de bugs de forma agradable."""
        info = {
            "remote_version": remote_version or "-",
            "changelog": changelog or "",
        }
        # Reutiliza el mismo look del dialogo de update sin botones de install
        if self.dialog:
            try:
                self.dialog.destroy()
            except tk.TclError:
                pass
        dialog = tk.Toplevel(self.parent)
        dialog.title("Novedades de la version")
        dialog.configure(bg=self.BG)
        dialog.resizable(False, False)
        dialog.transient(self.parent)
        dialog.grab_set()
        self._center(dialog, 480, 380)
        self.dialog = dialog

        header = tk.Frame(dialog, bg=self.HEADER)
        header.pack(fill=tk.X)
        tk.Label(header, text="NOVEDADES / BUGS CORREGIDOS",
                 bg=self.HEADER, fg="white",
                 font=("Helvetica", 12, "bold")).pack(pady=12)

        body = tk.Frame(dialog, bg=self.BG)
        body.pack(fill=tk.BOTH, expand=True, padx=16, pady=12)

        chips = tk.Frame(body, bg=self.BG)
        chips.pack(fill=tk.X, pady=(0, 10))
        local = local_version or self.updater.current_version
        for label, valor, bg, fg in (
            ("Instalada", str(local), "#ECEFF1", self.TEXT),
            ("Publicada", str(remote_version or "-"), self.OK, "white"),
        ):
            card = tk.Frame(chips, bg=bg, padx=12, pady=6)
            card.pack(side=tk.LEFT, padx=(0, 10))
            tk.Label(card, text=label, bg=bg, fg=fg,
                     font=("Helvetica", 8)).pack()
            tk.Label(card, text=valor, bg=bg, fg=fg,
                     font=("Helvetica", 14, "bold")).pack()

        card = tk.Frame(body, bg=self.CARD, highlightthickness=1,
                        highlightbackground="#CFD8DC")
        card.pack(fill=tk.BOTH, expand=True)
        titulo, items = format_changelog(changelog)
        tk.Label(card, text=titulo, bg=self.CARD, fg=self.HEADER,
                 font=("Helvetica", 11, "bold"), anchor="w",
                 padx=12, pady=(10, 4)).pack(fill=tk.X)
        txt = tk.Text(card, height=10, width=52, font=("Helvetica", 10),
                      bg=self.CARD, fg=self.TEXT, relief=tk.FLAT,
                      padx=8, pady=4, wrap=tk.WORD)
        txt.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        txt.tag_configure("item", lmargin1=8, lmargin2=22, spacing3=4)
        for it in items:
            txt.insert(tk.END, f"  {it}\n", "item")
        txt.config(state="disabled")

        btns = tk.Frame(body, bg=self.BG)
        btns.pack(fill=tk.X, pady=(12, 0))
        self._mk_btn(btns, "CERRAR", self.OK,
                     lambda: dialog.destroy(), width=12)

    def _start_update(self, download_url, checksum, update_format="exe", new_version=None):
        """Inicia el proceso de actualizacion (exe o zip de .py)"""
        progress_win = tk.Toplevel(self.parent)
        progress_win.title("Actualizando")
        progress_win.geometry("420x200")
        progress_win.configure(bg=self.BG)
        progress_win.resizable(False, False)
        progress_win.transient(self.parent)
        progress_win.grab_set()
        self._center(progress_win, 420, 200)

        hdr = tk.Frame(progress_win, bg=self.HEADER)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="INSTALANDO ACTUALIZACION",
                 bg=self.HEADER, fg="white",
                 font=("Helvetica", 11, "bold")).pack(pady=10)

        status_label = tk.Label(progress_win, text="Preparando la actualizacion...",
                                bg=self.BG, font=("Helvetica", 11))
        status_label.pack(pady=(16, 4))

        detail_label = tk.Label(progress_win, text="",
                                bg=self.BG, fg=self.MUTED,
                                font=("Helvetica", 9))
        detail_label.pack()

        progress = ttk.Progressbar(progress_win, length=360, mode="determinate")
        progress.pack(pady=14)

        def progress_callback(msg):
            detail_label.config(text=msg)
            progress_win.update()

        def do_download():
            try:
                status_label.config(text="Respaldo de seguridad...")
                progress_win.update()
                backup_path = self.updater._create_backup()

                status_label.config(text="Descargando la mejora...")
                progress_win.update()
                if sys.platform.startswith("win"):
                    ext = ".exe"
                elif sys.platform == "darwin":
                    ext = ".bin"
                else:
                    ext = ".bin"
                url_path = download_url.split("?")[0]
                real_ext = os.path.splitext(url_path)[1]
                if real_ext:
                    ext = real_ext
                elif update_format == "zip":
                    ext = ".zip"
                filename = f"{APP_NAME}_update{ext}"
                filepath = os.path.join(self.updater.updates_dir, filename)

                self.updater._download_file(download_url, filepath, progress_callback)

                if checksum:
                    status_label.config(text="Verificando...")
                    progress_win.update()
                    if not self.updater._verify_checksum(filepath, checksum):
                        progress_win.destroy()
                        messagebox.showerror(
                            "Aviso",
                            "La descarga fallo. Intente de nuevo.")
                        return

                status_label.config(text="Instalando...")
                progress_win.update()
                progress_win.update_idletasks()

                # Instala solo: el usuario final no elige rutas ni carpeta
                try:
                    result = self.updater.apply_update(
                        filepath, update_format, new_version)
                except Exception as e:
                    progress_win.destroy()
                    messagebox.showerror(
                        "No se pudo actualizar",
                        f"Ocurrio un problema al instalar.\n\n{e}\n\n"
                        "Puede intentar otra vez desde el boton ACTUALIZAR.")
                    return

                progress_win.destroy()
                mode = ""
                if isinstance(result, dict):
                    mode = result.get("mode") or result.get("version") or ""

                msg = "La actualizacion se instalo correctamente."
                if mode:
                    msg += f"\n\nNueva version: {mode}"
                if backup_path:
                    msg += "\nSu informacion anterior quedo respaldada."
                msg += "\n\nEl sistema se va a cerrar y volver a abrir solo."
                messagebox.showinfo("Listo", msg)
                self.parent.after(400, self.parent.destroy)
            except Exception as e:
                try:
                    progress_win.destroy()
                except tk.TclError:
                    pass
                messagebox.showerror(
                    "No se pudo actualizar",
                    f"Ocurrio un problema.\n\n{e}\n\n"
                    "Revise su conexion a internet e intente de nuevo.")

        thread = threading.Thread(target=do_download, daemon=True)
        thread.start()


def check_on_startup(parent, on_result=None):
    """Verifica actualizaciones al iniciar (sin bloquear la UI).

    on_result: opcional, recibe el dict del check.
    Si no se pasa callback y hay update, abre el dialogo (compat).
    """
    updater = AutoUpdater()
    config = load_config()

    if not config.get("auto_update", True):
        return

    if not updater.update_url:
        return

    def trabajo():
        try:
            result = updater.check_for_updates(silent=True)
        except Exception:
            result = None

        # Guardar fecha de comprobacion amable
        try:
            cfg = load_config()
            if result is not None:
                cfg["last_update_check"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                save_config(cfg)
        except Exception:
            pass

        def mostrar():
            try:
                if not parent.winfo_exists():
                    return
                if on_result is not None:
                    on_result(result)
                elif result and result.get("update_available"):
                    UpdateDialog(parent, updater).show_update_available(result)
            except Exception:
                pass

        try:
            parent.after(0, mostrar)
        except Exception:
            pass

    threading.Thread(target=trabajo, daemon=True).start()


def manual_check(parent):
    """Verificacion manual de actualizaciones (hilo en segundo plano)."""
    updater = AutoUpdater()
    dialog = UpdateDialog(parent, updater)
    checking = None
    try:
        checking = dialog.show_checking()
    except Exception:
        checking = None

    def trabajo():
        try:
            result = updater.check_for_updates(silent=False)
        except Exception as e:
            result = {"update_available": False, "message": str(e)}

        try:
            cfg = load_config()
            cfg["last_update_check"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            save_config(cfg)
        except Exception:
            pass

        def mostrar():
            try:
                if checking is not None and checking.winfo_exists():
                    checking.destroy()
            except Exception:
                pass
            if result and result.get("update_available"):
                dialog.show_update_available(result)
            elif result and result.get("message"):
                msg = result["message"]
                if "ultima version" in msg.lower():
                    dialog.show_no_updates()
                else:
                    dialog.show_error(msg)
            else:
                dialog.show_error(
                    "No hay servidor configurado. Configure en Configuracion.")

        try:
            parent.after(0, mostrar)
        except Exception:
            pass

    threading.Thread(target=trabajo, daemon=True).start()


def get_server_options():
    """Retorna opciones de servidores disponibles"""
    return {
        "github": {
            "name": "GitHub (Recomendado)",
            "description": "version.json + binarios en el repositorio",
            "example": GITHUB_REPO_DEFAULT
        },
        "dropbox": {
            "name": "Dropbox",
            "description": "Enlaces directos, 2GB gratis",
            "example": "https://www.dropbox.com/s/XXXXXXXXXX/updates"
        },
        "gdrive": {
            "name": "Google Drive",
            "description": "15GB gratis, puede requerir confirmacion",
            "example": "https://drive.google.com/drive/folders/XXXXX"
        },
        "http": {
            "name": "Servidor HTTP/HTTPS",
            "description": "Cualquier servidor web, rapido y confiable",
            "example": "https://tudominio.com/updates"
        },
        "ftp": {
            "name": "Servidor FTP",
            "description": "Simple pero no seguro",
            "example": "ftp://192.168.1.100/updates"
        }
    }
