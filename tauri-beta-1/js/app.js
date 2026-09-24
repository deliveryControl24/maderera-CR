import {
  store,
  stockDe,
  tc,
  ivaRate,
  crcToUsd,
  usdToCrc,
  fmtCrc,
  fmtUsd,
  fmtNum,
  ahora,
  hoy,
  applyTheme,
  exportCsv,
} from "./db.js";

const APP_VERSION = "1.0.0-beta.1";
const MODULE_IDS = [
  "pos", "productos", "kardex", "facturacion", "clientes",
  "proveedores", "contabilidad", "pedidos", "devoluciones",
  "series", "reportes", "graficos", "config",
];

let db = store.load();
let posCart = [];
let posMoneda = "CRC";
let facLines = [];
let selectedProdId = null;
let selectedCliId = null;
let selectedProvId = null;
let selectedPedId = null;
let selectedSerId = null;
let lastReport = { headers: [], rows: [], name: "reporte.csv" };
let lowStockDismissed = false;

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

function toast(msg, kind = "ok") {
  const el = $("#toast");
  el.textContent = msg;
  el.className = `toast ${kind}`;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.classList.add("hidden"), 2800);
  $("#statusMsg").textContent = msg;
}

function setView(name) {
  $$(".view").forEach((v) => v.classList.remove("active"));
  $$(".nav-btn").forEach((b) => b.classList.remove("active"));
  const view = $("#view-" + name);
  if (view) view.classList.add("active");
  const nav = $(`.nav-btn[data-view="${name}"]`);
  if (nav) nav.classList.add("active");
  renderAll();
}

function isTauri() {
  return !!(window.__TAURI__ || window.__TAURI_INTERNALS__);
}

function applyHiddenModules() {
  const hidden = new Set(db.config.hidden_modules || []);
  $$(".nav-btn, .tile").forEach((el) => {
    const id = el.dataset.view;
    if (!id || id === "home") return;
    el.classList.toggle("hidden-mod", hidden.has(id));
    if (hidden.has(id)) el.style.display = "none";
    else el.style.display = "";
  });
}

function refreshChrome() {
  const rate = tc(db);
  $("#tcBanner").textContent = `TC ${rate.toFixed(2)}`;
  $("#tcHome").textContent = rate.toFixed(2);
  $("#versionPill").textContent = APP_VERSION;
  $("#runtimePill").textContent = isTauri() ? "Tauri" : "Web (localStorage)";
  $("#statusClock").textContent = new Date().toLocaleString("es-CR");
  applyTheme(db.config.theme || "claro");
}

function renderKpis() {
  const productos = db.productos.filter((p) => p.activo !== 0);
  const stock = productos.reduce((s, p) => s + stockDe(db, p.id), 0);
  const facturas = db.facturas.length;
  const ventas = db.facturas.reduce(
    (s, f) => s + (f.moneda === "USD" ? usdToCrc(db, f.total) : f.total),
    0
  );
  const ing = (db.movimientos_contables || [])
    .filter((m) => m.tipo === "INGRESO")
    .reduce((s, m) => s + (m.monto_crc || 0), 0);
  const gas = (db.movimientos_contables || [])
    .filter((m) => m.tipo === "GASTO")
    .reduce((s, m) => s + (m.monto_crc || 0), 0);
  const items = [
    ["Productos", productos.length],
    ["Stock total", stock.toFixed(2)],
    ["Facturas", facturas],
    ["Ventas CRC", fmtCrc(ventas)],
    ["Clientes", db.clientes.filter((c) => c.activo !== 0).length],
    ["Proveedores", (db.proveedores || []).filter((c) => c.activo !== 0).length],
    ["Balance CRC", fmtCrc(ing - gas)],
    ["Mov. Kardex", db.kardex.length],
    ["Pedidos abiertos", (db.pedidos_pendientes || []).filter((p) => p.estado !== "CANCELADO" && p.estado !== "ENTREGADO").length],
  ];
  const html = items
    .map(([label, value]) => `<div class="kpi"><span>${label}</span><strong>${value}</strong></div>`)
    .join("");
  $("#kpis").innerHTML = html;
  $("#summaryGrid").innerHTML = html;
}

function maybeLowStock() {
  if (lowStockDismissed) return;
  const list = db.productos
    .filter((p) => p.activo !== 0)
    .map((p) => ({ p, st: stockDe(db, p.id) }))
    .filter((x) => x.st <= (x.p.stock_minimo || 0))
    .sort((a, b) => a.st - b.st)
    .slice(0, 10);
  const box = $("#lowStockAlert");
  if (!list.length) {
    box.classList.add("hidden");
    return;
  }
  box.classList.remove("hidden");
  $("#lowStockList").innerHTML = list
    .map((x) => {
      const estado = x.st <= 0 ? "CRITICO" : "BAJO";
      return `<li>[${estado}] ${x.p.codigo} ${x.p.nombre} — stock ${x.st} / min ${x.p.stock_minimo}</li>`;
    })
    .join("");
}

function fillSelects() {
  const cats = db.categorias
    .map((c) => `<option value="${c.id}">${c.nombre}</option>`)
    .join("");
  const catSel = $("#prodCategoria");
  const prevCat = catSel.value;
  catSel.innerHTML = cats;
  if (prevCat) catSel.value = prevCat;

  const activos = db.productos.filter((p) => p.activo !== 0);
  const prodOpts = activos
    .map(
      (p) =>
        `<option value="${p.id}">${p.codigo} - ${p.nombre} (stock ${stockDe(db, p.id)})</option>`
    )
    .join("");
  ["#kardexProducto", "#facProducto", "#kardexFilter", "#pedProducto", "#serProducto"].forEach((sel) => {
    const el = $(sel);
    if (!el) return;
    const prev = el.value;
    const head = sel === "#kardexFilter" ? `<option value="">Todos los productos</option>` : "";
    el.innerHTML = head + prodOpts;
    if (prev) el.value = prev;
  });

  const clientes = db.clientes.filter((c) => c.activo !== 0);
  const cliOpts = clientes.map((c) => `<option value="${c.id}">${c.nombre}</option>`).join("");
  $("#facCliente").innerHTML = cliOpts;

  const factOpts = [...db.facturas]
    .reverse()
    .map((f) => `<option value="${f.numero}">${f.numero}</option>`)
    .join("");
  const devFac = $("#devFactura");
  const prevFac = devFac.value;
  devFac.innerHTML = factOpts || `<option value="">Sin facturas</option>`;
  if (prevFac) devFac.value = prevFac;
  fillDevProductos();
}

function fillDevProductos() {
  const num = $("#devFactura").value;
  const el = $("#devProducto");
  if (!num) {
    el.innerHTML = `<option value="">Seleccione factura</option>`;
    return;
  }
  const f = db.facturas.find((x) => x.numero === num);
  if (!f) {
    el.innerHTML = `<option value="">Sin detalle</option>`;
    return;
  }
  const items = db.detalle_factura.filter((d) => d.factura_numero === num);
  el.innerHTML =
    items
      .map((d) => {
        const p = db.productos.find((x) => x.id === d.producto_id);
        return `<option value="${d.producto_id}">${p ? p.codigo + " - " + p.nombre : d.producto_id}</option>`;
      })
      .join("") || `<option value="">Sin productos</option>`;
}

function renderProductos() {
  const q = ($("#prodSearch").value || "").toLowerCase();
  $("#prodTable tbody").innerHTML = db.productos
    .filter((p) => p.activo !== 0)
    .filter((p) => !q || p.codigo.toLowerCase().includes(q) || p.nombre.toLowerCase().includes(q))
    .map((p) => {
      const cat = db.categorias.find((c) => c.id === p.categoria_id);
      return `<tr data-id="${p.id}" class="${selectedProdId === p.id ? "selected" : ""}">
        <td>${p.codigo}</td><td>${p.nombre}</td><td>${cat ? cat.nombre : "-"}</td>
        <td>${p.unidad_medida}</td>
        <td class="num">${fmtCrc(p.precio_venta)}</td>
        <td class="num">${fmtUsd(p.precio_venta_usd)}</td>
        <td class="num">${stockDe(db, p.id)}</td><td class="num">${p.stock_minimo}</td>
      </tr>`;
    })
    .join("");
}

function loadProdForm(p) {
  const f = $("#prodForm");
  f.reset();
  f.id.value = p ? p.id : "";
  if (!p) return;
  f.codigo.value = p.codigo;
  f.nombre.value = p.nombre;
  f.categoria_id.value = p.categoria_id || "";
  f.unidad_medida.value = p.unidad_medida || "pieza";
  f.precio_compra.value = p.precio_compra;
  f.precio_venta.value = p.precio_venta;
  f.precio_compra_usd.value = p.precio_compra_usd;
  f.precio_venta_usd.value = p.precio_venta_usd;
  f.stock_minimo.value = p.stock_minimo;
  f.descripcion.value = p.descripcion || "";
}

function renderClientes() {
  $("#cliTable tbody").innerHTML = db.clientes
    .filter((c) => c.activo !== 0)
    .map(
      (c) => `<tr data-id="${c.id}" class="${selectedCliId === c.id ? "selected" : ""}">
      <td>${c.nit || "-"}</td><td>${c.nombre}</td><td>${c.direccion || "-"}</td>
      <td>${c.telefono || "-"}</td><td>${c.email || "-"}</td></tr>`
    )
    .join("");
}

function loadCliForm(c) {
  const f = $("#cliForm");
  f.reset();
  f.id.value = c ? c.id : "";
  if (!c) return;
  f.nit.value = c.nit || "";
  f.nombre.value = c.nombre || "";
  f.direccion.value = c.direccion || "";
  f.telefono.value = c.telefono || "";
  f.email.value = c.email || "";
}

function renderProveedores() {
  $("#provTable tbody").innerHTML = (db.proveedores || [])
    .filter((c) => c.activo !== 0)
    .map(
      (c) => `<tr data-id="${c.id}" class="${selectedProvId === c.id ? "selected" : ""}">
      <td>${c.nit || "-"}</td><td>${c.nombre}</td><td>${c.direccion || "-"}</td>
      <td>${c.telefono || "-"}</td><td>${c.email || "-"}</td><td>${c.contacto || "-"}</td></tr>`
    )
    .join("");
}

function loadProvForm(c) {
  const f = $("#provForm");
  f.reset();
  f.id.value = c ? c.id : "";
  if (!c) return;
  f.nit.value = c.nit || "";
  f.nombre.value = c.nombre || "";
  f.direccion.value = c.direccion || "";
  f.telefono.value = c.telefono || "";
  f.email.value = c.email || "";
  f.contacto.value = c.contacto || "";
}

function renderKardex() {
  const filter = $("#kardexFilter").value;
  const rows = [...db.kardex]
    .filter((k) => !filter || k.producto_id === Number(filter))
    .reverse();
  $("#kardexTable tbody").innerHTML = rows
    .map((k) => {
      const p = db.productos.find((x) => x.id === k.producto_id);
      const tipo = k.tipo_movimiento === "ENTRADA" ? "E" : "S";
      return `<tr>
        <td>${k.fecha}</td><td>${tipo}</td><td>${p ? p.nombre : k.producto_id}</td>
        <td class="num">${k.cantidad}</td><td class="num">${fmtCrc(k.precio_unitario)}</td>
        <td class="num">${fmtCrc(k.total)}</td><td class="num">${k.saldo_cantidad}</td>
        <td>${k.documento_ref || ""}</td><td>${k.descripcion || ""}</td></tr>`;
    })
    .join("");
}

function renderPos() {
  const q = ($("#posSearch").value || "").toLowerCase();
  $("#posTable tbody").innerHTML = db.productos
    .filter((p) => p.activo !== 0)
    .filter((p) => !q || p.codigo.toLowerCase().includes(q) || p.nombre.toLowerCase().includes(q))
    .slice(0, 40)
    .map((p) => {
      const st = stockDe(db, p.id);
      return `<tr data-id="${p.id}">
        <td>${p.codigo}</td><td>${p.nombre}</td>
        <td class="num">${fmtCrc(p.precio_venta)}</td>
        <td class="num">${fmtUsd(p.precio_venta_usd)}</td>
        <td class="num">${st}</td>
        <td><button class="btn" data-add="${p.id}">+</button></td></tr>`;
    })
    .join("");
  renderCart();
}

function renderCart() {
  $("#cartTable tbody").innerHTML = posCart
    .map((line, i) => {
      const p = db.productos.find((x) => x.id === line.producto_id);
      return `<tr>
        <td>${p ? p.nombre : line.producto_id}</td>
        <td class="num">${line.cantidad}</td>
        <td class="num">${posMoneda === "CRC" ? fmtCrc(line.precio_unitario) : fmtUsd(line.precio_unitario_usd)}</td>
        <td class="num">${posMoneda === "CRC" ? fmtCrc(line.total) : fmtUsd(line.total_usd)}</td>
        <td><button class="btn danger" data-rm="${i}">x</button></td></tr>`;
    })
    .join("");
  const rate = ivaRate(db);
  const sub = posCart.reduce((s, l) => s + (posMoneda === "CRC" ? l.total : l.total_usd), 0);
  const iva = sub * rate;
  const f = (v) => (posMoneda === "CRC" ? fmtCrc(v) : fmtUsd(v));
  $("#posSubtotal").textContent = f(sub);
  $("#posIva").textContent = f(iva);
  $("#posTotal").textContent = f(sub + iva);
}

function addToCart(productoId) {
  const p = db.productos.find((x) => x.id === productoId);
  if (!p) return;
  const inCart = posCart.filter((l) => l.producto_id === productoId).reduce((s, l) => s + l.cantidad, 0);
  const st = stockDe(db, productoId);
  if (inCart + 1 > st) {
    toast(`Stock insuficiente (disponible ${st})`, "err");
    return;
  }
  const exist = posCart.find((l) => l.producto_id === productoId);
  const priceCrc = Number(p.precio_venta) || 0;
  const priceUsd = Number(p.precio_venta_usd) || 0;
  if (exist) {
    exist.cantidad += 1;
    exist.total = exist.cantidad * priceCrc;
    exist.total_usd = exist.cantidad * priceUsd;
  } else {
    posCart.push({
      producto_id: productoId,
      cantidad: 1,
      precio_unitario: priceCrc,
      precio_unitario_usd: priceUsd,
      total: priceCrc,
      total_usd: priceUsd,
    });
  }
  renderCart();
}

function invConfig() {
  const c = db.config;
  const g = (k, d = 1) => (c[k] === undefined ? d : Number(c[k]));
  return {
    header: c.invoice_header || "FACTURA",
    footer: c.invoice_footer || "Gracias por su compra",
    watermark: c.invoice_watermark || "",
    color: c.invoice_color || "#1565C0",
    font: Number(c.invoice_font_size) || 12,
    paper: c.invoice_paper || "carta",
    show: {
      numero: g("show_numero"),
      fecha: g("show_fecha"),
      nit: g("show_nit"),
      cliente: g("show_cliente"),
      direccion: g("show_direccion"),
      telefono: g("show_telefono"),
      subtotal: g("show_subtotal"),
      iva: g("show_iva"),
      tc: g("show_tc"),
    },
  };
}

function buildTicketText(factura, detalles, { cotizacion = false } = {}) {
  const cfg = invConfig();
  const emp = db.config;
  const width = cfg.paper === "ticket" ? 42 : 68;
  const line = (ch = "-") => ch.repeat(width);
  const center = (s) => {
    const pad = Math.max(0, Math.floor((width - s.length) / 2));
    return " ".repeat(pad) + s;
  };
  const rows = [];
  rows.push(center(emp.nombre_empresa || "PINO SYSTEM"));
  if (emp.nit) rows.push(center(`NIT ${emp.nit}`));
  if (emp.direccion) rows.push(center(emp.direccion));
  if (emp.telefono) rows.push(center(emp.telefono));
  rows.push(line("="));
  rows.push(center(cotizacion ? "COTIZACION" : cfg.header));
  rows.push(line());
  if (cfg.show.numero && factura.numero) rows.push(`No: ${factura.numero}`);
  if (cfg.show.fecha) rows.push(`Fecha: ${factura.fecha}`);
  if (cfg.show.cliente) rows.push(`Cliente: ${factura.cliente_nombre || "CONSUMIDOR FINAL"}`);
  if (cfg.show.nit && factura.nit) rows.push(`NIT: ${factura.nit}`);
  if (cfg.show.direccion && factura.direccion) rows.push(`Dir: ${factura.direccion}`);
  if (cfg.show.telefono && factura.telefono) rows.push(`Tel: ${factura.telefono}`);
  rows.push(line());
  rows.push(
    `${"Cant".padStart(6)} ${"Producto".padEnd(18)} ${"P.Unit".padStart(12)} ${"Total".padStart(12)}`
  );
  rows.push(line());
  let sub = 0;
  let subUsd = 0;
  for (const d of detalles) {
    const p = db.productos.find((x) => x.id === d.producto_id);
    const name = (p ? p.nombre : "?").slice(0, 18);
    const total = d.total;
    sub += total;
    subUsd += d.total_usd;
    rows.push(
      `${String(d.cantidad).padStart(6)} ${name.padEnd(18)} ${fmtNum(d.precio_unitario).padStart(12)} ${fmtNum(total).padStart(12)}`
    );
  }
  rows.push(line());
  const mon = factura.moneda || "CRC";
  const iva = ivaRate(db);
  if (invConfig().show.subtotal) {
    rows.push(`${"Subtotal".padEnd(width - 14)}${(mon === "CRC" ? fmtNum(sub) : fmtNum(subUsd)).padStart(14)}`);
  }
  if (invConfig().show.iva) {
    rows.push(`${`IVA ${(iva * 100).toFixed(0)}%`.padEnd(width - 14)}${(mon === "CRC" ? fmtNum(sub * (1 + 0)) : fmtNum(subUsd)).padStart(14)}`);
    rows[rows.length - 1] =
      `${`IVA ${(iva * 100).toFixed(0)}%`.padEnd(width - 14)}${(mon === "CRC" ? fmtNum(sub * iva) : fmtNum(subUsd * iva)).padStart(14)}`;
  }
  const total = mon === "CRC" ? sub + sub * iva : subUsd + subUsd * iva;
  rows.push(`${"TOTAL".padEnd(width - 14)}${(mon === "CRC" ? fmtNum(total) : fmtNum(total)).padStart(14)} ${mon}`);
  if (invConfig().show.tc) rows.push(`TC: ${tc(db).toFixed(2)}`);
  rows.push(line("="));
  if (cfg.watermark) rows.push(center(cfg.watermark));
  rows.push(center(cfg.footer));
  if (cotizacion) {
    rows.push("");
    rows.push(center("Cotizacion valida por 7 dias"));
  }
  return rows.join("\n");
}

function openPrint(title, body) {
  $("#printTitle").textContent = title;
  $("#printBody").textContent = body;
  $("#printModal").classList.remove("hidden");
}

function cobrar() {
  if (!posCart.length) {
    toast("El carrito esta vacio", "err");
    return;
  }
  const rate = tc(db);
  const ivaR = ivaRate(db);
  const idFac = store.nextId(db, "factura");
  const numero = "FAC-" + String(idFac).padStart(6, "0");
  const sub = posCart.reduce((s, l) => s + l.total, 0);
  const subUsd = posCart.reduce((s, l) => s + l.total_usd, 0);
  const moneda = posMoneda;
  const subtotal = moneda === "CRC" ? sub : subUsd;
  const subtotalUsd = moneda === "USD" ? subUsd : crcToUsd(db, sub);
  const imp = subtotal * ivaR;
  const impUsd = subtotalUsd * ivaR;
  const cliente = db.clientes.find((c) => c.id === Number($("#facCliente").value)) ||
    db.clientes.find((c) => c.activo !== 0) || { id: null, nombre: "CONSUMIDOR FINAL" };

  const factura = {
    id: idFac,
    numero,
    cliente_id: cliente.id,
    cliente_nombre: cliente.nombre,
    fecha: ahora(),
    moneda,
    subtotal,
    subtotal_usd: subtotalUsd,
    impuesto: imp,
    impuesto_usd: impUsd,
    total: subtotal + imp,
    total_usd: subtotalUsd + impUsd,
    tipo_cambio: rate,
    estado: "ACTIVA",
    observaciones: "Venta POS",
  };
  db.facturas.push(factura);

  for (const line of posCart) {
    db.detalle_factura.push({
      id: db.detalle_factura.length + 1,
      factura_numero: numero,
      producto_id: line.producto_id,
      cantidad: line.cantidad,
      precio_unitario: line.precio_unitario,
      precio_unitario_usd: line.precio_unitario_usd,
      total: line.total,
      total_usd: line.total_usd,
    });
    aplicarKardex(line.producto_id, "SALIDA", line.cantidad, line.precio_unitario, "Venta POS");
  }

  store.save(db);
  const detalles = [...posCart];
  posCart = [];
  toast(`Venta registrada: ${numero}`);
  openPrint("Ticket / Factura", buildTicketText(factura, detalles));
  renderAll();
}

function cotizar() {
  if (!posCart.length) {
    toast("Carrito vacio para cotizar", "err");
    return;
  }
  const fake = {
    numero: "COT-" + String(Date.now()).slice(-6),
    fecha: ahora(),
    cliente_nombre: "Cliente cotizacion",
    moneda: posMoneda,
  };
  openPrint("Cotizacion", buildTicketText(fake, posCart, { cotizacion: true }));
}

function aplicarKardex(productoId, tipo, cantidad, precio, nota = "") {
  const price = Number(precio) || 0;
  const priceUsd = crcToUsd(db, price);
  const anteriores = db.kardex.filter((k) => k.producto_id === productoId);
  const prev = anteriores[anteriores.length - 1];
  const prevSaldo = prev ? prev.saldo_cantidad : 0;
  const prevValor = prev ? prev.saldo_valor : 0;
  const prevUsd = prev ? prev.saldo_valor_usd : 0;
  const delta = tipo === "ENTRADA" ? cantidad : -cantidad;
  const saldo = prevSaldo + delta;
  if (saldo < 0) throw new Error("Stock insuficiente para SALIDA");
  const movValor = cantidad * price;
  const valor = tipo === "ENTRADA" ? prevValor + movValor : Math.max(0, prevValor - movValor);
  const valorUsd =
    tipo === "ENTRADA" ? prevUsd + crcToUsd(db, movValor) : Math.max(0, prevUsd - crcToUsd(db, movValor));

  db.kardex.push({
    id: store.nextId(db, "kardex"),
    producto_id: productoId,
    tipo_movimiento: tipo,
    cantidad,
    precio_unitario: price,
    precio_unitario_usd: priceUsd,
    total: cantidad * price,
    total_usd: cantidad * priceUsd,
    saldo_cantidad: saldo,
    saldo_valor: valor,
    saldo_valor_usd: valorUsd,
    documento_ref: "",
    proveedor_cliente: "",
    descripcion: nota,
    fecha: ahora(),
    usuario: "Admin",
  });
}

function renderFacturas() {
  $("#facListTable tbody").innerHTML = [...db.facturas]
    .reverse()
    .map(
      (f) => `<tr data-num="${f.numero}">
      <td>${f.numero}</td><td>${f.fecha}</td>
      <td>${f.cliente_nombre || f.cliente_id || "-"}</td><td>${f.moneda}</td>
      <td class="num">${f.moneda === "CRC" ? fmtCrc(f.total) : fmtUsd(f.total_usd)}</td>
      <td>${f.estado}</td>
      <td><button class="btn" data-viewfac="${f.numero}">Ver</button></td></tr>`
    )
    .join("");
  renderFacLines();
}

function renderFacLines() {
  $("#facTable tbody").innerHTML = facLines
    .map((line, i) => {
      const p = db.productos.find((x) => x.id === line.producto_id);
      const mon = $("#facMoneda").value;
      return `<tr>
        <td>${p ? p.nombre : line.producto_id}</td>
        <td class="num">${line.cantidad}</td>
        <td class="num">${mon === "CRC" ? fmtCrc(line.precio_unitario) : fmtUsd(line.precio_unitario_usd)}</td>
        <td class="num">${mon === "CRC" ? fmtCrc(line.total) : fmtUsd(line.total_usd)}</td>
        <td><button class="btn danger" data-rmfac="${i}">x</button></td></tr>`;
    })
    .join("");
  const mon = $("#facMoneda").value;
  const rate = ivaRate(db);
  const sub = facLines.reduce((s, l) => s + (mon === "CRC" ? l.total : l.total_usd), 0);
  const iva = sub * rate;
  $("#facSubtotal").textContent = mon === "CRC" ? fmtCrc(sub) : fmtUsd(sub);
  $("#facIva").textContent = mon === "CRC" ? fmtCrc(iva) : fmtUsd(iva);
  $("#facTotal").textContent = mon === "CRC" ? fmtCrc(sub + iva) : fmtUsd(sub + iva);
}

function guardarFactura() {
  if (!facLines.length) {
    toast("Agregue al menos una linea", "err");
    return;
  }
  try {
    const mon = $("#facMoneda").value;
    const ivaR = ivaRate(db);
    const clienteId = Number($("#facCliente").value);
    const cliente = db.clientes.find((c) => c.id === clienteId);
    const idFac = store.nextId(db, "factura");
    const numero = "FAC-" + String(idFac).padStart(6, "0");
    const sub = facLines.reduce((s, l) => s + (mon === "CRC" ? l.total : l.total_usd), 0);
    const subUsd = mon === "USD" ? sub : crcToUsd(db, sub);
    const imp = sub * ivaR;
    const impUsd = subUsd * ivaR;

    for (const line of facLines) {
      const p = db.productos.find((x) => x.id === line.producto_id);
      const available = stockDe(db, line.producto_id);
      if (line.cantidad > available) {
        throw new Error(`Stock insuficiente para ${p ? p.nombre : line.producto_id}`);
      }
      aplicarKardex(line.producto_id, "SALIDA", line.cantidad, line.precio_unitario, `Factura ${numero}`);
      db.detalle_factura.push({
        id: db.detalle_factura.length + 1,
        factura_numero: numero,
        producto_id: line.producto_id,
        cantidad: line.cantidad,
        precio_unitario: line.precio_unitario,
        precio_unitario_usd: line.precio_unitario_usd,
        total: line.total,
        total_usd: line.total_usd,
      });
    }

    const factura = {
      id: idFac,
      numero,
      cliente_id: clienteId,
      cliente_nombre: cliente ? cliente.nombre : "",
      fecha: ahora(),
      moneda: mon,
      subtotal: sub,
      subtotal_usd: subUsd,
      impuesto: imp,
      impuesto_usd: impUsd,
      total: sub + imp,
      total_usd: subUsd + impUsd,
      tipo_cambio: tc(db),
      estado: "ACTIVA",
      observaciones: "",
      nit: cliente ? cliente.nit : "",
      direccion: cliente ? cliente.direccion : "",
      telefono: cliente ? cliente.telefono : "",
    };
    db.facturas.push(factura);
    store.save(db);
    const detalles = [...facLines];
    facLines = [];
    toast(`Factura guardada: ${numero}`);
    openPrint("Factura", buildTicketText(factura, detalles));
    renderAll();
  } catch (e) {
    toast(e.message || "No se pudo guardar", "err");
  }
}

function renderContabilidad() {
  const filtro = $("#contFilter").value;
  const q = ($("#contSearch").value || "").toLowerCase();
  const rows = [...(db.movimientos_contables || [])]
    .filter((m) => !filtro || m.tipo === filtro)
    .filter(
      (m) =>
        !q ||
        (m.descripcion || "").toLowerCase().includes(q) ||
        (m.categoria || "").toLowerCase().includes(q) ||
        (m.proveedor_cliente || "").toLowerCase().includes(q)
    )
    .reverse();

  let ingC = 0, ingU = 0, gasC = 0, gasU = 0;
  for (const m of db.movimientos_contables || []) {
    if (m.tipo === "INGRESO") {
      ingC += m.monto_crc || 0;
      ingU += m.monto_usd || 0;
    } else {
      gasC += m.monto_crc || 0;
      gasU += m.monto_usd || 0;
    }
  }
  $("#contResumen").innerHTML = `
    <div class="kpi ok"><span>Ingresos</span><strong>${fmtCrc(ingC)}</strong><span>USD ${fmtNum(ingU)}</span></div>
    <div class="kpi bad"><span>Gastos</span><strong>${fmtCrc(gasC)}</strong><span>USD ${fmtNum(gasU)}</span></div>
    <div class="kpi"><span>Balance</span><strong>${fmtCrc(ingC - gasC)}</strong><span>USD ${fmtNum(ingU - gasU)}</span></div>`;

  $("#contTable tbody").innerHTML = rows
    .map(
      (m) => `<tr>
      <td>${(m.fecha || "").slice(0, 16)}</td><td>${m.tipo}</td><td>${m.categoria || ""}</td>
      <td>${m.descripcion || ""}</td><td class="num">${fmtCrc(m.monto_crc)}</td>
      <td class="num">${fmtUsd(m.monto_usd)}</td><td>${m.documento_ref || ""}</td>
      <td>${m.proveedor_cliente || ""}</td></tr>`
    )
    .join("");
}

function renderPedidos() {
  $("#pedTable tbody").innerHTML = (db.pedidos_pendientes || [])
    .filter((p) => p.estado !== "CANCELADO")
    .slice()
    .reverse()
    .map(
      (p) => `<tr data-id="${p.id}" class="${selectedPedId === p.id ? "selected" : ""}">
      <td>${p.id}</td><td>${(p.fecha_pedido || "").slice(0, 16)}</td>
      <td>${p.cliente_nombre || ""}</td><td>${p.producto_nombre || ""}</td>
      <td class="num">${p.cantidad_solicitada}</td><td class="num">${p.cantidad_entregada || 0}</td>
      <td>${p.estado}</td><td>${p.fecha_entrega_estimada || ""}</td></tr>`
    )
    .join("");
}

function renderDevoluciones() {
  const devs = (db.movimientos_contables || [])
    .filter((m) => m.categoria === "Devolucion")
    .reverse();
  $("#devTable tbody").innerHTML = devs
    .map(
      (d) => `<tr>
      <td>${(d.fecha || "").slice(0, 16)}</td><td>${d.documento_ref || ""}</td>
      <td>${d.proveedor_cliente || ""}</td><td>${d.descripcion || ""}</td>
      <td>REGISTRADA</td></tr>`
    )
    .join("");
}

function renderSeries() {
  $("#serTable tbody").innerHTML = (db.series_lotes || [])
    .slice()
    .reverse()
    .map((s) => {
      const p = db.productos.find((x) => x.id === s.producto_id);
      return `<tr data-id="${s.id}" class="${selectedSerId === s.id ? "selected" : ""}">
        <td>${s.id}</td>
        <td>${p ? p.codigo + " - " + p.nombre : s.producto_id}</td>
        <td>${s.numero_serie || ""}</td><td>${s.lote || ""}</td>
        <td class="num">${s.cantidad}</td><td>${s.ubicacion || ""}</td>
        <td>${s.fecha_vencimiento || ""}</td><td>${s.estado || "DISPONIBLE"}</td></tr>`;
    })
    .join("");
}

function renderConfig() {
  const c = db.config;
  const g = $("#cfgForm");
  g.tipo_cambio.value = c.tipo_cambio;
  g.iva.value = c.iva;
  g.moneda_local.value = c.moneda_local || "CRC";
  g.simbolo_local.value = c.simbolo_local || "CRC";
  g.theme.value = c.theme || "claro";

  const e = $("#cfgEmpresa");
  e.nombre_empresa.value = c.nombre_empresa || "";
  e.nit.value = c.nit || "";
  e.telefono.value = c.telefono || "";
  e.direccion.value = c.direccion || "";
  e.email.value = c.email || "";
  e.sitio_web.value = c.sitio_web || "";

  const f = $("#cfgFactura");
  f.invoice_header.value = c.invoice_header || "FACTURA";
  f.invoice_footer.value = c.invoice_footer || "";
  f.invoice_watermark.value = c.invoice_watermark || "";
  f.invoice_color.value = c.invoice_color || "#1565C0";
  f.invoice_font_size.value = c.invoice_font_size || 12;
  f.invoice_paper.value = c.invoice_paper || "carta";
  ["show_numero", "show_fecha", "show_nit", "show_cliente", "show_direccion",
   "show_telefono", "show_subtotal", "show_iva", "show_tc"].forEach((name) => {
    f[name].checked = Number(c[name] ?? 1) === 1;
  });

  const hidden = new Set(c.hidden_modules || []);
  $("#modToggles").innerHTML = MODULE_IDS.map(
    (id) => `
    <label class="span-2" style="flex-direction:row;align-items:center;gap:8px;color:var(--text);font-size:13px">
      <input type="checkbox" data-mod="${id}" ${hidden.has(id) ? "" : "checked"} />
      ${id}
    </label>`
  ).join("");

  $("#cfgSystemInfo").textContent =
    `Version ${APP_VERSION} · Runtime ${isTauri() ? "Tauri" : "Web"} · Productos ${db.productos.length} · Facturas ${db.facturas.length} · Clientes ${db.clientes.length} · Datos en localStorage (beta)`;
}

function runReport(kind) {
  const out = $("#repOut");
  let text = "";
  let headers = [];
  let rows = [];
  let name = "reporte.csv";

  if (kind === "inventario") {
    text += "INVENTARIO ACTUAL\n" + "=".repeat(72) + "\n";
    headers = ["codigo", "nombre", "unidad", "stock", "min", "p_venta_crc", "p_venta_usd"];
    for (const p of db.productos.filter((x) => x.activo !== 0)) {
      const st = stockDe(db, p.id);
      text += `${p.codigo.padEnd(12)} ${p.nombre.slice(0, 28).padEnd(30)} stock=${st} min=${p.stock_minimo}\n`;
      rows.push([p.codigo, p.nombre, p.unidad_medida, st, p.stock_minimo, p.precio_venta, p.precio_venta_usd]);
    }
    name = "inventario.csv";
  } else if (kind === "stock_bajo") {
    text += "STOCK BAJO MINIMO\n" + "=".repeat(72) + "\n";
    headers = ["estado", "codigo", "nombre", "stock", "min"];
    for (const p of db.productos.filter((x) => x.activo !== 0)) {
      const st = stockDe(db, p.id);
      if (st <= p.stock_minimo) {
        const estado = st <= 0 ? "CRITICO" : "BAJO";
        text += `[${estado}] ${p.codigo} ${p.nombre} stock=${st} min=${p.stock_minimo}\n`;
        rows.push([estado, p.codigo, p.nombre, st, p.stock_minimo]);
      }
    }
    name = "stock_bajo.csv";
  } else if (kind === "kardex") {
    text += "KARDEX GENERAL\n" + "=".repeat(72) + "\n";
    headers = ["fecha", "tipo", "codigo", "cantidad", "saldo"];
    for (const k of [...db.kardex].reverse().slice(0, 80)) {
      const p = db.productos.find((x) => x.id === k.producto_id);
      text += `${k.fecha} ${k.tipo_movimiento.padEnd(7)} ${(p ? p.codigo : "").padEnd(10)} cant=${k.cantidad} saldo=${k.saldo_cantidad}\n`;
      rows.push([k.fecha, k.tipo_movimiento, p ? p.codigo : "", k.cantidad, k.saldo_cantidad]);
    }
    name = "kardex.csv";
  } else if (kind === "ventas") {
    text += "VENTAS / FACTURAS\n" + "=".repeat(72) + "\n";
    headers = ["numero", "fecha", "cliente", "moneda", "total", "total_usd"];
    for (const f of [...db.facturas].reverse()) {
      text += `${f.numero} ${f.fecha} ${f.moneda} total=${f.moneda === "CRC" ? fmtCrc(f.total) : fmtUsd(f.total_usd)} ${f.cliente_nombre || ""}\n`;
      rows.push([f.numero, f.fecha, f.cliente_nombre || "", f.moneda, f.total, f.total_usd]);
    }
    const totalCrc = db.facturas.reduce(
      (s, f) => s + (f.moneda === "USD" ? usdToCrc(db, f.total) : f.total),
      0
    );
    text += `\nTOTAL estimado: ${fmtCrc(totalCrc)}\n`;
    name = "ventas.csv";
  } else if (kind === "proveedores") {
    text += "MOV. PROVEEDORES / CLIENTES (KARDEX)\n" + "=".repeat(72) + "\n";
    const map = {};
    for (const k of db.kardex) {
      const key = k.proveedor_cliente || "(sin referencia)";
      if (!map[key]) map[key] = { entradas: 0, salidas: 0 };
      if (k.tipo_movimiento === "ENTRADA") map[key].entradas += k.cantidad;
      else map[key].salidas += k.cantidad;
    }
    headers = ["referencia", "entradas", "salidas"];
    for (const [k, v] of Object.entries(map)) {
      text += `${k.padEnd(30)} E=${v.entradas} S=${v.salidas}\n`;
      rows.push([k, v.entradas, v.salidas]);
    }
    name = "mov_proveedores.csv";
  } else if (kind === "costos") {
    text += "ANALISIS DE COSTOS\n" + "=".repeat(72) + "\n";
    headers = ["codigo", "compra_crc", "venta_crc", "margen_pct", "compra_usd", "venta_usd"];
    for (const p of db.productos.filter((x) => x.activo !== 0)) {
      const compra = Number(p.precio_compra) || 0;
      const venta = Number(p.precio_venta) || 0;
      const margen = compra > 0 ? ((venta - compra) / compra) * 100 : 0;
      text += `${p.codigo.padEnd(12)} compra=${fmtCrc(compra)} venta=${fmtCrc(venta)} margen=${margen.toFixed(1)}%\n`;
      rows.push([p.codigo, compra, venta, margen.toFixed(1), p.precio_compra_usd, p.precio_venta_usd]);
    }
    name = "costos.csv";
  }

  out.textContent = text || "Sin datos.";
  lastReport = { headers, rows, name };
}

function barChart(container, items, colorClass = "") {
  const max = Math.max(...items.map((i) => Number(i.value) || 0), 1);
  container.innerHTML = items
    .map((i) => {
      const pct = ((Number(i.value) || 0) / max) * 100;
      return `<div class="bar-row">
        <div>${i.label}</div>
        <div class="bar-track"><div class="bar-fill ${colorClass}" style="width:${pct}%"></div></div>
        <div class="num">${i.display ?? i.value}</div>
      </div>`;
    })
    .join("");
}

function runGrafico(kind) {
  const box = $("#grafOut");
  if (kind === "ventas_mes") {
    const map = {};
    for (const f of db.facturas) {
      const mes = (f.fecha || "").slice(0, 7) || "s/f";
      const crc = f.moneda === "USD" ? usdToCrc(db, f.total) : f.total;
      map[mes] = (map[mes] || 0) + (crc || 0);
    }
    const items = Object.entries(map).map(([label, value]) => ({
      label,
      value,
      display: fmtNum(value),
    }));
    if (!items.length) {
      box.innerHTML = `<p class="hint">No hay datos de ventas</p>`;
      return;
    }
    barChart(box, items);
  } else if (kind === "top") {
    const map = {};
    for (const d of db.detalle_factura) {
      const p = db.productos.find((x) => x.id === d.producto_id);
      const name = p ? p.nombre.slice(0, 24) : String(d.producto_id);
      map[name] = (map[name] || 0) + (d.cantidad || 0);
    }
    const items = Object.entries(map)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10)
      .map(([label, value]) => ({ label, value }));
    if (!items.length) {
      box.innerHTML = `<p class="hint">No hay datos de ventas</p>`;
      return;
    }
    barChart(box, items, "green");
  } else if (kind === "ing_gasto") {
    const ing = (db.movimientos_contables || [])
      .filter((m) => m.tipo === "INGRESO")
      .reduce((s, m) => s + (m.monto_crc || 0), 0);
    const gas = (db.movimientos_contables || [])
      .filter((m) => m.tipo === "GASTO")
      .reduce((s, m) => s + (m.monto_crc || 0), 0);
    if (!ing && !gas) {
      box.innerHTML = `<p class="hint">No hay datos contables</p>`;
      return;
    }
    box.innerHTML = `
      <div class="bar-row"><div>Ingresos</div>
        <div class="bar-track"><div class="bar-fill green" style="width:${(ing / Math.max(ing, gas, 1)) * 100}%"></div></div>
        <div class="num">${fmtNum(ing)}</div></div>
      <div class="bar-row"><div>Gastos</div>
        <div class="bar-track"><div class="bar-fill red" style="width:${(gas / Math.max(ing, gas, 1)) * 100}%"></div></div>
        <div class="num">${fmtNum(gas)}</div></div>
      <p class="hint">Balance: ${fmtCrc(ing - gas)}</p>`;
  } else if (kind === "stock_cat") {
    const map = {};
    for (const p of db.productos.filter((x) => x.activo !== 0)) {
      const cat = db.categorias.find((c) => c.id === p.categoria_id);
      const name = cat ? cat.nombre : "Sin categoria";
      map[name] = (map[name] || 0) + 1;
    }
    const colors = ["#1565C0", "#2E7D32", "#C62828", "#6A1B9A", "#E65100", "#00838F", "#4527A0", "#AD1457", "#37474F"];
    const entries = Object.entries(map).sort((a, b) => b[1] - a[1]);
    if (!entries.length) {
      box.innerHTML = `<p class="hint">No hay datos</p>`;
      return;
    }
    box.innerHTML = `
      ${entries
        .map(([label, value], i) => {
          const total = entries.reduce((s, e) => s + e[1], 0) || 1;
          const pct = (value / total) * 100;
          return `<div class="bar-row">
            <div>${label}</div>
            <div class="bar-track"><div class="bar-fill" style="width:${pct}%;background:${colors[i % colors.length]}"></div></div>
            <div class="num">${value} (${pct.toFixed(1)}%)</div>
          </div>`;
        })
        .join("")}
      <div class="pie-legend">${entries
        .map(
          ([label], i) =>
            `<span><i class="swatch" style="background:${colors[i % colors.length]}"></i>${label}</span>`
        )
        .join("")}</div>`;
  } else if (kind === "moneda") {
    const map = { CRC: 0, USD: 0 };
    for (const f of db.facturas) map[f.moneda] = (map[f.moneda] || 0) + 1;
    if (!map.CRC && !map.USD) {
      box.innerHTML = `<p class="hint">No hay datos de ventas</p>`;
      return;
    }
    barChart(box, [
      { label: "CRC", value: map.CRC || 0 },
      { label: "USD", value: map.USD || 0 },
    ], "purple");
  }
}

function renderAll() {
  refreshChrome();
  renderKpis();
  maybeLowStock();
  applyHiddenModules();
  fillSelects();
  renderProductos();
  renderClientes();
  renderProveedores();
  renderKardex();
  renderPos();
  renderFacturas();
  renderContabilidad();
  renderPedidos();
  renderDevoluciones();
  renderSeries();
  renderConfig();
}

function bindEvents() {
  $$(".nav-btn, .tile").forEach((btn) => {
    btn.addEventListener("click", () => setView(btn.dataset.view));
  });

  $("#lowStockClose").addEventListener("click", () => {
    lowStockDismissed = true;
    $("#lowStockAlert").classList.add("hidden");
  });

  $("#prodSearch").addEventListener("input", renderProductos);
  $("#posSearch").addEventListener("input", renderPos);
  $("#posMoneda").addEventListener("change", (e) => {
    posMoneda = e.target.value;
    renderCart();
  });
  $("#kardexFilter").addEventListener("change", renderKardex);
  $("#facMoneda").addEventListener("change", renderFacLines);
  $("#devFactura").addEventListener("change", fillDevProductos);
  $("#contFilter").addEventListener("change", renderContabilidad);
  $("#contSearch").addEventListener("input", renderContabilidad);

  // Config tabs
  $("#cfgTabs").addEventListener("click", (e) => {
    const t = e.target.closest(".tab");
    if (!t) return;
    $$("#cfgTabs .tab").forEach((b) => b.classList.remove("active"));
    t.classList.add("active");
    $$(".tab-panel").forEach((p) => p.classList.remove("active"));
    const panel = $(`.tab-panel[data-panel="${t.dataset.tab}"]`);
    if (panel) panel.classList.add("active");
  });

  // Productos
  $("#prodForm").addEventListener("submit", (e) => {
    e.preventDefault();
    const f = e.target;
    const id = f.id.value ? Number(f.id.value) : store.nextId(db, "producto");
    const payload = {
      id,
      codigo: f.codigo.value.trim(),
      nombre: f.nombre.value.trim(),
      descripcion: f.descripcion.value.trim(),
      unidad_medida: f.unidad_medida.value,
      categoria_id: Number(f.categoria_id.value) || null,
      precio_compra: Number(f.precio_compra.value) || 0,
      precio_venta: Number(f.precio_venta.value) || 0,
      precio_compra_usd: Number(f.precio_compra_usd.value) || 0,
      precio_venta_usd: Number(f.precio_venta_usd.value) || 0,
      stock_minimo: Number(f.stock_minimo.value) || 0,
      activo: 1,
      fecha_creacion: ahora(),
    };
    if (db.productos.some((p) => p.codigo === payload.codigo && p.id !== id)) {
      toast("Ya existe ese codigo", "err");
      return;
    }
    const idx = db.productos.findIndex((p) => p.id === id);
    if (idx >= 0) db.productos[idx] = { ...db.productos[idx], ...payload };
    else db.productos.push(payload);
    store.save(db);
    selectedProdId = id;
    toast("Producto guardado");
    loadProdForm(null);
    renderAll();
  });
  $("#prodReset").addEventListener("click", () => {
    selectedProdId = null;
    loadProdForm(null);
    renderProductos();
  });
  $("#prodDelete").addEventListener("click", () => {
    const f = $("#prodForm");
    if (!f.id.value) return;
    const p = db.productos.find((x) => x.id === Number(f.id.value));
    if (p) p.activo = 0;
    store.save(db);
    selectedProdId = null;
    loadProdForm(null);
    toast("Producto eliminado (soft delete)");
    renderAll();
  });
  $("#prodExport").addEventListener("click", () => {
    exportCsv(
      "productos.csv",
      ["codigo", "nombre", "unidad", "precio_crc", "precio_usd", "stock", "min"],
      db.productos.filter((p) => p.activo !== 0).map((p) => [
        p.codigo, p.nombre, p.unidad_medida, p.precio_venta, p.precio_venta_usd,
        stockDe(db, p.id), p.stock_minimo,
      ])
    );
  });
  $("#prodTable tbody").addEventListener("click", (e) => {
    const tr = e.target.closest("tr[data-id]");
    if (!tr) return;
    selectedProdId = Number(tr.dataset.id);
    loadProdForm(db.productos.find((x) => x.id === selectedProdId));
    renderProductos();
  });

  // Clientes
  $("#cliForm").addEventListener("submit", (e) => {
    e.preventDefault();
    const f = e.target;
    const id = f.id.value ? Number(f.id.value) : store.nextId(db, "cliente");
    const payload = {
      id,
      nit: f.nit.value.trim(),
      nombre: f.nombre.value.trim(),
      direccion: f.direccion.value.trim(),
      telefono: f.telefono.value.trim(),
      email: f.email.value.trim(),
      activo: 1,
    };
    const idx = db.clientes.findIndex((c) => c.id === id);
    if (idx >= 0) db.clientes[idx] = { ...db.clientes[idx], ...payload };
    else db.clientes.push(payload);
    store.save(db);
    selectedCliId = id;
    loadCliForm(null);
    toast("Cliente guardado");
    renderAll();
  });
  $("#cliReset").addEventListener("click", () => {
    selectedCliId = null;
    loadCliForm(null);
    renderClientes();
  });
  $("#cliDelete").addEventListener("click", () => {
    const f = $("#cliForm");
    if (!f.id.value) return;
    const c = db.clientes.find((x) => x.id === Number(f.id.value));
    if (c) c.activo = 0;
    store.save(db);
    selectedCliId = null;
    loadCliForm(null);
    toast("Cliente eliminado");
    renderAll();
  });
  $("#cliExport").addEventListener("click", () => {
    exportCsv(
      "clientes.csv",
      ["nit", "nombre", "direccion", "telefono", "email"],
      db.clientes.filter((c) => c.activo !== 0).map((c) => [
        c.nit, c.nombre, c.direccion, c.telefono, c.email,
      ])
    );
  });
  $("#cliTable tbody").addEventListener("click", (e) => {
    const tr = e.target.closest("tr[data-id]");
    if (!tr) return;
    selectedCliId = Number(tr.dataset.id);
    loadCliForm(db.clientes.find((c) => c.id === selectedCliId));
    renderClientes();
  });

  // Proveedores
  $("#provForm").addEventListener("submit", (e) => {
    e.preventDefault();
    const f = e.target;
    const id = f.id.value ? Number(f.id.value) : store.nextId(db, "proveedor");
    const payload = {
      id,
      nit: f.nit.value.trim(),
      nombre: f.nombre.value.trim(),
      direccion: f.direccion.value.trim(),
      telefono: f.telefono.value.trim(),
      email: f.email.value.trim(),
      contacto: f.contacto.value.trim(),
      activo: 1,
    };
    const idx = (db.proveedores || []).findIndex((c) => c.id === id);
    if (idx >= 0) db.proveedores[idx] = { ...db.proveedores[idx], ...payload };
    else db.proveedores.push(payload);
    store.save(db);
    selectedProvId = id;
    loadProvForm(null);
    toast("Proveedor guardado");
    renderAll();
  });
  $("#provReset").addEventListener("click", () => {
    selectedProvId = null;
    loadProvForm(null);
    renderProveedores();
  });
  $("#provDelete").addEventListener("click", () => {
    const f = $("#provForm");
    if (!f.id.value) return;
    const c = (db.proveedores || []).find((x) => x.id === Number(f.id.value));
    if (c) c.activo = 0;
    store.save(db);
    selectedProvId = null;
    loadProvForm(null);
    toast("Proveedor eliminado");
    renderAll();
  });
  $("#provTable tbody").addEventListener("click", (e) => {
    const tr = e.target.closest("tr[data-id]");
    if (!tr) return;
    selectedProvId = Number(tr.dataset.id);
    loadProvForm((db.proveedores || []).find((c) => c.id === selectedProvId));
    renderProveedores();
  });

  // Kardex
  $("#kardexForm").addEventListener("submit", (e) => {
    e.preventDefault();
    const f = e.target;
    try {
      aplicarKardex(
        Number(f.producto_id.value),
        f.tipo_movimiento.value,
        Number(f.cantidad.value),
        Number(f.precio_unitario.value) || 0,
        f.descripcion.value || ""
      );
      const k = db.kardex[db.kardex.length - 1];
      k.documento_ref = f.documento_ref.value || "";
      k.proveedor_cliente = f.proveedor_cliente.value || "";
      store.save(db);
      toast("Movimiento registrado");
      f.cantidad.value = "";
      renderAll();
    } catch (err) {
      toast(err.message, "err");
    }
  });
  $("#kardexExport").addEventListener("click", () => {
    exportCsv(
      "kardex.csv",
      ["fecha", "tipo", "producto_id", "cantidad", "precio", "total", "saldo", "ref"],
      db.kardex.map((k) => [
        k.fecha, k.tipo_movimiento, k.producto_id, k.cantidad,
        k.precio_unitario, k.total, k.saldo_cantidad, k.documento_ref || "",
      ])
    );
  });

  // POS
  $("#posTable tbody").addEventListener("click", (e) => {
    const add = e.target.closest("[data-add]");
    if (add) {
      addToCart(Number(add.dataset.add));
      return;
    }
    const tr = e.target.closest("tr[data-id]");
    if (tr) addToCart(Number(tr.dataset.id));
  });
  $("#posAddBtn").addEventListener("click", () => {
    const first = $("#posTable tbody tr[data-id]");
    if (first) addToCart(Number(first.dataset.id));
    else toast("No hay producto para agregar", "err");
  });
  $("#cartTable tbody").addEventListener("click", (e) => {
    const rm = e.target.closest("[data-rm]");
    if (!rm) return;
    posCart.splice(Number(rm.dataset.rm), 1);
    renderCart();
  });
  $("#posClear").addEventListener("click", () => {
    posCart = [];
    renderCart();
  });
  $("#posCobrar").addEventListener("click", cobrar);
  $("#posCotizar").addEventListener("click", cotizar);

  // Facturacion
  $("#facAdd").addEventListener("click", () => {
    const id = Number($("#facProducto").value);
    const qty = Number($("#facCant").value) || 1;
    const p = db.productos.find((x) => x.id === id);
    if (!p) return;
    const already = facLines.filter((l) => l.producto_id === id).reduce((s, l) => s + l.cantidad, 0);
    if (already + qty > stockDe(db, id)) {
      toast("Stock insuficiente", "err");
      return;
    }
    facLines.push({
      producto_id: id,
      cantidad: qty,
      precio_unitario: Number(p.precio_venta) || 0,
      precio_unitario_usd: Number(p.precio_venta_usd) || 0,
      total: qty * (Number(p.precio_venta) || 0),
      total_usd: qty * (Number(p.precio_venta_usd) || 0),
    });
    renderFacLines();
  });
  $("#facTable tbody").addEventListener("click", (e) => {
    const rm = e.target.closest("[data-rmfac]");
    if (!rm) return;
    facLines.splice(Number(rm.dataset.rmfac), 1);
    renderFacLines();
  });
  $("#facSave").addEventListener("click", guardarFactura);
  $("#facExport").addEventListener("click", () => {
    exportCsv(
      "facturas.csv",
      ["numero", "fecha", "cliente", "moneda", "subtotal", "iva", "total"],
      db.facturas.map((f) => [
        f.numero, f.fecha, f.cliente_nombre || "", f.moneda, f.subtotal, f.impuesto, f.total,
      ])
    );
  });
  $("#facListTable tbody").addEventListener("click", (e) => {
    const btn = e.target.closest("[data-viewfac]");
    if (!btn) return;
    const num = btn.dataset.viewfac;
    const f = db.facturas.find((x) => x.numero === num);
    const dets = db.detalle_factura.filter((d) => d.factura_numero === num);
    if (f) openPrint("Factura", buildTicketText(f, dets));
  });

  // Contabilidad
  $("#contForm").addEventListener("submit", (e) => {
    e.preventDefault();
    const f = e.target;
    let montoCrc = Number(f.monto_crc.value) || 0;
    let montoUsd = Number(f.monto_usd.value) || 0;
    if (!montoCrc && !montoUsd) {
      toast("Ingrese un monto", "err");
      return;
    }
    if (montoCrc && !montoUsd) montoUsd = crcToUsd(db, montoCrc);
    if (montoUsd && !montoCrc) montoCrc = usdToCrc(db, montoUsd);
    db.movimientos_contables.push({
      id: store.nextId(db, "mov"),
      fecha: ahora(),
      tipo: f.tipo.value,
      categoria: f.categoria.value,
      descripcion: f.descripcion.value.trim(),
      monto_crc: montoCrc,
      monto_usd: montoUsd,
      documento_ref: f.documento_ref.value.trim(),
      proveedor_cliente: f.proveedor_cliente.value.trim(),
      observaciones: "",
    });
    store.save(db);
    toast(`${f.tipo.value} registrado`);
    f.reset();
    renderAll();
  });
  $("#contClear").addEventListener("click", () => $("#contForm").reset());
  $("#contExport").addEventListener("click", () => {
    exportCsv(
      "contabilidad.csv",
      ["fecha", "tipo", "categoria", "descripcion", "monto_crc", "monto_usd", "doc", "prov_cli"],
      (db.movimientos_contables || []).map((m) => [
        m.fecha, m.tipo, m.categoria, m.descripcion, m.monto_crc, m.monto_usd,
        m.documento_ref, m.proveedor_cliente,
      ])
    );
  });

  // Pedidos
  $("#pedForm").addEventListener("submit", (e) => {
    e.preventDefault();
    const f = e.target;
    const productoId = Number(f.producto_id.value);
    const p = db.productos.find((x) => x.id === productoId);
    if (!f.cliente_nombre.value.trim() || !p) {
      toast("Cliente y producto requeridos", "err");
      return;
    }
    const cantidad = Number(f.cantidad_solicitada.value) || 1;
    db.pedidos_pendientes.push({
      id: store.nextId(db, "pedido"),
      fecha_pedido: ahora(),
      cliente_nombre: f.cliente_nombre.value.trim(),
      producto_id: productoId,
      producto_codigo: p.codigo,
      producto_nombre: p.nombre,
      cantidad_solicitada: cantidad,
      cantidad_entregada: 0,
      estado: "PENDIENTE",
      precio_unitario_crc: p.precio_venta,
      precio_unitario_usd: p.precio_venta_usd,
      moneda: "CRC",
      observaciones: f.observaciones.value || f.telefono.value || "",
      fecha_entrega_estimada: f.fecha_entrega_estimada.value || "",
    });
    store.save(db);
    toast("Pedido registrado");
    f.reset();
    renderAll();
  });
  $("#pedTable tbody").addEventListener("click", (e) => {
    const tr = e.target.closest("tr[data-id]");
    if (!tr) return;
    selectedPedId = Number(tr.dataset.id);
    renderPedidos();
  });
  $("#pedEntregar").addEventListener("click", () => {
    const p = (db.pedidos_pendientes || []).find((x) => x.id === selectedPedId);
    if (!p) {
      toast("Seleccione un pedido", "err");
      return;
    }
    if (p.estado === "ENTREGADO") {
      toast("Ya fue entregado", "err");
      return;
    }
    p.estado = "ENTREGADO";
    p.cantidad_entregada = p.cantidad_solicitada;
    store.save(db);
    toast("Pedido entregado");
    renderAll();
  });
  $("#pedCancelar").addEventListener("click", () => {
    const p = (db.pedidos_pendientes || []).find((x) => x.id === selectedPedId);
    if (!p) {
      toast("Seleccione un pedido", "err");
      return;
    }
    p.estado = "CANCELADO";
    store.save(db);
    toast("Pedido cancelado");
    renderAll();
  });

  // Devoluciones
  $("#devForm").addEventListener("submit", (e) => {
    e.preventDefault();
    const f = e.target;
    const num = f.factura.value;
    const prodId = Number(f.producto.value);
    const motivo = f.motivo.value.trim();
    if (!num || !prodId || !motivo) {
      toast("Complete factura, producto y motivo", "err");
      return;
    }
    const p = db.productos.find((x) => x.id === prodId);
    db.movimientos_contables.push({
      id: store.nextId(db, "mov"),
      fecha: ahora(),
      tipo: "GASTO",
      categoria: "Devolucion",
      descripcion: `Devolucion: ${motivo}`,
      monto_crc: 0,
      monto_usd: 0,
      documento_ref: num,
      proveedor_cliente: p ? p.codigo : String(prodId),
      observaciones: f.cantidad.value,
    });
    try {
      aplicarKardex(prodId, "ENTRADA", Number(f.cantidad.value) || 1, p ? p.precio_venta : 0, `Devolucion ${num}`);
    } catch (_) {}
    store.save(db);
    toast("Devolucion registrada");
    f.reset();
    renderAll();
  });

  // Series
  $("#serForm").addEventListener("submit", (e) => {
    e.preventDefault();
    const f = e.target;
    const serie = f.numero_serie.value.trim();
    if (!serie) {
      toast("Numero de serie requerido", "err");
      return;
    }
    if ((db.series_lotes || []).some((s) => s.numero_serie === serie)) {
      toast("Esa serie ya existe", "err");
      return;
    }
    db.series_lotes.push({
      id: store.nextId(db, "serie"),
      producto_id: Number(f.producto_id.value),
      numero_serie: serie,
      lote: f.lote.value.trim(),
      cantidad: Number(f.cantidad.value) || 1,
      ubicacion: f.ubicacion.value.trim(),
      fecha_vencimiento: f.fecha_vencimiento.value || "",
      fecha_ingreso: hoy(),
      estado: "DISPONIBLE",
    });
    store.save(db);
    toast("Serie/Lote registrado");
    f.reset();
    renderAll();
  });
  $("#serTable tbody").addEventListener("click", (e) => {
    const tr = e.target.closest("tr[data-id]");
    if (!tr) return;
    selectedSerId = Number(tr.dataset.id);
    renderSeries();
  });
  $("#serDelete").addEventListener("click", () => {
    if (!selectedSerId) {
      toast("Seleccione un registro", "err");
      return;
    }
    db.series_lotes = (db.series_lotes || []).filter((s) => s.id !== selectedSerId);
    selectedSerId = null;
    store.save(db);
    toast("Registro eliminado");
    renderAll();
  });

  // Reportes
  $("#repButtons").addEventListener("click", (e) => {
    const b = e.target.closest("[data-rep]");
    if (b) runReport(b.dataset.rep);
  });
  $("#repExport").addEventListener("click", () => {
    if (!lastReport.headers.length) {
      toast("Genere un reporte primero", "err");
      return;
    }
    exportCsv(lastReport.name, lastReport.headers, lastReport.rows);
  });

  // Graficos
  $("#grafButtons").addEventListener("click", (e) => {
    const b = e.target.closest("[data-graf]");
    if (b) runGrafico(b.dataset.graf);
  });

  // Config forms
  $("#cfgForm").addEventListener("submit", (e) => {
    e.preventDefault();
    const f = e.target;
    db.config = {
      ...db.config,
      tipo_cambio: Number(f.tipo_cambio.value) || 520,
      iva: Number(f.iva.value) || 0,
      moneda_local: f.moneda_local.value,
      simbolo_local: f.simbolo_local.value,
      theme: f.theme.value,
    };
    store.save(db);
    applyTheme(db.config.theme);
    toast("Configuracion general guardada");
    renderAll();
  });
  $("#cfgEmpresa").addEventListener("submit", (e) => {
    e.preventDefault();
    const f = e.target;
    db.config = {
      ...db.config,
      nombre_empresa: f.nombre_empresa.value,
      nit: f.nit.value,
      telefono: f.telefono.value,
      direccion: f.direccion.value,
      email: f.email.value,
      sitio_web: f.sitio_web.value,
    };
    store.save(db);
    toast("Empresa guardada");
    renderAll();
  });
  $("#cfgFactura").addEventListener("submit", (e) => {
    e.preventDefault();
    const f = e.target;
    db.config = {
      ...db.config,
      invoice_header: f.invoice_header.value,
      invoice_footer: f.invoice_footer.value,
      invoice_watermark: f.invoice_watermark.value,
      invoice_color: f.invoice_color.value,
      invoice_font_size: Number(f.invoice_font_size.value) || 12,
      invoice_paper: f.invoice_paper.value,
    };
    ["show_numero", "show_fecha", "show_nit", "show_cliente", "show_direccion",
     "show_telefono", "show_subtotal", "show_iva", "show_tc"].forEach((name) => {
      db.config[name] = f[name].checked ? 1 : 0;
    });
    store.save(db);
    toast("Config de factura guardada");
    renderAll();
  });
  $("#cfgResetIva").addEventListener("click", () => {
    $("#cfgForm").iva.value = 12;
  });
  $("#cfgResetTc").addEventListener("click", () => {
    $("#cfgForm").tipo_cambio.value = 520;
  });
  $("#modToggles").addEventListener("change", (e) => {
    const cb = e.target.closest("[data-mod]");
    if (!cb) return;
    const hidden = new Set(db.config.hidden_modules || []);
    if (cb.checked) hidden.delete(cb.dataset.mod);
    else hidden.add(cb.dataset.mod);
    db.config.hidden_modules = [...hidden];
    store.save(db);
    applyHiddenModules();
    toast("Modulos actualizados");
  });
  $("#cfgExportJson").addEventListener("click", () => {
    const blob = new Blob([JSON.stringify(db.config, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "pino_config.json";
    a.click();
    URL.revokeObjectURL(a.href);
  });
  $("#cfgResetDb").addEventListener("click", () => {
    if (!confirm("Restablecer todos los datos a demo? Se perdera lo actual.")) return;
    db = store.resetAll();
    posCart = [];
    facLines = [];
    toast("Datos restablecidos");
    renderAll();
  });

  // Print modal
  $("#printClose").addEventListener("click", () => $("#printModal").classList.add("hidden"));
  $("#printCopy").addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText($("#printBody").textContent);
      toast("Copiado al portapapeles");
    } catch {
      toast("No se pudo copiar", "err");
    }
  });
  $("#printWindow").addEventListener("click", () => {
    const w = window.open("", "_blank", "width=480,height=700");
    if (!w) {
      toast("Permita ventanas emergentes para imprimir", "err");
      return;
    }
    const body = $("#printBody").textContent
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;");
    w.document.write(`<!DOCTYPE html><html><head><title>Imprimir</title>
      <style>body{font-family:monospace;white-space:pre-wrap;padding:12px;font-size:13px}</style>
      </head><body>${body}<script>window.print()</script></body></html>`);
    w.document.close();
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "F1") setView("pos");
    if (e.key === "F2") setView("productos");
    if (e.key === "F3") setView("kardex");
    if (e.key === "F4") setView("facturacion");
    if (e.key === "F5") setView("reportes");
    if (e.key === "Escape") $("#printModal").classList.add("hidden");
  });
}

function boot() {
  bindEvents();
  renderAll();
  setInterval(() => {
    $("#statusClock").textContent = new Date().toLocaleString("es-CR");
  }, 1000);
  toast("TAURI BETA 1 listo");
}

boot();
