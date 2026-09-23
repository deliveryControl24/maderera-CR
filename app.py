"""
PINO SYSTEM - Sistema de Inventario y Facturacion
Moneda Dual: Colones (CRC) y Dolares (USD)
Desarrollado con Python + Tkinter + SQLite
"""

import os
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox, font
from database import (init_db, ejecutar_select, ejecutar_select_one,
                      obtener_tipo_cambio, actualizar_tipo_cambio)
from modulos import (
    ProductosModulo, KardexModulo, FacturacionModulo,
    ClientesModulo, ReportesModulo, ConfiguracionModulo, VentasPOSModulo,
    ContabilidadModulo, ReportesGraficosModulo, DevolucionesModulo,
    PedidosPendientesModulo, SeriesLotesModulo
)
from utils import centrar_ventana, formatear_numero, formatear_colones, formatear_dolares, fecha_actual
from updater import check_on_startup, manual_check, AutoUpdater
from config_paths import ensure_data_migration, load_config, save_config, APP_VERSION, ensure_launcher, cleanup_old_versions
from themes import get_theme


class AppMaderera:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"PINO SYSTEM v{APP_VERSION} - Sistema de Inventario y Facturacion")
        self.tema = get_theme(load_config().get("theme", "claro"))
        self.root.configure(bg=self.tema["root_bg"])
        centrar_ventana(self.root, 1050, 700)
        self.root.minsize(850, 550)

        # Establecer icono
        try:
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pino.ico")
            if os.path.exists(icon_path):
                self.root.iconbitmap(icon_path)
        except:
            pass

        ensure_data_migration()
        init_db()
        try:
            ensure_launcher()
        except Exception:
            pass
        self.configurar_estilos()
        self.crear_menu()
        self.crear_widgets_principales()
        self.crear_barra_estado()
        self._update_info = None

        # Verificar actualizaciones y stock bajo al iniciar (sin congelar UI)
        self.root.after(1500, lambda: check_on_startup(
            self.root, on_result=self._on_update_check))
        # Limpieza de versiones viejas (side-by-side), diferida
        self.root.after(8000, self._limpiar_versiones_viejas)
        self.root.after(2500, self.verificar_stock_bajo)

    def _on_update_check(self, result):
        """Al iniciar: si hay update, abre el dialogo simple (un clic)."""
        if result and result.get("update_available"):
            self._update_info = result
            try:
                from updater import UpdateDialog, AutoUpdater
                UpdateDialog(self.root, AutoUpdater()).show_update_available(result)
            except Exception:
                try:
                    self.mostrar_inicio()
                except Exception:
                    pass

    def _banner_actualizacion(self, parent):
        """Barra en el inicio si cerro el dialogo y quedo pendiente."""
        info = getattr(self, "_update_info", None)
        if not info:
            return
        bar = tk.Frame(parent, bg="#1565C0", padx=8, pady=6)
        bar.pack(fill=tk.X, padx=20, pady=(6, 0))
        tk.Label(
            bar,
            text=f"Tienes una actualizacion pendiente "
                 f"(nueva version {info.get('remote_version', '')})",
            bg="#1565C0", fg="white",
            font=("Helvetica", 10, "bold"),
        ).pack(side=tk.LEFT, padx=(4, 10))

        def actualizar():
            from updater import UpdateDialog, AutoUpdater
            UpdateDialog(self.root, AutoUpdater()).show_update_available(info)

        def ocultar():
            self._update_info = None
            self.mostrar_inicio()

        for texto, cmd, color in (
            ("ACTUALIZAR", actualizar, "#FFD600"),
            ("LUEGO", ocultar, "#90A4AE"),
        ):
            cont = tk.Frame(bar, bg=color, padx=2, pady=2)
            cont.pack(side=tk.RIGHT, padx=4)
            tk.Button(
                cont, text=texto,
                bg="#F0F0F0", fg="#212121",
                font=("Helvetica", 9, "bold"),
                command=cmd, relief=tk.FLAT, cursor="hand2",
            ).pack()

    def recargar_tema(self):
        """Vuelve a leer el tema de config y repinta la pantalla de inicio."""
        self.tema = get_theme(load_config().get("theme", "claro"))
        self.root.configure(bg=self.tema["root_bg"])
        self.configurar_estilos()
        self.crear_menu()
        self.mostrar_inicio()

    def configurar_estilos(self):
        t = self.tema
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview",
                         background=t["tree_bg"], foreground=t["tree_fg"],
                         rowheight=26, fieldbackground=t["tree_field"],
                         font=("Helvetica", 9))
        style.configure("Treeview.Heading",
                         font=("Helvetica", 9, "bold"),
                         background=t["heading_bg"], foreground=t["heading_fg"])
        style.map("Treeview", background=[("selected", t["select"])])
        style.configure("TButton", background=t["btn_face"], foreground=t["btn_fg"])
        style.configure("TFrame", background=t["root_bg"])
        style.configure("TLabel", background=t["root_bg"], foreground=t["title_fg"])
        style.configure("TMenubutton", background=t["menu_bg"], foreground=t["menu_fg"])
        try:
            self.root.option_add("*Menu.background", t["menu_bg"])
            self.root.option_add("*Menu.foreground", t["menu_fg"])
        except Exception:
            pass

    def crear_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        archivo = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Archivo", menu=archivo)
        archivo.add_command(label="Inicio", command=self.mostrar_inicio, accelerator="Ctrl+I")
        archivo.add_command(label="Configuracion", command=self.abrir_configuracion, accelerator="Ctrl+,")
        archivo.add_separator()
        archivo.add_command(label="Salir", command=self.salir, accelerator="Ctrl+Q")

        try:
            cfg = load_config()
            hidden = set(cfg.get("hidden_modules") or [])
        except Exception:
            hidden = set()

        inventario = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Inventario", menu=inventario)
        if "productos" not in hidden:
            inventario.add_command(label="Productos / Maderas", command=self.abrir_productos, accelerator="Ctrl+P")
        if "kardex" not in hidden:
            inventario.add_command(label="Kardex", command=self.abrir_kardex, accelerator="Ctrl+K")
        if "productos" in hidden and "kardex" in hidden:
            inventario.add_command(label="(oculto en Configuracion)", state=tk.DISABLED)

        ventas = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Ventas", menu=ventas)
        if "facturacion" not in hidden or "pos" not in hidden:
            if "facturacion" not in hidden:
                ventas.add_command(label="Nueva Factura", command=self.abrir_facturacion, accelerator="Ctrl+F")
            if "pos" not in hidden:
                ventas.add_command(label="Punto de Venta (POS)", command=self.abrir_pos)
        else:
            ventas.add_command(label="(oculto en Configuracion)", state=tk.DISABLED)

        personas = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Personas", menu=personas)
        if "clientes" not in hidden:
            personas.add_command(label="Clientes", command=self.abrir_clientes)
        else:
            personas.add_command(label="(oculto en Configuracion)", state=tk.DISABLED)

        reportes = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Reportes", menu=reportes)
        if "reportes" not in hidden or "graficos" not in hidden:
            if "reportes" not in hidden:
                reportes.add_command(label="Ver Reportes", command=self.abrir_reportes, accelerator="Ctrl+R")
            if "graficos" not in hidden:
                reportes.add_command(label="Reportes Graficos", command=self.abrir_reportes_graficos)
        else:
            reportes.add_command(label="(oculto en Configuracion)", state=tk.DISABLED)

        ayuda = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Ayuda", menu=ayuda)
        ayuda.add_command(label="Buscar Actualizaciones", command=self.verificar_actualizaciones)
        ayuda.add_separator()
        ayuda.add_command(label="Escalar el Proyecto - SellFlow", command=self.abrir_sellflow)
        ayuda.add_separator()
        ayuda.add_command(label="Acerca de", command=self.acerca_de)

        self.root.bind("<Control-i>", lambda e: self.mostrar_inicio())
        self.root.bind("<Control-p>", lambda e: self.abrir_productos())
        self.root.bind("<Control-k>", lambda e: self.abrir_kardex())
        self.root.bind("<Control-f>", lambda e: self.abrir_facturacion())
        self.root.bind("<Control-r>", lambda e: self.abrir_reportes())
        self.root.bind("<Control-comma>", lambda e: self.abrir_configuracion())
        self.root.bind("<Control-q>", lambda e: self.salir())
        self._menu_ocultos = hidden

    def crear_widgets_principales(self):
        t = self.tema
        main_frame = tk.Frame(self.root, bg=t["root_bg"])
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Banner de actualizacion (si la revisión en background la encontro)
        self._banner_actualizacion(main_frame)

        # Titulo
        titulo_frame = tk.Frame(main_frame, bg=t["root_bg"])
        titulo_frame.pack(pady=(25, 5))

        tk.Label(titulo_frame, text="PINO SYSTEM",
                 font=("Helvetica", 38, "bold"),
                 bg=t["root_bg"], fg=t["title_fg"]).pack()
        tk.Label(titulo_frame, text=f"Version {APP_VERSION}  |  Sistema de Inventario y Facturacion KARDEX",
                 font=("Helvetica", 13),
                 bg=t["root_bg"], fg=t["sub_fg"]).pack(pady=(2, 0))

        # Tipo de cambio
        tc = obtener_tipo_cambio()
        tc_frame = tk.Frame(main_frame, bg=t["tc_bg"], bd=1, relief=tk.SUNKEN)
        tc_frame.pack(pady=(8, 12))
        tk.Label(tc_frame, text=f"  TIPO DE CAMBIO: 1 USD = CRC {tc:,.2f}  ",
                 bg=t["tc_bg"], fg=t["tc_fg"],
                 font=("Helvetica", 11, "bold")).pack(pady=4)

        # Contenedor con publicidades a los lados de los botones
        content_row = tk.Frame(main_frame, bg=t["root_bg"])
        content_row.pack(pady=(5, 10))

        # PUBLICIDAD IZQUIERDA
        pub_left = self._crear_pub_lateral(content_row, tk.LEFT)
        pub_left.pack(side=tk.LEFT, padx=(0, 15), fill=tk.Y)

        # Botones principales
        btn_frame = tk.Frame(content_row, bg=t["root_bg"])
        btn_frame.pack(side=tk.LEFT)

        botones_data = [
            ("VENTAS POS\nPunto de Venta", "#FF6F00", self.abrir_pos, "pos"),
            ("PRODUCTOS\nMaderas",          "#1565C0", self.abrir_productos, "productos"),
            ("KARDEX\nInventario",          "#C62828", self.abrir_kardex, "kardex"),
            ("FACTURACION\nNueva Venta",    "#00838F", self.abrir_facturacion, "facturacion"),
            ("CLIENTES",                    "#6A1B9A", self.abrir_clientes, "clientes"),
            ("REPORTES\nInformes",          "#E65100", self.abrir_reportes, "reportes"),
            ("REPORTES\nGraficos",          "#6A1B9A", self.abrir_reportes_graficos, "graficos"),
            ("ACTUALIZAR\nSistema",         "#2E7D32", self.verificar_actualizaciones, "actualizar"),
            ("CONFIGURACION\nDel Sistema",  "#37474F", self.abrir_configuracion, "config"),
        ]
        hidden = set(load_config().get("hidden_modules") or [])
        botones_visibles = [b for b in botones_data if b[3] not in hidden or b[3] == "config"]
        if not botones_visibles:
            botones_visibles = [b for b in botones_data if b[3] == "config"]

        for i, (texto, borde_color, cmd, _key) in enumerate(botones_visibles):
            contenedor = tk.Frame(btn_frame, bg=borde_color, bd=0, padx=3, pady=3)
            contenedor.grid(row=i // 3, column=i % 3, padx=8, pady=6)

            btn = tk.Button(
                contenedor,
                text=texto,
                font=("Helvetica", 12, "bold"),
                bg=t["btn_face"], fg=t["btn_fg"],
                activebackground="#E0E0E0", activeforeground="#000000",
                width=16, height=3,
                command=cmd,
                relief=tk.FLAT, bd=0,
                cursor="hand2"
            )
            btn.pack()

        # PUBLICIDAD DERECHA
        pub_right = self._crear_pub_lateral(content_row, tk.RIGHT)
        pub_right.pack(side=tk.RIGHT, padx=(15, 0), fill=tk.Y)

        # Resumen inferior
        self.crear_info_resumen(main_frame)

    def _crear_pub_lateral(self, parent, side):
        pub = tk.Frame(parent, bg="#FFD600", bd=0, padx=6, pady=10, width=170)
        pub.pack_propagate(False)

        def abrir(e=None):
            self.abrir_sellflow()

        def hover_in(e=None):
            pub.config(bg="#FFC107")
            for w in pub.winfo_children():
                try:
                    w.config(bg="#FFC107")
                except tk.TclError:
                    pass

        def hover_out(e=None):
            pub.config(bg="#FFD600")
            for w in pub.winfo_children():
                try:
                    w.config(bg="#FFD600")
                except tk.TclError:
                    pass

        for w in (pub,):
            w.bind("<Button-1>", abrir)
            w.bind("<Enter>", hover_in)
            w.bind("<Leave>", hover_out)

        def lbl(texto, fuente, color):
            l = tk.Label(pub, text=texto, font=fuente,
                         bg="#FFD600", fg=color, cursor="hand2",
                         justify=tk.CENTER, wraplength=150)
            l.pack(pady=3, padx=4)
            l.bind("<Button-1>", abrir)
            l.bind("<Enter>", hover_in)
            l.bind("<Leave>", hover_out)
            return l

        lbl("PUBLICIDAD", ("Helvetica", 9, "bold"), "#33691E")
        lbl("ESCALA TU\nNEGOCIO", ("Helvetica", 15, "bold"), "#1B5E20")
        lbl("SELLFLOW\n24", ("Helvetica", 20, "bold"), "#E65100")
        lbl("Automatiza tus\nventas y crece\nal siguiente nivel", ("Helvetica", 9), "#33691E")
        lbl("HAZ CLIC AQUI >>>", ("Helvetica", 10, "bold"), "#1B5E20")

        return pub

    def crear_info_resumen(self, parent):
        t = self.tema
        info_frame = tk.Frame(parent, bg=t["panel_bg"], bd=1, relief=tk.SUNKEN)
        info_frame.pack(fill=tk.X, padx=20, pady=(5, 5), side=tk.BOTTOM)

        stats = self.obtener_estadisticas()

        def lbl(texto, bold=False, fg=None, padx=0):
            return tk.Label(info_frame, text=texto, bg=t["panel_bg"],
                            fg=fg or t["status_fg"],
                            font=("Helvetica", 10, "bold" if bold else "normal")
                            ).pack(side=tk.LEFT, padx=padx)

        tk.Label(info_frame, text="RESUMEN", bg=t["panel_bg"], fg=t["status_fg"],
                 font=("Helvetica", 10, "bold")).pack(side=tk.LEFT, padx=12)

        tk.Label(info_frame, text="Productos:", bg=t["panel_bg"], fg=t["status_fg"],
                 font=("Helvetica", 10)).pack(side=tk.LEFT, padx=(8, 3))
        tk.Label(info_frame, text=str(stats["productos"]), bg=t["panel_bg"], fg=t["title_fg"],
                 font=("Helvetica", 11, "bold")).pack(side=tk.LEFT)

        tk.Label(info_frame, text="Stock:", bg=t["panel_bg"], fg=t["status_fg"],
                 font=("Helvetica", 10)).pack(side=tk.LEFT, padx=(15, 3))
        tk.Label(info_frame, text=str(stats["stock_total"]), bg=t["panel_bg"], fg=t["title_fg"],
                 font=("Helvetica", 11, "bold")).pack(side=tk.LEFT)

        tk.Label(info_frame, text="Facturas:", bg=t["panel_bg"], fg=t["status_fg"],
                 font=("Helvetica", 10)).pack(side=tk.LEFT, padx=(15, 3))
        tk.Label(info_frame, text=str(stats["facturas"]), bg=t["panel_bg"], fg=t["title_fg"],
                 font=("Helvetica", 11, "bold")).pack(side=tk.LEFT)

        tk.Label(info_frame, text="Ventas:", bg=t["panel_bg"], fg=t["status_fg"],
                 font=("Helvetica", 10)).pack(side=tk.LEFT, padx=(15, 3))
        tk.Label(info_frame,
                 text=f"CRC {formatear_numero(stats['ventas_crc'])} / USD {formatear_dolares(stats['ventas_usd'])}",
                 bg=t["panel_bg"], fg=t["accent"],
                 font=("Helvetica", 10, "bold")).pack(side=tk.LEFT)

    def obtener_estadisticas(self):
        productos = ejecutar_select_one("SELECT COUNT(*) as cnt FROM productos WHERE activo = 1")
        facturas = ejecutar_select_one("SELECT COUNT(*) as cnt FROM facturas")
        ventas = ejecutar_select_one(
            "SELECT COALESCE(SUM(total), 0) as crc, COALESCE(SUM(total_usd), 0) as usd FROM facturas"
        )
        stock = ejecutar_select("""
            SELECT SUM(saldo_cantidad) as total FROM (
                SELECT producto_id, saldo_cantidad
                FROM kardex
                WHERE id IN (SELECT MAX(id) FROM kardex GROUP BY producto_id)
            )
        """)
        return {
            "productos": productos["cnt"] if productos else 0,
            "facturas": facturas["cnt"] if facturas else 0,
            "ventas_crc": ventas["crc"] if ventas else 0,
            "ventas_usd": ventas["usd"] if ventas else 0,
            "stock_total": int(stock[0]["total"]) if stock and stock[0]["total"] else 0
        }

    def crear_barra_estado(self):
        t = self.tema
        self.status_bar = tk.Frame(self.root, bg=t["status_bg"], height=28)
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        self.status_bar.pack_propagate(False)

        tc = obtener_tipo_cambio()
        tk.Label(self.status_bar,
                 text=f"  Conectado | TC: CRC {tc:,.2f}/USD | {fecha_actual()}",
                 bg=t["status_bg"], fg=t["status_fg"],
                 font=("Helvetica", 9)).pack(side=tk.LEFT, padx=10)

        tk.Label(self.status_bar, text=f"PINO SYSTEM v{APP_VERSION} | CRC Colones + USD Dolares  ",
                 bg=t["status_bg"], fg=t["status_accent"],
                 font=("Helvetica", 9, "bold")).pack(side=tk.RIGHT, padx=10)

    def mostrar_inicio(self):
        for widget in self.root.winfo_children():
            if isinstance(widget, tk.Frame) and widget != self.status_bar:
                widget.destroy()
        self.crear_widgets_principales()

    def abrir_productos(self):
        ProductosModulo(self.root)

    def abrir_kardex(self):
        KardexModulo(self.root)

    def abrir_facturacion(self):
        FacturacionModulo(self.root)

    def abrir_clientes(self):
        ClientesModulo(self.root, tipo="clientes")

    def abrir_proveedores(self):
        ClientesModulo(self.root, tipo="proveedores")

    def abrir_pos(self):
        VentasPOSModulo(self.root)

    def abrir_reportes(self):
        ReportesModulo(self.root)

    def abrir_configuracion(self):
        ConfiguracionModulo(self.root, callback=self.recargar_tema)

    def abrir_contabilidad(self):
        ContabilidadModulo(self.root)

    def abrir_reportes_graficos(self):
        ReportesGraficosModulo(self.root)

    def abrir_devoluciones(self):
        DevolucionesModulo(self.root)

    def abrir_pedidos(self):
        PedidosPendientesModulo(self.root)

    def abrir_series(self):
        SeriesLotesModulo(self.root)

    def verificar_actualizaciones(self):
        manual_check(self.root)

    def verificar_stock_bajo(self):
        """Verifica y muestra alertas de stock bajo al iniciar"""
        from database import ejecutar_select

        try:
            productos = ejecutar_select("""
                SELECT p.id, p.codigo, p.nombre, p.stock_minimo
                FROM productos p WHERE p.activo=1""")

            # Una sola consulta de stock actual por producto
            stocks = {}
            for r in ejecutar_select("""
                    SELECT producto_id, saldo_cantidad
                    FROM kardex
                    WHERE id IN (
                        SELECT MAX(id) FROM kardex GROUP BY producto_id
                    )"""):
                stocks[r["producto_id"]] = r["saldo_cantidad"]

            bajos = []
            for p in productos:
                stock = stocks.get(p["id"], 0)
                minimo = p["stock_minimo"] or 0
                if minimo and stock < minimo:
                    bajos.append((p["codigo"], p["nombre"], stock, minimo))

            if not bajos:
                return

            msg = "ALERTA DE STOCK BAJO\n\n"
            msg += f"Hay {len(bajos)} productos por debajo del minimo:\n\n"
            for cod, nom, stk, mini in bajos[:10]:
                msg += f"  {cod} - {nom}: {stk:.1f} (min: {mini:.1f})\n"
            if len(bajos) > 10:
                msg += f"\n  ... y {len(bajos)-10} mas"
            messagebox.showwarning("Stock Bajo", msg)
        except Exception:
            pass

    def _limpiar_versiones_viejas(self):
        try:
            cleanup_old_versions(keep_previous=1)
        except Exception:
            pass

    def acerca_de(self):
        messagebox.showinfo("Acerca de",
            f"PINO SYSTEM - Sistema de Inventario y Facturacion KARDEX\n"
            f"Version {APP_VERSION}\n\n"
            "Moneda Dual:\n"
            "  CRC - Colones de Costa Rica\n"
            "  USD - Dolares Americanos\n\n"
            "Desarrollado con Python + Tkinter + SQLite\n\n"
            "Funcionalidades:\n"
            "  - Productos con precios en CRC y USD\n"
            "  - Control Kardex con ambas monedas\n"
            "  - Facturacion con IVA configurable\n"
            "  - Clientes\n"
            "  - Reportes e Informes\n"
            "  - Descargar reportes e inventario en Excel (.xlsx)\n"
            "  - Reportes Graficos\n"
            "  - Temas de interfaz (Claro / Oscuro / Bosque)\n"
            "  - Auto-actualizacion (carpeta nueva + swap)\n\n"
            "Queres escalar tu proyecto al siguiente nivel?\n"
            "Visita: https://www.sellflow24.com/es/")

    def abrir_sellflow(self):
        webbrowser.open("https://www.sellflow24.com/es/")

    def salir(self):
        if messagebox.askyesno("Salir", "Desea salir del sistema?"):
            self.root.destroy()

    def ejecutar(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = AppMaderera()
    app.ejecutar()
