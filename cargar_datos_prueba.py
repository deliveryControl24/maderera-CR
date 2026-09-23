import sqlite3
import os
import random
from datetime import datetime, timedelta
from config_paths import get_db_path, get_datos_dir

def crear_datos_prueba():
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print(f"Base de datos: {db_path}")
    
    # Verificar si ya hay datos
    cursor.execute("SELECT COUNT(*) FROM productos")
    count = cursor.fetchone()[0]
    if count > 0:
        print(f"Ya existen {count} productos.")
        return
    
    # Crear categorias
    categorias = [
        ("Madera Solida", "Madera en tablas, tablones y rollizos"),
        ("Madera Contrachapada", "Paneles contrachapados various"),
        ("MDF", "Planchas MDF various"),
        ("Triplay", "Hojas de triplay various"),
        ("Rollizos", "Rollizos para construcción"),
        ("Postes", "Postes y varillas"),
        ("Tela Impermeable", "Lona y tela impermeable"),
        ("Herramientas", "Herramientas de carpintería"),
        ("Tornilleria", "Tornillos, clavos y fijaciones"),
        ("Pinturas", "Pinturas y barnices"),
        (" selladores", "Silicona y selladores"),
        ("Aislantes", "Materiales de aislamiento"),
        ("Perfiles Metalicos", "Perfiles de acero y aluminio"),
        ("Pisos", "Pisos laminados y vinílicos"),
        ("Techos", "Materiales para techumbre"),
    ]
    
    for nombre, desc in categorias:
        cursor.execute("INSERT OR IGNORE INTO categorias (nombre, descripcion) VALUES (?, ?)", (nombre, desc))
    
    print(f"Creadas {len(categorias)} categorias")
    
    # Listas de maderas y productos
    maderas = [
        "Pino", "Cedro", "Roble", "Aliso", "Cypress", "Melina", "Laurel", 
        "Nogal", "Caoba", "Pinabete", "Encino", "Sauce", "Olmo", "Fresno",
        " Abedul", "Cerezo", "Haya", "Tilo", "Abeto", "Sicomoro"
    ]
    
    presentaciones = [
        ("Tabla", "pieza"), ("Tablon", "pieza"), ("Rollo", "pieza"),
        ("Plancha", "pieza"), ("Varilla", "pieza"), ("Poste", "pieza"),
        ("Panel", "pieza"), ("Lamina", "pieza"), ("Tira", "pieza"),
        ("Bloque", "pieza"), ("Pieza", "pieza"), ("Paquete", "paquete"),
        ("Metro Lineal", "ml"), ("Metro Cuadrado", "m2"), ("Kilogramo", "kg")
    ]
    
    grosores = [1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10, 12, 15, 18, 22, 25, 30, 40, 50]
    anchos = [10, 15, 20, 25, 30, 40, 50, 60, 75, 90, 100, 120, 150, 200]
    largos = [100, 120, 150, 180, 200, 240, 250, 300, 360, 400, 480]
    
    proveedores = [
        ("1234567890", "Maderas del Norte S.A.", "Cartago", "2222-3333", "norte@maderas.com"),
        ("2345678901", "Maderera Central", "San José", "2222-4444", "central@maderas.com"),
        ("3456789012", "Maderas del Sur", "Limón", "2222-5555", "sur@maderas.com"),
        ("4567890123", "Maderera del Caribe", "Limón", "2222-6666", "caribe@maderas.com"),
        ("5678901234", "Maderas Tropicales", "Puntarenas", "2222-7777", "tropicales@maderas.com"),
        ("6789012345", "Importadora de Maderas", "San José", "2222-8888", "importadora@maderas.com"),
        ("7890123456", "Maderera La Fortuna", "Alajuela", "2222-9999", "fortuna@maderas.com"),
        ("8901234567", "Maderas del Oeste", "Guanacaste", "2222-0000", "oeste@maderas.com"),
    ]
    
    for nit, nombre, dir, tel, email in proveedores:
        cursor.execute(
            "INSERT OR IGNORE INTO proveedores (nit, nombre, direccion, telefono, email) VALUES (?, ?, ?, ?, ?)",
            (nit, nombre, dir, tel, email)
        )
    
    print(f"Creados {len(proveedores)} proveedores")
    
    clientes = [
        ("1111111111", "Constructora ABC", "San José", "2222-1111", "abc@constructora.com"),
        ("2222222222", "Mueblería El Roble", "Cartago", "2222-2222", "elroble@muebles.com"),
        ("3333333333", "Carpintería Tica", "Alajuela", "2222-3333", "tica@carpinteria.com"),
        ("4444444444", "Construcciones López", "Heredia", "2222-4444", "lopez@construcciones.com"),
        ("5555555555", "Muebles del Este", "Limón", "2222-5555", "este@muebles.com"),
        ("6666666666", "Ferretería Central", "San José", "2222-6666", "central@ferreteria.com"),
        ("7777777777", "Constructora Norte", "Cartago", "2222-7777", "norte@constructora.com"),
        ("8888888888", "Maderera Tica", "Alajuela", "2222-8888", "tica@maderera.com"),
        ("9999999999", "Carpintería Artesanal", "Heredia", "2222-9999", "artesanal@carpinteria.com"),
        ("1010101010", "Constructora del Sur", "San José", "2222-0101", "sur@constructora.com"),
    ]
    
    for nit, nombre, dir, tel, email in clientes:
        cursor.execute(
            "INSERT OR IGNORE INTO clientes (nit, nombre, direccion, telefono, email) VALUES (?, ?, ?, ?, ?)",
            (nit, nombre, dir, tel, email)
        )
    
    print(f"Creados {len(clientes)} clientes")
    
    # Generar 400 productos
    productos_creados = 0
    tc = 520.0
    
    for i in range(1, 401):
        madera = random.choice(maderas)
        presentacion, unidad = random.choice(presentaciones)
        grosor = random.choice(grosores)
        ancho = random.choice(anchos)
        largo = random.choice(largos)
        cat_id = random.randint(1, len(categorias))
        
        # Generar codigo
        codigo = f"MT-{i:04d}"
        
        # Nombre descriptivo
        nombre = f"{madera} {presentacion} {grosor}x{ancho}x{largo}"
        
        # Precios (CRC)
        precio_compra_crc = round(random.uniform(500, 50000), 2)
        precio_venta_crc = round(precio_compra_crc * random.uniform(1.2, 1.8), 2)
        
        # Precios USD
        precio_compra_usd = round(precio_compra_crc / tc, 2)
        precio_venta_usd = round(precio_venta_crc / tc, 2)
        
        # Stock minimo
        stock_min = round(random.uniform(5, 100), 1)
        
        # Insertar producto
        cursor.execute("""
            INSERT OR IGNORE INTO productos (codigo, nombre, descripcion, unidad_medida, categoria_id,
                precio_compra, precio_venta, precio_compra_usd, precio_venta_usd, stock_minimo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (codigo, nombre, f"{madera} {presentacion} grosor {grosor}mm ancho {ancho}mm largo {largo}mm",
              unidad, cat_id, precio_compra_crc, precio_venta_crc, precio_compra_usd, precio_venta_usd, stock_min))
        
        producto_id = cursor.lastrowid
        
        # Generar movimientos kardex (2-5 movimientos por producto)
        num_movimientos = random.randint(2, 5)
        saldo_cant = 0
        saldo_valor_crc = 0
        saldo_valor_usd = 0
        
        fecha_base = datetime(2025, 1, 1)
        
        for j in range(num_movimientos):
            fecha = fecha_base + timedelta(days=random.randint(0, 600))
            fecha_str = fecha.strftime("%Y-%m-%d %H:%M:%S")
            
            tipo = "ENTRADA" if j == 0 or random.random() > 0.3 else "SALIDA"
            
            if tipo == "ENTRADA":
                cantidad = round(random.uniform(10, 200), 1)
                p_unit_crc = precio_compra_crc
                p_unit_usd = precio_compra_usd
            else:
                cantidad = round(random.uniform(5, min(50, saldo_cant if saldo_cant > 0 else 50)), 1)
                if cantidad > saldo_cant:
                    cantidad = round(saldo_cant * 0.5, 1) if saldo_cant > 0 else 10
                p_unit_crc = precio_venta_crc
                p_unit_usd = precio_venta_usd
            
            total_crc = round(cantidad * p_unit_crc, 2)
            total_usd = round(cantidad * p_unit_usd, 2)
            
            if tipo == "ENTRADA":
                saldo_cant = round(saldo_cant + cantidad, 1)
                saldo_valor_crc = round(saldo_valor_crc + total_crc, 2)
                saldo_valor_usd = round(saldo_valor_usd + total_usd, 2)
            else:
                saldo_cant = round(saldo_cant - cantidad, 1)
                saldo_valor_crc = round(saldo_valor_crc - total_crc, 2)
                saldo_valor_usd = round(saldo_valor_usd - total_usd, 2)
            
            proveedor = random.choice([p[1] for p in proveedores])
            descripcion = f"{'Ingreso' if tipo == 'ENTRADA' else 'Salida'} de inventario"
            doc_ref = f"DOC-{random.randint(1000, 9999)}"
            
            cursor.execute("""
                INSERT INTO kardex (producto_id, fecha, tipo_movimiento, cantidad,
                    precio_unitario, precio_unitario_usd, total, total_usd,
                    saldo_cantidad, saldo_valor, saldo_valor_usd,
                    documento_ref, proveedor_cliente, descripcion)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (producto_id, fecha_str, tipo, cantidad,
                  p_unit_crc, p_unit_usd, total_crc, total_usd,
                  saldo_cant, saldo_valor_crc, saldo_valor_usd,
                  doc_ref, proveedor, descripcion))
        
        productos_creados += 1
        if productos_creados % 50 == 0:
            print(f"  Productos creados: {productos_creados}/400")
    
    conn.commit()
    
    # Verificar
    cursor.execute("SELECT COUNT(*) FROM productos")
    total_prod = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM kardex")
    total_kardex = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM clientes")
    total_clientes = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM proveedores")
    total_prov = cursor.fetchone()[0]
    
    print(f"\n=== DATOS CREADOS ===")
    print(f"Productos: {total_prod}")
    print(f"Movimientos Kardex: {total_kardex}")
    print(f"Clientes: {total_clientes}")
    print(f"Proveedores: {total_prov}")
    print(f"Categorias: {len(categorias)}")
    
    conn.close()
    print("\nListo! Puede abrir la aplicacion.")

if __name__ == "__main__":
    crear_datos_prueba()
