import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
import csv
import os
from database import obtener_tipo_cambio


def centrar_ventana(ventana, ancho, alto):
    pantalla_ancho = ventana.winfo_screenwidth()
    pantalla_alto = ventana.winfo_screenheight()
    x = (pantalla_ancho // 2) - (ancho // 2)
    y = (pantalla_alto // 2) - (alto // 2)
    ventana.geometry(f"{ancho}x{alto}+{x}+{y}")


def crear_treeview(parent, columnas, encabezados, ancho_cols=None, alto=300):
    frame = tk.Frame(parent)
    frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    scroll_y = ttk.Scrollbar(frame, orient=tk.VERTICAL)
    scroll_x = ttk.Scrollbar(frame, orient=tk.HORIZONTAL)

    tree = ttk.Treeview(
        frame,
        columns=columnas,
        show="headings",
        yscrollcommand=scroll_y.set,
        xscrollcommand=scroll_x.set,
        selectmode="browse"
    )

    scroll_y.config(command=tree.yview)
    scroll_x.config(command=tree.xview)

    for i, col in enumerate(columnas):
        tree.heading(col, text=encabezados[i], anchor=tk.W)
        if ancho_cols and i < len(ancho_cols):
            tree.column(col, width=ancho_cols[i], minwidth=50)
        else:
            tree.column(col, width=120, minwidth=50)

    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
    scroll_x.pack(side=tk.BOTTOM, fill=tk.X)

    return tree


def formatear_numero(numero):
    try:
        return f"{float(numero):,.2f}"
    except (ValueError, TypeError):
        return "0.00"


def formatear_colones(numero):
    try:
        return f"₡{float(numero):,.2f}"
    except (ValueError, TypeError):
        return "₡0.00"


def formatear_dolares(numero):
    try:
        return f"${float(numero):,.2f}"
    except (ValueError, TypeError):
        return "$0.00"


def convertir_a_dolares(colones, tipo_cambio=None):
    if tipo_cambio is None:
        tipo_cambio = obtener_tipo_cambio()
    try:
        return float(colones) / tipo_cambio
    except (ValueError, TypeError, ZeroDivisionError):
        return 0


def convertir_a_colones(dolares, tipo_cambio=None):
    if tipo_cambio is None:
        tipo_cambio = obtener_tipo_cambio()
    try:
        return float(dolares) * tipo_cambio
    except (ValueError, TypeError, ZeroDivisionError):
        return 0


def fecha_actual():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def fecha_solo():
    return datetime.now().strftime("%Y-%m-%d")


def exportar_a_csv(tree, archivo):
    if not tree.get_children():
        messagebox.showinfo("Exportar", "No hay datos para exportar.")
        return

    columnas = tree["columns"]
    encabezados = [tree.heading(c)["text"] for c in columnas]

    with open(archivo, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(encabezados)
        for item in tree.get_children():
            valores = tree.item(item)["values"]
            writer.writerow(valores)

    messagebox.showinfo("Exportar", f"Datos exportados correctamente a:\n{archivo}")
