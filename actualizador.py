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


def _exe_targets(root):
    """EXE a reemplazar: el de la raiz y (si existe) el actual en versions."""
    targets = [os.path.abspath(os.path.join(root, "PINO_SYSTEM.exe"))]
    ver = ""
    cur = os.path.join(root, "current.txt")
    try:
        if os.path.isfile(cur):
            with open(cur, "r", encoding="utf-8") as f:
                ver = (f.read() or "").strip()
            if ver:
                ver = ver.splitlines()[0].strip()
    except Exception:
        ver = ""
    if ver:
        old = os.path.abspath(
            os.path.join(root, "versions", ver, "PINO_SYSTEM.exe"))
        if os.path.isfile(old) and old not in targets:
            targets.append(old)
    out, seen = [], set()
    for t in targets:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def instalar_exe(nuevo_exe, version):
    """Reemplaza el PINO_SYSTEM.exe actual en su misma carpeta (raiz)."""
    root = install_root()
    targets = _exe_targets(root)
    main_dest = targets[0]

    if not os.path.isfile(nuevo_exe) or os.path.getsize(nuevo_exe) < 1024:
        raise Exception("El EXE descargado esta vacio o corrupto")

    updates = _updates_dir()
    staged = os.path.join(updates, "PINO_SYSTEM_new.exe")
    shutil.copy2(nuevo_exe, staged)

    # borrar puntero side-by-side para que INICIAR use la raiz
    ptr = os.path.join(root, "current.txt")
    try:
        if os.path.isfile(ptr):
            os.remove(ptr)
    except Exception:
        pass

    if sys.platform.startswith("win"):
        # EXE en uso: bat diferido reemplaza y relanza
        lines = ["@echo off", "chcp 65001 >nul", "timeout /t 2 /nobreak >nul"]
        for dest in targets:
            d = os.path.dirname(dest)
            lines.append(f'if not exist "{d}" mkdir "{d}"')
            lines.append(f'if exist "{dest}" move /Y "{dest}" "{dest}.old" >nul 2>nul')
            lines.append(f'copy /Y "{staged}" "{dest}" >nul')
            lines.append(f'if exist "{dest}.old" del /F /Q "{dest}.old" >nul 2>nul')
        lines.append(f'start "" "{main_dest}"')
        lines.append('del "%~f0"')
        bat = os.path.join(updates, "update_replace.bat")
        with open(bat, "w", encoding="utf-8", newline="\r\n") as f:
            f.write("\n".join(lines) + "\n")
        subprocess.Popen([bat], shell=True, cwd=updates)
        return main_dest

    # Mac/Linux: copia directa
    for dest in targets:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(staged, dest)
        try:
            os.chmod(dest, 0o755)
        except Exception:
            pass
    popen = {"cwd": os.path.dirname(main_dest), "start_new_session": True}
    subprocess.Popen([main_dest], **popen)
    return main_dest


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

            self.after(0, lambda: self.set_estado("Instalando (reemplazando EXE)..."))
            path = instalar_exe(dest, remota)
            self.set_pct(100)
            self.after(0, lambda: messagebox.showinfo(
                "Listo",
                f"Se instalo la version {remota}.\n\n"
                "El EXE se reemplazo en su carpeta.\n"
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
