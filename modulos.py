import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from database import (ejecutar_consulta, ejecutar_select, ejecutar_select_one,
                      obtener_tipo_cambio, actualizar_tipo_cambio)
from utils import (
    centrar_ventana, crear_treeview, formatear_numero, formatear_colones,
    formatear_dolares, convertir_a_dolares, convertir_a_colones,
    fecha_actual, fecha_solo, exportar_a_csv
)
from excel_export import exportar_excel, tree_a_excel


# ═══════════════════════════════════════════════════════════════
# UTILIDAD: BOTON CON ESTILO FIJO
# ═══════════════════════════════════════════════════════════════
def btn(parent, texto, color, comando, ancho=14, alto=2, fontsize=10):
    """Crea un boton con borde de color y texto oscuro visible en macOS."""
    contenedor = tk.Frame(parent, bg=color, padx=2, pady=2)
    contenedor.pack(side=tk.LEFT, padx=3, pady=3)
    b = tk.Button(contenedor, text=texto, font=("Helvetica", fontsize, "bold"),
                  bg="#F0F0F0", fg="#212121", activebackground="#D0D0D0",
                  activeforeground="#000", width=ancho, height=alto,
                  command=comando, relief=tk.FLAT, bd=0, cursor="hand2")
    b.pack()
    return b


def obtener_iva_rate():
    """Retorna el IVA como decimal (ej: 0.12) desde la configuracion (cacheada)."""
    from database import obtener_config_completa
    cfg = obtener_config_completa()
    try:
        pct = float(cfg.get("iva", 12.0)) if cfg else 12.0
    except (TypeError, ValueError):
        pct = 12.0
    if pct < 0:
        pct = 12.0
    return pct / 100.0


def obtener_iva_pct():
    """Retorna el IVA como porcentaje (ej: 12)."""
    return obtener_iva_rate() * 100


def _debounce(widget, delay_ms, callback):
    """Retrasa la busqueda hasta dejar de teclear (evita lag al escribir)."""
    state = {"after": None}

    def _run(event=None):
        if state["after"]:
            try:
                widget.after_cancel(state["after"])
            except Exception:
                pass
        state["after"] = widget.after(delay_ms, callback)

    widget.bind("<KeyRelease>", _run, add="+")
    return _run


def _llenar_tree(tree, filas):
    """Limpia y rellena un Treeview de forma mas rapida."""
    tree.configure(takefocus=0)
    items = tree.get_children()
    if items:
        tree.delete(*items)
    for vals in filas:
        tree.insert("", "end", values=vals)
    tree.configure(takefocus=1)


def toggle_maximizar(win):
    """Alterna maximizar / restaurar la ventana."""
    try:
        if sys.platform == "darwin":
            win.attributes("-zoomed", not win.attributes("-zoomed"))
        else:
            if str(win.state()) == "zoomed":
                win.state("normal")
            else:
                win.state("zoomed")
    except tk.TclError:
        try:
            win.attributes("-fullscreen", not win.attributes("-fullscreen"))
        except tk.TclError:
            pass


def abrir_modulo(parent, nombre):
    """Abre un modulo por nombre desde la barra de navegacion."""
    mapa = {
        "pos": lambda p: VentasPOSModulo(p),
        "productos": lambda p: ProductosModulo(p),
        "kardex": lambda p: KardexModulo(p),
        "facturacion": lambda p: FacturacionModulo(p),
        "clientes": lambda p: ClientesModulo(p, tipo="clientes"),
        "reportes": lambda p: ReportesModulo(p),
        "graficos": lambda p: ReportesGraficosModulo(p),
        "config": lambda p: ConfiguracionModulo(p, callback=None),
    }
    fn = mapa.get(nombre)
    if fn:
        fn(parent)


def barra_navegacion(ventana, parent, actual=None):
    """Barra superior: Inicio, atajos a modulos, maximizar y cerrar."""
    bar = tk.Frame(ventana, bg="#263238")
    bar.pack(fill=tk.X, side=tk.TOP)

    def cerrar_nav(llamar_callback=None):
        try:
            ventana.grab_release()
        except tk.TclError:
            pass
        ventana.destroy()
        if llamar_callback:
            llamar_callback()

    def ir(nombre, es_inicio=False):
        if nombre == actual and not es_inicio:
            return
        cb = getattr(ventana, "_nav_callback", None)
        # Atras/Inicio siempre cierra; a otro modulo tambien cierra esta ventana
        cerrar_nav(cb)
        if nombre != "inicio":
            abrir_modulo(parent, nombre)

    try:
        from config_paths import load_config as _lc
        hidden = set(_lc().get("hidden_modules") or [])
    except Exception:
        hidden = set()
    mods = [
        ("INICIO", "inicio", "#2E7D32"),
        ("POS", "pos", "#FF6F00"),
        ("PROD", "productos", "#1565C0"),
        ("KARDEX", "kardex", "#C62828"),
        ("FACTURA", "facturacion", "#00838F"),
        ("CLIENTES", "clientes", "#6A1B9A"),
        ("REPORTES", "reportes", "#E65100"),
        ("GRAFICOS", "graficos", "#7B1FA2"),
        ("CONFIG", "config", "#546E7A"),
    ]
    mods = [m for m in mods if m[1] == "inicio" or m[1] == "config" or m[1] not in hidden]

    for texto, nombre, color in mods:
        es_actual = (nombre == actual)
        cont = tk.Frame(bar, bg=color if not es_actual else "#FFD600",
                        padx=2, pady=2)
        cont.pack(side=tk.LEFT, padx=(3 if texto == "INICIO" else 1, 1), pady=4)
        b = tk.Button(
            cont, text=texto,
            font=("Helvetica", 8, "bold"),
            bg="#FFD600" if es_actual else "#F5F5F5",
            fg="#212121",
            activebackground="#FFE082" if es_actual else "#E0E0E0",
            relief=tk.FLAT, bd=0, cursor="hand2",
            command=lambda n=nombre: ir(n))
        b.pack()

    # Lado derecho: maximizar / restaurar / cerrar
    der = tk.Frame(bar, bg="#263238")
    der.pack(side=tk.RIGHT, padx=6, pady=4)

    estado = {"max": False}

    def btn_max():
        toggle_maximizar(ventana)
        estado["max"] = not estado["max"]
        b_max.config(text="RESTAURAR" if estado["max"] else "MAXIMIZAR")

    b_max = tk.Button(der, text="MAXIMIZAR",
                      font=("Helvetica", 8, "bold"),
                      bg="#1565C0", fg="white",
                      activebackground="#1976D2",
                      relief=tk.FLAT, bd=0, cursor="hand2",
                      command=btn_max)
    b_max.pack(side=tk.LEFT, padx=2)

    # Retroceso / Atras = INICIO
    b_back = tk.Button(der, text="ATRAS",
                       font=("Helvetica", 8, "bold"),
                       bg="#E64A19", fg="white",
                       activebackground="#F57C00",
                       relief=tk.FLAT, bd=0, cursor="hand2",
                       command=lambda: ir("inicio", es_inicio=True))
    b_back.pack(side=tk.LEFT, padx=2)

    b_close = tk.Button(der, text="X",
                        font=("Helvetica", 8, "bold"),
                        bg="#C62828", fg="white",
                        activebackground="#E53935",
                        relief=tk.FLAT, bd=0, cursor="hand2",
                        width=3,
                        command=lambda: cerrar_nav(getattr(ventana, "_nav_callback", None)))
    b_close.pack(side=tk.LEFT, padx=2)

    # Escape = volver al inicio
    ventana.bind("<Escape>", lambda e: ir("inicio", es_inicio=True))
    # Doble click en barra = maximizar
    bar.bind("<Double-Button-1>", lambda e: btn_max())

    return bar


# ═══════════════════════════════════════════════════════════════
# MODULO: VENTAS POS
# ═══════════════════════════════════════════════════════════════
class VentasPOSModulo:
    def __init__(self, parent):
        self.parent = parent
        self.ventana = tk.Toplevel(parent)
        self.ventana.title("PINO SYSTEM - Ventas POS")
        self.ventana.configure(bg="#263238")
        centrar_ventana(self.ventana, 1100, 700)
        self.ventana.transient(parent)
        self.ventana.grab_set()
        barra_navegacion(self.ventana, parent, actual="pos")

        self.tipo_cambio = obtener_tipo_cambio()
        self.carrito = []
        self.crear_widgets()

    def crear_widgets(self):
        # Header
        header = tk.Frame(self.ventana, bg="#0D47A1", height=55)
        header.pack(fill=tk.X)
        tk.Label(header, text="VENTAS POS - PUNTO DE VENTA",
                 bg="#0D47A1", fg="white",
                 font=("Helvetica", 16, "bold")).pack(pady=14)

        # Panel izquierdo: productos
        panel_izq = tk.Frame(self.ventana, bg="#37474F", width=550)
        panel_izq.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 2), pady=5)

        # Busqueda de producto
        busca_frame = tk.Frame(panel_izq, bg="#37474F")
        busca_frame.pack(fill=tk.X, padx=5, pady=5)
        tk.Label(busca_frame, text="Buscar producto:", bg="#37474F", fg="white",
                 font=("Helvetica", 10, "bold")).pack(side=tk.LEFT, padx=3)
        self.entry_buscar = tk.Entry(busca_frame, width=30, font=("Helvetica", 11))
        self.entry_buscar.pack(side=tk.LEFT, padx=5)
        _debounce(self.entry_buscar, 250, self.buscar_producto)

        # Cantidad
        tk.Label(busca_frame, text="Cant:", bg="#37474F", fg="white",
                 font=("Helvetica", 10, "bold")).pack(side=tk.LEFT, padx=(10, 3))
        self.entry_cant = tk.Entry(busca_frame, width=6, font=("Helvetica", 11))
        self.entry_cant.pack(side=tk.LEFT, padx=3)
        self.entry_cant.insert(0, "1")

        # Lista de productos
        columnas = ("codigo", "nombre", "precio_crc", "precio_usd", "stock")
        encabezados = ("Codigo", "Nombre", "Precio CRC", "Precio USD", "Stock")
        ancho_cols = (70, 200, 100, 100, 60)

        self.tree_productos = crear_treeview(panel_izq, columnas, encabezados, ancho_cols, 350)
        self.tree_productos.bind("<Double-1>", self.agregar_al_carrito)

        # Boton agregar
        btn_agr = tk.Button(panel_izq, text="AGREGAR AL CARRITO  >>",
                            font=("Helvetica", 11, "bold"), bg="#2E7D32", fg="white",
                            command=self.agregar_al_carrito_btn, relief=tk.FLAT, height=2)
        btn_agr.pack(fill=tk.X, padx=5, pady=5)

        # Panel derecho: carrito
        panel_der = tk.Frame(self.ventana, bg="#263238", width=500)
        panel_der.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(2, 5), pady=5)

        tk.Label(panel_der, text="CARRITO DE VENTAS", bg="#263238", fg="#FFD54F",
                 font=("Helvetica", 13, "bold")).pack(pady=(5, 3))

        # Carrito treeview
        columnas_car = ("idx", "producto", "cantidad", "p_unit", "subtotal")
        encabezados_car = ("#", "Producto", "Cant.", "P.Unitario", "Subtotal")
        ancho_car = (35, 200, 60, 90, 100)

        self.tree_carrito = crear_treeview(panel_der, columnas_car, encabezados_car, ancho_car, 300)

        # Botones carrito
        btn_car_frame = tk.Frame(panel_der, bg="#263238")
        btn_car_frame.pack(fill=tk.X, padx=5, pady=3)

        tk.Button(btn_car_frame, text="ELIMINAR", bg="#C62828", fg="white",
                  font=("Helvetica", 9, "bold"), command=self.eliminar_del_carrito,
                  relief=tk.FLAT, width=12).pack(side=tk.LEFT, padx=3)
        tk.Button(btn_car_frame, text="VACIAR", bg="#78909C", fg="white",
                  font=("Helvetica", 9, "bold"), command=self.vaciar_carrito,
                  relief=tk.FLAT, width=12).pack(side=tk.LEFT, padx=3)
        tk.Button(btn_car_frame, text="LIMPIAR BUSQUEDA", bg="#455A64", fg="white",
                  font=("Helvetica", 9, "bold"), command=self.limpiar_busqueda,
                  relief=tk.FLAT, width=16).pack(side=tk.LEFT, padx=3)

        # Moneda selector
        mon_frame = tk.Frame(panel_der, bg="#263238")
        mon_frame.pack(fill=tk.X, padx=5, pady=3)
        tk.Label(mon_frame, text="Moneda:", bg="#263238", fg="white",
                 font=("Helvetica", 10, "bold")).pack(side=tk.LEFT, padx=3)
        self.var_moneda = tk.StringVar(value="CRC")
        tk.Radiobutton(mon_frame, text="CRC Colones", variable=self.var_moneda, value="CRC",
                       bg="#263238", fg="white", selectcolor="#37474F",
                       font=("Helvetica", 10), command=self.actualizar_total_carrito).pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(mon_frame, text="USD Dolares", variable=self.var_moneda, value="USD",
                       bg="#263238", fg="white", selectcolor="#37474F",
                       font=("Helvetica", 10), command=self.actualizar_total_carrito).pack(side=tk.LEFT, padx=5)

        # Totales
        tot_frame = tk.Frame(panel_der, bg="#1B5E20", relief=tk.SUNKEN, bd=1)
        tot_frame.pack(fill=tk.X, padx=5, pady=5)

        self.lbl_subtotal = tk.Label(tot_frame, text="Subtotal: CRC 0.00",
                                      bg="#1B5E20", fg="#C8E6C9",
                                      font=("Helvetica", 11, "bold"))
        self.lbl_subtotal.pack(padx=10, pady=2, anchor=tk.W)

        self.lbl_iva = tk.Label(tot_frame, text=f"IVA {obtener_iva_pct():g}%: CRC 0.00",
                                 bg="#1B5E20", fg="#C8E6C9",
                                 font=("Helvetica", 11, "bold"))
        self.lbl_iva.pack(padx=10, pady=2, anchor=tk.W)

        self.lbl_total = tk.Label(tot_frame, text="TOTAL: CRC 0.00",
                                   bg="#1B5E20", fg="#FFD54F",
                                   font=("Helvetica", 16, "bold"))
        self.lbl_total.pack(padx=10, pady=5, anchor=tk.W)

        # Botones finales
        fin_frame = tk.Frame(panel_der, bg="#263238")
        fin_frame.pack(fill=tk.X, padx=5, pady=5)

        tk.Button(fin_frame, text="COBRAR / FACTURAR",
                  font=("Helvetica", 13, "bold"), bg="#FF6F00", fg="white",
                  command=self.cobrar, relief=tk.FLAT, height=2, width=20).pack(side=tk.LEFT, padx=5)
        tk.Button(fin_frame, text="COTIZACION",
                  font=("Helvetica", 11, "bold"), bg="#1565C0", fg="white",
                  command=self.generar_cotizacion, relief=tk.FLAT, height=2, width=14).pack(side=tk.LEFT, padx=5)

        self.cargar_productos()

    def cargar_productos(self):
        for item in self.tree_productos.get_children():
            self.tree_productos.delete(item)
        productos = ejecutar_select("""
            SELECT p.codigo, p.nombre, p.precio_venta, p.precio_venta_usd,
                   COALESCE((
                       SELECT k.saldo_cantidad FROM kardex k
                       WHERE k.producto_id = p.id
                       ORDER BY k.id DESC LIMIT 1
                   ), 0) AS stock
            FROM productos p WHERE p.activo = 1 ORDER BY p.nombre""")
        filas = [(
            p["codigo"], p["nombre"],
            formatear_numero(p["precio_venta"]),
            formatear_dolares(p["precio_venta_usd"]),
            formatear_numero(p["stock"])) for p in productos]
        _llenar_tree(self.tree_productos, filas)

    def buscar_producto(self):
        texto = self.entry_buscar.get().strip().lower()
        param = f"%{texto}%"
        productos = ejecutar_select("""
            SELECT p.codigo, p.nombre, p.precio_venta, p.precio_venta_usd,
                   COALESCE((
                       SELECT k.saldo_cantidad FROM kardex k
                       WHERE k.producto_id = p.id
                       ORDER BY k.id DESC LIMIT 1
                   ), 0) AS stock
            FROM productos p WHERE p.activo = 1
            AND (LOWER(p.nombre) LIKE ? OR LOWER(p.codigo) LIKE ?)
            ORDER BY p.nombre""", (param, param))
        filas = [(
            p["codigo"], p["nombre"],
            formatear_numero(p["precio_venta"]),
            formatear_dolares(p["precio_venta_usd"]),
            formatear_numero(p["stock"])) for p in productos]
        _llenar_tree(self.tree_productos, filas)

    def agregar_al_carrito(self, event=None):
        sel = self.tree_productos.selection()
        if not sel:
            return
        self._agregar_item(sel[0])

    def agregar_al_carrito_btn(self):
        sel = self.tree_productos.selection()
        if not sel:
            messagebox.showwarning("Aviso", "Seleccione un producto de la lista")
            return
        self._agregar_item(sel[0])

    def _agregar_item(self, item_id):
        vals = self.tree_productos.item(item_id)["values"]
        try:
            cantidad = float(self.entry_cant.get())
        except ValueError:
            cantidad = 1

        if cantidad <= 0:
            return

        nombre = vals[1]
        codigo = str(vals[0])
        try:
            precio_crc = float(str(vals[2]).replace(",", ""))
            precio_usd = float(str(vals[3]).replace("$", "").replace(",", ""))
            stock = float(str(vals[4]).replace(",", ""))
        except ValueError:
            messagebox.showerror("Error", "Precio o stock invalido del producto.")
            return

        existente = 0
        for item in self.carrito:
            if item.get("codigo") == codigo:
                existente = item["cantidad"]
                break

        if stock < existente + cantidad:
            messagebox.showerror(
                "Error",
                f"Stock insuficiente. Disponible: {stock}, en carrito: {existente}")
            return

        subtotal_crc = cantidad * precio_crc
        subtotal_usd = cantidad * precio_usd

        # Verificar si ya esta en el carrito (por codigo)
        for item in self.carrito:
            if item.get("codigo") == codigo:
                item["cantidad"] += cantidad
                item["subtotal_crc"] = item["cantidad"] * precio_crc
                item["subtotal_usd"] = item["cantidad"] * precio_usd
                self.refrescar_carrito()
                return

        self.carrito.append({
            "codigo": codigo, "nombre": nombre, "cantidad": cantidad,
            "precio_crc": precio_crc, "precio_usd": precio_usd,
            "subtotal_crc": subtotal_crc, "subtotal_usd": subtotal_usd
        })
        self.refrescar_carrito()

    def refrescar_carrito(self):
        for item in self.tree_carrito.get_children():
            self.tree_carrito.delete(item)
        for i, c in enumerate(self.carrito):
            moneda = self.var_moneda.get()
            if moneda == "USD":
                precio = formatear_dolares(c["precio_usd"])
                sub = formatear_dolares(c["subtotal_usd"])
            else:
                precio = formatear_numero(c["precio_crc"])
                sub = formatear_numero(c["subtotal_crc"])
            self.tree_carrito.insert("", "end", values=(
                i + 1, c["nombre"], formatear_numero(c["cantidad"]),
                precio, sub))
        self.actualizar_total_carrito()

    def actualizar_total_carrito(self):
        moneda = self.var_moneda.get()
        subtotal_crc = sum(c["subtotal_crc"] for c in self.carrito)
        subtotal_usd = sum(c["subtotal_usd"] for c in self.carrito)
        iva_rate = obtener_iva_rate()
        iva_pct = obtener_iva_pct()
        iva_crc = subtotal_crc * iva_rate
        iva_usd = subtotal_usd * iva_rate
        total_crc = subtotal_crc + iva_crc
        total_usd = subtotal_usd + iva_usd

        if moneda == "USD":
            self.lbl_subtotal.config(text=f"Subtotal: USD {formatear_dolares(subtotal_usd)}")
            self.lbl_iva.config(text=f"IVA {iva_pct:g}%: USD {formatear_dolares(iva_usd)}")
            self.lbl_total.config(text=f"TOTAL: USD {formatear_dolares(total_usd)}")
        else:
            self.lbl_subtotal.config(text=f"Subtotal: CRC {formatear_numero(subtotal_crc)}")
            self.lbl_iva.config(text=f"IVA {iva_pct:g}%: CRC {formatear_numero(iva_crc)}")
            self.lbl_total.config(text=f"TOTAL: CRC {formatear_numero(total_crc)}")

    def eliminar_del_carrito(self):
        sel = self.tree_carrito.selection()
        if not sel:
            return
        idx = int(self.tree_carrito.item(sel[0])["values"][0]) - 1
        if 0 <= idx < len(self.carrito):
            self.carrito.pop(idx)
            self.refrescar_carrito()

    def vaciar_carrito(self):
        self.carrito = []
        self.refrescar_carrito()

    def limpiar_busqueda(self):
        self.entry_buscar.delete(0, tk.END)
        self.entry_cant.delete(0, tk.END)
        self.entry_cant.insert(0, "1")
        self.cargar_productos()

    def cobrar(self):
        if not self.carrito:
            messagebox.showwarning("Aviso", "El carrito esta vacio")
            return

        moneda = self.var_moneda.get()
        subtotal_crc = sum(c["subtotal_crc"] for c in self.carrito)
        subtotal_usd = sum(c["subtotal_usd"] for c in self.carrito)
        iva_rate = obtener_iva_rate()
        iva_crc = subtotal_crc * iva_rate
        iva_usd = subtotal_usd * iva_rate
        total_crc = subtotal_crc + iva_crc
        total_usd = subtotal_usd + iva_usd

        # Generar numero de factura
        ultima = ejecutar_select_one("SELECT numero FROM facturas ORDER BY id DESC LIMIT 1")
        if ultima:
            try: num = int(ultima["numero"].replace("FAC-", "")) + 1
            except: num = 1
        else:
            num = 1
        numero = f"FAC-{num:06d}"

        # Guardar factura
        try:
            factura_id = ejecutar_consulta("""
                INSERT INTO facturas (numero, moneda, subtotal, subtotal_usd,
                    impuesto, impuesto_usd, total, total_usd, tipo_cambio, observaciones)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (numero, moneda, subtotal_crc, subtotal_usd,
                  iva_crc, iva_usd, total_crc, total_usd,
                  self.tipo_cambio, "Venta POS"))

            # Buscar producto_id por codigo
            for c in self.carrito:
                if c.get("codigo"):
                    prod = ejecutar_select_one(
                        "SELECT id, precio_venta, precio_venta_usd FROM productos WHERE codigo=? AND activo=1",
                        (c["codigo"],))
                else:
                    prod = ejecutar_select_one(
                        "SELECT id, precio_venta, precio_venta_usd FROM productos WHERE nombre=? AND activo=1",
                        (c["nombre"],))
                if not prod:
                    continue

                ejecutar_consulta("""
                    INSERT INTO detalle_factura (factura_id, producto_id, cantidad,
                        precio_unitario, precio_unitario_usd, total, total_usd)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (factura_id, prod["id"], c["cantidad"],
                      c["precio_crc"], c["precio_usd"],
                      c["subtotal_crc"], c["subtotal_usd"]))

                # Kardex salida
                stock_actual = self._stock_by_id(prod["id"])
                nuevo_stock = stock_actual - c["cantidad"]
                ejecutar_consulta("""
                    INSERT INTO kardex (producto_id, tipo_movimiento, cantidad,
                        precio_unitario, precio_unitario_usd, total, total_usd,
                        saldo_cantidad, saldo_valor, saldo_valor_usd,
                        documento_ref, proveedor_cliente, descripcion)
                    VALUES (?, 'SALIDA', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (prod["id"], c["cantidad"],
                      c["precio_crc"], c["precio_usd"],
                      c["subtotal_crc"], c["subtotal_usd"],
                      nuevo_stock, nuevo_stock * c["precio_crc"],
                      nuevo_stock * c["precio_usd"],
                      numero, "CONSUMIDOR FINAL", f"Venta POS {numero}"))

            self.generar_ticket(numero, total_crc, total_usd, moneda)
            self.carrito = []
            self.refrescar_carrito()
            self.cargar_productos()
            messagebox.showinfo("Exito", f"Factura {numero} generada correctamente")

        except Exception as e:
            messagebox.showerror("Error", f"Error al facturar:\n{e}")

    def _stock_by_id(self, pid):
        r = ejecutar_select_one(
            "SELECT saldo_cantidad FROM kardex WHERE producto_id=? ORDER BY id DESC LIMIT 1", (pid,))
        return r["saldo_cantidad"] if r else 0

    def generar_ticket(self, numero, total_crc, total_usd, moneda):
        win = tk.Toplevel(self.ventana)
        win.title("Ticket de Venta")
        centrar_ventana(win, 420, 550)

        config = ejecutar_select_one("SELECT * FROM configuracion WHERE id=1") or {}
        empresa = config.get("nombre_empresa", "PINO SYSTEM")
        tc = self.tipo_cambio
        
        # Configuracion de factura
        invoice_color = config.get("invoice_color", "#1B5E20")
        font_size = config.get("invoice_font_size", 10)
        invoice_footer = config.get("invoice_footer", "Gracias por su compra!")
        invoice_header = config.get("invoice_header", "")
        titulo_factura = config.get("titulo_factura_text", "FACTURA")
        show_titulo = config.get("show_titulo_factura", 1)
        show_tc = config.get("show_tc", 1)
        show_subtotal = config.get("show_subtotal", 1)
        show_iva = config.get("show_iva", 1)
        show_nit = config.get("show_nit", 1)
        show_telefono = config.get("show_telefono", 1)
        show_direccion = config.get("show_direccion", 1)
        show_fecha = config.get("show_fecha", 1)
        show_numero = config.get("show_numero_factura", 1)

        text = tk.Text(win, font=("Courier", font_size), bg="white", wrap=tk.WORD)
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        lineas = []
        lineas.append("=" * 42)
        
        if show_titulo:
            lineas.append(f"  {titulo_factura}")
        
        lineas.append(f"  {empresa.upper()}")
        
        if show_nit:
            lineas.append(f"  NIT: {config.get('nit', 'N/A')}")
        if show_telefono:
            lineas.append(f"  TEL: {config.get('telefono', 'N/A')}")
        if show_direccion:
            lineas.append(f"  {config.get('direccion', '')}")
        
        if invoice_header:
            lineas.append(f"  {invoice_header}")
        
        lineas.append("=" * 42)
        
        if show_numero:
            lineas.append(f"  Ticket: {numero}")
        if show_fecha:
            lineas.append(f"  Fecha:  {fecha_actual()}")
        if show_tc:
            lineas.append(f"  TC: CRC {tc:,.2f}/USD")
        
        lineas.append("-" * 42)
        lineas.append(f"  {'Prod':<20} {'Cant':>5} {'Total':>12}")
        lineas.append("-" * 42)

        for c in self.carrito:
            nombre = c["nombre"][:20]
            if moneda == "USD":
                lineas.append(f"  {nombre:<20} {c['cantidad']:>5.1f} USD {c['subtotal_usd']:>9.2f}")
            else:
                lineas.append(f"  {nombre:<20} {c['cantidad']:>5.1f} CRC {c['subtotal_crc']:>8.2f}")

        lineas.append("-" * 42)
        subtotal_crc = sum(c["subtotal_crc"] for c in self.carrito)
        subtotal_usd = sum(c["subtotal_usd"] for c in self.carrito)
        iva_crc = subtotal_crc * (config.get("iva", 12) / 100)
        iva_usd = subtotal_usd * (config.get("iva", 12) / 100)
        tot_crc = subtotal_crc + iva_crc
        tot_usd = subtotal_usd + iva_usd

        if moneda == "USD":
            if show_subtotal:
                lineas.append(f"  {'Subtotal:':<25} USD {subtotal_usd:>9.2f}")
            if show_iva:
                lineas.append(f"  {'IVA ' + str(config.get('iva', 12)) + '%:':<25} USD {iva_usd:>9.2f}")
            lineas.append(f"  {'TOTAL:':<25} USD {tot_usd:>9.2f}")
        else:
            if show_subtotal:
                lineas.append(f"  {'Subtotal:':<25} CRC {subtotal_crc:>9.2f}")
            if show_iva:
                lineas.append(f"  {'IVA ' + str(config.get('iva', 12)) + '%:':<25} CRC {iva_crc:>9.2f}")
            lineas.append(f"  {'TOTAL:':<25} CRC {tot_crc:>9.2f}")

        lineas.append("=" * 42)
        
        if invoice_footer:
            lineas.append(f"  {invoice_footer}")
        
        lineas.append("=" * 42)

        text.insert(tk.END, "\n".join(lineas))
        text.config(state=tk.DISABLED)

    def generar_cotizacion(self):
        if not self.carrito:
            messagebox.showwarning("Aviso", "El carrito esta vacio")
            return
        moneda = self.var_moneda.get()
        subtotal_crc = sum(c["subtotal_crc"] for c in self.carrito)
        subtotal_usd = sum(c["subtotal_usd"] for c in self.carrito)
        iva_rate = obtener_iva_rate()
        total_crc = subtotal_crc * (1 + iva_rate)
        total_usd = subtotal_usd * (1 + iva_rate)

        win = tk.Toplevel(self.ventana)
        win.title("Cotizacion")
        centrar_ventana(win, 500, 550)

        text = tk.Text(win, font=("Courier", 10), bg="white", wrap=tk.WORD)
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        config = ejecutar_select_one("SELECT * FROM configuracion WHERE id=1") or {}
        empresa = config.get("nombre_empresa", "PINO SYSTEM")

        lineas = []
        lineas.append("=" * 50)
        lineas.append(f"       {empresa.upper()} - COTIZACION")
        lineas.append("=" * 50)
        lineas.append(f"  Fecha: {fecha_actual()}")
        lineas.append(f"  Tipo de Cambio: CRC {self.tipo_cambio:,.2f}")
        lineas.append("-" * 50)
        lineas.append(f"  {'Producto':<22} {'Cant':>5} {'P.Unit':>10} {'Total':>10}")
        lineas.append("-" * 50)

        for c in self.carrito:
            nombre = c["nombre"][:22]
            if moneda == "USD":
                lineas.append(f"  {nombre:<22} {c['cantidad']:>5.1f} USD {c['precio_usd']:>7.2f} USD {c['subtotal_usd']:>7.2f}")
            else:
                lineas.append(f"  {nombre:<22} {c['cantidad']:>5.1f} CRC {c['precio_crc']:>7.2f} CRC {c['subtotal_crc']:>7.2f}")

        lineas.append("-" * 50)
        iva_pct = obtener_iva_pct()
        if moneda == "USD":
            lineas.append(f"  {'Subtotal:':<38} USD {subtotal_usd:>9.2f}")
            lineas.append(f"  {'IVA ' + str(iva_pct) + '%:':<38} USD {subtotal_usd*obtener_iva_rate():>9.2f}")
            lineas.append(f"  {'TOTAL:':<38} USD {total_usd:>9.2f}")
        else:
            lineas.append(f"  {'Subtotal:':<38} CRC {subtotal_crc:>9.2f}")
            lineas.append(f"  {'IVA ' + str(iva_pct) + '%:':<38} CRC {subtotal_crc*obtener_iva_rate():>9.2f}")
            lineas.append(f"  {'TOTAL:':<38} CRC {total_crc:>9.2f}")
        lineas.append("=" * 50)
        lineas.append("  Esta cotizacion tiene vigencia de 7 dias.")
        lineas.append("=" * 50)

        text.insert(tk.END, "\n".join(lineas))
        text.config(state=tk.DISABLED)


# ═══════════════════════════════════════════════════════════════
# MODULO: CONFIGURACION
# ═══════════════════════════════════════════════════════════════
class ConfiguracionModulo:
    def __init__(self, parent, callback=None):
        self.parent = parent
        self.callback = callback
        self.ventana = tk.Toplevel(parent)
        self.ventana.title("PINO SYSTEM - Configuracion del Sistema")
        self.ventana.configure(bg="#ECEFF1")
        centrar_ventana(self.ventana, 880, 720)
        self.ventana.minsize(760, 600)
        self.ventana.transient(parent)
        self.ventana.grab_set()
        barra_navegacion(self.ventana, parent, actual="config")

        self.cambios_pendientes = False
        self.ventana._nav_callback = self._al_cerrar_nav
        self.crear_widgets()

    def _al_cerrar_nav(self):
        if getattr(self, "cambios_pendientes", False):
            if self.callback:
                self.callback()

    def _seccion(self, parent, texto, color="#37474F"):
        lbl = tk.Label(parent, text=texto, bg=color, fg="white",
                       font=("Helvetica", 11, "bold"), pady=6)
        lbl.pack(fill=tk.X, padx=12, pady=(12, 6))
        return lbl

    def _fila(self, parent, texto, ancho=18):
        f = tk.Frame(parent, bg="#ECEFF1")
        f.pack(fill=tk.X, padx=24, pady=3)
        tk.Label(f, text=texto, bg="#ECEFF1", width=ancho, anchor=tk.W,
                 font=("Helvetica", 10)).pack(side=tk.LEFT)
        return f

    def _scroll_tab(self, tab):
        canvas = tk.Canvas(tab, bg="#ECEFF1", highlightthickness=0)
        scrollbar = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        frame = tk.Frame(canvas, bg="#ECEFF1")
        frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=frame, anchor="nw", tags="inner")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def _on_wheel(event):
            if event.delta:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            elif getattr(event, "num", None) == 4:
                canvas.yview_scroll(-1, "units")
            elif getattr(event, "num", None) == 5:
                canvas.yview_scroll(1, "units")

        canvas.bind_all("<MouseWheel>", _on_wheel)
        canvas.bind_all("<Button-4>", _on_wheel)
        canvas.bind_all("<Button-5>", _on_wheel)
        self.ventana.bind("<Destroy>", lambda e: (
            canvas.unbind_all("<MouseWheel>"),
            canvas.unbind_all("<Button-4>"),
            canvas.unbind_all("<Button-5>"), e), add=True)
        return frame

    def _marcar_cambio(self, event=None):
        self.cambios_pendientes = True

    def crear_widgets(self):
        header = tk.Frame(self.ventana, bg="#37474F", height=54)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="CONFIGURACION DEL SISTEMA",
                 bg="#37474F", fg="white",
                 font=("Helvetica", 14, "bold")).pack(side=tk.LEFT, padx=18, pady=12)
        try:
            from config_paths import get_version
            ver = get_version()
        except Exception:
            ver = "0.0.0"
        tk.Label(header, text=f"v{ver}",
                 bg="#37474F", fg="#A5D6A7",
                 font=("Helvetica", 10, "bold")).pack(side=tk.RIGHT, padx=18)

        # Barra de botones ABAJO primero (para que no quede oculta)
        btn_frame = tk.Frame(self.ventana, bg="#CFD8DC", bd=1, relief=tk.SUNKEN)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM)

        self.lbl_estado = tk.Label(btn_frame, text="Sin cambios",
                                   bg="#CFD8DC", fg="#546E7A",
                                   font=("Helvetica", 9, "italic"))
        self.lbl_estado.pack(side=tk.LEFT, padx=12, pady=10)

        cont_def = tk.Frame(btn_frame, bg="#E64A19", padx=2, pady=2)
        cont_def.pack(side=tk.RIGHT, padx=6, pady=8)
        tk.Button(cont_def, text="RESTAURAR IVA/TC",
                  bg="#F0F0F0", fg="#212121", font=("Helvetica", 9, "bold"),
                  width=14, command=self._restaurar_default, relief=tk.FLAT).pack()

        cont_cancelar = tk.Frame(btn_frame, bg="#78909C", padx=2, pady=2)
        cont_cancelar.pack(side=tk.RIGHT, padx=4, pady=8)
        tk.Button(cont_cancelar, text="CANCELAR",
                  bg="#F0F0F0", fg="#212121", font=("Helvetica", 11, "bold"),
                  width=12, command=self._cerrar, relief=tk.FLAT).pack()

        cont_guardar = tk.Frame(btn_frame, bg="#2E7D32", padx=3, pady=3)
        cont_guardar.pack(side=tk.RIGHT, padx=8, pady=8)
        tk.Button(cont_guardar, text="GUARDAR CAMBIOS",
                  bg="#F0F0F0", fg="#212121", font=("Helvetica", 11, "bold"),
                  width=18, command=self.guardar, relief=tk.FLAT).pack()

        cont_test = tk.Frame(btn_frame, bg="#0288D1", padx=2, pady=2)
        cont_test.pack(side=tk.RIGHT, padx=6, pady=8)
        tk.Button(cont_test, text="VALIDAR",
                  bg="#F0F0F0", fg="#212121", font=("Helvetica", 9, "bold"),
                  width=10, command=self._validar_preview, relief=tk.FLAT).pack()

        notebook = ttk.Notebook(self.ventana)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(8, 4))
        self.notebook = notebook

        config = ejecutar_select_one("SELECT * FROM configuracion WHERE id=1") or {}

        self.check_vars = {}
        self.entries = {}
        self._tab_general(notebook, config)
        self._tab_modulos(notebook, config)
        self._tab_empresa(notebook, config)
        self._tab_factura(notebook, config)
        self._tab_backup(notebook, config)
        self._tab_actualizaciones(notebook, config)

    def _cerrar(self):
        if self.cambios_pendientes:
            if not messagebox.askyesno("Salir", "Hay cambios sin guardar. Desea salir igual?"):
                return
        self.ventana.destroy()

    def _restaurar_default(self):
        self.entry_tc.delete(0, tk.END)
        self.entry_tc.insert(0, "520.0")
        self.entry_iva.delete(0, tk.END)
        self.entry_iva.insert(0, "12")
        self.var_moneda.set("CRC")
        self.cambios_pendientes = True
        self.lbl_estado.config(text="Valores por defecto cargados (sin guardar)")

    def _validar_preview(self):
        errores = self._validar_todo()
        if errores:
            messagebox.showwarning("Validacion", "Corrija:\n- " + "\n- ".join(errores))
        else:
            messagebox.showinfo("Validacion OK",
                                "Todos los valores son validos.\nPuede guardar.")

    def _validar_todo(self):
        errores = []
        try:
            tc = float(self.entry_tc.get())
            if tc <= 0 or tc > 10000:
                errores.append("Tipo de cambio fuera de rango (0 - 10000)")
        except ValueError:
            errores.append("Tipo de cambio debe ser numerico")

        try:
            iva = float(self.entry_iva.get())
            if iva < 0 or iva > 100:
                errores.append("IVA debe estar entre 0 y 100")
        except ValueError:
            errores.append("IVA debe ser numerico")

        if not self.entries["entry_empresa"].get().strip():
            errores.append("Nombre de empresa vacio")

        email = self.entries["entry_email"].get().strip()
        if email and ("@" not in email or "." not in email):
            errores.append("Email invalido")

        color = self.entry_invoice_color.get().strip()
        if not (color.startswith("#") and len(color) in (4, 7)):
            errores.append("Color factura debe ser hex (#1B5E20)")

        try:
            fs = int(self.entry_font_size.get())
            if fs < 6 or fs > 24:
                errores.append("Tamano letra entre 6 y 24")
        except ValueError:
            errores.append("Tamano letra debe ser entero")

        try:
            mg = int(self.entry_margen.get())
            if mg < 0 or mg > 50:
                errores.append("Margen entre 0 y 50 mm")
        except ValueError:
            errores.append("Margen debe ser entero")

        url = self.entry_update_url.get().strip()
        if url and not (url.startswith("http") or url.startswith("ftp")):
            errores.append("URL actualizacion debe empezar por http o ftp")

        return errores

    # ── TAB GENERAL ──────────────────────────────────────────
    # ── TAB MODULOS (mostrar/ocultar en el inicio) ───────────
    def _tab_modulos(self, notebook, config):
        tab = tk.Frame(notebook, bg="#ECEFF1")
        notebook.add(tab, text="  Modulos  ")
        f = self._scroll_tab(tab)

        self._seccion(f, "BOTONES VISIBLES EN LA PANTALLA DE INICIO",
                      color="#00838F")
        tk.Label(f,
                 text="Marque los modulos que SI desea mostrar.\n"
                      "Los desmarcados se ocultan del inicio y del menu superior.\n"
                      "CONFIGURACION siempre queda visible para poder volver aqui.",
                 bg="#ECEFF1", fg="#546E7A", font=("Helvetica", 9),
                 justify=tk.LEFT, anchor=tk.W).pack(anchor=tk.W, padx=26, pady=(2, 8))

        from config_paths import load_config as _lcfg
        hidden_actual = set(_lcfg().get("hidden_modules") or [])

        modulos = [
            ("pos",         "VENTAS POS - Punto de Venta"),
            ("productos",   "PRODUCTOS - Maderas"),
            ("kardex",      "KARDEX - Inventario"),
            ("facturacion", "FACTURACION - Nueva Venta"),
            ("clientes",    "CLIENTES"),
            ("reportes",    "REPORTES - Informes"),
            ("graficos",    "REPORTES - Graficos"),
            ("actualizar",  "ACTUALIZAR Sistema"),
            ("config",      "CONFIGURACION Del Sistema (obligatorio)"),
        ]

        self.modulo_vars = {}
        for key, label in modulos:
            if key == "config":
                var = tk.BooleanVar(value=True)
                estado = tk.DISABLED
            else:
                var = tk.BooleanVar(value=key not in hidden_actual)
                estado = tk.NORMAL
            self.modulo_vars[key] = var
            chk = tk.Checkbutton(
                f, text=label, variable=var,
                bg="#ECEFF1", fg="#263238",
                activebackground="#ECEFF1", font=("Helvetica", 11),
                anchor=tk.W, state=estado,
                command=self._marcar_cambio)
            chk.pack(anchor=tk.W, padx=36, pady=2, fill=tk.X)

        fila_btns = tk.Frame(f, bg="#ECEFF1")
        fila_btns.pack(anchor=tk.W, padx=26, pady=10)
        tk.Button(fila_btns, text="TODOS VISIBLES",
                  bg="#F0F0F0", fg="#212121", font=("Helvetica", 9, "bold"),
                  command=lambda: self._set_modulos_todos(True),
                  relief=tk.FLAT).pack(side=tk.LEFT, padx=(0, 6))
        tk.Button(fila_btns, text="SOLO CONFIG",
                  bg="#F0F0F0", fg="#212121", font=("Helvetica", 9, "bold"),
                  command=lambda: self._set_modulos_todos(False),
                  relief=tk.FLAT).pack(side=tk.LEFT)

        tk.Label(f,
                 text="Los cambios se aplican al presionar GUARDAR CAMBIOS.",
                 bg="#ECEFF1", fg="#00695C", font=("Helvetica", 9, "italic"),
                 anchor=tk.W).pack(anchor=tk.W, padx=26, pady=(6, 0))

    def _set_modulos_todos(self, visible):
        for key, var in self.modulo_vars.items():
            if key == "config":
                var.set(True)
            else:
                var.set(bool(visible))
        self._marcar_cambio()

    def _modulos_ocultos_actuales(self):
        ocultos = []
        for key, var in getattr(self, "modulo_vars", {}).items():
            if key == "config":
                continue
            if not var.get():
                ocultos.append(key)
        return ocultos

    def _tab_general(self, notebook, config):
        tab = tk.Frame(notebook, bg="#ECEFF1")
        notebook.add(tab, text="  General  ")
        f = self._scroll_tab(tab)

        self._seccion(f, "TIPO DE CAMBIO")
        fila_tc = self._fila(f, "1 USD = CRC:")
        self.entry_tc = tk.Entry(fila_tc, width=14, font=("Helvetica", 14, "bold"),
                                 justify=tk.CENTER)
        self.entry_tc.pack(side=tk.LEFT, padx=4)
        self.entry_tc.insert(0, str(config.get("tipo_cambio", 520.0)))
        self.entry_tc.bind("<KeyRelease>", self._marcar_cambio)

        for delta in (-10, -1, +1, +10):
            tk.Button(fila_tc, text=f"{delta:+d}" if delta > 0 else str(delta),
                      font=("Helvetica", 9, "bold"), width=5,
                      bg="#F0F0F0", fg="#212121",
                      command=lambda d=delta: self._ajustar_tc(d),
                      relief=tk.FLAT).pack(side=tk.LEFT, padx=2)

        self.lbl_tc_preview = tk.Label(f, text="", bg="#ECEFF1", fg="#00695C",
                                       font=("Helvetica", 10, "italic"))
        self.lbl_tc_preview.pack(anchor=tk.W, padx=26)
        self._actualizar_tc_preview()

        self._seccion(f, "MONEDA PRINCIPAL")
        self.var_moneda = tk.StringVar(value=config.get("moneda_local", "CRC"))
        frame_mon = tk.Frame(f, bg="#ECEFF1")
        frame_mon.pack(anchor=tk.W, padx=26, pady=4)
        for val, txt in (("CRC", "Colones (CRC)"), ("USD", "Dolares (USD)")):
            r = tk.Radiobutton(frame_mon, text=txt, variable=self.var_moneda,
                               value=val, bg="#ECEFF1", font=("Helvetica", 11),
                               command=self._marcar_cambio)
            r.pack(side=tk.LEFT, padx=15)

        from config_paths import load_config as _lcfg
        from themes import theme_choices, get_theme
        theme_actual = _lcfg().get("theme", "claro")
        self.var_tema = tk.StringVar(value=theme_actual)

        self._seccion(f, "TEMA DE LA INTERFAZ")
        frame_tema = tk.Frame(f, bg="#ECEFF1")
        frame_tema.pack(anchor=tk.W, padx=26, pady=4)
        for tid, label in theme_choices():
            r = tk.Radiobutton(
                frame_tema, text=label, variable=self.var_tema, value=tid,
                bg="#ECEFF1", font=("Helvetica", 11), indicatoron=True,
                command=self._preview_tema)
            r.pack(side=tk.LEFT, padx=12)

        # Muestra de colores del tema elegido
        self.preview_tema_frame = tk.Frame(f, bg="#ECEFF1", height=64)
        self.preview_tema_frame.pack(fill=tk.X, padx=26, pady=(4, 8))
        self.preview_tema_frame.pack_propagate(False)
        self._preview_tema()

        tk.Label(f, text="El tema se aplica al guardar. Opciones: Claro, Oscuro y Bosque.",
                 bg="#ECEFF1", fg="#546E7A", font=("Helvetica", 9),
                 anchor=tk.W).pack(anchor=tk.W, padx=26)

        self._seccion(f, "IMPUESTO (IVA)")
        fila_iva = self._fila(f, "Porcentaje IVA (%):")
        self.entry_iva = tk.Entry(fila_iva, width=8, font=("Helvetica", 13, "bold"),
                                  justify=tk.CENTER)
        self.entry_iva.pack(side=tk.LEFT, padx=4)
        self.entry_iva.insert(0, str(config.get("iva", 12)))
        self.entry_iva.bind("<KeyRelease>", self._marcar_cambio)
        for pct in (0, 1, 4, 8, 12, 13, 16, 18):
            tk.Button(fila_iva, text=f"{pct}%", width=4, font=("Helvetica", 9),
                      bg="#F0F0F0", fg="#212121",
                      command=lambda p=pct: self._set_iva(p),
                      relief=tk.FLAT).pack(side=tk.LEFT, padx=1)

        tk.Label(f, text="IVA valido: 0 - 100. Se aplica a POS, facturas y tickets.",
                 bg="#ECEFF1", fg="#546E7A", font=("Helvetica", 9),
                 anchor=tk.W).pack(anchor=tk.W, padx=26, pady=(4, 0))

        tk.Label(f, text="Info del sistema:", bg="#ECEFF1",
                 font=("Helvetica", 10, "bold")).pack(anchor=tk.W, padx=26, pady=(18, 4))
        from config_paths import get_db_path, get_app_data_dir, get_version
        info = (
            f"Version sistema:  {get_version()}\n"
            f"Base de datos:  {get_db_path()}\n"
            f"Carpeta datos:  {get_app_data_dir()}\n"
            f"Ultima config:  {config.get('fecha_actualizacion', 'n/a')}"
        )
        tk.Label(f, text=info, bg="#ECEFF1", fg="#455A64",
                 font=("Helvetica", 9), justify=tk.LEFT).pack(anchor=tk.W, padx=26)

    def _ajustar_tc(self, delta):
        try:
            val = float(self.entry_tc.get()) + delta
        except ValueError:
            val = 520.0 + delta
        val = max(1.0, val)
        self.entry_tc.delete(0, tk.END)
        self.entry_tc.insert(0, f"{val:.2f}")
        self._marcar_cambio()
        self._actualizar_tc_preview()

    def _set_iva(self, pct):
        self.entry_iva.delete(0, tk.END)
        self.entry_iva.insert(0, str(pct))
        self._marcar_cambio()

    def _preview_tema(self):
        """Muestra una miniatura de los colores del tema seleccionado."""
        from themes import get_theme
        if not hasattr(self, "preview_tema_frame"):
            return
        for w in self.preview_tema_frame.winfo_children():
            w.destroy()
        t = get_theme(self.var_tema.get() if hasattr(self, "var_tema") else None)
        self.preview_tema_frame.configure(bg=t["root_bg"])

        c1 = tk.Frame(self.preview_tema_frame, bg=t["panel_bg"], width=120, height=44)
        c1.pack(side=tk.LEFT, padx=8, pady=10)
        c1.pack_propagate(False)
        tk.Label(c1, text=t["label"], bg=t["panel_bg"], fg=t["title_fg"],
                 font=("Helvetica", 10, "bold")).pack(expand=True)

        c2 = tk.Frame(self.preview_tema_frame, bg=t["tree_bg"], width=140, height=44)
        c2.pack(side=tk.LEFT, padx=4, pady=10)
        c2.pack_propagate(False)
        tk.Label(c2, text="Fila lista", bg=t["tree_bg"], fg=t["tree_fg"],
                 font=("Helvetica", 9)).pack(expand=True)

        c3 = tk.Frame(self.preview_tema_frame, bg=t["select"], width=90, height=44)
        c3.pack(side=tk.LEFT, padx=4, pady=10)
        c3.pack_propagate(False)
        tk.Label(c3, text="Activo", bg=t["select"], fg="white",
                 font=("Helvetica", 9, "bold")).pack(expand=True)

        c4 = tk.Frame(self.preview_tema_frame, bg=t["accent"], width=70, height=44)
        c4.pack(side=tk.LEFT, padx=4, pady=10)
        c4.pack_propagate(False)

        self._marcar_cambio()

    def _actualizar_tc_preview(self, event=None):
        try:
            tc = float(self.entry_tc.get())
        except ValueError:
            self.lbl_tc_preview.config(text="Valor invalido")
            return
        self.lbl_tc_preview.config(
            text=f"Preview:  CRC 1,000 = USD {1000 / tc:,.2f}  |  USD 100 = CRC {tc * 100:,.2f}")

    # ── TAB EMPRESA ──────────────────────────────────────────
    def _tab_empresa(self, notebook, config):
        tab = tk.Frame(notebook, bg="#ECEFF1")
        notebook.add(tab, text="  Empresa  ")
        f = self._scroll_tab(tab)

        self._seccion(f, "DATOS DE LA EMPRESA (aparecen en facturas y tickets)")

        campos = [
            ("Nombre Empresa:", "entry_empresa", config.get("nombre_empresa", "PINO SYSTEM")),
            ("NIT:", "entry_nit", config.get("nit", "")),
            ("Telefono:", "entry_tel", config.get("telefono", "")),
            ("Direccion:", "entry_dir", config.get("direccion", "")),
            ("Email:", "entry_email", config.get("email", "")),
            ("Sitio Web:", "entry_web", config.get("sitio_web", "")),
        ]

        self.entries = {}
        for texto, attr, valor in campos:
            fr = self._fila(f, texto, ancho=16)
            entry = tk.Entry(fr, width=40, font=("Helvetica", 10))
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))
            entry.insert(0, valor)
            entry.bind("<KeyRelease>", self._marcar_cambio)
            self.entries[attr] = entry
        # defaults para preview si la tab Empresa no corrio aun
        for k, v in (("entry_empresa", "PINO SYSTEM"), ("entry_nit", ""),
                     ("entry_email", "")):
            if k not in self.entries:
                self.entries[k] = type("E", (), {"get": staticmethod(lambda _v=v: _v)})()

        self._seccion(f, "LOGO")
        f_logo = self._fila(f, "Logo (imagen):", ancho=16)
        self.entry_logo = tk.Entry(f_logo, width=35, font=("Helvetica", 10))
        self.entry_logo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.entry_logo.insert(0, config.get("logo_path", ""))
        self.entry_logo.bind("<KeyRelease>", self._marcar_cambio)

        def buscar_logo():
            archivo = filedialog.askopenfilename(
                filetypes=[("Imagen", "*.png *.jpg *.jpeg *.gif *.bmp")])
            if archivo:
                self.entry_logo.delete(0, tk.END)
                self.entry_logo.insert(0, archivo)
                self._marcar_cambio()
                self._preview_logo()

        tk.Button(f_logo, text="Examinar...", command=buscar_logo,
                  bg="#F0F0F0", fg="#212121", font=("Helvetica", 9)).pack(side=tk.LEFT, padx=4)
        tk.Button(f_logo, text="Ver logo", command=self._preview_logo,
                  bg="#F0F0F0", fg="#212121", font=("Helvetica", 9)).pack(side=tk.LEFT, padx=2)

        self.lbl_logo_status = tk.Label(f, text="", bg="#ECEFF1", fg="#546E7A",
                                        font=("Helvetica", 9), anchor=tk.W)
        self.lbl_logo_status.pack(anchor=tk.W, padx=26)
        self.lbl_logo_img = tk.Label(f, bg="#ECEFF1")
        self.lbl_logo_img.pack(anchor=tk.W, padx=26, pady=4)
        self._preview_logo()

        self._seccion(f, "NOTA PARA IMPRESION")
        tk.Label(f, text="Estos datos se usan en tickets, facturas y reportes.",
                 bg="#ECEFF1", fg="#546E7A", font=("Helvetica", 9),
                 justify=tk.LEFT).pack(anchor=tk.W, padx=26)

    def _preview_logo(self):
        path = self.entry_logo.get().strip()
        if not path:
            self.lbl_logo_status.config(text="Sin logo configurado.", fg="#546E7A")
            return
        if not os.path.exists(path):
            self.lbl_logo_status.config(text=f"No encontrado: {path}", fg="#C62828")
            return
        try:
            from PIL import Image, ImageTk
            img = Image.open(path)
            img.thumbnail((180, 80))
            self._logo_img = ImageTk.PhotoImage(img)
            self.lbl_logo_img.config(image=self._logo_img)
            self.lbl_logo_status.config(
                text=f"Logo OK: {os.path.basename(path)}", fg="#2E7D32")
        except Exception as e:
            self.lbl_logo_img.config(image="")
            self.lbl_logo_status.config(text=f"Error logo: {e}", fg="#C62828")

    # ── TAB FACTURA ──────────────────────────────────────────
    def _tab_factura(self, notebook, config):
        tab = tk.Frame(notebook, bg="#ECEFF1")
        notebook.add(tab, text="  Factura  ")
        f = self._scroll_tab(tab)

        # Acciones masivas
        acc = tk.Frame(f, bg="#ECEFF1")
        acc.pack(fill=tk.X, padx=14, pady=(10, 4))
        for txt, val in (("Marcar todos", 1), ("Desmarcar todos", 0)):
            tk.Button(acc, text=txt, font=("Helvetica", 9),
                      bg="#F0F0F0", fg="#212121",
                      command=lambda v=val: self._set_all_checks(v),
                      relief=tk.FLAT).pack(side=tk.LEFT, padx=4)

        self._seccion(f, "TEXTOS DE LA FACTURA")

        for label, attr, key, default in (
            ("Titulo:", "entry_titulo_factura", "titulo_factura_text", "FACTURA"),
            ("Encabezado:", "entry_invoice_header", "invoice_header", ""),
            ("Pie de factura:", "entry_invoice_footer", "invoice_footer", "Gracias por su compra!"),
            ("Marca de agua:", "entry_invoice_watermark", "invoice_watermark", ""),
        ):
            fr = self._fila(f, label, ancho=18)
            e = tk.Entry(fr, width=45, font=("Helvetica", 10))
            e.pack(side=tk.LEFT, fill=tk.X, expand=True)
            e.insert(0, config.get(key, default))
            e.bind("<KeyRelease>", self._marcar_cambio)
            setattr(self, attr, e)

        # Color con picker
        self._seccion(f, "ESTILO")
        fr_color = self._fila(f, "Color encabezado:", ancho=18)
        self.entry_invoice_color = tk.Entry(fr_color, width=12, font=("Helvetica", 10))
        self.entry_invoice_color.pack(side=tk.LEFT, padx=2)
        self.entry_invoice_color.insert(0, config.get("invoice_color", "#1B5E20"))
        self.entry_invoice_color.bind("<KeyRelease>", self._marcar_cambio)
        self.swatch_color = tk.Frame(fr_color, bg=config.get("invoice_color", "#1B5E20"),
                                     width=28, height=20, bd=1, relief=tk.SUNKEN)
        self.swatch_color.pack(side=tk.LEFT, padx=6)
        self.swatch_color.pack_propagate(False)

        def pick_color():
            from tkinter import colorchooser
            actual = self.entry_invoice_color.get().strip() or "#1B5E20"
            rgb_hex = actual if actual.startswith("#") else "#1B5E20"
            elegido = colorchooser.askcolor(color=rgb_hex, title="Color factura")
            if elegido and elegido[1]:
                self.entry_invoice_color.delete(0, tk.END)
                self.entry_invoice_color.insert(0, elegido[1])
                self.swatch_color.config(bg=elegido[1])
                self._marcar_cambio()

        tk.Button(fr_color, text="Elegir color...", command=pick_color,
                  bg="#F0F0F0", fg="#212121", font=("Helvetica", 9)).pack(side=tk.LEFT, padx=4)
        self.entry_invoice_color.bind("<KeyRelease>", lambda e: self._safe_swatch())

        # Papel / font / margen
        fr_paper = self._fila(f, "Tamano papel:", ancho=18)
        self.var_paper = tk.StringVar(value=config.get("invoice_paper_size", "ticket"))
        for val, txt in (("ticket", "Ticket (58mm)"), ("carta", "Carta")):
            tk.Radiobutton(fr_paper, text=txt, variable=self.var_paper, value=val,
                           bg="#ECEFF1", font=("Helvetica", 10),
                           command=self._marcar_cambio).pack(side=tk.LEFT, padx=8)

        fr_font = self._fila(f, "Tamano letra / Margen:", ancho=18)
        self.entry_font_size = tk.Entry(fr_font, width=5, justify=tk.CENTER,
                                        font=("Helvetica", 10))
        self.entry_font_size.pack(side=tk.LEFT, padx=2)
        self.entry_font_size.insert(0, str(config.get("invoice_font_size", 10)))
        self.entry_font_size.bind("<KeyRelease>", self._marcar_cambio)
        tk.Label(fr_font, text="pt  |  Margen:", bg="#ECEFF1",
                 font=("Helvetica", 10)).pack(side=tk.LEFT, padx=4)
        self.entry_margen = tk.Entry(fr_font, width=5, justify=tk.CENTER,
                                     font=("Helvetica", 10))
        self.entry_margen.pack(side=tk.LEFT, padx=2)
        self.entry_margen.insert(0, str(config.get("invoice_margen", 5)))
        self.entry_margen.bind("<KeyRelease>", self._marcar_cambio)
        tk.Label(fr_font, text="mm", bg="#ECEFF1", font=("Helvetica", 10)).pack(side=tk.LEFT)

        # Checkboxes (crear vars ANTES de la vista previa)
        self.check_vars = {}
        campos_check = [
            ("show_numero_factura", "Numero de Factura", 1),
            ("show_fecha", "Fecha", 1),
            ("show_nit", "NIT Empresa", 1),
            ("show_cliente", "Datos Cliente", 1),
            ("show_direccion", "Direccion", 1),
            ("show_telefono", "Telefono", 1),
            ("show_email", "Email", 1),
            ("show_sitio_web", "Sitio Web", 0),
            ("show_titulo_factura", "Titulo Factura", 1),
            ("show_codigo_producto", "Codigo Producto", 1),
            ("show_unidad_medida", "Unidad Medida", 0),
            ("show_precio_unitario", "Precio Unitario", 1),
            ("show_descuento", "Descuento General", 0),
            ("show_descuento_producto", "Descuento por Producto", 0),
            ("show_subtotal", "Subtotal", 1),
            ("show_iva", "IVA", 1),
            ("show_tc", "Tipo de Cambio", 1),
            ("show_vendedor", "Vendedor", 0),
            ("show_condicion_pago", "Condicion de Pago", 1),
        ]
        for campo, label, defval in campos_check:
            var = tk.BooleanVar(value=bool(config.get(campo, defval)))
            var.trace_add("write", lambda *_: self._marcar_cambio())
            self.check_vars[campo] = var

        # Preview
        self._seccion(f, "VISTA PREVIA RAPIDA")
        self.preview_text = tk.Text(f, height=10, font=("Courier", 9),
                                    bg="white", wrap=tk.WORD)
        self.preview_text.pack(fill=tk.X, padx=24, pady=(0, 8))
        self.preview_text.config(state=tk.DISABLED)
        tk.Button(f, text="Actualizar vista previa",
                  command=self._actualizar_preview_factura,
                  bg="#F0F0F0", fg="#212121", font=("Helvetica", 9)).pack(anchor=tk.W, padx=24, pady=(0, 8))
        self._actualizar_preview_factura()

        # Checkboxes UI
        self._seccion(f, "CAMPOS A MOSTRAR EN LA FACTURA")
        grid = tk.Frame(f, bg="#ECEFF1")
        grid.pack(fill=tk.X, padx=24, pady=4)
        for i, (campo, label, defval) in enumerate(campos_check):
            cell = tk.Frame(grid, bg="#ECEFF1")
            cell.grid(row=i // 2, column=i % 2, sticky=tk.W, pady=1, padx=8)
            tk.Checkbutton(cell, text=label, variable=self.check_vars[campo],
                           bg="#ECEFF1", font=("Helvetica", 10),
                           activebackground="#ECEFF1").pack(side=tk.LEFT)

    def _safe_swatch(self):
        color = self.entry_invoice_color.get().strip()
        if color.startswith("#") and len(color) in (4, 7):
            try:
                self.swatch_color.config(bg=color)
            except tk.TclError:
                pass

    def _set_all_checks(self, val):
        for v in self.check_vars.values():
            v.set(bool(val))
        self._marcar_cambio()

    def _actualizar_preview_factura(self):
        if not hasattr(self, "preview_text"):
            return
        empresa = "EMPRESA"
        nit = "-"
        if hasattr(self, "entries"):
            empresa = self.entries.get("entry_empresa", empresa)
            nit = self.entries.get("entry_nit", nit)
            empresa = empresa.get().strip() if hasattr(empresa, "get") else str(empresa)
            nit = nit.get().strip() if hasattr(nit, "get") else str(nit)
        empresa = empresa or "EMPRESA"
        nit = nit or "-"
        titulo = self.entry_titulo_factura.get().strip() or "FACTURA"
        hdr = self.entry_invoice_header.get().strip()
        ftr = self.entry_invoice_footer.get().strip()
        iva = self.entry_iva.get().strip() or "12"
        tc = self.entry_tc.get().strip() or "520"
        try:
            checks = getattr(self, "check_vars", {}) or {}
            activos = [lbl for campo, lbl, _ in [
                ("show_numero_factura", "Numero", 1), ("show_fecha", "Fecha", 1),
                ("show_nit", "NIT", 1), ("show_cliente", "Cliente", 1),
                ("show_subtotal", "Subtotal", 1), ("show_iva", "IVA", 1),
            ] if campo in checks and checks[campo].get()]
        except Exception:
            activos = []

        lineas = [
            "=" * 48,
            f"  {titulo}",
            f"  {empresa.upper()}",
            f"  NIT: {nit}",
        ]
        if hdr:
            lineas.append(f"  {hdr}")
        lineas += ["=" * 48,
                   "  FAC-000001          Fecha: hoy",
                   "  Cliente: CONSUMIDOR FINAL",
                   "-" * 48,
                   f"  {'Prod':<20} {'Cant':>5} {'Total':>12}",
                   f"  {'Madera de pino':<20} {2:>5} {15000:>12.2f}",
                   "-" * 48,
                   f"  Subtotal:            {15000:>12.2f}",
                   f"  IVA {iva}%:                {15000 * float(iva or 12) / 100:>12.2f}",
                   f"  TOTAL:               {15000 * (1 + float(iva or 12) / 100):>12.2f}",
                   f"  TC: CRC {tc}/USD"]
        if ftr:
            lineas.append(f"  {ftr}")
        lineas.append("=" * 48)
        lineas.append(f"  Campos activos: {', '.join(activos) if activos else 'ninguno'}")

        self.preview_text.config(state=tk.NORMAL)
        self.preview_text.delete("1.0", tk.END)
        self.preview_text.insert(tk.END, "\n".join(lineas))
        self.preview_text.config(state=tk.DISABLED)

    # ── TAB BACKUP ───────────────────────────────────────────
    def _tab_backup(self, notebook, config):
        tab = tk.Frame(notebook, bg="#ECEFF1")
        notebook.add(tab, text="  Backup / Datos  ")
        f = self._scroll_tab(tab)

        from config_paths import get_db_path, get_datos_dir
        import shutil
        import sqlite3
        from datetime import datetime as _dt

        db = get_db_path()
        resp_dir = os.path.join(get_datos_dir(), "respaldos")

        def _sqlite_backup(destino):
            """Copia consistente de la BD (segura con WAL)."""
            os.makedirs(os.path.dirname(destino), exist_ok=True)
            origen = sqlite3.connect(db, timeout=15)
            try:
                dest = sqlite3.connect(destino, timeout=15)
                try:
                    origen.backup(dest)
                finally:
                    dest.close()
            finally:
                origen.close()

        def _cerrar_conexiones():
            try:
                from database import close_connection
                close_connection()
            except Exception:
                pass

        self._seccion(f, "BASE DE DATOS")
        tk.Label(f, text=f"Ubicacion:\n{db}",
                 bg="#ECEFF1", fg="#455A64", font=("Helvetica", 10),
                 justify=tk.LEFT).pack(anchor=tk.W, padx=26)
        if os.path.exists(db):
            mb = os.path.getsize(db) / (1024 * 1024)
            tk.Label(f, text=f"Tamano actual: {mb:.2f} MB",
                     bg="#ECEFF1", fg="#00695C",
                     font=("Helvetica", 10, "bold")).pack(anchor=tk.W, padx=26, pady=4)

        acciones = tk.Frame(f, bg="#ECEFF1")
        acciones.pack(fill=tk.X, padx=24, pady=8)

        def crear_backup():
            if not os.path.exists(db):
                messagebox.showerror("Backup", "No existe la base de datos.")
                return
            destino = os.path.join(
                resp_dir, f"backup_{_dt.now().strftime('%Y%m%d_%H%M%S')}.db")
            try:
                _sqlite_backup(destino)
                self._listar_backups()
                messagebox.showinfo(
                    "Backup",
                    f"Respaldo guardado en la lista:\n{os.path.basename(destino)}")
            except Exception as e:
                messagebox.showerror("Backup", f"Error:\n{e}")

        def guardar_copia_externa():
            if not os.path.exists(db):
                messagebox.showerror("Backup", "No existe la base de datos.")
                return
            destino = filedialog.asksaveasfilename(
                defaultextension=".db",
                filetypes=[("SQLite DB", "*.db")],
                initialfile=f"backup_pino_system_{_dt.now().strftime('%Y%m%d')}.db")
            if not destino:
                return
            try:
                _sqlite_backup(destino)
                messagebox.showinfo("Backup", "Copia guardada en su carpeta.")
            except Exception as e:
                messagebox.showerror("Backup", f"Error:\n{e}")

        def _ruta_seleccionada():
            sel = self.lst_backups.curselection()
            if not sel:
                return None
            texto = self.lst_backups.get(sel[0])
            nombre = texto.split("  (")[0].strip()
            if nombre.startswith("("):
                return None
            return os.path.join(resp_dir, nombre)

        def cargar_desde_lista():
            origen = _ruta_seleccionada()
            if not origen:
                messagebox.showwarning("Cargar", "Seleccione un respaldo de la lista.")
                return
            if not os.path.exists(origen):
                messagebox.showerror("Cargar", "Ese archivo ya no existe.")
                self._listar_backups()
                return
            if not messagebox.askyesno(
                    "Cargar respaldo",
                    "Esto REEMPLAZARA la base de datos actual.\n"
                    "Se creara un backup antes de cargar.\n\nContinuar?"):
                return
            try:
                previo = os.path.join(
                    resp_dir, f"backup_previo_{_dt.now().strftime('%Y%m%d_%H%M%S')}.db")
                if os.path.exists(db):
                    _sqlite_backup(previo)
                _cerrar_conexiones()
                for suf in ("", "-wal", "-shm"):
                    p = db + suf
                    if os.path.exists(p):
                        os.remove(p)
                shutil.copy2(origen, db)
                self._listar_backups()
                messagebox.showinfo(
                    "Listo",
                    "Base de datos cargada.\nCierre y abra el sistema para ver los datos.")
                if self.callback:
                    self.callback()
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo cargar:\n{e}")

        def cargar_archivo_externo():
            origen = filedialog.askopenfilename(
                filetypes=[("SQLite DB", "*.db")])
            if not origen:
                return
            if not messagebox.askyesno(
                    "Cargar archivo",
                    "Esto REEMPLAZARA la base de datos actual.\n"
                    "Se creara un backup antes de cargar.\n\nContinuar?"):
                return
            try:
                previo = os.path.join(
                    resp_dir, f"backup_previo_{_dt.now().strftime('%Y%m%d_%H%M%S')}.db")
                if os.path.exists(db):
                    _sqlite_backup(previo)
                _cerrar_conexiones()
                for suf in ("", "-wal", "-shm"):
                    p = db + suf
                    if os.path.exists(p):
                        os.remove(p)
                shutil.copy2(origen, db)
                messagebox.showinfo(
                    "Listo",
                    "Base de datos cargada.\nCierre y abra el sistema para ver los datos.")
                if self.callback:
                    self.callback()
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo cargar:\n{e}")

        def borrar_seleccionado():
            origen = _ruta_seleccionada()
            if not origen:
                messagebox.showwarning("Borrar", "Seleccione un respaldo de la lista.")
                return
            if not messagebox.askyesno("Borrar", f"Eliminar {os.path.basename(origen)}?"):
                return
            try:
                os.remove(origen)
                self._listar_backups()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        def abrir_carpeta():
            import subprocess
            os.makedirs(resp_dir, exist_ok=True)
            if sys.platform == "darwin":
                subprocess.Popen(["open", resp_dir])
            elif sys.platform.startswith("win"):
                os.startfile(resp_dir)
            else:
                subprocess.Popen(["xdg-open", resp_dir])

        for txt, color, cmd in (
            ("CREAR BACKUP", "#1565C0", crear_backup),
            ("CARGAR SELECCIONADO", "#E64A19", cargar_desde_lista),
            ("CARGAR ARCHIVO", "#6A1B9A", cargar_archivo_externo),
            ("GUARDAR COPIA", "#00695C", guardar_copia_externa),
            ("BORRAR", "#B71C1C", borrar_seleccionado),
            ("ABRIR CARPETA", "#37474F", abrir_carpeta),
        ):
            c = tk.Frame(acciones, bg=color, padx=2, pady=2)
            c.pack(side=tk.LEFT, padx=4, pady=3)
            tk.Button(c, text=txt, bg="#F0F0F0", fg="#212121",
                      font=("Helvetica", 8, "bold"),
                      command=cmd, relief=tk.FLAT).pack()

        self._seccion(f, "RESPALDOS EN CARPETA (seleccione y CARGAR)")
        self.lst_backups = tk.Listbox(f, height=8, font=("Helvetica", 9))
        self.lst_backups.pack(fill=tk.X, padx=26, pady=4)
        self._listar_backups()

        # Exportar/importar config JSON
        self._seccion(f, "EXPORTAR / IMPORTAR CONFIGURACION")

        def exportar_cfg():
            from config_paths import load_config, get_config_path
            destino = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON", "*.json")],
                initialfile="pino_config.json")
            if not destino:
                return
            try:
                import json as _json
                data = {
                    "config": load_config(),
                    "db_config": dict(ejecutar_select_one(
                        "SELECT * FROM configuracion WHERE id=1") or {}),
                }
                with open(destino, "w", encoding="utf-8") as fh:
                    _json.dump(data, fh, indent=2, ensure_ascii=False, default=str)
                messagebox.showinfo("Exportar", "Configuracion exportada.")
            except Exception as e:
                messagebox.showerror("Error", str(e))

        def importar_cfg():
            origen = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
            if not origen:
                return
            try:
                import json as _json
                with open(origen, "r", encoding="utf-8") as fh:
                    data = _json.load(fh)
                if "config" in data:
                    from config_paths import save_config
                    save_config(data["config"])
                if "db_config" in data and data["db_config"]:
                    d = data["db_config"]
                    cols_ok = [c for c in d if c != "id"]
                    if cols_ok:
                        sets = ", ".join(f"{c}=?" for c in cols_ok)
                        vals = [d[c] for c in cols_ok]
                        ejecutar_consulta(
                            f"UPDATE configuracion SET {sets} WHERE id=1", vals)
                messagebox.showinfo("Importar",
                                    "Configuracion importada. Reinicie para ver cambios.")
                if self.callback:
                    self.callback()
                self.ventana.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo importar:\n{e}")

        exp = tk.Frame(f, bg="#ECEFF1")
        exp.pack(fill=tk.X, padx=24, pady=6)
        for txt, cmd in (("EXPORTAR config", exportar_cfg),
                         ("IMPORTAR config", importar_cfg)):
            c = tk.Frame(exp, bg="#6A1B9A", padx=2, pady=2)
            c.pack(side=tk.LEFT, padx=5)
            tk.Button(c, text=txt, bg="#F0F0F0", fg="#212121",
                      font=("Helvetica", 9, "bold"),
                      command=cmd, relief=tk.FLAT).pack()

    def _listar_backups(self):
        from config_paths import get_datos_dir
        self.lst_backups.delete(0, tk.END)
        resp_dir = os.path.join(get_datos_dir(), "respaldos")
        if not os.path.isdir(resp_dir):
            return
        archivos = sorted(
            (a for a in os.listdir(resp_dir) if a.endswith(".db")),
            reverse=True)
        for a in archivos[:50]:
            ruta = os.path.join(resp_dir, a)
            try:
                mb = os.path.getsize(ruta) / (1024 * 1024)
                self.lst_backups.insert(tk.END, f"{a}  ({mb:.2f} MB)")
            except OSError:
                self.lst_backups.insert(tk.END, a)
        if not archivos:
            self.lst_backups.insert(tk.END, "(sin respaldos todavia)")

    # ── TAB ACTUALIZACIONES ──────────────────────────────────
    def _tab_actualizaciones(self, notebook, config):
        tab = tk.Frame(notebook, bg="#ECEFF1")
        notebook.add(tab, text="  Actualizaciones  ")
        f = self._scroll_tab(tab)

        self._seccion(f, "SERVIDOR DE ACTUALIZACIONES")

        from updater import AutoUpdater, UpdateDialog
        updater_cfg = AutoUpdater()

        # Estado de la version (agradable para el usuario)
        from config_paths import get_version, load_config as _lcfg_app
        estado = tk.Frame(f, bg="#E8F5E9", highlightthickness=1,
                          highlightbackground="#A5D6A7")
        estado.pack(fill=tk.X, padx=24, pady=(4, 8))
        tk.Label(estado, text="ESTADO DE TU SISTEMA",
                 bg="#E8F5E9", fg="#1B5E20",
                 font=("Helvetica", 10, "bold")).pack(anchor="w", padx=12, pady=(8, 2))
        last_chk = _lcfg_app().get("last_update_check") or "nunca"
        tk.Label(estado,
                 text=f"Version instalada: {get_version()}\n"
                      f"Ultima comprobacion: {last_chk}",
                 bg="#E8F5E9", fg="#33691E",
                 font=("Helvetica", 10), justify=tk.LEFT).pack(anchor="w", padx=12, pady=(0, 6))
        fila_estado = tk.Frame(estado, bg="#E8F5E9")
        fila_estado.pack(anchor="w", padx=10, pady=(0, 10))

        def buscar_updates_desde_config():
            self.lbl_estado.config(text="Buscando actualizaciones...")
            self.ventana.update_idletasks()

            def trabajo():
                try:
                    result = updater_cfg.check_for_updates(silent=False)
                except Exception as e:
                    result = {"update_available": False, "message": str(e)}

                def mostrar():
                    self.lbl_estado.config(text="Comprobacion terminada")
                    dlg = UpdateDialog(self.ventana, updater_cfg)
                    if result and result.get("update_available"):
                        dlg.show_update_available(result)
                    elif result and result.get("message") and (
                            "ultima version" in result["message"].lower()):
                        dlg.show_no_updates()
                    else:
                        dlg.show_error(
                            (result or {}).get("message") or "Error desconocido")

                try:
                    self.ventana.after(0, mostrar)
                except Exception:
                    pass

            import threading as _th
            _th.Thread(target=trabajo, daemon=True).start()

        def ver_novedades():
            self.lbl_estado.config(text="Descargando novedades...")
            self.ventana.update_idletasks()

            def trabajo():
                try:
                    result = updater_cfg.check_for_updates(silent=False)
                except Exception as e:
                    result = {"update_available": False, "message": str(e)}

                def mostrar():
                    self.lbl_estado.config(text="Listo")
                    if not result:
                        dlg = UpdateDialog(self.ventana, updater_cfg)
                        dlg.show_error("No se pudo leer el servidor.")
                        return
                    # Muestra changelog aunque no haya update (novedades publicadas)
                    dlg = UpdateDialog(self.ventana, updater_cfg)
                    remote = result.get("remote_version")
                    if result.get("update_available"):
                        dlg.show_changelog(remote, result.get("changelog", ""))
                    elif result.get("message") and "Error" in str(result.get("message")):
                        dlg.show_error(result.get("message"))
                    else:
                        # al dia: aun asi mostrar ultimo changelog si vino en la respuesta
                        dlg.show_changelog(
                            remote or get_version(),
                            result.get("changelog") or "Estas al dia con la ultima version publicada.")

                try:
                    self.ventana.after(0, mostrar)
                except Exception:
                    pass

            import threading as _th
            _th.Thread(target=trabajo, daemon=True).start()

        for txt, color, cmd in (
            ("BUSCAR ACTUALIZACIONES", "#1565C0", buscar_updates_desde_config),
            ("VER NOVEDADES / BUGS", "#6A1B9A", ver_novedades),
        ):
            cont = tk.Frame(fila_estado, bg=color, padx=2, pady=2)
            cont.pack(side=tk.LEFT, padx=4)
            tk.Button(cont, text=txt, bg="#F0F0F0", fg="#212121",
                      font=("Helvetica", 9, "bold"), command=cmd,
                      relief=tk.FLAT).pack()

        f_type = self._fila(f, "Tipo servidor:", ancho=14)
        self.combo_server_type = ttk.Combobox(f_type, width=28, state="readonly",
                                               font=("Helvetica", 10))
        self.combo_server_type.pack(side=tk.LEFT, padx=4)
        self.combo_server_type["values"] = [
            "GitHub (Recomendado)",
            "Dropbox",
            "Google Drive",
            "Servidor HTTP/HTTPS",
            "FTP",
        ]
        server_types = {
            "github": 0, "dropbox": 1, "gdrive": 2, "http": 3, "ftp": 4,
        }
        current_type = updater_cfg.config.get("update_type", "github")
        self.combo_server_type.current(server_types.get(current_type, 0))

        f_url = self._fila(f, "URL repo/servidor:", ancho=14)
        self.entry_update_url = tk.Entry(f_url, width=55, font=("Helvetica", 10))
        self.entry_update_url.pack(side=tk.LEFT, fill=tk.X, expand=True)
        default_upd = updater_cfg.update_url or "https://github.com/deliveryControl24/maderera-CR"
        self.entry_update_url.insert(0, default_upd)
        self.entry_update_url.bind("<KeyRelease>", self._marcar_cambio)

        self.lbl_instrucciones = tk.Label(f, text="", bg="#ECEFF1", fg="#455A64",
                                          font=("Helvetica", 9), justify=tk.LEFT)
        self.lbl_instrucciones.pack(anchor=tk.W, padx=26, pady=6)

        def actualizar_instrucciones(event=None):
            tipo = self.combo_server_type.get()
            self._marcar_cambio()
            if "GitHub" in tipo:
                instrucciones = (
                    "INSTRUCCIONES GITHUB:\n"
                    "1. Repo: https://github.com/deliveryControl24/maderera-CR\n"
                    "2. Suba version.json en la raiz del repo (branch main)\n"
                    "3. Suba el binario en updates/ (ej: updates/PINO_SYSTEM.exe)\n"
                    "4. En version.json use download_url relativo:\n"
                    "  updates/PINO_SYSTEM.exe  (Windows)\n"
                    "  updates/PINO_SYSTEM      (macOS/Linux)\n"
                    "5. El sistema lee:\n"
                    "  raw.githubusercontent.com/.../main/version.json"
                )
            elif "Dropbox" in tipo:
                instrucciones = (
                    "INSTRUCCIONES DROPBOX:\n"
                    "1. Cree una carpeta 'updates' en Dropbox\n"
                    "2. Suba PINO_SYSTEM y version.json\n"
                    "3. Clic derecho > Compartir > Cualquier persona con el enlace\n"
                    "4. Copie el enlace de CADA archivo (con ?dl=1)\n"
                    "5. version.json va en esta URL\n"
                    "  Ejemplo: https://www.dropbox.com/s/XXXX/version.json?dl=1"
                )
            elif "Google Drive" in tipo:
                instrucciones = (
                    "INSTRUCCIONES GOOGLE DRIVE:\n"
                    "1. Carpeta 'updates' en Google Drive\n"
                    "2. Suba el ejecutable y version.json\n"
                    "3. Compartir > Cualquier persona con el enlace\n"
                    "4. Pegue la URL de la carpeta o del version.json"
                )
            elif "HTTP" in tipo:
                instrucciones = (
                    "INSTRUCCIONES SERVIDOR HTTP:\n"
                    "1. Suba archivos a su servidor web\n"
                    "2. Use HTTPS si es posible\n"
                    "3. URL base: https://tudominio.com/updates/"
                )
            else:
                instrucciones = (
                    "INSTRUCCIONES FTP:\n"
                    "1. Configure servidor FTP\n"
                    "2. Suba archivos a /updates/\n"
                    "3. Pegue: ftp://ip:puerto/updates/"
                )
            self.lbl_instrucciones.config(text=instrucciones)

        self.combo_server_type.bind("<<ComboboxSelected>>", actualizar_instrucciones)
        actualizar_instrucciones()

        # Auto-update
        from config_paths import load_config as _load_app_config
        self.var_auto_update = tk.BooleanVar(
            value=_load_app_config().get("auto_update", True))
        f_auto = tk.Frame(f, bg="#ECEFF1")
        f_auto.pack(fill=tk.X, padx=26, pady=6)
        tk.Checkbutton(f_auto, text="Buscar actualizaciones al iniciar",
                       variable=self.var_auto_update,
                       bg="#ECEFF1", font=("Helvetica", 10),
                       activebackground="#ECEFF1",
                       command=self._marcar_cambio).pack(side=tk.LEFT)

        # Acciones updater
        self._seccion(f, "HERRAMIENTAS")
        acc = tk.Frame(f, bg="#ECEFF1")
        acc.pack(fill=tk.X, padx=24, pady=6)

        def probar_servidor():
            url = self.entry_update_url.get().strip()
            if not url:
                messagebox.showwarning("Aviso", "Primero pegue la URL del servidor.")
                return
            upd = AutoUpdater()
            upd.set_update_server(url, self._map_server_type())
            self.lbl_estado.config(text="Probando servidor...")
            self.ventana.update_idletasks()

            def trabajo():
                try:
                    result = upd.check_for_updates(silent=False)
                except Exception as e:
                    result = {"update_available": False, "message": str(e)}

                def mostrar():
                    if result and result.get("update_available"):
                        messagebox.showinfo(
                            "Servidor OK",
                            f"Hay actualizacion disponible: "
                            f"{result.get('remote_version')}")
                    elif result and result.get("message"):
                        m = result["message"]
                        if "ultima version" in m.lower():
                            messagebox.showinfo(
                                "Servidor OK",
                                "Conexion correcta. Sin actualizaciones nuevas.")
                        elif "No hay servidor" in m:
                            messagebox.showwarning("Aviso", m)
                        else:
                            messagebox.showerror("Error servidor", m)
                    else:
                        messagebox.showerror("Error", "Respuesta inesperada.")
                    self.lbl_estado.config(text="Prueba de servidor terminada")

                self.ventana.after(0, mostrar)

            import threading
            threading.Thread(target=trabajo, daemon=True).start()

        def generar_version_json():
            upd = AutoUpdater()
            from config_paths import get_version
            dlg = tk.Toplevel(self.ventana)
            dlg.title("Crear version.json")
            dlg.configure(bg="#ECEFF1")
            centrar_ventana(dlg, 480, 280)
            dlg.transient(self.ventana)
            dlg.grab_set()

            tk.Label(dlg, text="Crear version.json para subir al servidor",
                     bg="#ECEFF1", font=("Helvetica", 11, "bold")).pack(pady=10)
            campos = {}
            for label, key, default in (
                ("Version:", "version", get_version()),
                ("URL descarga EXE:", "download_url", "https://.../PINO_SYSTEM"),
                ("Changelog:", "changelog", "Mejoras y correcciones"),
                ("Checksum SHA256 (opcional):", "checksum", ""),
            ):
                fr = tk.Frame(dlg, bg="#ECEFF1")
                fr.pack(fill=tk.X, padx=16, pady=3)
                tk.Label(fr, text=label, bg="#ECEFF1", width=22,
                         anchor=tk.W, font=("Helvetica", 9)).pack(side=tk.LEFT)
                e = tk.Entry(fr, font=("Helvetica", 9))
                e.pack(side=tk.LEFT, fill=tk.X, expand=True)
                e.insert(0, default)
                campos[key] = e

            def crear():
                try:
                    path = upd.create_version_file(
                        campos["version"].get().strip(),
                        campos["download_url"].get().strip(),
                        campos["changelog"].get().strip(),
                        campos["checksum"].get().strip())
                    messagebox.showinfo("Creado",
                                        f"version.json en:\n{path}\n\n"
                                        "Subalo a su carpeta de actualizaciones.")
                    dlg.destroy()
                except Exception as e:
                    messagebox.showerror("Error", str(e))

            c = tk.Frame(dlg, bg="#2E7D32", padx=2, pady=2)
            c.pack(pady=12)
            tk.Button(c, text="CREAR version.json", command=crear,
                      bg="#F0F0F0", fg="#212121",
                      font=("Helvetica", 10, "bold"), relief=tk.FLAT).pack()

        for txt, color, cmd in (
            ("PROBAR SERVIDOR", "#0288D1", probar_servidor),
            ("CREAR version.json", "#6A1B9A", generar_version_json),
        ):
            c = tk.Frame(acc, bg=color, padx=2, pady=2)
            c.pack(side=tk.LEFT, padx=5)
            tk.Button(c, text=txt, bg="#F0F0F0", fg="#212121",
                      font=("Helvetica", 9, "bold"),
                      command=cmd, relief=tk.FLAT).pack()

        tk.Label(f,
                 text="Version actual de la app se lee de config.json.\n"
                      "Al subir version.json con version mayor, el sistema "
                      "ofrecera actualizarse al iniciar.",
                 bg="#ECEFF1", fg="#546E7A", font=("Helvetica", 9),
                 justify=tk.LEFT).pack(anchor=tk.W, padx=26, pady=10)

    def _map_server_type(self):
        server_type_map = {
            "GitHub (Recomendado)": "github",
            "Dropbox": "dropbox",
            "Google Drive": "gdrive",
            "Servidor HTTP/HTTPS": "http",
            "FTP": "ftp",
        }
        return server_type_map.get(self.combo_server_type.get(), "github")

    def guardar(self):
        errores = self._validar_todo()
        if errores:
            messagebox.showwarning("Validacion", "Corrija:\n- " + "\n- ".join(errores))
            return

        try:
            tc = float(self.entry_tc.get())
            actualizar_tipo_cambio(tc)
        except ValueError:
            messagebox.showwarning("Error", "Tipo de cambio invalido")
            return

        empresa = self.entries["entry_empresa"].get().strip()
        nit_emp = self.entries["entry_nit"].get().strip()
        tel = self.entries["entry_tel"].get().strip()
        direc = self.entries["entry_dir"].get().strip()
        email = self.entries["entry_email"].get().strip()
        web = self.entries["entry_web"].get().strip()
        moneda = self.var_moneda.get()

        try:
            iva = float(self.entry_iva.get())
            if iva < 0 or iva > 100:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Error", "IVA invalido (0-100)")
            return
        iva = max(0.0, min(100.0, iva))

        invoice_header = self.entry_invoice_header.get().strip()
        invoice_footer = self.entry_invoice_footer.get().strip()
        invoice_watermark = self.entry_invoice_watermark.get().strip()
        titulo_factura = self.entry_titulo_factura.get().strip()
        invoice_color = self.entry_invoice_color.get().strip()
        invoice_paper = self.var_paper.get()
        try:
            font_size = int(self.entry_font_size.get())
        except ValueError:
            font_size = 10
        try:
            margen = int(self.entry_margen.get())
        except ValueError:
            margen = 5
        logo_path = self.entry_logo.get().strip()

        update_url = self.entry_update_url.get().strip()
        auto_update = self.var_auto_update.get()
        update_type = self._map_server_type()

        ejecutar_consulta("""
            UPDATE configuracion SET
                tipo_cambio=?, nombre_empresa=?, nit=?, telefono=?,
                direccion=?, email=?, sitio_web=?, moneda_local=?, iva=?,
                logo_path=?, invoice_header=?, invoice_footer=?,
                invoice_watermark=?, show_nit=?, show_cliente=?,
                show_direccion=?, show_telefono=?, show_email=?,
                show_sitio_web=?, show_iva=?, show_tc=?,
                show_subtotal=?, show_descuento=?, invoice_color=?,
                invoice_font_size=?, invoice_paper_size=?, invoice_margen=?,
                show_numero_factura=?, show_fecha=?, show_vendedor=?,
                show_condicion_pago=?, show_titulo_factura=?,
                titulo_factura_text=?, show_codigo_producto=?,
                show_unidad_medida=?, show_precio_unitario=?,
                show_descuento_producto=?,
                fecha_actualizacion=datetime('now','localtime')
            WHERE id=1
        """, (tc, empresa, nit_emp, tel, direc, email, web, moneda, iva,
              logo_path, invoice_header, invoice_footer,
              invoice_watermark,
              int(self.check_vars["show_nit"].get()),
              int(self.check_vars["show_cliente"].get()),
              int(self.check_vars["show_direccion"].get()),
              int(self.check_vars["show_telefono"].get()),
              int(self.check_vars["show_email"].get()),
              int(self.check_vars["show_sitio_web"].get()),
              int(self.check_vars["show_iva"].get()),
              int(self.check_vars["show_tc"].get()),
              int(self.check_vars["show_subtotal"].get()),
              int(self.check_vars["show_descuento"].get()),
              invoice_color, font_size, invoice_paper, margen,
              int(self.check_vars["show_numero_factura"].get()),
              int(self.check_vars["show_fecha"].get()),
              int(self.check_vars["show_vendedor"].get()),
              int(self.check_vars["show_condicion_pago"].get()),
              int(self.check_vars["show_titulo_factura"].get()),
              titulo_factura,
              int(self.check_vars["show_codigo_producto"].get()),
              int(self.check_vars["show_unidad_medida"].get()),
              int(self.check_vars["show_precio_unitario"].get()),
              int(self.check_vars["show_descuento_producto"].get()),
        ))

        from config_paths import load_config, save_config
        cfg_app = load_config()
        cfg_app["update_url"] = update_url
        cfg_app["update_type"] = update_type
        cfg_app["auto_update"] = auto_update
        cfg_app["exchange_rate"] = tc
        cfg_app["iva_percent"] = iva
        cfg_app["currency"] = moneda
        cfg_app["company_name"] = empresa
        if hasattr(self, "var_tema"):
            cfg_app["theme"] = self.var_tema.get()
        if hasattr(self, "modulo_vars"):
            ocultos = self._modulos_ocultos_actuales()
            if "config" in ocultos:
                ocultos = [k for k in ocultos if k != "config"]
            cfg_app["hidden_modules"] = ocultos
        save_config(cfg_app)

        if update_url:
            from updater import AutoUpdater
            upd = AutoUpdater()
            upd.set_update_server(update_url, update_type)

        # Backup automatico al guardar
        try:
            import shutil
            from datetime import datetime as _dt
            from config_paths import get_db_path, get_datos_dir
            resp = os.path.join(get_datos_dir(), "respaldos",
                                f"backup_config_{_dt.now().strftime('%Y%m%d_%H%M%S')}.db")
            os.makedirs(os.path.dirname(resp), exist_ok=True)
            shutil.copy2(get_db_path(), resp)
        except Exception:
            pass

        self.cambios_pendientes = False
        tema_txt = ""
        if hasattr(self, "var_tema"):
            from themes import get_theme
            tema_txt = f"\nTema: {get_theme(self.var_tema.get())['label']}"
        try:
            ocultos_txt = ", ".join(self._modulos_ocultos_actuales()) or "ninguno"
        except Exception:
            ocultos_txt = "n/d"
        messagebox.showinfo(
            "Exito",
            "Configuracion guardada correctamente.\n"
            f"TC: CRC {tc:,.2f}/USD | IVA: {iva:g}% | Moneda: {moneda}{tema_txt}\n"
            f"Modulos ocultos en inicio: {ocultos_txt}")
        if self.callback:
            self.callback()
        self.ventana.destroy()


# ═══════════════════════════════════════════════════════════════
# MODULO: PRODUCTOS
# ═══════════════════════════════════════════════════════════════
class ProductosModulo:
    def __init__(self, parent):
        self.parent = parent
        self.ventana = tk.Toplevel(parent)
        self.ventana.title("PINO SYSTEM - Gestion de Productos")
        self.ventana.configure(bg="#ECEFF1")
        centrar_ventana(self.ventana, 1150, 650)
        self.ventana.transient(parent)
        self.ventana.grab_set()
        barra_navegacion(self.ventana, parent, actual="productos")

        self.tipo_cambio = obtener_tipo_cambio()
        self.crear_widgets()
        self.cargar_productos()

    def crear_widgets(self):
        header = tk.Frame(self.ventana, bg="#1565C0", height=50)
        header.pack(fill=tk.X)
        tk.Label(header, text="GESTION DE PRODUCTOS / MADERAS",
                 bg="#1565C0", fg="white",
                 font=("Helvetica", 15, "bold")).pack(pady=12)

        form_frame = tk.LabelFrame(self.ventana, text="Datos del Producto",
                                    bg="#ECEFF1", font=("Helvetica", 10, "bold"))
        form_frame.pack(fill=tk.X, padx=10, pady=5)

        fila1 = tk.Frame(form_frame, bg="#ECEFF1")
        fila1.pack(fill=tk.X, padx=5, pady=2)

        for lbl, attr, w in [("Codigo:", "entry_codigo", 12), ("Nombre:", "entry_nombre", 22),
                              ("Categoria:", None, 18), ("Unidad:", None, 10)]:
            tk.Label(fila1, text=lbl, bg="#ECEFF1", font=("Helvetica", 9)).pack(side=tk.LEFT, padx=3)
            if lbl == "Categoria:":
                self.combo_categoria = ttk.Combobox(fila1, width=w, state="readonly", font=("Helvetica", 9))
                self.combo_categoria.pack(side=tk.LEFT, padx=3)
            elif lbl == "Unidad:":
                self.combo_unidad = ttk.Combobox(fila1, width=w,
                    values=["pieza", "m2", "ml", "kg", "rollizo", "tablon", "paquete"],
                    state="readonly", font=("Helvetica", 9))
                self.combo_unidad.pack(side=tk.LEFT, padx=3)
                self.combo_unidad.set("pieza")
            else:
                e = tk.Entry(fila1, width=w, font=("Helvetica", 9))
                e.pack(side=tk.LEFT, padx=3)
                setattr(self, attr, e)

        fila2 = tk.Frame(form_frame, bg="#ECEFF1")
        fila2.pack(fill=tk.X, padx=5, pady=2)
        tk.Label(fila2, text="PRECIOS CRC:", bg="#C8E6C9", fg="#1B5E20",
                 font=("Helvetica", 9, "bold"), width=14, anchor=tk.W).pack(side=tk.LEFT, padx=3)

        for lbl, attr, w in [("Compra CRC:", "entry_pcompra", 12), ("Venta CRC:", "entry_pventa", 12),
                              ("Stock Min:", "entry_stock_min", 8)]:
            tk.Label(fila2, text=lbl, bg="#ECEFF1", font=("Helvetica", 9)).pack(side=tk.LEFT, padx=3)
            e = tk.Entry(fila2, width=w, font=("Helvetica", 9))
            e.pack(side=tk.LEFT, padx=3)
            setattr(self, attr, e)

        fila3 = tk.Frame(form_frame, bg="#ECEFF1")
        fila3.pack(fill=tk.X, padx=5, pady=2)
        tk.Label(fila3, text="PRECIOS USD:", bg="#BBDEFB", fg="#0D47A1",
                 font=("Helvetica", 9, "bold"), width=14, anchor=tk.W).pack(side=tk.LEFT, padx=3)

        for lbl, attr, w in [("Compra USD:", "entry_pcompra_usd", 12), ("Venta USD:", "entry_pventa_usd", 12)]:
            tk.Label(fila3, text=lbl, bg="#ECEFF1", font=("Helvetica", 9)).pack(side=tk.LEFT, padx=3)
            e = tk.Entry(fila3, width=w, font=("Helvetica", 9))
            e.pack(side=tk.LEFT, padx=3)
            setattr(self, attr, e)

        tk.Label(fila3, text=f"(TC: {self.tipo_cambio})", bg="#ECEFF1",
                 font=("Helvetica", 8), fg="#666").pack(side=tk.LEFT, padx=3)
        tk.Label(fila3, text="Descripcion:", bg="#ECEFF1", font=("Helvetica", 9)).pack(side=tk.LEFT, padx=(10, 3))
        self.entry_descripcion = tk.Entry(fila3, width=18, font=("Helvetica", 9))
        self.entry_descripcion.pack(side=tk.LEFT, padx=3)

        btn_frame = tk.Frame(form_frame, bg="#ECEFF1")
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        for txt, color, cmd in [("GUARDAR", "#2E7D32", self.guardar_producto),
                                 ("MODIFICAR", "#1565C0", self.modificar_producto),
                                 ("ELIMINAR", "#C62828", self.eliminar_producto),
                                 ("LIMPIAR", "#78909C", self.limpiar_campos)]:
            cont = tk.Frame(btn_frame, bg=color, padx=2, pady=2)
            cont.pack(side=tk.LEFT, padx=3)
            tk.Button(cont, text=txt, bg="#F0F0F0", fg="#212121",
                      font=("Helvetica", 9, "bold"), width=12,
                      command=cmd, relief=tk.FLAT).pack()

        busca_frame = tk.Frame(self.ventana, bg="#ECEFF1")
        busca_frame.pack(fill=tk.X, padx=10, pady=2)
        tk.Label(busca_frame, text="Buscar:", bg="#ECEFF1",
                 font=("Helvetica", 10, "bold")).pack(side=tk.LEFT, padx=5)
        self.entry_buscar = tk.Entry(busca_frame, width=30, font=("Helvetica", 10))
        self.entry_buscar.pack(side=tk.LEFT, padx=5)
        _debounce(self.entry_buscar, 250, self.buscar_producto)
        btn_exp = tk.Frame(busca_frame, bg="#455A64", padx=2, pady=2)
        btn_exp.pack(side=tk.RIGHT, padx=5)
        tk.Button(btn_exp, text="Excel", bg="#F0F0F0", fg="#212121",
                  font=("Helvetica", 9, "bold"), command=self.exportar_excel,
                  relief=tk.FLAT).pack(side=tk.LEFT, padx=1)
        tk.Button(btn_exp, text="CSV", bg="#F0F0F0", fg="#212121",
                  font=("Helvetica", 9), command=self.exportar, relief=tk.FLAT).pack(side=tk.LEFT)

        columnas = ("id", "codigo", "nombre", "categoria", "unidad", "pcompra_crc",
                    "pventa_crc", "pcompra_usd", "pventa_usd", "stock", "descripcion")
        encabezados = ("ID", "Codigo", "Nombre", "Categoria", "Unid.", "Compra CRC",
                       "Venta CRC", "Compra USD", "Venta USD", "Stock", "Descripcion")
        ancho_cols = (35, 70, 150, 120, 55, 80, 80, 80, 80, 65, 120)

        self.tree = crear_treeview(self.ventana, columnas, encabezados, ancho_cols, 250)
        self.tree.bind("<<TreeviewSelect>>", self.seleccionar_producto)
        self.cargar_categorias()

    def cargar_categorias(self):
        cats = ejecutar_select("SELECT id, nombre FROM categorias ORDER BY nombre")
        self.categorias = {c["nombre"]: c["id"] for c in cats}
        self.combo_categoria["values"] = list(self.categorias.keys())
        if self.combo_categoria["values"]:
            self.combo_categoria.current(0)

    def cargar_productos(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        productos = ejecutar_select("""
            SELECT p.id, p.codigo, p.nombre, c.nombre as categoria, p.unidad_medida,
                   p.precio_compra, p.precio_venta, p.precio_compra_usd, p.precio_venta_usd,
                   p.stock_minimo, p.descripcion,
                   COALESCE((
                       SELECT k.saldo_cantidad FROM kardex k
                       WHERE k.producto_id = p.id
                       ORDER BY k.id DESC LIMIT 1
                   ), 0) AS stock
            FROM productos p LEFT JOIN categorias c ON p.categoria_id = c.id
            WHERE p.activo = 1 ORDER BY p.nombre""")
        filas = [(
            p["id"], p["codigo"], p["nombre"], p["categoria"] or "N/A",
            p["unidad_medida"], formatear_numero(p["precio_compra"]),
            formatear_numero(p["precio_venta"]),
            formatear_dolares(p["precio_compra_usd"]),
            formatear_dolares(p["precio_venta_usd"]),
            formatear_numero(p["stock"]), p["descripcion"] or "") for p in productos]
        _llenar_tree(self.tree, filas)

    def _stock(self, pid):
        r = ejecutar_select_one("SELECT saldo_cantidad FROM kardex WHERE producto_id=? ORDER BY id DESC LIMIT 1", (pid,))
        return r["saldo_cantidad"] if r else 0

    def seleccionar_producto(self, event):
        sel = self.tree.selection()
        if not sel: return
        vals = self.tree.item(sel[0])["values"]
        self.limpiar_campos()
        self.entry_codigo.insert(0, vals[1])
        self.entry_nombre.insert(0, vals[2])
        if vals[3] and vals[3] in self.categorias:
            self.combo_categoria.set(vals[3])
        elif self.combo_categoria["values"]:
            self.combo_categoria.current(-1)
            self.combo_categoria.set("")
        self.combo_unidad.set(vals[4])
        self.entry_pcompra.insert(0, str(vals[5]).replace(",", ""))
        self.entry_pventa.insert(0, str(vals[6]).replace(",", ""))
        self.entry_pcompra_usd.insert(0, str(vals[7]).replace("$", "").replace(",", ""))
        self.entry_pventa_usd.insert(0, str(vals[8]).replace("$", "").replace(",", ""))
        sm = ejecutar_select_one("SELECT stock_minimo FROM productos WHERE id=?", (vals[0],))
        stock_minimo = sm["stock_minimo"] if sm else 0
        self.entry_stock_min.insert(0, str(stock_minimo).replace(",", ""))
        self.entry_descripcion.insert(0, vals[10])
        self.producto_id = vals[0]

    def limpiar_campos(self):
        for w in [self.entry_codigo, self.entry_nombre, self.entry_pcompra,
                  self.entry_pventa, self.entry_pcompra_usd, self.entry_pventa_usd,
                  self.entry_stock_min, self.entry_descripcion]:
            w.delete(0, tk.END)
        if self.combo_categoria["values"]:
            self.combo_categoria.current(0)
        else:
            self.combo_categoria.set("")
        self.combo_unidad.set("pieza")
        self.producto_id = None

    def guardar_producto(self):
        codigo = self.entry_codigo.get().strip()
        nombre = self.entry_nombre.get().strip()
        if not codigo or not nombre:
            messagebox.showwarning("Validacion", "Codigo y Nombre son obligatorios.")
            return
        cat_id = self.categorias.get(self.combo_categoria.get())
        try:
            pc = float(self.entry_pcompra.get() or 0)
            pv = float(self.entry_pventa.get() or 0)
            pcu = float(self.entry_pcompra_usd.get() or 0)
            pvu = float(self.entry_pventa_usd.get() or 0)
            stock_min = float(self.entry_stock_min.get() or 0)
        except ValueError:
            messagebox.showwarning("Validacion",
                                   "Los precios y stock minimo deben ser numeros validos.")
            return
        if pcu == 0 and pc > 0: pcu = convertir_a_dolares(pc, self.tipo_cambio)
        if pvu == 0 and pv > 0: pvu = convertir_a_dolares(pv, self.tipo_cambio)
        if pc == 0 and pcu > 0: pc = convertir_a_colones(pcu, self.tipo_cambio)
        if pv == 0 and pvu > 0: pv = convertir_a_colones(pvu, self.tipo_cambio)
        try:
            ejecutar_consulta("""
                INSERT INTO productos (codigo, nombre, descripcion, unidad_medida, categoria_id,
                    precio_compra, precio_venta, precio_compra_usd, precio_venta_usd, stock_minimo)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (codigo, nombre, self.entry_descripcion.get().strip(),
                  self.combo_unidad.get(), cat_id, pc, pv, pcu, pvu, stock_min))
            messagebox.showinfo("Exito", "Producto registrado correctamente.")
            self.limpiar_campos()
            self.cargar_productos()
        except Exception as e:
            messagebox.showerror("Error", f"Error al guardar:\n{e}")

    def modificar_producto(self):
        if not hasattr(self, "producto_id") or not self.producto_id:
            messagebox.showwarning("Validacion", "Seleccione un producto.")
            return
        cat_id = self.categorias.get(self.combo_categoria.get())
        try:
            pc = float(self.entry_pcompra.get() or 0)
            pv = float(self.entry_pventa.get() or 0)
            pcu = float(self.entry_pcompra_usd.get() or 0)
            pvu = float(self.entry_pventa_usd.get() or 0)
            stock_min = float(self.entry_stock_min.get() or 0)
        except ValueError:
            messagebox.showwarning("Validacion",
                                   "Los precios y stock minimo deben ser numeros validos.")
            return
        if pcu == 0 and pc > 0: pcu = convertir_a_dolares(pc, self.tipo_cambio)
        if pvu == 0 and pv > 0: pvu = convertir_a_dolares(pv, self.tipo_cambio)
        if pc == 0 and pcu > 0: pc = convertir_a_colones(pcu, self.tipo_cambio)
        if pv == 0 and pvu > 0: pv = convertir_a_colones(pvu, self.tipo_cambio)
        try:
            ejecutar_consulta("""
                UPDATE productos SET codigo=?, nombre=?, descripcion=?, unidad_medida=?,
                    categoria_id=?, precio_compra=?, precio_venta=?,
                    precio_compra_usd=?, precio_venta_usd=?, stock_minimo=?
                WHERE id=?
            """, (self.entry_codigo.get().strip(), self.entry_nombre.get().strip(),
                  self.entry_descripcion.get().strip(), self.combo_unidad.get(),
                  cat_id, pc, pv, pcu, pvu, stock_min, self.producto_id))
            messagebox.showinfo("Exito", "Producto modificado.")
            self.limpiar_campos()
            self.cargar_productos()
        except Exception as e:
            messagebox.showerror("Error", f"Error:\n{e}")

    def eliminar_producto(self):
        if not hasattr(self, "producto_id") or not self.producto_id:
            messagebox.showwarning("Validacion", "Seleccione un producto.")
            return
        if messagebox.askyesno("Confirmar", "Desactivar este producto?"):
            ejecutar_consulta("UPDATE productos SET activo = 0 WHERE id = ?", (self.producto_id,))
            self.limpiar_campos()
            self.cargar_productos()

    def buscar_producto(self):
        texto = self.entry_buscar.get().strip().lower()
        param = f"%{texto}%"
        productos = ejecutar_select("""
            SELECT p.id, p.codigo, p.nombre, c.nombre as categoria, p.unidad_medida,
                   p.precio_compra, p.precio_venta, p.precio_compra_usd, p.precio_venta_usd,
                   p.stock_minimo, p.descripcion,
                   COALESCE((
                       SELECT k.saldo_cantidad FROM kardex k
                       WHERE k.producto_id = p.id
                       ORDER BY k.id DESC LIMIT 1
                   ), 0) AS stock
            FROM productos p LEFT JOIN categorias c ON p.categoria_id = c.id
            WHERE p.activo = 1 AND (LOWER(p.nombre) LIKE ? OR LOWER(p.codigo) LIKE ?
                   OR LOWER(c.nombre) LIKE ?) ORDER BY p.nombre""", (param, param, param))
        filas = [(
            p["id"], p["codigo"], p["nombre"], p["categoria"] or "N/A",
            p["unidad_medida"], formatear_numero(p["precio_compra"]),
            formatear_numero(p["precio_venta"]),
            formatear_dolares(p["precio_compra_usd"]),
            formatear_dolares(p["precio_venta_usd"]),
            formatear_numero(p["stock"]), p["descripcion"] or "") for p in productos]
        _llenar_tree(self.tree, filas)

    def exportar(self):
        archivo = filedialog.asksaveasfilename(defaultextension=".csv",
            filetypes=[("CSV", "*.csv")], initialfile="productos.csv")
        if archivo:
            exportar_a_csv(self.tree, archivo)

    def exportar_excel(self):
        archivo = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")],
            initialfile="inventario_productos.xlsx")
        if not archivo:
            return
        ok, msg = tree_a_excel(
            self.tree, archivo,
            titulo="INVENTARIO DE PRODUCTOS / MADERAS",
            hoja="Inventario")
        if ok:
            messagebox.showinfo("Excel", f"Exportado correctamente:\n{msg}")
        else:
            messagebox.showerror("Excel", f"No se pudo exportar:\n{msg}")


# ═══════════════════════════════════════════════════════════════
# MODULO: KARDEX
# ═══════════════════════════════════════════════════════════════
class KardexModulo:
    def __init__(self, parent):
        self.parent = parent
        self.ventana = tk.Toplevel(parent)
        self.ventana.title("PINO SYSTEM - Kardex de Inventario")
        self.ventana.configure(bg="#ECEFF1")
        centrar_ventana(self.ventana, 1200, 700)
        self.ventana.transient(parent)
        self.ventana.grab_set()
        barra_navegacion(self.ventana, parent, actual="kardex")
        self.tipo_cambio = obtener_tipo_cambio()
        self.crear_widgets()
        self.cargar_kardex()

    def crear_widgets(self):
        header = tk.Frame(self.ventana, bg="#C62828", height=50)
        header.pack(fill=tk.X)
        tk.Label(header, text="KARDEX - CONTROL DE INVENTARIO",
                 bg="#C62828", fg="white",
                 font=("Helvetica", 15, "bold")).pack(pady=12)

        form = tk.LabelFrame(self.ventana, text="Registrar Movimiento",
                              bg="#ECEFF1", font=("Helvetica", 10, "bold"))
        form.pack(fill=tk.X, padx=10, pady=5)

        fila1 = tk.Frame(form, bg="#ECEFF1")
        fila1.pack(fill=tk.X, padx=5, pady=3)

        tk.Label(fila1, text="Tipo:", bg="#ECEFF1", font=("Helvetica", 9)).pack(side=tk.LEFT, padx=3)
        self.combo_tipo = ttk.Combobox(fila1, values=["ENTRADA", "SALIDA"], width=10,
                                        state="readonly", font=("Helvetica", 9))
        self.combo_tipo.pack(side=tk.LEFT, padx=3)
        self.combo_tipo.set("ENTRADA")

        tk.Label(fila1, text="Producto:", bg="#ECEFF1", font=("Helvetica", 9)).pack(side=tk.LEFT, padx=3)
        self.combo_producto = ttk.Combobox(fila1, width=28, state="readonly", font=("Helvetica", 9))
        self.combo_producto.pack(side=tk.LEFT, padx=3)

        tk.Label(fila1, text="Cant:", bg="#ECEFF1", font=("Helvetica", 9)).pack(side=tk.LEFT, padx=3)
        self.entry_cantidad = tk.Entry(fila1, width=7, font=("Helvetica", 9))
        self.entry_cantidad.pack(side=tk.LEFT, padx=3)

        tk.Label(fila1, text="P.Unit CRC:", bg="#C8E6C9", fg="#1B5E20",
                 font=("Helvetica", 9, "bold")).pack(side=tk.LEFT, padx=3)
        self.entry_punitario = tk.Entry(fila1, width=10, font=("Helvetica", 9))
        self.entry_punitario.pack(side=tk.LEFT, padx=3)

        tk.Label(fila1, text="P.Unit USD:", bg="#BBDEFB", fg="#0D47A1",
                 font=("Helvetica", 9, "bold")).pack(side=tk.LEFT, padx=3)
        self.entry_punitario_usd = tk.Entry(fila1, width=10, font=("Helvetica", 9))
        self.entry_punitario_usd.pack(side=tk.LEFT, padx=3)

        tk.Label(fila1, text=f"TC:{self.tipo_cambio}", bg="#ECEFF1",
                 font=("Helvetica", 8), fg="#666").pack(side=tk.LEFT, padx=3)

        fila2 = tk.Frame(form, bg="#ECEFF1")
        fila2.pack(fill=tk.X, padx=5, pady=3)
        for lbl, attr, w in [("Doc.Ref:", "entry_docref", 15), ("Prov/Cliente:", "entry_prov_cli", 25),
                              ("Descripcion:", "entry_desc", 28)]:
            tk.Label(fila2, text=lbl, bg="#ECEFF1", font=("Helvetica", 9)).pack(side=tk.LEFT, padx=3)
            e = tk.Entry(fila2, width=w, font=("Helvetica", 9))
            e.pack(side=tk.LEFT, padx=3)
            setattr(self, attr, e)

        btn_frame = tk.Frame(form, bg="#ECEFF1")
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        for txt, color, cmd in [("REGISTRAR ENTRADA", "#2E7D32", self.registrar_entrada),
                                 ("REGISTRAR SALIDA", "#C62828", self.registrar_salida),
                                 ("LIMPIAR", "#78909C", self.limpiar)]:
            cont = tk.Frame(btn_frame, bg=color, padx=2, pady=2)
            cont.pack(side=tk.LEFT, padx=3)
            tk.Button(cont, text=txt, bg="#F0F0F0", fg="#212121",
                      font=("Helvetica", 9, "bold"), width=18,
                      command=cmd, relief=tk.FLAT).pack()

        filtro = tk.Frame(self.ventana, bg="#ECEFF1")
        filtro.pack(fill=tk.X, padx=10, pady=2)
        tk.Label(filtro, text="Filtrar:", bg="#ECEFF1",
                 font=("Helvetica", 10, "bold")).pack(side=tk.LEFT, padx=5)
        self.combo_filtro = ttk.Combobox(filtro, width=28, state="readonly", font=("Helvetica", 9))
        self.combo_filtro.pack(side=tk.LEFT, padx=5)
        self.combo_filtro.bind("<<ComboboxSelected>>", lambda e: self.cargar_kardex())

        columnas = ("id", "fecha", "tipo", "producto", "cantidad", "p_unit_crc",
                    "p_unit_usd", "total_crc", "total_usd", "saldo_cant",
                    "saldo_crc", "saldo_usd", "doc_ref")
        encabezados = ("ID", "Fecha", "Tipo", "Producto", "Cant.", "P.Unit CRC",
                       "P.Unit USD", "Total CRC", "Total USD", "Saldo C.",
                       "Saldo CRC", "Saldo USD", "Doc.Ref")
        ancho_cols = (35, 120, 60, 130, 55, 75, 75, 85, 85, 60, 85, 85, 80)

        self.tree = crear_treeview(self.ventana, columnas, encabezados, ancho_cols, 280)
        self.cargar_productos_combo()

    def cargar_productos_combo(self):
        productos = ejecutar_select(
            "SELECT id, codigo, nombre FROM productos WHERE activo = 1 ORDER BY nombre")
        self.lista_productos = {f"{p['codigo']} - {p['nombre']}": p["id"] for p in productos}
        valores = list(self.lista_productos.keys())
        self.combo_producto["values"] = valores
        self.combo_filtro["values"] = ["TODOS"] + valores
        if valores:
            self.combo_producto.current(0)
            self.combo_filtro.current(0)

    def _saldo(self, pid):
        r = ejecutar_select_one(
            "SELECT saldo_cantidad, saldo_valor, saldo_valor_usd FROM kardex WHERE producto_id=? ORDER BY id DESC LIMIT 1",
            (pid,))
        if r: return r["saldo_cantidad"], r["saldo_valor"], r.get("saldo_valor_usd", 0)
        return 0, 0, 0

    def registrar_entrada(self): self._registrar("ENTRADA")
    def registrar_salida(self): self._registrar("SALIDA")

    def _registrar(self, tipo):
        prod_text = self.combo_producto.get()
        if not prod_text:
            messagebox.showwarning("Validacion", "Seleccione un producto.")
            return
        try: cantidad = float(self.entry_cantidad.get())
        except ValueError:
            messagebox.showwarning("Validacion", "Cantidad numerica requerida.")
            return

        pc = 0; pu = 0
        try: pc = float(self.entry_punitario.get() or 0)
        except: pass
        try: pu = float(self.entry_punitario_usd.get() or 0)
        except: pass
        if pc > 0 and pu == 0: pu = convertir_a_dolares(pc, self.tipo_cambio)
        elif pu > 0 and pc == 0: pc = convertir_a_colones(pu, self.tipo_cambio)
        if cantidad <= 0:
            messagebox.showwarning("Validacion", "Cantidad invalida.")
            return

        pid = self.lista_productos[prod_text]
        tc = cantidad * pc
        tu = cantidad * pu
        sc, sv, svu = self._saldo(pid)

        if tipo == "SALIDA":
            if sc < cantidad:
                messagebox.showerror("Error", f"Stock insuficiente. Disponible: {sc}")
                return
            nsc, nsv, nsvu = sc - cantidad, sv - tc, svu - tu
        else:
            nsc, nsv, nsvu = sc + cantidad, sv + tc, svu + tu

        try:
            ejecutar_consulta("""
                INSERT INTO kardex (producto_id, tipo_movimiento, cantidad,
                    precio_unitario, precio_unitario_usd, total, total_usd,
                    saldo_cantidad, saldo_valor, saldo_valor_usd,
                    documento_ref, proveedor_cliente, descripcion)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (pid, tipo, cantidad, pc, pu, tc, tu, nsc, nsv, nsvu,
                  self.entry_docref.get().strip(), self.entry_prov_cli.get().strip(),
                  self.entry_desc.get().strip()))
            messagebox.showinfo("Exito", f"{tipo} registrada. Saldo: {nsc} uds")
            self.limpiar()
            self.cargar_kardex()
        except Exception as e:
            messagebox.showerror("Error", f"Error:\n{e}")

    def limpiar(self):
        for w in [self.entry_cantidad, self.entry_punitario, self.entry_punitario_usd,
                  self.entry_docref, self.entry_prov_cli, self.entry_desc]:
            w.delete(0, tk.END)

    def cargar_kardex(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        filtro = self.combo_filtro.get()
        if filtro and filtro != "TODOS":
            pid = self.lista_productos.get(filtro)
            movs = ejecutar_select("SELECT k.*, p.nombre as pn FROM kardex k JOIN productos p ON k.producto_id=p.id WHERE k.producto_id=? ORDER BY k.id", (pid,))
        else:
            movs = ejecutar_select("SELECT k.*, p.nombre as pn FROM kardex k JOIN productos p ON k.producto_id=p.id ORDER BY k.id")
        for m in movs:
            self.tree.insert("", "end", values=(
                m["id"], m["fecha"][:16], m["tipo_movimiento"], m["pn"],
                formatear_numero(m["cantidad"]), formatear_numero(m["precio_unitario"]),
                formatear_dolares(m.get("precio_unitario_usd", 0)),
                formatear_numero(m["total"]), formatear_dolares(m.get("total_usd", 0)),
                formatear_numero(m["saldo_cantidad"]), formatear_numero(m["saldo_valor"]),
                formatear_dolares(m.get("saldo_valor_usd", 0)), m["documento_ref"] or ""))


# ═══════════════════════════════════════════════════════════════
# MODULO: FACTURACION
# ═══════════════════════════════════════════════════════════════
class FacturacionModulo:
    def __init__(self, parent):
        self.parent = parent
        self.ventana = tk.Toplevel(parent)
        self.ventana.title("PINO SYSTEM - Facturacion")
        self.ventana.configure(bg="#ECEFF1")
        centrar_ventana(self.ventana, 1150, 720)
        self.ventana.transient(parent)
        self.ventana.grab_set()
        barra_navegacion(self.ventana, parent, actual="facturacion")
        self.tipo_cambio = obtener_tipo_cambio()
        self.items_factura = []
        self.crear_widgets()
        self.nueva_factura()

    def crear_widgets(self):
        header = tk.Frame(self.ventana, bg="#0D47A1", height=50)
        header.pack(fill=tk.X)
        tk.Label(header, text="FACTURACION",
                 bg="#0D47A1", fg="white",
                 font=("Helvetica", 15, "bold")).pack(pady=12)

        datos_frame = tk.Frame(self.ventana, bg="#ECEFF1")
        datos_frame.pack(fill=tk.X, padx=10, pady=5)
        for lbl, attr, w in [("N Factura:", "entry_num_factura", 15), ("Fecha:", None, 12)]:
            tk.Label(datos_frame, text=lbl, bg="#ECEFF1", font=("Helvetica", 10, "bold")).pack(side=tk.LEFT, padx=3)
            if lbl == "Fecha:":
                self.entry_fecha = tk.Entry(datos_frame, width=w, font=("Helvetica", 10))
                self.entry_fecha.pack(side=tk.LEFT, padx=3)
                self.entry_fecha.insert(0, fecha_solo())
                self.entry_fecha.config(state="readonly")
            else:
                e = tk.Entry(datos_frame, width=w, font=("Helvetica", 10))
                e.pack(side=tk.LEFT, padx=3)
                setattr(self, attr, e)

        tk.Label(datos_frame, text="Moneda:", bg="#ECEFF1",
                 font=("Helvetica", 10, "bold")).pack(side=tk.LEFT, padx=(15, 3))
        self.combo_moneda = ttk.Combobox(datos_frame, values=["CRC Colones", "USD Dolares"],
                                          width=15, state="readonly", font=("Helvetica", 10))
        self.combo_moneda.pack(side=tk.LEFT, padx=3)
        self.combo_moneda.set("CRC Colones")

        tk.Label(datos_frame, text="Cliente:", bg="#ECEFF1",
                 font=("Helvetica", 10, "bold")).pack(side=tk.LEFT, padx=3)
        self.combo_cliente = ttk.Combobox(datos_frame, width=22, state="readonly",
                                          font=("Helvetica", 10))
        self.combo_cliente.pack(side=tk.LEFT, padx=3)

        cont_nuevo = tk.Frame(datos_frame, bg="#2E7D32", padx=2, pady=2)
        cont_nuevo.pack(side=tk.LEFT, padx=3)
        tk.Button(cont_nuevo, text="+ Nuevo", bg="#F0F0F0", fg="#212121",
                  font=("Helvetica", 8), command=self.nuevo_cliente, relief=tk.FLAT).pack()

        add_frame = tk.LabelFrame(self.ventana, text="Agregar Producto",
                                   bg="#ECEFF1", font=("Helvetica", 10, "bold"))
        add_frame.pack(fill=tk.X, padx=10, pady=3)

        fila = tk.Frame(add_frame, bg="#ECEFF1")
        fila.pack(fill=tk.X, padx=5, pady=3)
        tk.Label(fila, text="Producto:", bg="#ECEFF1", font=("Helvetica", 9)).pack(side=tk.LEFT, padx=3)
        self.combo_producto = ttk.Combobox(fila, width=28, state="readonly", font=("Helvetica", 9))
        self.combo_producto.pack(side=tk.LEFT, padx=3)
        tk.Label(fila, text="Cant:", bg="#ECEFF1", font=("Helvetica", 9)).pack(side=tk.LEFT, padx=3)
        self.entry_cant = tk.Entry(fila, width=7, font=("Helvetica", 9))
        self.entry_cant.pack(side=tk.LEFT, padx=3)
        tk.Label(fila, text="P.Unit CRC:", bg="#C8E6C9", fg="#1B5E20",
                 font=("Helvetica", 9, "bold")).pack(side=tk.LEFT, padx=3)
        self.entry_punit_crc = tk.Entry(fila, width=10, font=("Helvetica", 9))
        self.entry_punit_crc.pack(side=tk.LEFT, padx=3)
        tk.Label(fila, text="P.Unit USD:", bg="#BBDEFB", fg="#0D47A1",
                 font=("Helvetica", 9, "bold")).pack(side=tk.LEFT, padx=3)
        self.entry_punit_usd = tk.Entry(fila, width=10, font=("Helvetica", 9))
        self.entry_punit_usd.pack(side=tk.LEFT, padx=3)

        cont_agr = tk.Frame(fila, bg="#2E7D32", padx=2, pady=2)
        cont_agr.pack(side=tk.LEFT, padx=5)
        tk.Button(cont_agr, text="AGREGAR", bg="#F0F0F0", fg="#212121",
                  font=("Helvetica", 9, "bold"), command=self.agregar_item, relief=tk.FLAT).pack()
        cont_qui = tk.Frame(fila, bg="#C62828", padx=2, pady=2)
        cont_qui.pack(side=tk.LEFT, padx=3)
        tk.Button(cont_qui, text="QUITAR", bg="#F0F0F0", fg="#212121",
                  font=("Helvetica", 9, "bold"), command=self.quitar_item, relief=tk.FLAT).pack()

        columnas = ("idx", "producto", "cantidad", "p_unit_crc", "p_unit_usd",
                    "subtotal_crc", "subtotal_usd")
        encabezados = ("#", "Producto", "Cant.", "P.Unit CRC", "P.Unit USD",
                       "Subtotal CRC", "Subtotal USD")
        self.tree = crear_treeview(self.ventana, columnas, encabezados, (35, 250, 60, 90, 90, 100, 100), 220)

        totales_frame = tk.Frame(self.ventana, bg="#BBDEFB", relief=tk.SUNKEN, bd=1)
        totales_frame.pack(fill=tk.X, padx=10, pady=5)
        self.lbl_subtotal_crc = tk.Label(totales_frame, text="Subtotal CRC: 0", bg="#BBDEFB",
                                          font=("Helvetica", 10, "bold"))
        self.lbl_subtotal_crc.pack(side=tk.LEFT, padx=10)
        self.lbl_impuesto_crc = tk.Label(totales_frame, text="IVA CRC: 0", bg="#BBDEFB",
                                          font=("Helvetica", 10, "bold"))
        self.lbl_impuesto_crc.pack(side=tk.LEFT, padx=10)
        self.lbl_subtotal_usd = tk.Label(totales_frame, text="Subtotal USD: 0", bg="#BBDEFB",
                                          font=("Helvetica", 10, "bold"), fg="#0D47A1")
        self.lbl_subtotal_usd.pack(side=tk.LEFT, padx=10)
        self.lbl_impuesto_usd = tk.Label(totales_frame, text="IVA USD: 0", bg="#BBDEFB",
                                          font=("Helvetica", 10, "bold"), fg="#0D47A1")
        self.lbl_impuesto_usd.pack(side=tk.LEFT, padx=10)
        self.lbl_total = tk.Label(totales_frame, text="TOTAL: 0", bg="#BBDEFB", fg="#C62828",
                                   font=("Helvetica", 14, "bold"))
        self.lbl_total.pack(side=tk.RIGHT, padx=15)

        obs_frame = tk.Frame(self.ventana, bg="#ECEFF1")
        obs_frame.pack(fill=tk.X, padx=10, pady=3)
        tk.Label(obs_frame, text="Obs:", bg="#ECEFF1", font=("Helvetica", 9, "bold")).pack(side=tk.LEFT)
        self.entry_obs = tk.Entry(obs_frame, width=60, font=("Helvetica", 9))
        self.entry_obs.pack(side=tk.LEFT, padx=5)

        btn_frame = tk.Frame(self.ventana, bg="#ECEFF1")
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        for txt, color, cmd in [("GUARDAR FACTURA", "#0D47A1", self.guardar_factura),
                                 ("IMPRIMIR", "#455A64", self.imprimir_factura),
                                 ("NUEVA FACTURA", "#2E7D32", self.nueva_factura),
                                 ("VER FACTURAS", "#1565C0", self.ver_facturas)]:
            cont = tk.Frame(btn_frame, bg=color, padx=2, pady=2)
            cont.pack(side=tk.LEFT, padx=3)
            tk.Button(cont, text=txt, bg="#F0F0F0", fg="#212121",
                      font=("Helvetica", 10, "bold"), width=16,
                      command=cmd, relief=tk.FLAT).pack()

        self.cargar_productos()
        self.cargar_clientes()

    def cargar_productos(self):
        productos = ejecutar_select(
            "SELECT id, codigo, nombre, precio_venta, precio_venta_usd FROM productos WHERE activo=1 ORDER BY nombre")
        self.lista = {}; self.pcrc = {}; self.pusd = {}
        for p in productos:
            k = f"{p['codigo']} - {p['nombre']}"
            self.lista[k] = p["id"]; self.pcrc[k] = p["precio_venta"]; self.pusd[k] = p["precio_venta_usd"]
        self.combo_producto["values"] = list(self.lista.keys())
        self.combo_producto.bind("<<ComboboxSelected>>", self.sel_producto)
        if self.lista:
            self.combo_producto.current(0)
            self.sel_producto()
        else:
            self.combo_producto.set("")
            self.entry_punit_crc.delete(0, tk.END)
            self.entry_punit_usd.delete(0, tk.END)

    def sel_producto(self, e=None):
        p = self.combo_producto.get()
        if p in self.pcrc:
            self.entry_punit_crc.delete(0, tk.END); self.entry_punit_crc.insert(0, str(self.pcrc[p]))
            self.entry_punit_usd.delete(0, tk.END); self.entry_punit_usd.insert(0, str(self.pusd[p]))

    def cargar_clientes(self):
        clientes = ejecutar_select("SELECT id, nombre FROM clientes WHERE activo=1 ORDER BY nombre")
        self.lista_clientes = {c["nombre"]: c["id"] for c in clientes}
        self.combo_cliente["values"] = list(self.lista_clientes.keys())

    def nuevo_cliente(self):
        VentanaNuevoCliente(self.ventana, self.cargar_clientes)

    def nueva_factura(self):
        self.items_factura = []
        self.entry_num_factura.delete(0, tk.END)
        ultima = ejecutar_select_one("SELECT numero FROM facturas ORDER BY id DESC LIMIT 1")
        if ultima:
            try: num = int(ultima["numero"].replace("FAC-", "")) + 1
            except: num = 1
        else: num = 1
        self.entry_num_factura.insert(0, f"FAC-{num:06d}")
        self.entry_fecha.config(state="normal")
        self.entry_fecha.delete(0, tk.END); self.entry_fecha.insert(0, fecha_solo())
        self.entry_fecha.config(state="readonly")
        self.entry_obs.delete(0, tk.END); self.combo_cliente.set("")
        self.combo_moneda.set("CRC Colones")
        for item in self.tree.get_children(): self.tree.delete(item)
        self.actualizar_totales()

    def agregar_item(self):
        prod_text = self.combo_producto.get()
        if not prod_text:
            messagebox.showwarning("Aviso", "Seleccione un producto.")
            return
        try: cant = float(self.entry_cant.get())
        except: messagebox.showwarning("Aviso", "Cantidad numerica."); return
        pc = pu = 0
        try: pc = float(self.entry_punit_crc.get() or 0)
        except: pass
        try: pu = float(self.entry_punit_usd.get() or 0)
        except: pass
        if pc > 0 and pu == 0: pu = convertir_a_dolares(pc, self.tipo_cambio)
        elif pu > 0 and pc == 0: pc = convertir_a_colones(pu, self.tipo_cambio)
        if cant <= 0: return
        pid = self.lista[prod_text]
        stock = self._stock(pid)
        total_pid = sum(i["cant"] for i in self.items_factura if i["pid"] == pid)
        if stock < total_pid + cant:
            messagebox.showerror(
                "Error",
                f"Stock insuficiente. Disponible: {stock}, ya en factura: {total_pid}")
            return
        sub_crc = cant * pc; sub_usd = cant * pu
        nombre = prod_text.split(" - ", 1)[1] if " - " in prod_text else prod_text
        self.items_factura.append({"pid": pid, "nombre": nombre, "cant": cant,
                                    "pc": pc, "pu": pu, "sub_crc": sub_crc, "sub_usd": sub_usd})
        idx = len(self.items_factura)
        self.tree.insert("", "end", values=(idx, nombre, formatear_numero(cant),
            formatear_numero(pc), formatear_dolares(pu),
            formatear_numero(sub_crc), formatear_dolares(sub_usd)))
        self.entry_cant.delete(0, tk.END)
        self.actualizar_totales()

    def quitar_item(self):
        sel = self.tree.selection()
        if not sel: return
        idx = int(self.tree.item(sel[0])["values"][0]) - 1
        if 0 <= idx < len(self.items_factura):
            self.items_factura.pop(idx)
            self.tree.delete(sel[0])
            self._reordenar()
            self.actualizar_totales()

    def _reordenar(self):
        for item in self.tree.get_children(): self.tree.delete(item)
        for i, it in enumerate(self.items_factura):
            self.tree.insert("", "end", values=(i+1, it["nombre"], formatear_numero(it["cant"]),
                formatear_numero(it["pc"]), formatear_dolares(it["pu"]),
                formatear_numero(it["sub_crc"]), formatear_dolares(it["sub_usd"])))

    def actualizar_totales(self):
        sc = sum(i["sub_crc"] for i in self.items_factura)
        su = sum(i["sub_usd"] for i in self.items_factura)
        iva_rate = obtener_iva_rate()
        iva_pct = obtener_iva_pct()
        ic = sc * iva_rate; iu = su * iva_rate
        self.lbl_subtotal_crc.config(text=f"Subtotal CRC: CRC {formatear_numero(sc)}")
        self.lbl_impuesto_crc.config(text=f"IVA {iva_pct:g}% CRC: CRC {formatear_numero(ic)}")
        self.lbl_subtotal_usd.config(text=f"Subtotal USD: USD {formatear_dolares(su)}")
        self.lbl_impuesto_usd.config(text=f"IVA {iva_pct:g}% USD: USD {formatear_dolares(iu)}")
        if "Dolares" in self.combo_moneda.get():
            self.lbl_total.config(text=f"TOTAL: USD {formatear_dolares(su + iu)}")
        else:
            self.lbl_total.config(text=f"TOTAL: CRC {formatear_numero(sc + ic)}")

    def _stock(self, pid):
        r = ejecutar_select_one("SELECT saldo_cantidad FROM kardex WHERE producto_id=? ORDER BY id DESC LIMIT 1", (pid,))
        return r["saldo_cantidad"] if r else 0

    def guardar_factura(self):
        if not self.items_factura:
            messagebox.showwarning("Aviso", "No hay items.")
            return
        cn = self.combo_cliente.get()
        cid = self.lista_clientes.get(cn) if cn else None
        if cn and not cid:
            messagebox.showwarning("Aviso", "Seleccione un cliente valido de la lista.")
            return
        sc = sum(i["sub_crc"] for i in self.items_factura)
        su = sum(i["sub_usd"] for i in self.items_factura)
        iva_rate = obtener_iva_rate()
        ic = sc * iva_rate; iu = su * iva_rate
        numero = self.entry_num_factura.get()
        moneda = "USD" if "Dolares" in self.combo_moneda.get() else "CRC"

        try:
            fid = ejecutar_consulta("""
                INSERT INTO facturas (numero, cliente_id, moneda, subtotal, subtotal_usd,
                    impuesto, impuesto_usd, total, total_usd, tipo_cambio, observaciones)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (numero, cid, moneda, sc, su, ic, iu, sc+ic, su+iu,
                  self.tipo_cambio, self.entry_obs.get().strip()))

            for it in self.items_factura:
                ejecutar_consulta("""
                    INSERT INTO detalle_factura (factura_id, producto_id, cantidad,
                        precio_unitario, precio_unitario_usd, total, total_usd)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (fid, it["pid"], it["cant"], it["pc"], it["pu"], it["sub_crc"], it["sub_usd"]))
                sa = self._stock(it["pid"])
                ns = sa - it["cant"]
                ejecutar_consulta("""
                    INSERT INTO kardex (producto_id, tipo_movimiento, cantidad,
                        precio_unitario, precio_unitario_usd, total, total_usd,
                        saldo_cantidad, saldo_valor, saldo_valor_usd,
                        documento_ref, proveedor_cliente, descripcion)
                    VALUES (?, 'SALIDA', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (it["pid"], it["cant"], it["pc"], it["pu"], it["sub_crc"], it["sub_usd"],
                      ns, ns*it["pc"], ns*it["pu"], numero, cn or "CONSUMIDOR FINAL",
                      f"Salida por {numero}"))

            messagebox.showinfo("Exito", f"Factura {numero} guardada.")
            self.nueva_factura()
        except Exception as e:
            messagebox.showerror("Error", f"Error:\n{e}")

    def imprimir_factura(self):
        if not self.items_factura:
            messagebox.showwarning("Aviso", "No hay items.")
            return
        win = tk.Toplevel(self.ventana)
        win.title("Vista Previa")
        centrar_ventana(win, 520, 580)
        text = tk.Text(win, font=("Courier", 10), bg="white", wrap=tk.WORD)
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        sc = sum(i["sub_crc"] for i in self.items_factura)
        su = sum(i["sub_usd"] for i in self.items_factura)
        iva_rate = obtener_iva_rate()
        iva_pct = obtener_iva_pct()
        ic = sc * iva_rate; iu = su * iva_rate
        lineas = ["="*55, "       PINO SYSTEM - FACTURA DE VENTA", "="*55,
                  f"  Factura: {self.entry_num_factura.get()}",
                  f"  Fecha:   {self.entry_fecha.get()}",
                  f"  Cliente: {self.combo_cliente.get() or 'CONSUMIDOR FINAL'}",
                  "-"*55, f"  {'Producto':<22} {'Cant':>5} {'P.Unit':>10} {'Total':>10}", "-"*55]
        for it in self.items_factura:
            lineas.append(f"  {it['nombre'][:22]:<22} {it['cant']:>5.1f} {it['pc']:>10.2f} {it['sub_crc']:>10.2f}")
        lineas += ["-"*55,
                  f"  {'Subtotal CRC:':<35} {sc:>10.2f}",
                  f"  {'IVA {iva_pct:g}% CRC:':<35} {ic:>10.2f}",
                  f"  {'TOTAL CRC:':<35} {sc+ic:>10.2f}", "",
                  f"  {'Subtotal USD:':<35} USD {su:>9.2f}",
                  f"  {'IVA {iva_pct:g}% USD:':<35} USD {iu:>9.2f}",
                  f"  {'TOTAL USD:':<35} USD {su+iu:>9.2f}",
                  "="*55, "  Gracias por su compra!", "="*55]
        text.insert(tk.END, "\n".join(lineas))
        text.config(state=tk.DISABLED)

    def ver_facturas(self):
        VerFacturas(self.ventana)


class VentanaNuevoCliente:
    def __init__(self, parent, callback=None):
        self.callback = callback
        self.ventana = tk.Toplevel(parent)
        self.ventana.title("Nuevo Cliente")
        centrar_ventana(self.ventana, 400, 300)
        self.ventana.transient(parent)
        self.ventana.grab_set()
        tk.Label(self.ventana, text="Registrar Nuevo Cliente",
                 font=("Helvetica", 12, "bold")).pack(pady=10)
        form = tk.Frame(self.ventana)
        form.pack(padx=20, pady=5, fill=tk.X)
        for texto, attr in [("NIT:", "entry_nit"), ("Nombre:", "entry_nombre"),
                             ("Direccion:", "entry_dir"), ("Telefono:", "entry_tel"),
                             ("Email:", "entry_email")]:
            f = tk.Frame(form); f.pack(fill=tk.X, pady=2)
            tk.Label(f, text=texto, width=12, anchor=tk.W).pack(side=tk.LEFT)
            e = tk.Entry(f, width=30); e.pack(side=tk.LEFT, fill=tk.X, expand=True)
            setattr(self, attr, e)
        cont = tk.Frame(self.ventana, bg="#2E7D32", padx=2, pady=2)
        cont.pack(pady=10)
        tk.Button(cont, text="Guardar", bg="#F0F0F0", fg="#212121",
                  font=("Helvetica", 10, "bold"), command=self.guardar, relief=tk.FLAT).pack()

    def guardar(self):
        n = self.entry_nombre.get().strip()
        if not n:
            messagebox.showwarning("Aviso", "Nombre obligatorio.")
            return
        ejecutar_consulta("INSERT INTO clientes (nit,nombre,direccion,telefono,email) VALUES (?,?,?,?,?)",
            (self.entry_nit.get().strip(), n, self.entry_dir.get().strip(),
             self.entry_tel.get().strip(), self.entry_email.get().strip()))
        messagebox.showinfo("Exito", "Cliente registrado.")
        if self.callback: self.callback()
        self.ventana.destroy()


class VerFacturas:
    def __init__(self, parent):
        self.ventana = tk.Toplevel(parent)
        self.ventana.title("Facturas Emitidas")
        centrar_ventana(self.ventana, 900, 450)
        self.ventana.transient(parent)
        tk.Label(self.ventana, text="Facturas Emitidas",
                 font=("Helvetica", 14, "bold"), bg="#0D47A1", fg="white").pack(fill=tk.X)
        columnas = ("numero", "fecha", "cliente", "moneda", "subtotal", "subtotal_usd",
                    "impuesto", "impuesto_usd", "total", "total_usd", "estado")
        encabezados = ("N Factura", "Fecha", "Cliente", "Mon", "Sub CRC", "Sub USD",
                       "IVA CRC", "IVA USD", "Total CRC", "Total USD", "Estado")
        self.tree = crear_treeview(self.ventana, columnas, encabezados,
            (90, 120, 150, 45, 85, 85, 70, 70, 85, 85, 60), 350)
        facturas = ejecutar_select("""
            SELECT f.numero, f.fecha, COALESCE(c.nombre,'CONSUMIDOR FINAL') as cliente,
                   f.moneda, f.subtotal, f.subtotal_usd, f.impuesto, f.impuesto_usd,
                   f.total, f.total_usd, f.estado
            FROM facturas f LEFT JOIN clientes c ON f.cliente_id=c.id ORDER BY f.id DESC""")
        for f in facturas:
            self.tree.insert("", "end", values=(
                f["numero"], f["fecha"][:16], f["cliente"], f["moneda"],
                formatear_numero(f["subtotal"]), formatear_dolares(f["subtotal_usd"]),
                formatear_numero(f["impuesto"]), formatear_dolares(f["impuesto_usd"]),
                formatear_numero(f["total"]), formatear_dolares(f["total_usd"]), f["estado"]))


# ═══════════════════════════════════════════════════════════════
# MODULO: CLIENTES Y PROVEEDORES
# ═══════════════════════════════════════════════════════════════
class ClientesModulo:
    def __init__(self, parent, tipo="clientes"):
        self.tipo = tipo
        self.parent = parent
        self.ventana = tk.Toplevel(parent)
        titulo = "Clientes" if tipo == "clientes" else "Proveedores"
        self.ventana.title(f"PINO SYSTEM - {titulo}")
        self.ventana.configure(bg="#ECEFF1")
        centrar_ventana(self.ventana, 850, 520)
        self.ventana.transient(parent)
        self.ventana.grab_set()
        barra_navegacion(self.ventana, parent, actual="clientes")
        self.crear_widgets()
        self.cargar_datos()

    def crear_widgets(self):
        color = "#0D47A1" if self.tipo == "clientes" else "#6A1B9A"
        titulo = "CLIENTES" if self.tipo == "clientes" else "PROVEEDORES"
        header = tk.Frame(self.ventana, bg=color, height=50)
        header.pack(fill=tk.X)
        tk.Label(header, text=f"GESTION DE {titulo}", bg=color, fg="white",
                 font=("Helvetica", 15, "bold")).pack(pady=12)

        form = tk.LabelFrame(self.ventana, text=f"Datos", bg="#ECEFF1",
                              font=("Helvetica", 10, "bold"))
        form.pack(fill=tk.X, padx=10, pady=5)

        fila1 = tk.Frame(form, bg="#ECEFF1"); fila1.pack(fill=tk.X, padx=5, pady=3)
        for lbl, attr, w in [("NIT:", "entry_nit", 15), ("Nombre:", "entry_nombre", 30),
                              ("Telefono:", "entry_tel", 15)]:
            tk.Label(fila1, text=lbl, bg="#ECEFF1", font=("Helvetica", 9)).pack(side=tk.LEFT, padx=3)
            e = tk.Entry(fila1, width=w, font=("Helvetica", 9)); e.pack(side=tk.LEFT, padx=3)
            setattr(self, attr, e)

        fila2 = tk.Frame(form, bg="#ECEFF1"); fila2.pack(fill=tk.X, padx=5, pady=3)
        for lbl, attr, w in [("Direccion:", "entry_dir", 30), ("Email:", "entry_email", 25)]:
            tk.Label(fila2, text=lbl, bg="#ECEFF1", font=("Helvetica", 9)).pack(side=tk.LEFT, padx=3)
            e = tk.Entry(fila2, width=w, font=("Helvetica", 9)); e.pack(side=tk.LEFT, padx=3)
            setattr(self, attr, e)
        if self.tipo == "proveedores":
            tk.Label(fila2, text="Contacto:", bg="#ECEFF1", font=("Helvetica", 9)).pack(side=tk.LEFT, padx=3)
            self.entry_contacto = tk.Entry(fila2, width=20, font=("Helvetica", 9))
            self.entry_contacto.pack(side=tk.LEFT, padx=3)

        btn_frame = tk.Frame(form, bg="#ECEFF1"); btn_frame.pack(fill=tk.X, padx=5, pady=5)
        for txt, color, cmd in [("GUARDAR", "#2E7D32", self.guardar),
                                 ("MODIFICAR", "#1565C0", self.modificar),
                                 ("ELIMINAR", "#C62828", self.eliminar),
                                 ("LIMPIAR", "#78909C", self.limpiar)]:
            cont = tk.Frame(btn_frame, bg=color, padx=2, pady=2)
            cont.pack(side=tk.LEFT, padx=3)
            tk.Button(cont, text=txt, bg="#F0F0F0", fg="#212121",
                      font=("Helvetica", 9, "bold"), width=12,
                      command=cmd, relief=tk.FLAT).pack()

        if self.tipo == "clientes":
            columnas = ("id", "nit", "nombre", "direccion", "telefono", "email")
            encabezados = ("ID", "NIT", "Nombre", "Direccion", "Telefono", "Email")
        else:
            columnas = ("id", "nit", "nombre", "direccion", "telefono", "email", "contacto")
            encabezados = ("ID", "NIT", "Nombre", "Direccion", "Telefono", "Email", "Contacto")
        self.tree = crear_treeview(self.ventana, columnas, encabezados,
            (40, 100, 180, 180, 100, 150) if self.tipo == "clientes" else (40, 100, 180, 180, 100, 150, 120), 200)
        self.tree.bind("<<TreeviewSelect>>", self.seleccionar)

    def cargar_datos(self):
        for item in self.tree.get_children(): self.tree.delete(item)
        tabla = "clientes" if self.tipo == "clientes" else "proveedores"
        datos = ejecutar_select(f"SELECT * FROM {tabla} WHERE activo=1 ORDER BY nombre")
        for d in datos:
            if self.tipo == "clientes":
                self.tree.insert("", "end", values=(d["id"], d["nit"] or "", d["nombre"],
                    d["direccion"] or "", d["telefono"] or "", d["email"] or ""))
            else:
                self.tree.insert("", "end", values=(d["id"], d["nit"] or "", d["nombre"],
                    d["direccion"] or "", d["telefono"] or "", d["email"] or "", d.get("contacto","") or ""))

    def seleccionar(self, event):
        sel = self.tree.selection()
        if not sel: return
        vals = self.tree.item(sel[0])["values"]
        self.limpiar()
        self.entry_nit.insert(0, vals[1]); self.entry_nombre.insert(0, vals[2])
        self.entry_dir.insert(0, vals[3]); self.entry_tel.insert(0, vals[4])
        self.entry_email.insert(0, vals[5])
        if self.tipo == "proveedores" and len(vals) > 6:
            self.entry_contacto.insert(0, vals[6])
        self.id_sel = vals[0]

    def limpiar(self):
        for w in [self.entry_nit, self.entry_nombre, self.entry_dir,
                  self.entry_tel, self.entry_email]: w.delete(0, tk.END)
        if self.tipo == "proveedores": self.entry_contacto.delete(0, tk.END)
        self.id_sel = None

    def guardar(self):
        n = self.entry_nombre.get().strip()
        if not n:
            messagebox.showwarning("Aviso", "Nombre obligatorio.")
            return
        tabla = "clientes" if self.tipo == "clientes" else "proveedores"
        try:
            if self.tipo == "clientes":
                ejecutar_consulta(f"INSERT INTO {tabla} (nit,nombre,direccion,telefono,email) VALUES (?,?,?,?,?)",
                    (self.entry_nit.get().strip(), n, self.entry_dir.get().strip(),
                     self.entry_tel.get().strip(), self.entry_email.get().strip()))
            else:
                ejecutar_consulta(f"INSERT INTO {tabla} (nit,nombre,direccion,telefono,email,contacto) VALUES (?,?,?,?,?,?)",
                    (self.entry_nit.get().strip(), n, self.entry_dir.get().strip(),
                     self.entry_tel.get().strip(), self.entry_email.get().strip(),
                     self.entry_contacto.get().strip()))
            messagebox.showinfo("Exito", "Registro guardado.")
            self.limpiar(); self.cargar_datos()
        except Exception as e:
            messagebox.showerror("Error", f"Error:\n{e}")

    def modificar(self):
        if not hasattr(self, "id_sel") or not self.id_sel:
            messagebox.showwarning("Aviso", "Seleccione un registro.")
            return
        tabla = "clientes" if self.tipo == "clientes" else "proveedores"
        try:
            if self.tipo == "clientes":
                ejecutar_consulta(f"UPDATE {tabla} SET nit=?,nombre=?,direccion=?,telefono=?,email=? WHERE id=?",
                    (self.entry_nit.get().strip(), self.entry_nombre.get().strip(),
                     self.entry_dir.get().strip(), self.entry_tel.get().strip(),
                     self.entry_email.get().strip(), self.id_sel))
            else:
                ejecutar_consulta(f"UPDATE {tabla} SET nit=?,nombre=?,direccion=?,telefono=?,email=?,contacto=? WHERE id=?",
                    (self.entry_nit.get().strip(), self.entry_nombre.get().strip(),
                     self.entry_dir.get().strip(), self.entry_tel.get().strip(),
                     self.entry_email.get().strip(), self.entry_contacto.get().strip(), self.id_sel))
            messagebox.showinfo("Exito", "Registro modificado.")
            self.limpiar(); self.cargar_datos()
        except Exception as e:
            messagebox.showerror("Error", f"Error:\n{e}")

    def eliminar(self):
        if not hasattr(self, "id_sel") or not self.id_sel:
            messagebox.showwarning("Aviso", "Seleccione un registro.")
            return
        if messagebox.askyesno("Confirmar", "Desactivar registro?"):
            tabla = "clientes" if self.tipo == "clientes" else "proveedores"
            ejecutar_consulta(f"UPDATE {tabla} SET activo=0 WHERE id=?", (self.id_sel,))
            self.limpiar(); self.cargar_datos()


# ═══════════════════════════════════════════════════════════════
# MODULO: REPORTES
# ═══════════════════════════════════════════════════════════════
class ReportesModulo:
    def __init__(self, parent):
        self.parent = parent
        self.ventana = tk.Toplevel(parent)
        self.ventana.title("PINO SYSTEM - Reportes")
        self.ventana.configure(bg="#ECEFF1")
        centrar_ventana(self.ventana, 1000, 620)
        self.ventana.transient(parent)
        self.ventana.grab_set()
        barra_navegacion(self.ventana, parent, actual="reportes")
        self.tc = obtener_tipo_cambio()
        self.crear_widgets()

    def crear_widgets(self):
        header = tk.Frame(self.ventana, bg="#E65100", height=50)
        header.pack(fill=tk.X)
        tk.Label(header, text="REPORTES E INFORMES",
                 bg="#E65100", fg="white",
                 font=("Helvetica", 15, "bold")).pack(pady=12)

        btn_frame = tk.Frame(self.ventana, bg="#ECEFF1")
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        for txt, color, cmd in [("Inventario Actual", "#2E7D32", self.r_inventario),
                                 ("Stock Bajo Minimo", "#C62828", self.r_bajo),
                                 ("Kardex General", "#1565C0", self.r_kardex),
                                 ("Ventas Periodo", "#6A1B9A", self.r_ventas),
                                 ("Mov. Proveedores", "#00695C", self.r_proveedores),
                                 ("Analisis Costos", "#37474F", self.r_costos)]:
            cont = tk.Frame(btn_frame, bg=color, padx=2, pady=2)
            cont.pack(side=tk.LEFT, padx=4, pady=5)
            tk.Button(cont, text=txt, bg="#F0F0F0", fg="#212121",
                      font=("Helvetica", 9, "bold"), width=18, height=2,
                      command=cmd, relief=tk.FLAT).pack()

        self.text_res = tk.Text(self.ventana, font=("Courier", 9), bg="white", wrap=tk.WORD)
        self.text_res.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Pie: exportar el reporte actual a Excel / CSV
        pie = tk.Frame(self.ventana, bg="#ECEFF1")
        pie.pack(fill=tk.X, padx=10, pady=(0, 8))
        self.lbl_reporte_actual = tk.Label(
            pie, text="Genere un reporte y luego exportelo a Excel",
            bg="#ECEFF1", fg="#546E7A", font=("Helvetica", 9))
        self.lbl_reporte_actual.pack(side=tk.LEFT, padx=4)

        c_exp = tk.Frame(pie, bg="#2E7D32", padx=2, pady=2)
        c_exp.pack(side=tk.RIGHT, padx=4)
        tk.Button(c_exp, text="DESCARGAR EXCEL", bg="#F0F0F0", fg="#212121",
                  font=("Helvetica", 9, "bold"), command=self.exportar_excel_actual,
                  relief=tk.FLAT).pack()

        c_csv = tk.Frame(pie, bg="#1565C0", padx=2, pady=2)
        c_csv.pack(side=tk.RIGHT, padx=4)
        tk.Button(c_csv, text="CSV", bg="#F0F0F0", fg="#212121",
                  font=("Helvetica", 9), command=self.exportar_csv_actual,
                  relief=tk.FLAT).pack()

        self._excel_headers = []
        self._excel_rows = []
        self._excel_nombre = "reporte"
        self._excel_titulo = "REPORTE"

    def _set_excel_data(self, headers, rows, nombre, titulo):
        self._excel_headers = headers
        self._excel_rows = rows
        self._excel_nombre = nombre
        self._excel_titulo = titulo
        self.lbl_reporte_actual.config(
            text=f"Reporte listo: {titulo} ({len(rows)} filas)")

    def exportar_excel_actual(self):
        if not self._excel_headers or not self._excel_rows:
            messagebox.showinfo("Excel", "Primero genere un reporte.")
            return
        archivo = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")],
            initialfile=f"{self._excel_nombre}.xlsx")
        if not archivo:
            return
        ok, msg = exportar_excel(
            archivo, self._excel_headers, self._excel_rows,
            titulo=self._excel_titulo, hoja=self._excel_nombre[:31])
        if ok:
            messagebox.showinfo("Excel", f"Descargado correctamente:\n{msg}")
        else:
            messagebox.showerror("Excel", f"No se pudo exportar:\n{msg}")

    def exportar_csv_actual(self):
        if not self._excel_headers or not self._excel_rows:
            messagebox.showinfo("CSV", "Primero genere un reporte.")
            return
        archivo = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile=f"{self._excel_nombre}.csv")
        if not archivo:
            return
        try:
            import csv
            with open(archivo, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow(self._excel_headers)
                w.writerows(self._excel_rows)
            messagebox.showinfo("CSV", f"Exportado:\n{archivo}")
        except Exception as e:
            messagebox.showerror("CSV", str(e))

    def _limpiar(self):
        self.text_res.config(state=tk.NORMAL)
        self.text_res.delete("1.0", tk.END)

    def _stock(self, cod):
        r = ejecutar_select_one(
            "SELECT k.saldo_cantidad FROM kardex k JOIN productos p ON k.producto_id=p.id WHERE p.codigo=? ORDER BY k.id DESC LIMIT 1",
            (cod,))
        return r["saldo_cantidad"] if r else 0

    def r_inventario(self):
        self._limpiar()
        prods = ejecutar_select("""
            SELECT p.codigo, p.nombre, c.nombre as cat, p.unidad_medida,
                   p.precio_compra, p.precio_venta, p.precio_venta_usd
            FROM productos p LEFT JOIN categorias c ON p.categoria_id=c.id
            WHERE p.activo=1 ORDER BY p.nombre""")
        l = ["="*95, "                    REPORTE DE INVENTARIO ACTUAL",
             f"                    Fecha: {fecha_actual()} | TC: CRC {self.tc}", "="*95,
             f"{'Codigo':<8} {'Nombre':<22} {'Categoria':<16} {'Stock':>7} {'P.Compra':>12} {'P.Venta':>12} {'P.Venta $':>10}",
             "-"*95]
        headers = ["Codigo", "Nombre", "Categoria", "Unidad", "Stock",
                   "Precio Compra CRC", "Precio Venta CRC", "Precio Venta USD"]
        rows = []
        for p in prods:
            s = self._stock(p["codigo"])
            l.append(f"{p['codigo']:<8} {p['nombre'][:22]:<22} {(p['cat'] or 'N/A')[:16]:<16} {s:>7.1f} {p['precio_compra']:>12,.2f} {p['precio_venta']:>12,.2f} USD {p['precio_venta_usd']:>8.2f}")
            rows.append([
                p["codigo"], p["nombre"], p["cat"] or "N/A",
                p["unidad_medida"] or "", s,
                p["precio_compra"] or 0, p["precio_venta"] or 0,
                p["precio_venta_usd"] or 0,
            ])
        l += ["-"*95, f"Total: {len(prods)}", "="*95]
        self.text_res.insert(tk.END, "\n".join(l)); self.text_res.config(state=tk.DISABLED)
        self._set_excel_data(headers, rows, "inventario_actual", "INVENTARIO ACTUAL")

    def r_bajo(self):
        self._limpiar()
        prods = ejecutar_select("SELECT p.codigo, p.nombre, p.unidad_medida, p.stock_minimo FROM productos p WHERE p.activo=1 ORDER BY p.nombre")
        l = ["="*80, "              PRODUCTOS CON STOCK BAJO EL MINIMO",
             f"              Fecha: {fecha_actual()}", "="*80,
             f"{'Codigo':<10} {'Nombre':<25} {'Unidad':<8} {'Minimo':>10} {'Actual':>10} {'Estado':>10}", "-"*80]
        headers = ["Codigo", "Nombre", "Unidad", "Stock Minimo", "Stock Actual", "Estado"]
        rows = []
        c = 0
        for p in prods:
            s = self._stock(p["codigo"])
            if s < p["stock_minimo"]:
                c += 1
                estado = "CRITICO" if s == 0 else "BAJO"
                l.append(f"{p['codigo']:<10} {p['nombre'][:25]:<25} {p['unidad_medida']:<8} {p['stock_minimo']:>10.1f} {s:>10.1f} {estado:>10}")
                rows.append([p["codigo"], p["nombre"], p["unidad_medida"],
                             p["stock_minimo"] or 0, s, estado])
        l += ["-"*80, f"Total bajo minimo: {c}", "="*80]
        self.text_res.insert(tk.END, "\n".join(l)); self.text_res.config(state=tk.DISABLED)
        self._set_excel_data(headers, rows, "stock_bajo", "STOCK BAJO MINIMO")

    def r_kardex(self):
        self._limpiar()
        movs = ejecutar_select("SELECT k.fecha, k.tipo_movimiento, p.codigo, p.nombre, k.cantidad, k.precio_unitario, k.total, k.saldo_cantidad, k.saldo_valor, k.saldo_valor_usd FROM kardex k JOIN productos p ON k.producto_id=p.id ORDER BY k.id")
        l = ["="*100, f"                    REPORTE KARDEX | TC: CRC {self.tc}",
             f"                    Fecha: {fecha_actual()}", "="*100,
             f"{'Fecha':<14} {'Tipo':<7} {'Producto':<18} {'Cant':>6} {'P.U':>10} {'Total':>12} {'Saldo C':>7} {'Saldo V':>12} {'Saldo USD':>10}", "-"*100]
        headers = ["Fecha", "Tipo", "Codigo", "Producto", "Cantidad",
                   "Precio Unit.", "Total", "Saldo Cant.", "Saldo Valor CRC", "Saldo Valor USD"]
        rows = []
        for m in movs:
            l.append(f"{m['fecha'][:13]:<14} {m['tipo_movimiento']:<7} {m['nombre'][:18]:<18} {m['cantidad']:>6.1f} {m['precio_unitario']:>10.2f} {m['total']:>12.2f} {m['saldo_cantidad']:>7.1f} {m['saldo_valor']:>12.2f} USD {m['saldo_valor_usd']:>8.2f}")
            rows.append([
                m["fecha"], m["tipo_movimiento"], m["codigo"], m["nombre"],
                m["cantidad"], m["precio_unitario"], m["total"],
                m["saldo_cantidad"], m["saldo_valor"], m["saldo_valor_usd"] or 0,
            ])
        l += ["="*100, f"Total: {len(movs)}"]
        self.text_res.insert(tk.END, "\n".join(l)); self.text_res.config(state=tk.DISABLED)
        self._set_excel_data(headers, rows, "kardex_general", "KARDEX GENERAL")

    def r_ventas(self):
        self._limpiar()
        facts = ejecutar_select("SELECT f.numero, f.fecha, COALESCE(c.nombre,'CF') as cliente, f.moneda, f.subtotal, f.subtotal_usd, f.total, f.total_usd FROM facturas f LEFT JOIN clientes c ON f.cliente_id=c.id ORDER BY f.id DESC")
        l = ["="*95, f"                    REPORTE DE VENTAS | TC: CRC {self.tc}",
             f"                    Fecha: {fecha_actual()}", "="*95,
             f"{'N Factura':<13} {'Fecha':<14} {'Cliente':<22} {'Mon':>4} {'Sub CRC':>12} {'Sub USD':>10} {'Total CRC':>12} {'Total USD':>10}", "-"*95]
        headers = ["N Factura", "Fecha", "Cliente", "Moneda",
                   "Subtotal CRC", "Subtotal USD", "Total CRC", "Total USD"]
        rows = []
        tc = tu = 0
        for f in facts:
            l.append(f"{f['numero']:<13} {f['fecha'][:13]:<14} {f['cliente'][:22]:<22} {f['moneda']:>4} {f['subtotal']:>12,.2f} USD {f['subtotal_usd']:>8.2f} {f['total']:>12,.2f} USD {f['total_usd']:>8.2f}")
            tc += f["total"]; tu += f["total_usd"]
            rows.append([
                f["numero"], f["fecha"], f["cliente"], f["moneda"],
                f["subtotal"] or 0, f["subtotal_usd"] or 0,
                f["total"] or 0, f["total_usd"] or 0,
            ])
        l += ["-"*95, f"Total: {len(facts)} | CRC {tc:,.2f} | USD {tu:,.2f}", "="*95]
        self.text_res.insert(tk.END, "\n".join(l)); self.text_res.config(state=tk.DISABLED)
        self._set_excel_data(headers, rows, "ventas_periodo", "REPORTE DE VENTAS")

    def r_proveedores(self):
        self._limpiar()
        movs = ejecutar_select("SELECT proveedor_cliente, tipo_movimiento, SUM(cantidad) as ct, SUM(total) as tc, SUM(total_usd) as tu FROM kardex WHERE proveedor_cliente IS NOT NULL AND proveedor_cliente!='' GROUP BY proveedor_cliente, tipo_movimiento ORDER BY proveedor_cliente")
        l = ["="*75, f"           MOVIMIENTOS POR PROVEEDOR/CLIENTE",
             f"           Fecha: {fecha_actual()} | TC: CRC {self.tc}", "="*75,
             f"{'Proveedor/Cliente':<28} {'Tipo':<8} {'Cant.':>8} {'Total CRC':>14} {'Total USD':>12}", "-"*75]
        headers = ["Proveedor/Cliente", "Tipo", "Cantidad", "Total CRC", "Total USD"]
        rows = []
        for m in movs:
            l.append(f"{m['proveedor_cliente'][:28]:<28} {m['tipo_movimiento']:<8} {m['ct']:>8.1f} {m['tc']:>14,.2f} USD {m['tu']:>11.2f}")
            rows.append([m["proveedor_cliente"], m["tipo_movimiento"],
                         m["ct"], m["tc"], m["tu"]])
        l.append("="*75)
        self.text_res.insert(tk.END, "\n".join(l)); self.text_res.config(state=tk.DISABLED)
        self._set_excel_data(headers, rows, "mov_proveedores", "MOVIMIENTOS PROVEEDORES")

    def r_costos(self):
        self._limpiar()
        from database import obtener_reporte_costos
        reporte = obtener_reporte_costos()

        l = ["="*110, "                    ANALISIS DE COSTOS POR PRODUCTO",
             f"                    Fecha: {fecha_actual()} | TC: CRC {self.tc}", "="*110,
             f"{'Codigo':<8} {'Nombre':<20} {'C.Compra':>10} {'C.Promedio':>11} {'C.Ultimo':>10} {'P.Venta':>10} {'Margen%':>8} {'Margen$':>10}",
             "-"*110]
        headers = ["Codigo", "Nombre", "Precio Compra", "Costo Promedio",
                   "Costo Ultimo", "Precio Venta", "Margen % CRC", "Margen % USD"]
        rows = []

        for r in reporte:
            l.append(f"{r['codigo']:<8} {r['nombre'][:20]:<20} {r['precio_compra']:>10,.2f} {r['costo_promedio_crc']:>11,.2f} {r['costo_ultimo_crc']:>10,.2f} {r['precio_venta']:>10,.2f} {r['margen_crc']:>7.1f}% {r['margen_usd']:>9.1f}%")
            rows.append([
                r["codigo"], r["nombre"], r["precio_compra"],
                r["costo_promedio_crc"], r["costo_ultimo_crc"],
                r["precio_venta"], r["margen_crc"], r["margen_usd"],
            ])

        l += ["-"*110, f"Total: {len(reporte)} productos analizados", "="*110]
        l.append("\nleyenda:")
        l.append("  C.Compra   = Precio de compra registrado")
        l.append("  C.Promedio = Costo promedio ponderado de todas las entradas")
        l.append("  C.Ultimo   = Ultimo precio de compra registrado")
        l.append("  Margen%    = ((Venta - Costo) / Costo) * 100")

        self.text_res.insert(tk.END, "\n".join(l)); self.text_res.config(state=tk.DISABLED)
        self._set_excel_data(headers, rows, "analisis_costos", "ANALISIS DE COSTOS")


# ═══════════════════════════════════════════════════════════════
# MODULO: CONTABILIDAD BASICA (INGRESOS / GASTOS)
# ═══════════════════════════════════════════════════════════════
class ContabilidadModulo:
    def __init__(self, parent):
        self.parent = parent
        self.ventana = tk.Toplevel(parent)
        self.ventana.title("PINO SYSTEM - Contabilidad")
        self.ventana.configure(bg="#ECEFF1")
        centrar_ventana(self.ventana, 1100, 650)
        self.ventana.transient(parent)
        self.ventana.grab_set()
        self.tc = obtener_tipo_cambio()
        self.crear_widgets()
        self.cargar_movimientos()

    def crear_widgets(self):
        header = tk.Frame(self.ventana, bg="#00695C", height=50)
        header.pack(fill=tk.X)
        tk.Label(header, text="CONTABILIDAD - INGRESOS Y GASTOS",
                 bg="#00695C", fg="white",
                 font=("Helvetica", 15, "bold")).pack(pady=12)

        form_frame = tk.LabelFrame(self.ventana, text="Registrar Movimiento",
                                    bg="#ECEFF1", font=("Helvetica", 10, "bold"))
        form_frame.pack(fill=tk.X, padx=10, pady=5)

        fila1 = tk.Frame(form_frame, bg="#ECEFF1")
        fila1.pack(fill=tk.X, padx=5, pady=2)

        tk.Label(fila1, text="Tipo:", bg="#ECEFF1", font=("Helvetica", 9)).pack(side=tk.LEFT, padx=3)
        self.combo_tipo = ttk.Combobox(fila1, values=["INGRESO", "GASTO"], width=10,
                                        state="readonly", font=("Helvetica", 9))
        self.combo_tipo.pack(side=tk.LEFT, padx=3)
        self.combo_tipo.set("GASTO")

        tk.Label(fila1, text="Categoria:", bg="#ECEFF1", font=("Helvetica", 9)).pack(side=tk.LEFT, padx=3)
        self.combo_categoria = ttk.Combobox(fila1, width=20, font=("Helvetica", 9))
        self.combo_categoria.pack(side=tk.LEFT, padx=3)
        self.combo_categoria["values"] = [
            "Compra Materia Prima", "Mano de Obra", "Transporte", "Alquiler",
            "Servicios Publicos", "Impuestos", "Mantenimiento", "Equipo",
            "Otros Gastos", "Venta Productos", "Cobro Clientes", "Otros Ingresos"
        ]
        self.combo_categoria.set("Otros Gastos")

        tk.Label(fila1, text="Monto CRC:", bg="#C8E6C9", fg="#1B5E20",
                 font=("Helvetica", 9, "bold")).pack(side=tk.LEFT, padx=3)
        self.entry_monto_crc = tk.Entry(fila1, width=12, font=("Helvetica", 9))
        self.entry_monto_crc.pack(side=tk.LEFT, padx=3)

        tk.Label(fila1, text="Monto USD:", bg="#BBDEFB", fg="#0D47A1",
                 font=("Helvetica", 9, "bold")).pack(side=tk.LEFT, padx=3)
        self.entry_monto_usd = tk.Entry(fila1, width=12, font=("Helvetica", 9))
        self.entry_monto_usd.pack(side=tk.LEFT, padx=3)

        fila2 = tk.Frame(form_frame, bg="#ECEFF1")
        fila2.pack(fill=tk.X, padx=5, pady=2)
        for lbl, attr, w in [("Descripcion:", "entry_descripcion", 35),
                              ("Doc.Ref:", "entry_docref", 15),
                              ("Prov/Cliente:", "entry_prov_cli", 20)]:
            tk.Label(fila2, text=lbl, bg="#ECEFF1", font=("Helvetica", 9)).pack(side=tk.LEFT, padx=3)
            e = tk.Entry(fila2, width=w, font=("Helvetica", 9))
            e.pack(side=tk.LEFT, padx=3)
            setattr(self, attr, e)

        btn_frame = tk.Frame(form_frame, bg="#ECEFF1")
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        for txt, color, cmd in [("REGISTRAR", "#2E7D32", self.registrar),
                                 ("LIMPIAR", "#78909C", self.limpiar)]:
            cont = tk.Frame(btn_frame, bg=color, padx=2, pady=2)
            cont.pack(side=tk.LEFT, padx=3)
            tk.Button(cont, text=txt, bg="#F0F0F0", fg="#212121",
                      font=("Helvetica", 9, "bold"), width=14,
                      command=cmd, relief=tk.FLAT).pack()

        # Resumen
        resumen_frame = tk.Frame(self.ventana, bg="#ECEFF1")
        resumen_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.lbl_total_ingresos = tk.Label(resumen_frame, text="Ingresos: CRC 0.00 | USD 0.00",
                                           bg="#C8E6C9", fg="#1B5E20",
                                           font=("Helvetica", 10, "bold"), padx=10)
        self.lbl_total_ingresos.pack(side=tk.LEFT, padx=5)
        
        self.lbl_total_gastos = tk.Label(resumen_frame, text="Gastos: CRC 0.00 | USD 0.00",
                                         bg="#FFCDD2", fg="#C62828",
                                         font=("Helvetica", 10, "bold"), padx=10)
        self.lbl_total_gastos.pack(side=tk.LEFT, padx=5)
        
        self.lbl_balance = tk.Label(resumen_frame, text="Balance: CRC 0.00 | USD 0.00",
                                    bg="#E0E0E0", fg="#212121",
                                    font=("Helvetica", 10, "bold"), padx=10)
        self.lbl_balance.pack(side=tk.LEFT, padx=5)

        # Treeview
        columnas = ("id", "fecha", "tipo", "categoria", "desc", "monto_crc", "monto_usd", "doc_ref", "prov_cli")
        encabezados = ("ID", "Fecha", "Tipo", "Categoria", "Descripcion", "Monto CRC", "Monto USD", "Doc.Ref", "Prov/Cliente")
        ancho_cols = (35, 120, 70, 130, 150, 90, 90, 80, 120)
        self.tree = crear_treeview(self.ventana, columnas, encabezados, ancho_cols, 250)

        # Filtros
        filtro_frame = tk.Frame(self.ventana, bg="#ECEFF1")
        filtro_frame.pack(fill=tk.X, padx=10, pady=2)
        
        tk.Label(filtro_frame, text="Filtrar:", bg="#ECEFF1",
                 font=("Helvetica", 10, "bold")).pack(side=tk.LEFT, padx=5)
        
        self.combo_filtro_tipo = ttk.Combobox(filtro_frame, values=["TODOS", "INGRESO", "GASTO"],
                                               width=12, state="readonly", font=("Helvetica", 9))
        self.combo_filtro_tipo.pack(side=tk.LEFT, padx=5)
        self.combo_filtro_tipo.set("TODOS")
        self.combo_filtro_tipo.bind("<<ComboboxSelected>>", lambda e: self.cargar_movimientos())
        
        tk.Label(filtro_frame, text="Buscar:", bg="#ECEFF1",
                 font=("Helvetica", 9)).pack(side=tk.LEFT, padx=(10, 3))
        self.entry_buscar = tk.Entry(filtro_frame, width=25, font=("Helvetica", 9))
        self.entry_buscar.pack(side=tk.LEFT, padx=3)
        self.entry_buscar.bind("<KeyRelease>", lambda e: self.cargar_movimientos())

    def cargar_movimientos(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        filtro_tipo = self.combo_filtro_tipo.get()
        texto = self.entry_buscar.get().strip().lower()
        
        sql = "SELECT * FROM movimientos_contables WHERE 1=1"
        params = []
        
        if filtro_tipo != "TODOS":
            sql += " AND tipo = ?"
            params.append(filtro_tipo)
        
        if texto:
            sql += " AND (LOWER(descripcion) LIKE ? OR LOWER(categoria) LIKE ? OR LOWER(proveedor_cliente) LIKE ?)"
            params.extend([f"%{texto}%"] * 3)
        
        sql += " ORDER BY id DESC"
        
        movs = ejecutar_select(sql, params)
        
        total_ing_crc = 0
        total_ing_usd = 0
        total_gas_crc = 0
        total_gas_usd = 0
        
        for m in movs:
            self.tree.insert("", "end", values=(
                m["id"], m["fecha"][:16] if m["fecha"] else "", m["tipo"],
                m["categoria"], m["descripcion"] or "",
                formatear_numero(m["monto_crc"]), formatear_dolares(m["monto_usd"]),
                m["documento_ref"] or "", m["proveedor_cliente"] or ""
            ))
            
            if m["tipo"] == "INGRESO":
                total_ing_crc += m["monto_crc"] or 0
                total_ing_usd += m["monto_usd"] or 0
            else:
                total_gas_crc += m["monto_crc"] or 0
                total_gas_usd += m["monto_usd"] or 0
        
        balance_crc = total_ing_crc - total_gas_crc
        balance_usd = total_ing_usd - total_gas_usd
        
        self.lbl_total_ingresos.config(text=f"Ingresos: CRC {total_ing_crc:,.2f} | USD {total_ing_usd:,.2f}")
        self.lbl_total_gastos.config(text=f"Gastos: CRC {total_gas_crc:,.2f} | USD {total_gas_usd:,.2f}")
        self.lbl_balance.config(text=f"Balance: CRC {balance_crc:,.2f} | USD {balance_usd:,.2f}")

    def registrar(self):
        tipo = self.combo_tipo.get()
        categoria = self.combo_categoria.get().strip()
        desc = self.entry_descripcion.get().strip()
        doc_ref = self.entry_docref.get().strip()
        prov_cli = self.entry_prov_cli.get().strip()
        
        try:
            monto_crc = float(self.entry_monto_crc.get() or 0)
        except ValueError:
            monto_crc = 0
        try:
            monto_usd = float(self.entry_monto_usd.get() or 0)
        except ValueError:
            monto_usd = 0
        
        if monto_crc == 0 and monto_usd == 0:
            messagebox.showwarning("Validacion", "Ingrese un monto.")
            return
        
        if not categoria:
            messagebox.showwarning("Validacion", "Seleccione una categoria.")
            return
        
        # Auto-convertir monto
        if monto_crc > 0 and monto_usd == 0:
            monto_usd = convertir_a_dolares(monto_crc, self.tc)
        elif monto_usd > 0 and monto_crc == 0:
            monto_crc = convertir_a_colones(monto_usd, self.tc)
        
        ejecutar_consulta("""
            INSERT INTO movimientos_contables (tipo, categoria, descripcion,
                monto_crc, monto_usd, documento_ref, proveedor_cliente)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (tipo, categoria, desc, monto_crc, monto_usd, doc_ref, prov_cli))
        
        messagebox.showinfo("Exito", f"{tipo} registrado correctamente.")
        self.limpiar()
        self.cargar_movimientos()

    def limpiar(self):
        self.entry_monto_crc.delete(0, tk.END)
        self.entry_monto_usd.delete(0, tk.END)
        self.entry_descripcion.delete(0, tk.END)
        self.entry_docref.delete(0, tk.END)
        self.entry_prov_cli.delete(0, tk.END)


# ═══════════════════════════════════════════════════════════════
# MODULO: REPORTES GRAFICOS
# ═══════════════════════════════════════════════════════════════
class ReportesGraficosModulo:
    def __init__(self, parent):
        self.parent = parent
        self.ventana = tk.Toplevel(parent)
        self.ventana.title("PINO SYSTEM - Reportes Graficos")
        self.ventana.configure(bg="#ECEFF1")
        centrar_ventana(self.ventana, 1000, 700)
        self.ventana.transient(parent)
        self.ventana.grab_set()
        barra_navegacion(self.ventana, parent, actual="graficos")
        self.tc = obtener_tipo_cambio()
        self.crear_widgets()

    def crear_widgets(self):
        header = tk.Frame(self.ventana, bg="#6A1B9A", height=50)
        header.pack(fill=tk.X)
        tk.Label(header, text="REPORTES GRAFICOS",
                 bg="#6A1B9A", fg="white",
                 font=("Helvetica", 15, "bold")).pack(pady=12)

        btn_frame = tk.Frame(self.ventana, bg="#ECEFF1")
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        
        for txt, color, cmd in [("Ventas por Mes", "#1565C0", self.graf_ventas_mes),
                                 ("Top Productos", "#2E7D32", self.graf_top_productos),
                                 ("Ingresos vs Gastos", "#E65100", self.graf_ingresos_gastos),
                                 ("Stock por Categoria", "#C62828", self.graf_stock_categoria),
                                 ("Ventas por Moneda", "#00838F", self.graf_ventas_moneda)]:
            cont = tk.Frame(btn_frame, bg=color, padx=2, pady=2)
            cont.pack(side=tk.LEFT, padx=4, pady=5)
            tk.Button(cont, text=txt, bg="#F0F0F0", fg="#212121",
                      font=("Helvetica", 9, "bold"), width=18, height=2,
                      command=cmd, relief=tk.FLAT).pack()

        self.frame_grafico = tk.Frame(self.ventana, bg="white", relief=tk.SUNKEN, bd=1)
        self.frame_grafico.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    def _limpiar_grafico(self):
        for widget in self.frame_grafico.winfo_children():
            widget.destroy()

    def graf_ventas_mes(self):
        self._limpiar_grafico()
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        
        facts = ejecutar_select("""
            SELECT strftime('%Y-%m', fecha) as mes, SUM(total) as total_crc, SUM(total_usd) as total_usd
            FROM facturas GROUP BY mes ORDER BY mes""")
        
        if not facts:
            tk.Label(self.frame_grafico, text="No hay datos de ventas",
                    bg="white", font=("Helvetica", 12)).pack(pady=50)
            return
        
        meses = [f["mes"] for f in facts]
        totales_crc = [f["total_crc"] for f in facts]
        
        fig, ax = plt.subplots(figsize=(9, 4))
        ax.bar(meses, totales_crc, color='#1565C0', edgecolor='white')
        ax.set_title('Ventas por Mes (CRC)', fontsize=14, fontweight='bold')
        ax.set_xlabel('Mes')
        ax.set_ylabel('Monto CRC')
        ax.tick_params(axis='x', rotation=45)
        plt.tight_layout()
        
        canvas = FigureCanvasTkAgg(fig, self.frame_grafico)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        plt.close(fig)

    def graf_top_productos(self):
        self._limpiar_grafico()
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        
        tops = ejecutar_select("""
            SELECT p.nombre, SUM(d.cantidad) as total_vendido
            FROM detalle_factura d JOIN productos p ON d.producto_id=p.id
            GROUP BY d.producto_id ORDER BY total_vendido DESC LIMIT 10""")
        
        if not tops:
            tk.Label(self.frame_grafico, text="No hay datos de ventas",
                    bg="white", font=("Helvetica", 12)).pack(pady=50)
            return
        
        nombres = [t["nombre"][:20] for t in tops]
        cantidades = [t["total_vendido"] for t in tops]
        
        fig, ax = plt.subplots(figsize=(9, 4))
        ax.barh(nombres[::-1], cantidades[::-1], color='#2E7D32', edgecolor='white')
        ax.set_title('Top 10 Productos Mas Vendidos', fontsize=14, fontweight='bold')
        ax.set_xlabel('Cantidad Vendida')
        plt.tight_layout()
        
        canvas = FigureCanvasTkAgg(fig, self.frame_grafico)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        plt.close(fig)

    def graf_ingresos_gastos(self):
        self._limpiar_grafico()
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        
        ing = ejecutar_select_one("SELECT COALESCE(SUM(monto_crc),0) as total FROM movimientos_contables WHERE tipo='INGRESO'")
        gas = ejecutar_select_one("SELECT COALESCE(SUM(monto_crc),0) as total FROM movimientos_contables WHERE tipo='GASTO'")
        
        ingresos = ing["total"] if ing else 0
        gastos = gas["total"] if gas else 0
        
        if ingresos == 0 and gastos == 0:
            tk.Label(self.frame_grafico, text="No hay datos contables",
                    bg="white", font=("Helvetica", 12)).pack(pady=50)
            return
        
        fig, ax = plt.subplots(figsize=(6, 4))
        categorias = ['Ingresos', 'Gastos']
        valores = [ingresos, gastos]
        colores = ['#2E7D32', '#C62828']
        ax.bar(categorias, valores, color=colores, edgecolor='white', width=0.5)
        ax.set_title('Ingresos vs Gastos (CRC)', fontsize=14, fontweight='bold')
        ax.set_ylabel('Monto CRC')
        
        for i, v in enumerate(valores):
            ax.text(i, v + max(valores)*0.02, f'{v:,.0f}', ha='center', fontweight='bold')
        
        plt.tight_layout()
        canvas = FigureCanvasTkAgg(fig, self.frame_grafico)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        plt.close(fig)

    def graf_stock_categoria(self):
        self._limpiar_grafico()
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        
        cats = ejecutar_select("""
            SELECT c.nombre, COUNT(p.id) as cantidad
            FROM categorias c LEFT JOIN productos p ON c.id=p.categoria_id AND p.activo=1
            GROUP BY c.id HAVING cantidad > 0 ORDER BY cantidad DESC""")
        
        if not cats:
            tk.Label(self.frame_grafico, text="No hay datos",
                    bg="white", font=("Helvetica", 12)).pack(pady=50)
            return
        
        nombres = [c["nombre"][:15] for c in cats]
        cantidades = [c["cantidad"] for c in cats]
        
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.pie(cantidades, labels=nombres, autopct='%1.1f%%', startangle=90,
               colors=plt.cm.Set3.colors[:len(nombres)])
        ax.set_title('Productos por Categoria', fontsize=14, fontweight='bold')
        plt.tight_layout()
        
        canvas = FigureCanvasTkAgg(fig, self.frame_grafico)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        plt.close(fig)

    def graf_ventas_moneda(self):
        self._limpiar_grafico()
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        
        monedas = ejecutar_select("""
            SELECT moneda, COUNT(*) as cantidad, SUM(total) as suma
            FROM facturas GROUP BY moneda""")
        
        if not monedas:
            tk.Label(self.frame_grafico, text="No hay datos de ventas",
                    bg="white", font=("Helvetica", 12)).pack(pady=50)
            return
        
        labels = [m["moneda"] for m in monedas]
        cantidades = [m["cantidad"] for m in monedas]
        
        fig, ax = plt.subplots(figsize=(6, 4))
        colores = ['#1565C0' if l == 'CRC' else '#2E7D32' for l in labels]
        ax.bar(labels, cantidades, color=colores, edgecolor='white', width=0.4)
        ax.set_title('Ventas por Moneda', fontsize=14, fontweight='bold')
        ax.set_ylabel('Cantidad de Facturas')
        
        for i, v in enumerate(cantidades):
            ax.text(i, v + max(cantidades)*0.02, str(v), ha='center', fontweight='bold')
        
        plt.tight_layout()
        canvas = FigureCanvasTkAgg(fig, self.frame_grafico)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        plt.close(fig)


# ═══════════════════════════════════════════════════════════════
# MODULO: DEVOLUCIONES
# ═══════════════════════════════════════════════════════════════
class DevolucionesModulo:
    def __init__(self, parent):
        self.parent = parent
        self.ventana = tk.Toplevel(parent)
        self.ventana.title("PINO SYSTEM - Devoluciones")
        self.ventana.configure(bg="#ECEFF1")
        centrar_ventana(self.ventana, 1000, 600)
        self.ventana.transient(parent)
        self.ventana.grab_set()
        self.tc = obtener_tipo_cambio()
        self.crear_widgets()
        self.cargar_devoluciones()

    def crear_widgets(self):
        header = tk.Frame(self.ventana, bg="#C62828", height=50)
        header.pack(fill=tk.X)
        tk.Label(header, text="DEVOLUCIONES DE PRODUCTOS",
                 bg="#C62828", fg="white",
                 font=("Helvetica", 15, "bold")).pack(pady=12)

        form_frame = tk.LabelFrame(self.ventana, text="Nueva Devolucion",
                                    bg="#ECEFF1", font=("Helvetica", 10, "bold"))
        form_frame.pack(fill=tk.X, padx=10, pady=5)

        fila1 = tk.Frame(form_frame, bg="#ECEFF1")
        fila1.pack(fill=tk.X, padx=5, pady=2)

        tk.Label(fila1, text="Factura:", bg="#ECEFF1", font=("Helvetica", 9)).pack(side=tk.LEFT, padx=3)
        self.combo_factura = ttk.Combobox(fila1, width=15, state="readonly", font=("Helvetica", 9))
        self.combo_factura.pack(side=tk.LEFT, padx=3)
        self._cargar_facturas()

        tk.Label(fila1, text="Producto:", bg="#ECEFF1", font=("Helvetica", 9)).pack(side=tk.LEFT, padx=3)
        self.combo_producto = ttk.Combobox(fila1, width=25, state="readonly", font=("Helvetica", 9))
        self.combo_producto.pack(side=tk.LEFT, padx=3)

        tk.Label(fila1, text="Cantidad:", bg="#ECEFF1", font=("Helvetica", 9)).pack(side=tk.LEFT, padx=3)
        self.entry_cantidad = tk.Entry(fila1, width=8, font=("Helvetica", 9))
        self.entry_cantidad.pack(side=tk.LEFT, padx=3)

        fila2 = tk.Frame(form_frame, bg="#ECEFF1")
        fila2.pack(fill=tk.X, padx=5, pady=2)
        tk.Label(fila2, text="Motivo:", bg="#ECEFF1", font=("Helvetica", 9)).pack(side=tk.LEFT, padx=3)
        self.entry_motivo = tk.Entry(fila2, width=40, font=("Helvetica", 9))
        self.entry_motivo.pack(side=tk.LEFT, padx=3, fill=tk.X, expand=True)

        btn_frame = tk.Frame(form_frame, bg="#ECEFF1")
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        
        cont_reg = tk.Frame(btn_frame, bg="#C62828", padx=2, pady=2)
        cont_reg.pack(side=tk.LEFT, padx=3)
        tk.Button(cont_reg, text="REGISTRAR DEVOLUCION", bg="#F0F0F0", fg="#212121",
                  font=("Helvetica", 9, "bold"), width=20,
                  command=self.registrar_devolucion, relief=tk.FLAT).pack()

        # Treeview
        columnas = ("id", "fecha", "factura", "producto", "cantidad", "motivo", "estado")
        encabezados = ("ID", "Fecha", "Factura", "Producto", "Cantidad", "Motivo", "Estado")
        ancho_cols = (35, 120, 80, 150, 70, 200, 80)
        self.tree = crear_treeview(self.ventana, columnas, encabezados, ancho_cols, 250)

    def _cargar_facturas(self):
        facts = ejecutar_select("SELECT id, numero FROM facturas ORDER BY id DESC")
        self.lista_facturas = {f["numero"]: f["id"] for f in facts}
        self.combo_factura["values"] = list(self.lista_facturas.keys())
        if self.lista_facturas:
            self.combo_factura.current(0)
            self.combo_factura.bind("<<ComboboxSelected>>", self._cargar_productos_factura)

    def _cargar_productos_factura(self, event=None):
        num = self.combo_factura.get()
        if not num:
            return
        fid = self.lista_facturas.get(num)
        if not fid:
            return
        items = ejecutar_select("""
            SELECT DISTINCT p.codigo, p.nombre
            FROM detalle_factura d JOIN productos p ON d.producto_id=p.id
            WHERE d.factura_id=?""", (fid,))
        self.lista_productos = {f"{i['codigo']} - {i['nombre']}": i['codigo'] for i in items}
        self.combo_producto["values"] = list(self.lista_productos.keys())
        if self.lista_productos:
            self.combo_producto.current(0)

    def registrar_devolucion(self):
        num_fact = self.combo_factura.get()
        prod_text = self.combo_producto.get()
        
        if not num_fact or not prod_text:
            messagebox.showwarning("Validacion", "Seleccione factura y producto.")
            return
        
        try:
            cantidad = float(self.entry_cantidad.get())
        except ValueError:
            messagebox.showwarning("Validacion", "Cantidad invalida.")
            return
        
        motivo = self.entry_motivo.get().strip()
        if not motivo:
            messagebox.showwarning("Validacion", "Ingrese un motivo.")
            return
        
        fid = self.lista_facturas.get(num_fact)
        prod_code = self.lista_productos.get(prod_text)
        
        # Registrar devolucion
        ejecutar_consulta("""
            INSERT INTO movimientos_contables (tipo, categoria, descripcion,
                monto_crc, monto_usd, documento_ref, proveedor_cliente)
            VALUES ('GASTO', 'Devolucion', ?, 0, 0, ?, ?)
        """, (f"Devolucion: {motivo}", f"FAC-{num_fact}", prod_code))
        
        messagebox.showinfo("Exito", "Devolucion registrada.")
        self.entry_cantidad.delete(0, tk.END)
        self.entry_motivo.delete(0, tk.END)
        self.cargar_devoluciones()

    def cargar_devoluciones(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        devs = ejecutar_select("""
            SELECT * FROM movimientos_contables
            WHERE categoria='Devolucion' ORDER BY id DESC""")
        
        for d in devs:
            self.tree.insert("", "end", values=(
                d["id"], d["fecha"][:16] if d["fecha"] else "",
                d["documento_ref"] or "", d["descripcion"] or "",
                "", d["proveedor_cliente"] or "", "REGISTRADA"
            ))


# ═══════════════════════════════════════════════════════════════
# MODULO: PEDIDOS PENDIENTES
# ═══════════════════════════════════════════════════════════════
class PedidosPendientesModulo:
    def __init__(self, parent):
        self.parent = parent
        self.ventana = tk.Toplevel(parent)
        self.ventana.title("PINO SYSTEM - Pedidos Pendientes")
        self.ventana.configure(bg="#ECEFF1")
        centrar_ventana(self.ventana, 1050, 650)
        self.ventana.transient(parent)
        self.ventana.grab_set()
        self.crear_widgets()
        self.cargar_pedidos()

    def crear_widgets(self):
        header = tk.Frame(self.ventana, bg="#E65100", height=50)
        header.pack(fill=tk.X)
        tk.Label(header, text="PEDIDOS PENDIENTES POR ENTREGAR",
                 bg="#E65100", fg="white",
                 font=("Helvetica", 15, "bold")).pack(pady=12)

        form_frame = tk.LabelFrame(self.ventana, text="Nuevo Pedido",
                                    bg="#ECEFF1", font=("Helvetica", 10, "bold"))
        form_frame.pack(fill=tk.X, padx=10, pady=5)

        fila1 = tk.Frame(form_frame, bg="#ECEFF1")
        fila1.pack(fill=tk.X, padx=5, pady=2)

        for lbl, attr, w in [("Cliente:", "entry_cliente", 20), ("Telefono:", "entry_tel", 12)]:
            tk.Label(fila1, text=lbl, bg="#ECEFF1", font=("Helvetica", 9)).pack(side=tk.LEFT, padx=3)
            e = tk.Entry(fila1, width=w, font=("Helvetica", 9))
            e.pack(side=tk.LEFT, padx=3)
            setattr(self, attr, e)

        tk.Label(fila1, text="Producto:", bg="#ECEFF1", font=("Helvetica", 9)).pack(side=tk.LEFT, padx=3)
        self.combo_producto = ttk.Combobox(fila1, width=25, state="readonly", font=("Helvetica", 9))
        self.combo_producto.pack(side=tk.LEFT, padx=3)
        self._cargar_productos()

        tk.Label(fila1, text="Cant:", bg="#ECEFF1", font=("Helvetica", 9)).pack(side=tk.LEFT, padx=3)
        self.entry_cantidad = tk.Entry(fila1, width=7, font=("Helvetica", 9))
        self.entry_cantidad.pack(side=tk.LEFT, padx=3)

        tk.Label(fila1, text="Entrega:", bg="#ECEFF1", font=("Helvetica", 9)).pack(side=tk.LEFT, padx=3)
        self.entry_fecha_entrega = tk.Entry(fila1, width=12, font=("Helvetica", 9))
        self.entry_fecha_entrega.pack(side=tk.LEFT, padx=3)
        self.entry_fecha_entrega.insert(0, "2026-12-31")

        btn_frame = tk.Frame(form_frame, bg="#ECEFF1")
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        
        cont_reg = tk.Frame(btn_frame, bg="#2E7D32", padx=2, pady=2)
        cont_reg.pack(side=tk.LEFT, padx=3)
        tk.Button(cont_reg, text="REGISTRAR PEDIDO", bg="#F0F0F0", fg="#212121",
                  font=("Helvetica", 9, "bold"), width=18,
                  command=self.registrar_pedido, relief=tk.FLAT).pack()
        
        cont_ent = tk.Frame(btn_frame, bg="#1565C0", padx=2, pady=2)
        cont_ent.pack(side=tk.LEFT, padx=3)
        tk.Button(cont_ent, text="MARCAR ENTREGADO", bg="#F0F0F0", fg="#212121",
                  font=("Helvetica", 9, "bold"), width=18,
                  command=self.marcar_entregado, relief=tk.FLAT).pack()
        
        cont_can = tk.Frame(btn_frame, bg="#C62828", padx=2, pady=2)
        cont_can.pack(side=tk.LEFT, padx=3)
        tk.Button(cont_can, text="CANCELAR PEDIDO", bg="#F0F0F0", fg="#212121",
                  font=("Helvetica", 9, "bold"), width=18,
                  command=self.cancelar_pedido, relief=tk.FLAT).pack()

        # Treeview
        columnas = ("id", "fecha", "cliente", "producto", "cant_sol", "cant_ent", "estado", "entrega_est")
        encabezados = ("ID", "Fecha", "Cliente", "Producto", "Solicitado", "Entregado", "Estado", "Entrega Est.")
        ancho_cols = (35, 110, 150, 150, 70, 70, 80, 90)
        self.tree = crear_treeview(self.ventana, columnas, encabezados, ancho_cols, 250)

    def _cargar_productos(self):
        prods = ejecutar_select("SELECT id, codigo, nombre FROM productos WHERE activo=1 ORDER BY nombre")
        self.lista_productos = {f"{p['codigo']} - {p['nombre']}": p['codigo'] for p in prods}
        self.combo_producto["values"] = list(self.lista_productos.keys())
        if self.lista_productos:
            self.combo_producto.current(0)

    def registrar_pedido(self):
        cliente = self.entry_cliente.get().strip()
        prod_text = self.combo_producto.get()
        
        if not cliente or not prod_text:
            messagebox.showwarning("Validacion", "Ingrese cliente y producto.")
            return
        
        try:
            cantidad = float(self.entry_cantidad.get())
        except ValueError:
            messagebox.showwarning("Validacion", "Cantidad invalida.")
            return
        
        prod_code = self.lista_productos.get(prod_text)
        prod_info = ejecutar_select_one("SELECT id, nombre, precio_venta, precio_venta_usd FROM productos WHERE codigo=?", (prod_code,))
        
        ejecutar_consulta("""
            INSERT INTO pedidos_pendientes (cliente_nombre, producto_id, producto_codigo,
                producto_nombre, cantidad_solicitada, precio_unitario_crc, precio_unitario_usd,
                fecha_entrega_estimada, observaciones)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (cliente, prod_info["id"], prod_code, prod_info["nombre"],
              cantidad, prod_info["precio_venta"], prod_info["precio_venta_usd"],
              self.entry_fecha_entrega.get().strip(), self.entry_tel.get().strip()))
        
        messagebox.showinfo("Exito", "Pedido registrado.")
        self.entry_cliente.delete(0, tk.END)
        self.entry_tel.delete(0, tk.END)
        self.entry_cantidad.delete(0, tk.END)
        self.cargar_pedidos()

    def marcar_entregado(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Aviso", "Seleccione un pedido.")
            return
        vals = self.tree.item(sel[0])["values"]
        eid = vals[0]
        estado = vals[6]
        
        if estado == "ENTREGADO":
            messagebox.showinfo("Aviso", "Este pedido ya fue entregado.")
            return
        
        ejecutar_consulta("UPDATE pedidos_pendientes SET estado='ENTREGADO', cantidad_entregada=cantidad_solicitada WHERE id=?", (eid,))
        messagebox.showinfo("Exito", "Pedido marcado como entregado.")
        self.cargar_pedidos()

    def cancelar_pedido(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Aviso", "Seleccione un pedido.")
            return
        vals = self.tree.item(sel[0])["values"]
        eid = vals[0]
        
        if messagebox.askyesno("Confirmar", "Desea cancelar este pedido?"):
            ejecutar_consulta("UPDATE pedidos_pendientes SET estado='CANCELADO' WHERE id=?", (eid,))
            self.cargar_pedidos()

    def cargar_pedidos(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        pedidos = ejecutar_select("""
            SELECT * FROM pedidos_pendientes
            WHERE estado != 'CANCELADO' ORDER BY id DESC""")
        
        for p in pedidos:
            self.tree.insert("", "end", values=(
                p["id"], p["fecha_pedido"][:16] if p["fecha_pedido"] else "",
                p["cliente_nombre"] or "", p["producto_nombre"] or "",
                formatear_numero(p["cantidad_solicitada"]),
                formatear_numero(p["cantidad_entregada"]),
                p["estado"], p["fecha_entrega_estimada"] or ""
            ))


# ═══════════════════════════════════════════════════════════════
# MODULO: SERIES Y LOTES
# ═══════════════════════════════════════════════════════════════
class SeriesLotesModulo:
    def __init__(self, parent):
        self.parent = parent
        self.ventana = tk.Toplevel(parent)
        self.ventana.title("PINO SYSTEM - Series y Lotes")
        self.ventana.configure(bg="#ECEFF1")
        centrar_ventana(self.ventana, 1000, 600)
        self.ventana.transient(parent)
        self.ventana.grab_set()
        self.crear_widgets()
        self.cargar_series()

    def crear_widgets(self):
        header = tk.Frame(self.ventana, bg="#00838F", height=50)
        header.pack(fill=tk.X)
        tk.Label(header, text="SERIES Y LOTES",
                 bg="#00838F", fg="white",
                 font=("Helvetica", 15, "bold")).pack(pady=12)

        form_frame = tk.LabelFrame(self.ventana, text="Nueva Serie/Lote",
                                    bg="#ECEFF1", font=("Helvetica", 10, "bold"))
        form_frame.pack(fill=tk.X, padx=10, pady=5)

        fila1 = tk.Frame(form_frame, bg="#ECEFF1")
        fila1.pack(fill=tk.X, padx=5, pady=2)

        tk.Label(fila1, text="Producto:", bg="#ECEFF1", font=("Helvetica", 9)).pack(side=tk.LEFT, padx=3)
        self.combo_producto = ttk.Combobox(fila1, width=25, state="readonly", font=("Helvetica", 9))
        self.combo_producto.pack(side=tk.LEFT, padx=3)
        self._cargar_productos()

        tk.Label(fila1, text="N.Serie:", bg="#ECEFF1", font=("Helvetica", 9)).pack(side=tk.LEFT, padx=3)
        self.entry_serie = tk.Entry(fila1, width=15, font=("Helvetica", 9))
        self.entry_serie.pack(side=tk.LEFT, padx=3)

        tk.Label(fila1, text="Lote:", bg="#ECEFF1", font=("Helvetica", 9)).pack(side=tk.LEFT, padx=3)
        self.entry_lote = tk.Entry(fila1, width=12, font=("Helvetica", 9))
        self.entry_lote.pack(side=tk.LEFT, padx=3)

        tk.Label(fila1, text="Cant:", bg="#ECEFF1", font=("Helvetica", 9)).pack(side=tk.LEFT, padx=3)
        self.entry_cantidad = tk.Entry(fila1, width=7, font=("Helvetica", 9))
        self.entry_cantidad.pack(side=tk.LEFT, padx=3)

        fila2 = tk.Frame(form_frame, bg="#ECEFF1")
        fila2.pack(fill=tk.X, padx=5, pady=2)
        tk.Label(fila2, text="Ubicacion:", bg="#ECEFF1", font=("Helvetica", 9)).pack(side=tk.LEFT, padx=3)
        self.entry_ubicacion = tk.Entry(fila2, width=20, font=("Helvetica", 9))
        self.entry_ubicacion.pack(side=tk.LEFT, padx=3)

        tk.Label(fila2, text="Vence:", bg="#ECEFF1", font=("Helvetica", 9)).pack(side=tk.LEFT, padx=3)
        self.entry_vence = tk.Entry(fila2, width=12, font=("Helvetica", 9))
        self.entry_vence.pack(side=tk.LEFT, padx=3)

        btn_frame = tk.Frame(form_frame, bg="#ECEFF1")
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        
        cont_reg = tk.Frame(btn_frame, bg="#2E7D32", padx=2, pady=2)
        cont_reg.pack(side=tk.LEFT, padx=3)
        tk.Button(cont_reg, text="REGISTRAR", bg="#F0F0F0", fg="#212121",
                  font=("Helvetica", 9, "bold"), width=14,
                  command=self.registrar_serie, relief=tk.FLAT).pack()
        
        cont_del = tk.Frame(btn_frame, bg="#C62828", padx=2, pady=2)
        cont_del.pack(side=tk.LEFT, padx=3)
        tk.Button(cont_del, text="ELIMINAR", bg="#F0F0F0", fg="#212121",
                  font=("Helvetica", 9, "bold"), width=14,
                  command=self.eliminar_serie, relief=tk.FLAT).pack()

        # Treeview
        columnas = ("id", "producto", "serie", "lote", "cantidad", "ubicacion", "vence", "estado")
        encabezados = ("ID", "Producto", "N.Serie", "Lote", "Cantidad", "Ubicacion", "Vence", "Estado")
        ancho_cols = (35, 180, 100, 80, 70, 120, 90, 80)
        self.tree = crear_treeview(self.ventana, columnas, encabezados, ancho_cols, 250)

    def _cargar_productos(self):
        prods = ejecutar_select("SELECT id, codigo, nombre FROM productos WHERE activo=1 ORDER BY nombre")
        self.lista_productos = {f"{p['codigo']} - {p['nombre']}": p['id'] for p in prods}
        self.combo_producto["values"] = list(self.lista_productos.keys())
        if self.lista_productos:
            self.combo_producto.current(0)

    def registrar_serie(self):
        prod_text = self.combo_producto.get()
        serie = self.entry_serie.get().strip()
        
        if not prod_text or not serie:
            messagebox.showwarning("Validacion", "Seleccione producto y numero de serie.")
            return
        
        try:
            cantidad = float(self.entry_cantidad.get() or 1)
        except ValueError:
            cantidad = 1
        
        pid = self.lista_productos.get(prod_text)
        lote = self.entry_lote.get().strip()
        ubicacion = self.entry_ubicacion.get().strip()
        vence = self.entry_vence.get().strip()
        
        try:
            ejecutar_consulta("""
                INSERT INTO series_lotes (producto_id, numero_serie, lote,
                    cantidad, ubicacion, fecha_vencimiento)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (pid, serie, lote, cantidad, ubicacion, vence if vence else None))
            
            messagebox.showinfo("Exito", "Serie/Lote registrado.")
            self.entry_serie.delete(0, tk.END)
            self.entry_lote.delete(0, tk.END)
            self.entry_cantidad.delete(0, tk.END)
            self.entry_ubicacion.delete(0, tk.END)
            self.entry_vence.delete(0, tk.END)
            self.cargar_series()
        except Exception as e:
            messagebox.showerror("Error", f"Error al registrar: {str(e)}")

    def eliminar_serie(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Aviso", "Seleccione un registro.")
            return
        vals = self.tree.item(sel[0])["values"]
        eid = vals[0]
        
        if messagebox.askyesno("Confirmar", "Desea eliminar este registro?"):
            ejecutar_consulta("DELETE FROM series_lotes WHERE id=?", (eid,))
            self.cargar_series()

    def cargar_series(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        series = ejecutar_select("""
            SELECT s.*, p.codigo, p.nombre
            FROM series_lotes s JOIN productos p ON s.producto_id=p.id
            ORDER BY s.id DESC""")
        
        for s in series:
            self.tree.insert("", "end", values=(
                s["id"], f"{s['codigo']} - {s['nombre']}",
                s["numero_serie"] or "", s["lote"] or "",
                formatear_numero(s["cantidad"]), s["ubicacion"] or "",
                s["fecha_vencimiento"] or "", s["estado"]
            ))
