# DGA Módulo de Oposiciones — Frontend (Portal Institucional)

**Versión:** `v1.0.0`  
**Autoría Oficial:** DGA Core Tools — by Daniel Díaz L. & AI Engine Antigravity  
**Institución:** Dirección General de Aguas (DGA) — Ministerio de Obras Públicas (MOP)  

---

## 1. Ficha Técnica

* **Lenguaje:** **HTML5**, **CSS3 Nativo**, **Vanilla JavaScript (ES6+)**.
* **Framework:** Ninguno (Zero Node.js, Zero `npm`, Zero dependencias externas / Zero CDN).
* **Diseño Visual:** Framework de Diseño Digital del Estado de Chile (**Kit Digital Gob.cl 2026**).
* **Seguridad & Rendimiento:**
  - Cumplimiento **OWASP Top 10** (cabeceras CSP, X-Frame-Options, X-Content-Type-Options).
  - **Zero-CDN:** 100% de los estilos y fuentes residen localmente en `css/style.css`.
  - **Validación Local:** Algoritmo canónico chileno Módulo 11 para feedback instantáneo de RUTs.
* **Web Server / Reverse Proxy:** Nginx Alpine (Puerto `80`), enrutando `/api/` hacia el contenedor backend.

---

## 2. Estructura de Archivos

```
frontend/
├── index.html        # Portal principal Kit Digital Gob.cl
├── css/
│   └── style.css     # Hoja de estilos autónoma Kit Digital 2026
├── js/
│   └── app.js        # Lógica cliente desacoplada (consumo de /api/*)
├── nginx.conf        # Proxy inverso Nginx con cabeceras de seguridad
├── Dockerfile        # Imagen ultraligera Nginx Alpine
└── README.md         # Documentación técnica del frontend
```

---

## 3. Endpoints que Consume

* `GET /api/health`: Chequeo de salud y conexión a `BD_EXP`.
* `GET /api/catalogo/tipos-tramite`: Catálogo de tipos de trámite.
* `GET /api/catalogo/regiones`: 16 regiones oficiales ordenadas del 1 al 16.
* `GET /api/catalogo/provincias?reg_codigo={id}`: Cascada de provincias.
* `GET /api/catalogo/comunas?reg_codigo={id}&pro_codigo={id}`: Cascada de comunas.
* `GET /api/oposiciones/search`: Búsqueda de solicitudes con conteo de oposiciones.
* `POST /api/oposiciones/agregar`: Registro formal de oposición en `BD_EXP`.
