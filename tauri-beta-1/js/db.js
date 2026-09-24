const KEY = "pino_tauri_beta_v2";

const defaults = () => ({
  config: {
    tipo_cambio: 520,
    iva: 12,
    moneda_local: "CRC",
    simbolo_local: "CRC",
    theme: "claro",
    nombre_empresa: "Maderera CR",
    nit: "",
    telefono: "",
    direccion: "",
    email: "",
    sitio_web: "",
    invoice_header: "FACTURA",
    invoice_footer: "Gracias por su compra",
    invoice_watermark: "",
    invoice_color: "#1565C0",
    invoice_font_size: 12,
    invoice_paper: "carta",
    show_numero: 1,
    show_fecha: 1,
    show_nit: 1,
    show_cliente: 1,
    show_direccion: 1,
    show_telefono: 1,
    show_subtotal: 1,
    show_iva: 1,
    show_tc: 1,
    hidden_modules: [],
  },
  categorias: [
    { id: 1, nombre: "Madera Rolliza" },
    { id: 2, nombre: "Aserrada" },
    { id: 3, nombre: "Triplay" },
    { id: 4, nombre: "MDF" },
    { id: 5, nombre: "Melamina" },
    { id: 6, nombre: "Herramientas" },
    { id: 7, nombre: "Tornilleria" },
    { id: 8, nombre: "Barnices" },
    { id: 9, nombre: "Accesorios" },
  ],
  productos: [],
  clientes: [],
  proveedores: [],
  kardex: [],
  facturas: [],
  detalle_factura: [],
  movimientos_contables: [],
  pedidos_pendientes: [],
  series_lotes: [],
  seq: {
    producto: 1,
    cliente: 1,
    proveedor: 1,
    kardex: 1,
    factura: 1,
    mov: 1,
    pedido: 1,
    serie: 1,
  },
});

function seedDemo(db) {
  if (db.productos.length) return db;
  const prods = [
    ["M001", "Tablon pino 1x6", 2, "tablon", 8500, 18.5, 5],
    ["M002", "Rollizo 8cm x 3m", 1, "rollizo", 4200, 9.2, 12],
    ["T001", "Triplay 4x8 6mm", 3, "paquete", 12500, 26.0, 8],
    ["H001", "Clavos 2 pulg (kg)", 7, "kg", 3200, 7.1, 20],
  ];
  for (const [codigo, nombre, cat, und, compra, venta, min] of prods) {
    const id = db.seq.producto++;
    db.productos.push({
      id,
      codigo,
      nombre,
      descripcion: "",
      unidad_medida: und,
      categoria_id: cat,
      precio_compra: compra,
      precio_venta: Math.round(compra * 1.45),
      precio_compra_usd: compra / 520,
      precio_venta_usd: venta,
      stock_minimo: min,
      activo: 1,
      fecha_creacion: ahora(),
    });
    db.kardex.push({
      id: db.seq.kardex++,
      producto_id: id,
      tipo_movimiento: "ENTRADA",
      cantidad: min * 3,
      precio_unitario: compra,
      precio_unitario_usd: compra / 520,
      total: compra * min * 3,
      total_usd: (compra * min * 3) / 520,
      saldo_cantidad: min * 3,
      saldo_valor: compra * min * 3,
      saldo_valor_usd: (compra * min * 3) / 520,
      documento_ref: "SEED",
      proveedor_cliente: "Demo",
      descripcion: "Carga inicial",
      fecha: ahora(),
      usuario: "Admin",
    });
  }
  db.clientes.push({
    id: db.seq.cliente++,
    nit: "3012345678",
    nombre: "CONSUMIDOR FINAL",
    direccion: "",
    telefono: "",
    email: "",
    activo: 1,
  });
  return db;
}

function load() {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) return JSON.parse(raw);
    const seed = seedDemo(defaults());
    localStorage.setItem(KEY, JSON.stringify(seed));
    return seed;
  } catch {
    return seedDemo(defaults());
  }
}

function save(db) {
  localStorage.setItem(KEY, JSON.stringify(db));
  return db;
}

function resetAll() {
  const seed = seedDemo(defaults());
  localStorage.setItem(KEY, JSON.stringify(seed));
  return seed;
}

export const store = { load, save, resetAll, nextId(db, key) {
  const id = db.seq[key] || 1;
  db.seq[key] = id + 1;
  return id;
} };

export function stockDe(db, productoId) {
  const movs = db.kardex.filter((k) => k.producto_id === productoId);
  if (!movs.length) return 0;
  return movs[movs.length - 1].saldo_cantidad;
}

export function tc(db) {
  return Number(db.config.tipo_cambio) || 520;
}

export function ivaRate(db) {
  return (Number(db.config.iva) || 0) / 100;
}

export function crcToUsd(db, v) {
  return (Number(v) || 0) / tc(db);
}

export function usdToCrc(db, v) {
  return (Number(v) || 0) * tc(db);
}

export function fmtCrc(v) {
  return "CRC " + (Number(v) || 0).toLocaleString("es-CR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export function fmtUsd(v) {
  return "$" + (Number(v) || 0).toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export function fmtNum(v) {
  return (Number(v) || 0).toLocaleString("es-CR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export function ahora() {
  const d = new Date();
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

export function hoy() {
  const d = new Date();
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

export const THEMES = {
  claro: {
    root: "#1B5E20",
    panel: "#0D3D0D",
    tcBg: "#0D3D0D",
    tcFg: "#C8E6C9",
    title: "#FFFFFF",
    sub: "#A5D6A7",
    side: "#0D3D0D",
    accent: "#FFD54F",
    navActive: "#FF6F00",
  },
  oscuro: {
    root: "#121212",
    panel: "#000000",
    tcBg: "#1E1E1E",
    tcFg: "#B0BEC5",
    title: "#FFFFFF",
    sub: "#9E9E9E",
    side: "#000000",
    accent: "#FFD54F",
    navActive: "#43A047",
  },
  bosque: {
    root: "#1B4332",
    panel: "#081C15",
    tcBg: "#081C15",
    tcFg: "#D8F3DC",
    title: "#F1FAEE",
    sub: "#95D5B2",
    side: "#081C15",
    accent: "#FFB703",
    navActive: "#2D6A4F",
  },
};

export function applyTheme(id) {
  const t = THEMES[id] || THEMES.claro;
  const r = document.documentElement.style;
  r.setProperty("--root", t.root);
  r.setProperty("--panel", t.panel);
  r.setProperty("--tc-bg", t.tcBg);
  r.setProperty("--tc-fg", t.tcFg);
  r.setProperty("--title", t.title);
  r.setProperty("--sub", t.sub);
  r.setProperty("--side", t.side);
  r.setProperty("--accent", t.accent);
  r.setProperty("--nav-active", t.navActive);
}

export function exportCsv(filename, headers, rows) {
  const esc = (v) => {
    const s = String(v ?? "");
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const lines = [headers.map(esc).join(",")];
  for (const row of rows) lines.push(row.map(esc).join(","));
  const blob = new Blob(["\uFEFF" + lines.join("\n")], {
    type: "text/csv;charset=utf-8",
  });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}
