use rusqlite::{params, Connection, Result};
use serde::Serialize;
use std::fs;
use std::path::PathBuf;
use tauri::Manager;

#[derive(Serialize)]
struct SystemInfo {
    version: String,
    data_dir: String,
    db_path: String,
    runtime: String,
}

fn data_dir() -> PathBuf {
    if let Some(dir) = std::env::var_os("PINO_DATA_DIR") {
        return PathBuf::from(dir);
    }
    let base = dirs_data();
    let dir = base.join("PinoSystem").join("datos");
    let _ = fs::create_dir_all(&dir);
    dir
}

fn dirs_data() -> PathBuf {
    // Avoid extra crate: use platform convention
    if cfg!(windows) {
        if let Some(p) = std::env::var_os("LOCALAPPDATA") {
            return PathBuf::from(p);
        }
        PathBuf::from(".")
    } else if cfg!(target_os = "macos") {
        if let Some(home) = std::env::var_os("HOME") {
            return PathBuf::from(home).join("Library").join("Application Support");
        }
        PathBuf::from(".")
    } else {
        if let Some(home) = std::env::var_os("HOME") {
            return PathBuf::from(home).join(".local").join("share");
        }
        PathBuf::from(".")
    }
}

fn db_path() -> PathBuf {
    data_dir().join("pino_system.db")
}

fn open_db() -> Result<Connection> {
    let path = db_path();
    let conn = Connection::open(path)?;
    conn.execute_batch(
        "
        PRAGMA foreign_keys = ON;
        PRAGMA journal_mode = WAL;
        PRAGMA synchronous = NORMAL;
        ",
    )?;
    Ok(conn)
}

fn init_schema(conn: &Connection) -> Result<()> {
    conn.execute_batch(
        r#"
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

        CREATE TABLE IF NOT EXISTS configuracion (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            tipo_cambio REAL DEFAULT 520,
            moneda_local TEXT DEFAULT 'CRC',
            simbolo_local TEXT DEFAULT 'CRC',
            nombre_empresa TEXT,
            telefono TEXT,
            direccion TEXT,
            email TEXT,
            sitio_web TEXT,
            iva REAL DEFAULT 12,
            fecha_actualizacion TEXT
        );

        INSERT OR IGNORE INTO configuracion (id) VALUES (1);

        INSERT OR IGNORE INTO categorias (nombre) VALUES
            ('Madera Rolliza'), ('Aserrada'), ('Triplay'), ('MDF'),
            ('Melamina'), ('Herramientas'), ('Tornilleria'),
            ('Barnices'), ('Accesorios');

        INSERT OR IGNORE INTO clientes (nit, nombre, direccion, telefono, email, activo)
        VALUES ('', 'CONSUMIDOR FINAL', '', '', '', 1);

        CREATE TABLE IF NOT EXISTS proveedores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            nit TEXT,
            contacto TEXT,
            telefono TEXT,
            email TEXT,
            direccion TEXT,
            activo INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS movimientos_contables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT DEFAULT (datetime('now','localtime')),
            tipo TEXT NOT NULL CHECK(tipo IN ('INGRESO','GASTO')),
            categoria TEXT,
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
            cliente_nombre TEXT,
            producto_id INTEGER,
            producto_codigo TEXT,
            producto_nombre TEXT,
            cantidad_solicitada REAL DEFAULT 1,
            cantidad_entregada REAL DEFAULT 0,
            estado TEXT DEFAULT 'PENDIENTE',
            precio_unitario_crc REAL DEFAULT 0,
            precio_unitario_usd REAL DEFAULT 0,
            moneda TEXT DEFAULT 'CRC',
            observaciones TEXT,
            fecha_entrega_estimada TEXT,
            FOREIGN KEY (producto_id) REFERENCES productos(id)
        );

        CREATE TABLE IF NOT EXISTS series_lotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            producto_id INTEGER NOT NULL,
            numero_serie TEXT UNIQUE,
            lote TEXT,
            cantidad REAL DEFAULT 1,
            ubicacion TEXT,
            fecha_vencimiento TEXT,
            fecha_ingreso TEXT,
            estado TEXT DEFAULT 'DISPONIBLE',
            FOREIGN KEY (producto_id) REFERENCES productos(id)
        );
        "#,
    )?;
    Ok(())
}

#[tauri::command]
fn app_info() -> Result<SystemInfo, String> {
    let dir = data_dir();
    let db = db_path();
    Ok(SystemInfo {
        version: env!("CARGO_PKG_VERSION").to_string(),
        data_dir: dir.to_string_lossy().to_string(),
        db_path: db.to_string_lossy().to_string(),
        runtime: "tauri".to_string(),
    })
}

#[tauri::command]
fn db_exec(sql: String, values: Option<Vec<serde_json::Value>>) -> Result<u64, String> {
    let conn = open_db().map_err(|e| e.to_string())?;
    init_schema(&conn).map_err(|e| e.to_string())?;
    let upper = sql.trim().to_ascii_uppercase();
    if upper.starts_with("SELECT") {
        return Err("Use db_select for SELECT".into());
    }
    let vals = values.unwrap_or_default();
    let mut params: Vec<Box<dyn rusqlite::ToSql>> = Vec::new();
    for v in vals {
        match v {
            serde_json::Value::Null => params.push(Box::new(rusqlite::types::Value::Null)),
            serde_json::Value::Bool(b) => params.push(Box::new(b)),
            serde_json::Value::Number(n) => {
                if let Some(i) = n.as_i64() {
                    params.push(Box::new(i));
                } else if let Some(f) = n.as_f64() {
                    params.push(Box::new(f));
                } else {
                    return Err("Numero invalido".into());
                }
            }
            serde_json::Value::String(s) => params.push(Box::new(s)),
            other => params.push(Box::new(other.to_string())),
        }
    }
    let refs: Vec<&dyn rusqlite::ToSql> = params.iter().map(|b| b.as_ref()).collect();
    let n = conn
        .execute(&sql, refs.as_slice())
        .map_err(|e| e.to_string())?;
    Ok(n as u64)
}

#[tauri::command]
fn db_select(sql: String, values: Option<Vec<serde_json::Value>>) -> Result<Vec<serde_json::Value>, String> {
    let conn = open_db().map_err(|e| e.to_string())?;
    init_schema(&conn).map_err(|e| e.to_string())?;
    let vals = values.unwrap_or_default();
    let mut params: Vec<Box<dyn rusqlite::ToSql>> = Vec::new();
    for v in vals {
        match v {
            serde_json::Value::Null => params.push(Box::new(rusqlite::types::Value::Null)),
            serde_json::Value::Bool(b) => params.push(Box::new(b)),
            serde_json::Value::Number(n) => {
                if let Some(i) = n.as_i64() {
                    params.push(Box::new(i));
                } else if let Some(f) = n.as_f64() {
                    params.push(Box::new(f));
                } else {
                    return Err("Numero invalido".into());
                }
            }
            serde_json::Value::String(s) => params.push(Box::new(s)),
            other => params.push(Box::new(other.to_string())),
        }
    }
    let refs: Vec<&dyn rusqlite::ToSql> = params.iter().map(|b| b.as_ref()).collect();
    let mut stmt = conn.prepare(&sql).map_err(|e| e.to_string())?;
    let col_count = stmt.column_count();
    let mut rows = stmt.query(refs.as_slice()).map_err(|e| e.to_string())?;
    let mut out = Vec::new();
    while let Some(row) = rows.next().map_err(|e| e.to_string())? {
        let mut obj = serde_json::Map::new();
        for i in 0..col_count {
            let name = stmt.column_name(i).unwrap_or("col").to_string();
            let val: serde_json::Value = match row.get_ref(i) {
                Ok(rusqlite::types::ValueRef::Null) => serde_json::Value::Null,
                Ok(rusqlite::types::ValueRef::Integer(n)) => serde_json::Value::from(n),
                Ok(rusqlite::types::ValueRef::Real(f)) => serde_json::json!(f),
                Ok(rusqlite::types::ValueRef::Text(t)) => {
                    serde_json::Value::String(String::from_utf8_lossy(t).to_string())
                }
                Ok(rusqlite::types::ValueRef::Blob(b)) => {
                    serde_json::Value::String(format!("<blob {} bytes>", b.len()))
                }
                Err(e) => return Err(e.to_string()),
            };
            obj.insert(name, val);
        }
        out.push(serde_json::Value::Object(obj));
    }
    Ok(out)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_sql::Builder::default().build())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_process::init())
        .setup(|app| {
            let path = db_path();
            if let Ok(conn) = Connection::open(&path) {
                let _ = init_schema(&conn);
            }
            let _ = app.path().app_data_dir();
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![app_info, db_exec, db_select])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
