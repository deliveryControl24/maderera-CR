import os
import sys
import json
import urllib.request
import urllib.error
import hashlib
import subprocess
import shutil
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from datetime import datetime

from config_paths import (
    get_updates_dir, get_version, save_config, 
    load_config, get_executable_dir, get_datos_dir, APP_NAME
)

GITHUB_REPO_DEFAULT = "https://github.com/deliveryControl24/maderera-CR"


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
                    "Verifique que updates/PINO_SYSTEM.exe este subido a GitHub."
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
            changelog = data.get("changelog", "Sin detalles")
            checksum = data.get("checksum", "")
            min_size = data.get("min_size", 0)

            if self._version_compare(remote_version, self.current_version) > 0:
                return {
                    "update_available": True,
                    "remote_version": remote_version,
                    "download_url": download_url,
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
    
    def apply_update(self, update_exe_path):
        """Aplica la actualizacion (Windows, macOS, Linux) y retorna True si se senalo reinicio."""
        if getattr(sys, 'frozen', False):
            current_exe = sys.executable
        else:
            # Desarrollo: no hay ejecutable que reemplazar
            raise Exception("Ejecutable no encontrado (modo desarrollo)")

        if not current_exe or not os.path.exists(current_exe):
            raise Exception("No se encontro el ejecutable actual")

        if sys.platform.startswith("win"):
            bat_content = f'''@echo off
timeout /t 2 /nobreak >nul
copy /Y "{update_exe_path}" "{current_exe}"
echo Actualizacion completada
start "" "{current_exe}"
del "%~f0"
'''
            bat_path = os.path.join(self.updates_dir, "update.bat")
            with open(bat_path, 'w') as f:
                f.write(bat_content)
            subprocess.Popen([bat_path], shell=True)
            return True

        # macOS / Linux: script shell que espera, copia y relanza
        sh_content = f'''#!/bin/sh
sleep 2
cp -f "{update_exe_path}" "{current_exe}" || exit 1
chmod +x "{current_exe}"
nohup "{current_exe}" >/dev/null 2>&1 &
'''
        sh_path = os.path.join(self.updates_dir, "update.sh")
        with open(sh_path, 'w') as f:
            f.write(sh_content)
        os.chmod(sh_path, 0o755)
        subprocess.Popen(["/bin/sh", sh_path], start_new_session=True)
        return True
    
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
    """Diagrama de actualizacion mejorado"""
    
    def __init__(self, parent, updater):
        self.parent = parent
        self.updater = updater
        self.dialog = None
        
    def show_checking(self):
        """Muestra dialogo de verificacion"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Verificando actualizaciones")
        self.dialog.geometry("350x120")
        self.dialog.configure(bg="#F5F5F5")
        self.dialog.resizable(False, False)
        self.dialog.transient(self.parent)
        self.dialog.grab_set()
        
        # Centrar
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - 175
        y = (self.dialog.winfo_screenheight() // 2) - 60
        self.dialog.geometry(f"350x120+{x}+{y}")
        
        tk.Label(self.dialog, text="Verificando actualizaciones...",
                 bg="#F5F5F5", font=("Helvetica", 12)).pack(pady=20)
        
        self.status_label = tk.Label(self.dialog, text="Conectando con servidor...",
                                     bg="#F5F5F5", fg="#666666", font=("Helvetica", 10))
        self.status_label.pack()
        
        self.dialog.update()
        return self.dialog
    
    def show_update_available(self, info):
        """Muestra dialogo cuando hay actualizacion disponible"""
        if self.dialog:
            self.dialog.destroy()
        
        dialog = tk.Toplevel(self.parent)
        dialog.title("Actualizacion disponible")
        dialog.geometry("420x350")
        dialog.configure(bg="#F5F5F5")
        dialog.resizable(False, False)
        dialog.transient(self.parent)
        dialog.grab_set()
        
        # Centrar
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - 210
        y = (dialog.winfo_screenheight() // 2) - 175
        dialog.geometry(f"420x350+{x}+{y}")
        
        # Header
        header = tk.Frame(dialog, bg="#1565C0")
        header.pack(fill=tk.X)
        tk.Label(header, text="NUEVA ACTUALIZACION DISPONIBLE",
                 bg="#1565C0", fg="white", font=("Helvetica", 12, "bold")).pack(pady=10)
        
        # Info
        info_frame = tk.Frame(dialog, bg="#F5F5F5")
        info_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        tk.Label(info_frame, text=f"Version actual: {self.updater.current_version}",
                bg="#F5F5F5", font=("Helvetica", 10)).pack(anchor="w")
        tk.Label(info_frame, text=f"Nueva version: {info['remote_version']}",
                bg="#F5F5F5", fg="#1565C0", font=("Helvetica", 10, "bold")).pack(anchor="w")
        
        tk.Label(info_frame, text="\nCambios:", bg="#F5F5F5", 
                font=("Helvetica", 10, "bold")).pack(anchor="w")
        
        # Changelog
        changelog_text = tk.Text(info_frame, height=6, width=45, font=("Helvetica", 9))
        changelog_text.pack(fill=tk.X, pady=5)
        changelog_text.insert("1.0", info.get("changelog", "Correcciones de errores"))
        changelog_text.config(state="disabled")
        
        # Botones
        btn_frame = tk.Frame(dialog, bg="#F5F5F5")
        btn_frame.pack(fill=tk.X, padx=20, pady=10)
        
        def on_update():
            dialog.destroy()
            self._start_update(info["download_url"], info.get("checksum", ""))
        
        def on_cancel():
            dialog.destroy()
        
        # Boton actualizar
        cont_act = tk.Frame(btn_frame, bg="#2E7D32", padx=2, pady=2)
        cont_act.pack(side=tk.LEFT, padx=5)
        tk.Button(cont_act, text="ACTUALIZAR AHORA", bg="#F0F0F0", fg="#212121",
                 font=("Helvetica", 10, "bold"), command=on_update).pack()
        
        # Boton cancelar
        cont_cancel = tk.Frame(btn_frame, bg="#78909C", padx=2, pady=2)
        cont_cancel.pack(side=tk.LEFT, padx=5)
        tk.Button(cont_cancel, text="MAS TARDE", bg="#F0F0F0", fg="#212121",
                 font=("Helvetica", 10), command=on_cancel).pack()
    
    def _start_update(self, download_url, checksum):
        """Inicia el proceso de actualizacion"""
        progress_win = tk.Toplevel(self.parent)
        progress_win.title("Actualizando")
        progress_win.geometry("400x180")
        progress_win.configure(bg="#F5F5F5")
        progress_win.resizable(False, False)
        progress_win.transient(self.parent)
        progress_win.grab_set()
        
        # Centrar
        progress_win.update_idletasks()
        x = (progress_win.winfo_screenwidth() // 2) - 200
        y = (progress_win.winfo_screenheight() // 2) - 90
        progress_win.geometry(f"400x180+{x}+{y}")
        
        status_label = tk.Label(progress_win, text="Preparando actualizacion...",
                               bg="#F5F5F5", font=("Helvetica", 11))
        status_label.pack(pady=15)
        
        detail_label = tk.Label(progress_win, text="",
                               bg="#F5F5F5", fg="#666666", font=("Helvetica", 9))
        detail_label.pack()
        
        # Barra de progreso
        progress = ttk.Progressbar(progress_win, length=350, mode='determinate')
        progress.pack(pady=10)
        
        def progress_callback(msg):
            detail_label.config(text=msg)
            progress_win.update()
        
        def do_download():
            try:
                # 1. Crear backup
                status_label.config(text="Creando backup...")
                progress_win.update()
                backup_path = self.updater._create_backup()
                
                # 2. Descargar
                status_label.config(text="Descargando actualizacion...")
                progress_win.update()
                if sys.platform.startswith("win"):
                    ext = ".exe"
                elif sys.platform == "darwin":
                    ext = ".bin"
                else:
                    ext = ".bin"
                # Preferir extension real de la URL
                url_path = download_url.split("?")[0]
                real_ext = os.path.splitext(url_path)[1]
                if real_ext:
                    ext = real_ext
                filename = f"{APP_NAME}_update{ext}"
                filepath = os.path.join(self.updater.updates_dir, filename)
                
                self.updater._download_file(download_url, filepath, progress_callback)
                
                # 3. Verificar checksum
                if checksum:
                    status_label.config(text="Verificando archivo...")
                    progress_win.update()
                    if not self.updater._verify_checksum(filepath, checksum):
                        progress_win.destroy()
                        messagebox.showerror("Error", "El archivo descargado esta corrupto.\nIntente de nuevo.")
                        return
                
                progress_win.destroy()
                
                # 4. Preguntar si desea reiniciar
                msg = "Actualizacion descargada correctamente."
                if backup_path:
                    msg += "\n\nSe creo un backup de la version actual."
                
                if messagebox.askyesno("Actualizacion lista", msg + "\n\nDesea reiniciar ahora?"):
                    try:
                        self.updater.apply_update(filepath)
                        # Cerrar la app en el hilo principal (sys.exit no sirve en threads)
                        self.parent.after(300, self.parent.destroy)
                    except Exception as e:
                        messagebox.showerror("Error", f"No se pudo aplicar la actualizacion:\n{e}")
                else:
                    messagebox.showinfo("Actualizacion",
                                       "La actualizacion se aplicara la proxima vez que inicie la aplicacion.")
            except Exception as e:
                progress_win.destroy()
                messagebox.showerror("Error", f"Error en la actualizacion:\n{str(e)}")
        
        thread = threading.Thread(target=do_download, daemon=True)
        thread.start()
    
    def show_no_updates(self):
        """Muestra dialogo cuando no hay actualizaciones"""
        messagebox.showinfo("Sin actualizaciones", 
                           "Estas en la ultima version del sistema.")
    
    def show_error(self, message):
        """Muestra error de verificacion"""
        messagebox.showwarning("Error", 
                              f"No se pudo verificar actualizaciones:\n{message}")


def check_on_startup(parent):
    """Verifica actualizaciones al iniciar la app (sin bloquear la UI)."""
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
        if not (result and result.get("update_available")):
            return

        def mostrar():
            try:
                if not parent.winfo_exists():
                    return
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
