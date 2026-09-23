"""
PINO ACTUALIZADOR - EXE chico aparte del sistema.
Comprueba version.json en GitHub, baja PINO_SYSTEM.exe y lo instala.
Sirve aunque el PINO principal este viejo o no abra.
"""
import json
import os
import shutil
import subprocess
import sys
import threading
import tkinter as tk
import tkinter.messagebox as messagebox
import urllib.error
import urllib.request
from datetime import datetime
from tkinter import ttk

APP_NAME = "PinoSystem"
VERSION_URL = (
    "https://raw.githubusercontent.com/deliveryControl24/"
    "maderera-CR/main/version.json"
)
RAW_BASE = "https://raw.githubusercontent.com/deliveryControl24/maderera-CR/main/"


def _app_data():
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser(
            "~\\AppData\\Local")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.path.expanduser("~/.local/share")
    path = os.path.join(base, APP_NAME, "datos")
    os.makedirs(path, exist_ok=True)
    return path


def _updates_dir():
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser(
            "~\\AppData\\Local")
        path = os.path.join(base, APP_NAME, "updates")
    else:
        path = os.path.join(_app_data(), "updates")
    os.makedirs(path, exist_ok=True)
    return path



def install_root():
    """Carpeta donde viven versions\\ y current.txt (junto al EXE o raiz)."""
    if getattr(sys, "frozen", False):
        code_dir = os.path.dirname(os.path.abspath(sys.executable))
    else:
        code_dir = os.path.dirname(os.path.abspath(__file__))
    parent = os.path.dirname(code_dir)
    if os.path.basename(parent).lower() == "versions":
        return os.path.dirname(parent)
    if os.path.basename(code_dir).lower() == "versions":
        return parent
    return code_dir


def local_version():
    try:
        from config_paths import APP_VERSION
        return APP_VERSION
    except Exception:
        pass
    # leyendo current.txt + carpeta
    try:
        cur = os.path.join(install_root(), "current.txt")
        if os.path.isfile(cur):
            with open(cur, "r", encoding="utf-8") as f:
                v = f.read().strip()
                if v:
                    return v
    except Exception:
        pass
    return "0.0.0"


def ver_mayor(a, b):
    try:
        pa = [int(x) for x in str(a).split(".")]
        pb = [int(x) for x in str(b).split(".")]
        for i in range(max(len(pa), len(pb))):
            x = pa[i] if i < len(pa) else 0
            y = pb[i] if i < len(pb) else 0
            if x > y:
                return 1
            if x < y:
                return -1
        return 0
    except Exception:
        return 0


def descargar(url, dest, on_pct=None):
    req = urllib.request.Request(url, headers={"User-Agent": "PinoActualizador/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        with open(dest, "wb") as out:
            while True:
                chunk = resp.read(1 << 20)
                if not chunk:
                    break
                out.write(chunk)
                done += len(chunk)
                if on_pct and total:
                    on_pct(int(done * 100 / total))
    if os.path.getsize(dest) < 1024:
        raise Exception("Descarga incompleta")


def instalar_exe(nuevo_exe, version):
    root = install_root()
    ver = str(version).strip() or "nueva"
    dest_dir = os.path.join(root, "versions", ver)
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, "PINO_SYSTEM.exe")
    running = ""
    if getattr(sys, "frozen", False):
        running = os.path.abspath(sys.executable)
    if running and os.path.abspath(dest) == running:
        dest_dir = os.path.join(root, "versions", ver + "_new")
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, "PINO_SYSTEM.exe")
    tmp = dest + ".tmp"
    shutil.copy2(nuevo_exe, tmp)
    os.replace(tmp, dest)
    if sys.platform != "win32":
        try:
            os.chmod(dest, 0o755)
        except Exception:
            pass
    # puntero + launcher
    ptr = os.path.join(root, "current.txt")
    with open(ptr + ".tmp", "w", encoding="utf-8") as f:
        f.write(os.path.basename(dest_dir) + "\n")
    os.replace(ptr + ".tmp", ptr)
    try:
        from config_paths import ensure_launcher
        ensure_launcher()
    except Exception:
        pass
    # lanzar nuevo
    popen = {"cwd": dest_dir}
    if not sys.platform.startswith("win"):
        popen["start_new_session"] = True
    subprocess.Popen([dest], **popen)
    return dest


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PINO - Actualizador")
        self.configure(bg="#ECEFF1")
        self.resizable(False, False)
        w, h = 460, 280
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 3
        self.geometry(f"{w}x{h}+{x}+{y}")

        tk.Frame(self, bg="#1565C0", height=52).pack(fill=tk.X)
        tk.Label(self, text="ACTUALIZADOR PINO SYSTEM",
                 bg="#1565C0", fg="white",
                 font=("Helvetica", 13, "bold")).pack(pady=(14, 0))
        tk.Label(self, text="Busca la version nueva y la instala sola",
                 bg="#ECEFF1", fg="#546E7A",
                 font=("Helvetica", 9)).pack(pady=(4, 10))

        self.lbl = tk.Label(self, text=f"Version en este equipo: {local_version()}",
                            bg="#ECEFF1", fg="#212121",
                            font=("Helvetica", 11, "bold"))
        self.lbl.pack(pady=6)

        self.estado = tk.Label(self, text="Listo para comprobar",
                               bg="#ECEFF1", fg="#546E7A",
                               font=("Helvetica", 10))
        self.estado.pack(pady=4)

        self.bar = ttk.Progressbar(self, length=340, mode="determinate")
        self.bar.pack(pady=8)

        cont = tk.Frame(self, bg="#ECEFF1")
        cont.pack(pady=10)
        c_ok = tk.Frame(cont, bg="#2E7D32", padx=2, pady=2)
        c_ok.pack(side=tk.LEFT, padx=6)
        tk.Button(c_ok, text="BUSCAR Y ACTUALIZAR",
                  bg="#F0F0F0", fg="#212121",
                  font=("Helvetica", 11, "bold"),
                  width=20, command=self.empezar,
                  relief=tk.FLAT, cursor="hand2").pack()
        c_no = tk.Frame(cont, bg="#78909C", padx=2, pady=2)
        c_no.pack(side=tk.LEFT, padx=6)
        tk.Button(c_no, text="SALIR",
                  bg="#F0F0F0", fg="#212121",
                  font=("Helvetica", 11, "bold"),
                  width=10, command=self.destroy,
                  relief=tk.FLAT, cursor="hand2").pack()

    def set_estado(self, text):
        self.estado.config(text=text)
        self.update_idletasks()

    def set_pct(self, n):
        self.bar["value"] = n
        self.update_idletasks()

    def empezar(self):
        self.set_pct(0)
        threading.Thread(target=self._trabajo, daemon=True).start()

    def _trabajo(self):
        try:
            self.after(0, lambda: self.set_estado("Conectando con el servidor..."))
            req = urllib.request.Request(VERSION_URL, headers={
                "User-Agent": "PinoActualizador/1.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.loads(r.read().decode("utf-8"))
            remota = data.get("version", "0.0.0")
            local = local_version()
            self.after(0, lambda: self.set_estado(
                f"En el equipo: {local}  |  Disponible: {remota}"))
            if ver_mayor(remota, local) <= 0:
                self.after(0, lambda: messagebox.showinfo(
                    "Actualizado",
                    f"Ya tienes la ultima version ({local}).\nNo hay nada que instalar."))
                self.after(0, self.set_estado, "Todo al dia")
                return

            url = data.get("download_url_win") or data.get("download_url") or ""
            if url and not url.startswith("http"):
                url = RAW_BASE + url.lstrip("/")
            if not url:
                raise Exception("El servidor no indico donde bajar el sistema")

            dest = os.path.join(_updates_dir(), "PINO_SYSTEM_update.exe")
            self.after(0, lambda: self.set_estado("Descargando sistema nuevo..."))
            descargar(url, dest, on_pct=lambda n: self.after(0, self.set_pct, n))

            self.after(0, lambda: self.set_estado("Instalando..."))
            path = instalar_exe(dest, remota)
            self.set_pct(100)
            self.after(0, lambda: messagebox.showinfo(
                "Listo",
                f"Se instalo la version {remota}.\n\n"
                "El sistema se va a abrir solo.\n"
                f"Instalado en:\n{path}"))
            self.after(600, self.destroy)
        except urllib.error.URLError as e:
            self.after(0, lambda: messagebox.showerror(
                "Sin conexion",
                "No se pudo contactar el servidor.\n"
                "Revise su internet e intente de nuevo."))
            self.after(0, lambda: self.set_estado("Fallo la conexion"))
        except Exception as e:
            self.after(0, lambda: messagebox.showerror(
                "No se pudo actualizar", str(e)))
            self.after(0, lambda: self.set_estado("No se pudo actualizar"))


if __name__ == "__main__":
    App().mainloop()
