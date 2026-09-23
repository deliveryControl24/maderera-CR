import sqlite3
import os
import threading
from datetime import datetime
from config_paths import get_db_path, ensure_data_migration

DB_PATH = get_db_path()

# Conexion reutilizable por hilo (evita abrir/cerrar en cada query)
_local = threading.local()


def get_connection():
    conn = getattr(_local, "conn", None)
    if conn is not None:
        try:
            conn.execute("SELECT 1")
        except Exception:
            try:
                conn.close()
            except Exception:
                pass
            conn = None
            _local.conn = None
    if conn is None:
        conn = sqlite3.connect(DB_PATH, timeout=15.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA cache_size = -20000")  # ~20MB
        conn.execute("PRAGMA temp_store = MEMORY")
        conn.execute("PRAGMA mmap_size = 268435456")  # 256MB
        _local.conn = conn
    return conn


def close_connection():
    conn = getattr(_local, "conn", None)
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass
        _local.conn = None


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS categorias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            descripcion TEXT
        );

        CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT NOT NULL UNIQUE,
            nombre TEXT NOT NULL,
            descripcion TEXT,
            unidad_medida TEXT NOT NULL DEFAULT 'pieza',
            categoria_id INTEGER,
            precio_compra REAL DEFAULT 0,
            precio_venta REAL DEFAULT 0,
            precio_compra_usd REAL DEFAULT 0,
            precio_venta_usd REAL DEFAULT 0,
            stock_minimo REAL DEFAULT 0,
            activo INTEGER DEFAULT 1,
            fecha_creacion TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (categoria_id) REFERENCES categorias(id)
        );

        CREATE TABLE IF NOT EXISTS proveedores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nit TEXT UNIQUE,
            nombre TEXT NOT NULL,
            direccion TEXT,
            telefono TEXT,
            email TEXT,
            contacto TEXT,
            activo INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nit TEXT,
            nombre TEXT NOT NULL,
            direccion TEXT,
            telefono TEXT,
            email TEXT,
            activo INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS kardex (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            producto_id INTEGER NOT NULL,
            tipo_movimiento TEXT NOT NULL CHECK(tipo_movimiento IN ('ENTRADA','SALIDA')),
            cantidad REAL NOT NULL,
            precio_unitario REAL NOT NULL,
            precio_unitario_usd REAL DEFAULT 0,
            total REAL NOT NULL,
            total_usd REAL DEFAULT 0,
            saldo_cantidad REAL NOT NULL,
            saldo_valor REAL NOT NULL,
            saldo_valor_usd REAL DEFAULT 0,
            documento_ref TEXT,
            proveedor_cliente TEXT,
            descripcion TEXT,
            fecha TEXT DEFAULT (datetime('now','localtime')),
            usuario TEXT DEFAULT 'Admin',
            FOREIGN KEY (producto_id) REFERENCES productos(id)
        );

        CREATE TABLE IF NOT EXISTS facturas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero TEXT NOT NULL UNIQUE,
            cliente_id INTEGER,
            fecha TEXT DEFAULT (datetime('now','localtime')),
            moneda TEXT DEFAULT 'CRC',
            subtotal REAL DEFAULT 0,
            subtotal_usd REAL DEFAULT 0,
            impuesto REAL DEFAULT 0,
            impuesto_usd REAL DEFAULT 0,
            total REAL DEFAULT 0,
            total_usd REAL DEFAULT 0,
            tipo_cambio REAL DEFAULT 1,
            estado TEXT DEFAULT 'ACTIVA',
            observaciones TEXT,
            FOREIGN KEY (cliente_id) REFERENCES clientes(id)
        );

        CREATE TABLE IF NOT EXISTS detalle_factura (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            factura_id INTEGER NOT NULL,
            producto_id INTEGER NOT NULL,
            cantidad REAL NOT NULL,
            precio_unitario REAL NOT NULL,
            precio_unitario_usd REAL DEFAULT 0,
            total REAL NOT NULL,
            total_usd REAL DEFAULT 0,
            FOREIGN KEY (factura_id) REFERENCES facturas(id),
            FOREIGN KEY (producto_id) REFERENCES productos(id)
        );

        CREATE TABLE IF NOT EXISTS movimientos_contables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT DEFAULT (datetime('now','localtime')),
            tipo TEXT NOT NULL CHECK(tipo IN ('INGRESO', 'GASTO')),
            categoria TEXT NOT NULL,
            descripcion TEXT,
            monto_crc REAL DEFAULT 0,
            monto_usd REAL DEFAULT 0,
            documento_ref TEXT,
            proveedor_cliente TEXT,
            observaciones TEXT
        );

        CREATE TABLE IF NOT EXISTS pedidos_pendientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_pedido TEXT DEFAULT (datetime('now','localtime')),
            cliente_id INTEGER,
            cliente_nombre TEXT,
            producto_id INTEGER,
            producto_codigo TEXT,
            producto_nombre TEXT,
            cantidad_solicitada REAL DEFAULT 0,
            cantidad_entregada REAL DEFAULT 0,
            estado TEXT DEFAULT 'PENDIENTE' CHECK(estado IN ('PENDIENTE', 'PARCIAL', 'ENTREGADO', 'CANCELADO')),
            precio_unitario_crc REAL DEFAULT 0,
            precio_unitario_usd REAL DEFAULT 0,
            moneda TEXT DEFAULT 'CRC',
            observaciones TEXT,
            fecha_entrega_estimada TEXT,
            FOREIGN KEY (cliente_id) REFERENCES clientes(id),
            FOREIGN KEY (producto_id) REFERENCES productos(id)
        );

        CREATE TABLE IF NOT EXISTS series_lotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            producto_id INTEGER NOT NULL,
            numero_serie TEXT UNIQUE,
            lote TEXT,
            fecha_ingreso TEXT DEFAULT (datetime('now','localtime')),
            fecha_vencimiento TEXT,
            cantidad REAL DEFAULT 0,
            ubicacion TEXT,
            estado TEXT DEFAULT 'DISPONIBLE' CHECK(estado IN ('DISPONIBLE', 'RESERVADO', 'VENDIDO', 'VENCIDO')),
            FOREIGN KEY (producto_id) REFERENCES productos(id)
        );

        CREATE TABLE IF NOT EXISTS configuracion (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo_cambio REAL DEFAULT 520.0,
            moneda_local TEXT DEFAULT 'CRC',
            simbolo_local TEXT DEFAULT 'CRC',
            nombre_empresa TEXT DEFAULT 'PINO SYSTEM',
            telefono TEXT DEFAULT '',
            direccion TEXT DEFAULT '',
            email TEXT DEFAULT '',
            sitio_web TEXT DEFAULT '',
            iva REAL DEFAULT 12.0,
            fecha_actualizacion TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            nombre_completo TEXT,
            rol TEXT DEFAULT 'operador'
        );
    """)

    # Verificar si existe la tabla configuracion y si tiene datos
    try:
        existe = cursor.execute("SELECT COUNT(*) FROM configuracion").fetchone()[0]
        if existe == 0:
            cursor.execute(
                "INSERT INTO configuracion (tipo_cambio, moneda_local, simbolo_local, nombre_empresa) VALUES (?, ?, ?, ?)",
                (520.0, "CRC", "CRC", "PINO SYSTEM")
            )
    except sqlite3.OperationalError:
        # Si la tabla no existe, crearla
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS configuracion (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo_cambio REAL DEFAULT 520.0,
                moneda_local TEXT DEFAULT 'CRC',
                simbolo_local TEXT DEFAULT 'CRC',
                nombre_empresa TEXT DEFAULT 'PINO SYSTEM',
                telefono TEXT DEFAULT '',
                direccion TEXT DEFAULT '',
                email TEXT DEFAULT '',
                sitio_web TEXT DEFAULT '',
                iva REAL DEFAULT 12.0,
                fecha_actualizacion TEXT DEFAULT (datetime('now','localtime'))
            )
        """)
        cursor.execute(
            "INSERT INTO configuracion (tipo_cambio, moneda_local, simbolo_local, nombre_empresa) VALUES (?, ?, ?, ?)",
            (520.0, "CRC", "CRC", "PINO SYSTEM")
        )

    # Insertar categorias por defecto para pino system
    categorias_default = [
        ("Madera Rolliza", "Troncos y rollizos de diversas especies"),
        ("Madera Aserrada", "Tablas y tablones aserrados"),
        ("Triplay", "Láminas de triplay y contrachapado"),
        ("MDF", "Planchas de fibra de densidad media"),
        ("Melamina", "Planchas de melamina"),
        ("Herramientas", "Herramientas para carpintería"),
        ("Tornillería", "Tornillos, clavos y fijaciones"),
        ("Barnices y Pinturas", "Productos de acabado"),
        ("Accesorios", "Bisagras, manijas y accesorios"),
    ]

    for cat in categorias_default:
        try:
            cursor.execute("INSERT INTO categorias (nombre, descripcion) VALUES (?, ?)", cat)
        except sqlite3.IntegrityError:
            pass

    # Usuario admin por defecto
    try:
        cursor.execute(
            "INSERT INTO usuarios (usuario, password, nombre_completo, rol) VALUES (?, ?, ?, ?)",
            ("admin", "admin123", "Administrador", "admin")
        )
    except sqlite3.IntegrityError:
        pass

    conn.commit()

    # Indices para busquedas y stock (alto impacto con muchos movimientos)
    for idx_sql in (
        "CREATE INDEX IF NOT EXISTS idx_kardex_producto ON kardex(producto_id, id)",
        "CREATE INDEX IF NOT EXISTS idx_kardex_fecha ON kardex(fecha)",
        "CREATE INDEX IF NOT EXISTS idx_productos_nombre ON productos(nombre)",
        "CREATE INDEX IF NOT EXISTS idx_productos_codigo ON productos(codigo)",
        "CREATE INDEX IF NOT EXISTS idx_productos_activo ON productos(activo, nombre)",
        "CREATE INDEX IF NOT EXISTS idx_facturas_fecha ON facturas(fecha)",
        "CREATE INDEX IF NOT EXISTS idx_detalle_factura ON detalle_factura(factura_id)",
        "CREATE INDEX IF NOT EXISTS idx_clientes_nombre ON clientes(nombre)",
    ):
        try:
            cursor.execute(idx_sql)
        except sqlite3.OperationalError:
            pass

    conn.commit()
    # No cerrar: la conexion se reutiliza por hilo

    # Migrar tabla configuracion con nuevas columnas
    migrar_tabla_configuracion()


def migrar_tabla_configuracion():
    """Agrega columnas nuevas a la tabla configuracion si no existen"""
    conn = get_connection()
    cursor = conn.cursor()

    columnas_nuevas = [
        ("logo_path", "TEXT DEFAULT ''"),
        ("invoice_header", "TEXT DEFAULT ''"),
        ("invoice_footer", "TEXT DEFAULT 'Gracias por su compra!'"),
        ("invoice_watermark", "TEXT DEFAULT ''"),
        ("show_nit", "INTEGER DEFAULT 1"),
        ("show_cliente", "INTEGER DEFAULT 1"),
        ("show_direccion", "INTEGER DEFAULT 1"),
        ("show_telefono", "INTEGER DEFAULT 1"),
        ("show_email", "INTEGER DEFAULT 1"),
        ("show_sitio_web", "INTEGER DEFAULT 0"),
        ("show_iva", "INTEGER DEFAULT 1"),
        ("show_tc", "INTEGER DEFAULT 1"),
        ("show_subtotal", "INTEGER DEFAULT 1"),
        ("show_descuento", "INTEGER DEFAULT 0"),
        ("invoice_color", "TEXT DEFAULT '#1B5E20'"),
        ("invoice_font_size", "INTEGER DEFAULT 10"),
        ("invoice_paper_size", "TEXT DEFAULT 'ticket'"),
        ("invoice_margen", "INTEGER DEFAULT 5"),
        ("show_numero_factura", "INTEGER DEFAULT 1"),
        ("show_fecha", "INTEGER DEFAULT 1"),
        ("show_vendedor", "INTEGER DEFAULT 0"),
        ("show_condicion_pago", "INTEGER DEFAULT 1"),
        ("show_titulo_factura", "INTEGER DEFAULT 1"),
        ("titulo_factura_text", "TEXT DEFAULT 'FACTURA'"),
        ("show_codigo_producto", "INTEGER DEFAULT 1"),
        ("show_unidad_medida", "INTEGER DEFAULT 0"),
        ("show_precio_unitario", "INTEGER DEFAULT 1"),
        ("show_descuento_producto", "INTEGER DEFAULT 0"),
        ("nit", "TEXT DEFAULT ''"),
    ]

    for columna, tipo in columnas_nuevas:
        try:
            cursor.execute(f"ALTER TABLE configuracion ADD COLUMN {columna} {tipo}")
        except sqlite3.OperationalError:
            pass  # Columna ya existe

    conn.commit()


# Cache corta de config (evita abrir DB en cada formato de precio/IVA)
_config_cache = {"data": None, "ts": 0.0}
_CONFIG_TTL = 20.0  # segundos


def obtener_config_completa(use_cache=True):
    """Obtiene toda la configuracion incluyendo campos de factura"""
    import time
    if use_cache and _config_cache["data"] is not None:
        if time.time() - _config_cache["ts"] < _CONFIG_TTL:
            return _config_cache["data"]
    config = ejecutar_select_one("SELECT * FROM configuracion WHERE id=1")
    if not config:
        config = {}
    _config_cache["data"] = config
    _config_cache["ts"] = time.time()
    return config


def invalidar_cache_config():
    _config_cache["data"] = None
    _config_cache["ts"] = 0.0


def obtener_tipo_cambio():
    config = obtener_config_completa()
    return config["tipo_cambio"] if config and config.get("tipo_cambio") is not None else 520.0


def actualizar_tipo_cambio(tipo_cambio):
    ejecutar_consulta(
        "UPDATE configuracion SET tipo_cambio = ?, fecha_actualizacion = datetime('now','localtime') WHERE id = 1",
        (tipo_cambio,)
    )
    invalidar_cache_config()


def obtener_stocks_actuales():
    """Retorna {producto_id: saldo} en una sola consulta."""
    filas = ejecutar_select("""
        SELECT producto_id, saldo_cantidad
        FROM kardex
        WHERE id IN (SELECT MAX(id) FROM kardex GROUP BY producto_id)
    """)
    return {r["producto_id"]: r["saldo_cantidad"] for r in filas}


def ejecutar_consulta(sql, params=()):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(sql, params)
    conn.commit()
    return cursor.lastrowid


def ejecutar_select(sql, params=()):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(sql, params)
    return [dict(row) for row in cursor.fetchall()]


def ejecutar_select_one(sql, params=()):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(sql, params)
    row = cursor.fetchone()
    return dict(row) if row else None


def calcular_costo_promedio(producto_id):
    """Calcula el costo promedio ponderado de un producto basado en entradas"""
    movs = ejecutar_select("""
        SELECT cantidad, precio_unitario, precio_unitario_usd
        FROM kardex
        WHERE producto_id=? AND tipo_movimiento='ENTRADA'
        ORDER BY id""", (producto_id,))
    
    if not movs:
        return 0, 0
    
    total_cant = 0
    total_valor_crc = 0
    total_valor_usd = 0
    
    for m in movs:
        total_cant += m["cantidad"]
        total_valor_crc += m["cantidad"] * m["precio_unitario"]
        total_valor_usd += m["cantidad"] * (m["precio_unitario_usd"] or 0)
    
    if total_cant == 0:
        return 0, 0
    
    costo_crc = total_valor_crc / total_cant
    costo_usd = total_valor_usd / total_cant
    
    return round(costo_crc, 2), round(costo_usd, 2)


def calcular_costo_ultimate(producto_id):
    """Calcula el costo usando el ultimo precio de entrada"""
    mov = ejecutar_select_one("""
        SELECT precio_unitario, precio_unitario_usd
        FROM kardex
        WHERE producto_id=? AND tipo_movimiento='ENTRADA'
        ORDER BY id DESC LIMIT 1""", (producto_id,))
    
    if not mov:
        return 0, 0
    
    return mov["precio_unitario"], mov["precio_unitario_usd"] or 0


def calcular_margen_venta(producto_id):
    """Calcula el margen de ganancia por producto"""
    prod = ejecutar_select_one(
        "SELECT precio_compra, precio_venta, precio_compra_usd, precio_venta_usd FROM productos WHERE id=?",
        (producto_id,))
    
    if not prod or prod["precio_compra"] == 0:
        return 0, 0
    
    margen_crc = ((prod["precio_venta"] - prod["precio_compra"]) / prod["precio_compra"]) * 100
    margen_usd = 0
    if prod["precio_compra_usd"] and prod["precio_compra_usd"] > 0:
        margen_usd = ((prod["precio_venta_usd"] - prod["precio_compra_usd"]) / prod["precio_compra_usd"]) * 100
    
    return round(margen_crc, 2), round(margen_usd, 2)


def actualizar_costos_automaticos():
    """Actualiza precios de compra con costo promedio en una sola pasada SQL."""
    filas = ejecutar_select("""
        SELECT producto_id AS id,
               CASE WHEN SUM(cantidad) > 0
                    THEN SUM(cantidad * precio_unitario) / SUM(cantidad)
                    ELSE 0 END AS costo_crc,
               CASE WHEN SUM(cantidad) > 0
                    THEN SUM(cantidad * precio_unitario_usd) / SUM(cantidad)
                    ELSE 0 END AS costo_usd
        FROM kardex
        WHERE tipo_movimiento = 'ENTRADA'
        GROUP BY producto_id
    """)
    actualizados = 0
    conn = get_connection()
    cur = conn.cursor()
    for r in filas:
        if r["costo_crc"] and r["costo_crc"] > 0:
            cur.execute(
                "UPDATE productos SET precio_compra=?, precio_compra_usd=? WHERE id=?",
                (round(r["costo_crc"], 2), round(r["costo_usd"] or 0, 2), r["id"]),
            )
            actualizados += 1
    conn.commit()
    return actualizados


def obtener_reporte_costos():
    """Genera reporte de costos por producto (sin N+1)."""
    productos = ejecutar_select("""
        SELECT p.id, p.codigo, p.nombre, p.precio_compra, p.precio_venta,
               p.precio_compra_usd, p.precio_venta_usd,
               COALESCE(ap.prom_crc, 0) AS costo_promedio_crc,
               COALESCE(ap.prom_usd, 0) AS costo_promedio_usd,
               COALESCE(ult.ult_crc, 0) AS costo_ultimo_crc,
               COALESCE(ult.ult_usd, 0) AS costo_ultimo_usd
        FROM productos p
        LEFT JOIN (
            SELECT producto_id,
                   SUM(cantidad * precio_unitario) / NULLIF(SUM(cantidad), 0) AS prom_crc,
                   SUM(cantidad * precio_unitario_usd) / NULLIF(SUM(cantidad), 0) AS prom_usd
            FROM kardex
            WHERE tipo_movimiento = 'ENTRADA'
            GROUP BY producto_id
        ) ap ON ap.producto_id = p.id
        LEFT JOIN (
            SELECT k.producto_id, k.precio_unitario AS ult_crc, k.precio_unitario_usd AS ult_usd
            FROM kardex k
            JOIN (
                SELECT producto_id, MAX(id) AS mid
                FROM kardex
                WHERE tipo_movimiento = 'ENTRADA'
                GROUP BY producto_id
            ) m ON m.mid = k.id
        ) ult ON ult.producto_id = p.id
        WHERE p.activo = 1
        ORDER BY p.nombre
    """)

    reporte = []
    for p in productos:
        pc = p["precio_compra"] or 0
        pv = p["precio_venta"] or 0
        pcu = p["precio_compra_usd"] or 0
        pvu = p["precio_venta_usd"] or 0
        margen_crc = ((pv - pc) / pc * 100) if pc else 0
        margen_usd = ((pvu - pcu) / pcu * 100) if pcu else 0
        reporte.append({
            "codigo": p["codigo"],
            "nombre": p["nombre"],
            "precio_compra": pc,
            "precio_venta": pv,
            "costo_promedio_crc": round(p["costo_promedio_crc"] or 0, 2),
            "costo_promedio_usd": round(p["costo_promedio_usd"] or 0, 2),
            "costo_ultimo_crc": round(p["costo_ultimo_crc"] or 0, 2),
            "costo_ultimo_usd": round(p["costo_ultimo_usd"] or 0, 2),
            "margen_crc": round(margen_crc, 2),
            "margen_usd": round(margen_usd, 2),
        })
    return reporte
