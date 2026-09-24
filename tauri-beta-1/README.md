# PINO SYSTEM - TAURI BETA 1

Version: **1.0.0-beta.1**

Reescritura del sistema de inventario y facturacion **PINO SYSTEM** con:

- **Tauri 2** (escritorio)
- **HTML / CSS / JavaScript** (Vite)
- Moneda dual **CRC / USD**
- KARDEX, POS, Productos, Clientes, Facturacion, Reportes, Config
- Actualizaciones via GitHub (Tauri updater)
- CI/CD en **GitHub Actions** (Windows, macOS, Linux)

> Beta 1: la UI y la logica de negocio corren en el navegador con `localStorage`.
> El backend Rust (`src-tauri`) ya trae SQLite + comandos `db_exec` / `db_select`
> para migrar los datos a BD nativa en la siguiente beta.

---

## Estructura

```
tauri-beta-1/
  index.html          SPA (vistas: home, pos, productos, kardex, ...)
  css/styles.css      Tema bosque/verde del PINO original
  js/app.js           Logica de UI + negocio (beta)
  js/db.js            Capa de datos (localStorage)
  vite.config.js
  package.json
  src-tauri/
    tauri.conf.json   Ventana, plugins sql/updater, bundle
    Cargo.toml
    src/main.rs
    src/lib.rs        SQLite schema + comandos Tauri
  .github/workflows/tauri.yml
```

---

## Requisitos (desarrollo)

1. **Node.js** 20+
2. **Rust** (https://rustup.rs)
3. Dependencias de sistema para Tauri 2:
   - **Linux**: `libwebkit2gtk-4.1-dev`, etc. (ver workflow)
   - **macOS**: Xcode CLT
   - **Windows**: WebView2 Runtime + MSVC

---

## Correr en desarrollo

```bash
cd tauri-beta-1
npm install
npm run tauri:dev
```

Solo la web (sin Rust):

```bash
npm install
npm run dev
# abre http://localhost:5173
```

---

## Build

```bash
cd tauri-beta-1
npm install
npm run tauri:build
```

Artefactos en `src-tauri/target/release/bundle/`.

---

## GitHub

- El workflow **TAURI BETA 1** (`.github/workflows/tauri.yml`) compila en
  push a `main` y en tags `v*`.
- Al taggear `v1.0.0-beta.1` crea **GitHub Release** con los binarios
  (prerelease).

```bash
git add tauri-beta-1
git commit -m "tauri-beta-1: TAURI BETA 1 (1.0.0-beta.1)"
git push origin main
```

### Updater (desde beta 2+)

1. Generar claves: `npm run tauri signer generate`
2. Poner `pubkey` en `src-tauri/tauri.conf.json` → `plugins.updater.pubkey`
3. Publicar `latest.json` + firmas en el endpoint configurado
   (`.../tauri-beta-1/latest.json` en este repo)

---

## Atajos

| Tecla | Vista |
|------|--------|
| F1 | POS |
| F2 | Productos |
| F3 | Kardex |
| F4 | Facturas |

---

## Relacion con el EXE actual (v2.6.5)

| Actual (Python) | Tauri Beta 1 |
|-----------------|--------------|
| `app.py` + `modulos.py` | `index.html` + `js/app.js` |
| SQLite en `PinoSystem/datos` | Mismo path en Rust (`app_info`) / localStorage en beta |
| `updater.py` + `version.json` | `tauri-plugin-updater` + GitHub Releases |
| `PUBLICAR.bat` + PyInstaller | `build_exe.bat` / GitHub Actions `tauri.yml` |

El sistema **Tkinter 2.6.5 sigue siendo el oficial** de produccion.
Este beta es la base de la version moderna.
