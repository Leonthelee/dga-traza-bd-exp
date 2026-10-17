/**
 * Lógica Cliente Desacoplada — Módulo de Oposiciones DGA Gob.cl
 * Consume API REST (/api/*) con soporte local y reverse proxy Nginx
 * Kit Digital Gob.cl 2026 — Zero Frameworks / Vanilla JS ES6+
 */

const API_BASE = window.location.origin.includes(":80") || window.location.origin.includes(":5500") || window.location.origin.includes(":3000")
    ? "" // Servido por Nginx con proxy /api/
    : "http://127.0.0.1:8000"; // Fallback desarrollo local directo

// Elementos DOM
const selTipo = document.getElementById("selTipo");
const selRegion = document.getElementById("selRegion");
const selProvincia = document.getElementById("selProvincia");
const selComuna = document.getElementById("selComuna");
const txtExpediente = document.getElementById("txtExpediente");
const txtSolicitante = document.getElementById("txtSolicitante");
const btnBuscar = document.getElementById("btnBuscar");
const btnLimpiar = document.getElementById("btnLimpiar");

const metricTotal = document.getElementById("metricTotal");
const metricConOpo = document.getElementById("metricConOpo");
const metricEnTramite = document.getElementById("metricEnTramite");
const tableBody = document.getElementById("tableBody");
const badgeDbStatus = document.getElementById("badgeDbStatus");

// Modal Oposiciones
const modalOposicion = document.getElementById("modalOposicion");
const btnCerrarModal = document.getElementById("btnCerrarModal");
const btnCancelarModal = document.getElementById("btnCancelarModal");
const formOposicion = document.getElementById("formOposicion");
const modalExpCodigo = document.getElementById("modalExpCodigo");
const modalDocNro = document.getElementById("modalDocNro");
const modalFecha = document.getElementById("modalFecha");
const modalRut = document.getElementById("modalRut");
const modalNombre = document.getElementById("modalNombre");
const modalObs = document.getElementById("modalObs");
const rutFeedback = document.getElementById("rutFeedback");
const btnSubmitOpo = document.getElementById("btnSubmitOpo");

// Toast
const toast = document.getElementById("toast");

function showToast(message, type = "success") {
    toast.textContent = message;
    toast.className = `toast toast-${type}`;
    toast.style.display = "block";
    setTimeout(() => {
        toast.style.display = "none";
    }, 4000);
}

// ============================================================================
// Validación Canónica Módulo 11 Chileno (Frontend)
// ============================================================================
function validateRut(rut) {
    if (!rut || typeof rut !== "string") return false;
    let clean = rut.replace(/\./g, "").replace(/\s/g, "").toUpperCase();
    let cuerpo, dv;
    if (clean.includes("-")) {
        const parts = clean.split("-");
        if (parts.length !== 2) return false;
        cuerpo = parts[0];
        dv = parts[1];
    } else {
        if (clean.length < 2) return false;
        cuerpo = clean.slice(0, -1);
        dv = clean.slice(-1);
    }
    cuerpo = cuerpo.replace(/^0+/, "");
    if (!/^\d+$/.test(cuerpo) || cuerpo.length < 6 || cuerpo.length > 9) return false;

    const mults = [2, 3, 4, 5, 6, 7];
    let suma = 0;
    const rev = cuerpo.split("").reverse();
    for (let i = 0; i < rev.length; i++) {
        suma += parseInt(rev[i], 10) * mults[i % 6];
    }
    const resto = 11 - (suma % 11);
    let dvEsperado = "0";
    if (resto === 11) dvEsperado = "0";
    else if (resto === 10) dvEsperado = "K";
    else dvEsperado = resto.toString();

    return dv === dvEsperado;
}

// Formateador visual de RUT
function formatRut(rut) {
    let clean = rut.replace(/[^0-9kK]/g, "").toUpperCase();
    if (clean.length <= 1) return clean;
    const cuerpo = clean.slice(0, -1);
    const dv = clean.slice(-1);
    return `${cuerpo}-${dv}`;
}

// ============================================================================
// Carga de Catálogos en Cascada (BD_PAR)
// ============================================================================
async function initHealthCheck() {
    try {
        const res = await fetch(`${API_BASE}/api/health`);
        if (res.ok) {
            const data = await res.json();
            if (data.database_connected) {
                badgeDbStatus.innerHTML = `<span class="dot-green"></span> BD_EXP Conectado (Producción)`;
            } else {
                badgeDbStatus.innerHTML = `<span style="width:8px;height:8px;border-radius:50%;background:#F59E0B;display:inline-block;"></span> Modo Local / Simulación`;
            }
        }
    } catch {
        badgeDbStatus.innerHTML = `<span style="width:8px;height:8px;border-radius:50%;background:#EF4444;display:inline-block;"></span> Sin Conexión API`;
    }
}

async function loadTiposTramite() {
    try {
        const res = await fetch(`${API_BASE}/api/catalogo/tipos-tramite`);
        const json = await res.json();
        if (json.success) {
            selTipo.innerHTML = `<option value="">TODOS - Todos los Tipos</option>`;
            json.data.forEach(t => {
                selTipo.innerHTML += `<option value="${t.TeoCodigo}">${t.TeoCodigo} - ${t.TeoNombre}</option>`;
            });
        }
    } catch (e) {
        console.error("Error al cargar tipos:", e);
    }
}

async function loadRegiones() {
    try {
        const res = await fetch(`${API_BASE}/api/catalogo/regiones`);
        const json = await res.json();
        if (json.success) {
            selRegion.innerHTML = `<option value="">Todas las Regiones (1 a 16)</option>`;
            json.data.forEach(r => {
                selRegion.innerHTML += `<option value="${r.RegCodigo}">${r.RegCodigo} - ${r.RegNombre}</option>`;
            });
        }
    } catch (e) {
        console.error("Error al cargar regiones:", e);
    }
}

async function loadProvincias(regCodigo) {
    selProvincia.innerHTML = `<option value="">Cargando provincias...</option>`;
    selProvincia.disabled = true;
    selComuna.innerHTML = `<option value="">Seleccione Provincia primero</option>`;
    selComuna.disabled = true;

    if (!regCodigo) {
        selProvincia.innerHTML = `<option value="">Seleccione Región primero</option>`;
        return;
    }

    try {
        const res = await fetch(`${API_BASE}/api/catalogo/provincias?reg_codigo=${regCodigo}`);
        const json = await res.json();
        if (json.success && json.data.length > 0) {
            selProvincia.innerHTML = `<option value="">Todas las Provincias</option>`;
            json.data.forEach(p => {
                selProvincia.innerHTML += `<option value="${p.ProCodigo}">${p.ProNombre}</option>`;
            });
            selProvincia.disabled = false;
        } else {
            selProvincia.innerHTML = `<option value="">Sin provincias asociadas</option>`;
        }
    } catch (e) {
        console.error("Error al cargar provincias:", e);
        selProvincia.innerHTML = `<option value="">Error al cargar</option>`;
    }
}

async function loadComunas(regCodigo, proCodigo) {
    selComuna.innerHTML = `<option value="">Cargando comunas...</option>`;
    selComuna.disabled = true;

    if (!regCodigo || !proCodigo) {
        selComuna.innerHTML = `<option value="">Seleccione Provincia primero</option>`;
        return;
    }

    try {
        const res = await fetch(`${API_BASE}/api/catalogo/comunas?reg_codigo=${regCodigo}&pro_codigo=${proCodigo}`);
        const json = await res.json();
        if (json.success && json.data.length > 0) {
            selComuna.innerHTML = `<option value="">Todas las Comunas</option>`;
            json.data.forEach(c => {
                selComuna.innerHTML += `<option value="${c.ComCodigo}">${c.ComNombre}</option>`;
            });
            selComuna.disabled = false;
        } else {
            selComuna.innerHTML = `<option value="">Sin comunas registradas</option>`;
        }
    } catch (e) {
        console.error("Error al cargar comunas:", e);
        selComuna.innerHTML = `<option value="">Error al cargar</option>`;
    }
}

// ============================================================================
// Búsqueda y Renderizado de Expedientes con Oposiciones
// ============================================================================
async function doSearch() {
    tableBody.innerHTML = `<tr><td colspan="10" style="text-align:center;padding:2rem;color:#64748B;">Cargando solicitudes de derechos de aguas...</td></tr>`;

    const params = new URLSearchParams();
    if (selTipo.value) params.append("tipo_tramite", selTipo.value);
    if (selRegion.value) params.append("reg_codigo", selRegion.value);
    if (selProvincia.value) params.append("pro_codigo", selProvincia.value);
    if (selComuna.value) params.append("com_codigo", selComuna.value);
    if (txtExpediente.value.trim()) params.append("exp_llave", txtExpediente.value.trim());
    if (txtSolicitante.value.trim()) params.append("solicitante", txtSolicitante.value.trim());

    try {
        const res = await fetch(`${API_BASE}/api/oposiciones/search?${params.toString()}`);
        const json = await res.json();

        if (!json.success) {
            tableBody.innerHTML = `<tr><td colspan="10" style="text-align:center;padding:2rem;color:#DC2626;">Error al consultar: ${json.error || "No se pudo conectar a la base de datos"}</td></tr>`;
            return;
        }

        metricTotal.textContent = json.total;
        metricConOpo.textContent = json.con_oposiciones;
        metricEnTramite.textContent = json.en_tramite;

        if (!json.data || json.data.length === 0) {
            tableBody.innerHTML = `<tr><td colspan="10" style="text-align:center;padding:2rem;color:#64748B;">No se encontraron solicitudes con los criterios indicados.</td></tr>`;
            return;
        }

        renderTable(json.data);
    } catch (e) {
        console.error("Error en búsqueda:", e);
        tableBody.innerHTML = `<tr><td colspan="10" style="text-align:center;padding:2rem;color:#DC2626;">Error de conexión con la API de backend.</td></tr>`;
    }
}

function renderTable(rows) {
    let html = "";
    rows.forEach(r => {
        const expCodigo = r.ExpConcatLlave || "S/I";
        const rutSol = r.RutSolicitante || r.RutPasSolicitante || "S/I";
        const fechaSol = r.FechaSolicitud || r.FechaInicio || "S/I";
        const numOpo = r.NumOposiciones || "0 - No";
        const solicitante = r.Solicitante || "S/I";
        const region = r.GLRegion || "-";
        const provincia = r.GLProvincia || "-";
        const comuna = r.GLComuna || "-";
        const derecho = r.GLTipoDerecho || "-";
        const estado = r.Estado || "EN TRAMITE";

        const hasOpo = numOpo.includes("Sí") || numOpo.includes("Si") || (r.NumOposicionesRaw > 0);
        const opoBadgeClass = hasOpo ? "badge-oposicion-si" : "badge-oposicion-no";
        const estadoBadgeClass = estado.includes("APROBADO") ? "badge-aprobado" : "badge-tramite";

        html += `
        <tr>
            <td style="font-weight:700;font-family:monospace;color:#0039A6;">${expCodigo}</td>
            <td style="font-family:monospace;">${rutSol}</td>
            <td>${fechaSol}</td>
            <td><span class="badge-status ${opoBadgeClass}">${numOpo}</span></td>
            <td style="font-weight:600;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${solicitante}">${solicitante}</td>
            <td>${region}</td>
            <td>${provincia}</td>
            <td>${comuna}</td>
            <td>${derecho}</td>
            <td>
                <div style="display:flex;align-items:center;gap:0.5rem;justify-content:space-between;">
                    <span class="badge-status ${estadoBadgeClass}">${estado}</span>
                    <button type="button" class="btn btn-action-opo" onclick="openAgregarModal('${expCodigo}')" title="Agregar Oposición a este expediente">
                        Agregar Oposicion
                    </button>
                </div>
            </td>
        </tr>
        `;
    });
    tableBody.innerHTML = html;
}

// ============================================================================
// Modal: Agregar Oposición Oficial
// ============================================================================
window.openAgregarModal = function(expCodigo) {
    modalExpCodigo.value = expCodigo;
    modalDocNro.value = `OPO-${new Date().getFullYear()}-${Math.floor(1000 + Math.random() * 9000)}`;
    const today = new Date();
    const dd = String(today.getDate()).padStart(2, "0");
    const mm = String(today.getMonth() + 1).padStart(2, "0");
    modalFecha.value = `${dd}/${mm}/${today.getFullYear()}`;
    modalRut.value = "";
    modalNombre.value = "";
    modalObs.value = "";
    rutFeedback.textContent = "";
    rutFeedback.style.display = "none";

    modalOposicion.classList.add("show");
};

function closeModal() {
    modalOposicion.classList.remove("show");
}

modalRut.addEventListener("input", () => {
    modalRut.value = formatRut(modalRut.value);
    if (modalRut.value.length >= 8) {
        if (validateRut(modalRut.value)) {
            rutFeedback.textContent = "✓ RUT Módulo 11 Válido";
            rutFeedback.style.color = "#059669";
            rutFeedback.style.display = "block";
        } else {
            rutFeedback.textContent = "✗ Dígito verificador incorrecto";
            rutFeedback.style.color = "#DC2626";
            rutFeedback.style.display = "block";
        }
    } else {
        rutFeedback.style.display = "none";
    }
});

formOposicion.addEventListener("submit", async (e) => {
    e.preventDefault();
    const rutVal = modalRut.value.trim();
    if (!validateRut(rutVal)) {
        showToast("El RUT ingresado no es válido según Módulo 11.", "error");
        modalRut.focus();
        return;
    }

    btnSubmitOpo.disabled = true;
    btnSubmitOpo.textContent = "Registrando en BD_EXP...";

    const payload = {
        exp_codigo: modalExpCodigo.value,
        fecha_ingreso: modalFecha.value,
        doc_nro: modalDocNro.value,
        opositor_nombre: modalNombre.value.trim(),
        opositor_rut: rutVal,
        observaciones: modalObs.value.trim(),
    };

    try {
        const res = await fetch(`${API_BASE}/api/oposiciones/agregar`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });

        const json = await res.json();
        if (res.ok && json.success) {
            closeModal();
            showToast(json.message || "Oposición registrada exitosamente en BD_EXP.", "success");
            doSearch();
        } else {
            showToast(json.detail || json.message || "Error al registrar la oposición", "error");
        }
    } catch (err) {
        console.error(err);
        showToast("Error de comunicación con el servidor backend.", "error");
    } finally {
        btnSubmitOpo.disabled = false;
        btnSubmitOpo.textContent = "Guardar Oposición en BD_EXP";
    }
});

// Event Listeners
selRegion.addEventListener("change", () => loadProvincias(selRegion.value));
selProvincia.addEventListener("change", () => loadComunas(selRegion.value, selProvincia.value));
btnBuscar.addEventListener("click", doSearch);
btnLimpiar.addEventListener("click", () => {
    selTipo.value = "";
    selRegion.value = "";
    selProvincia.innerHTML = `<option value="">Seleccione Región primero</option>`;
    selProvincia.disabled = true;
    selComuna.innerHTML = `<option value="">Seleccione Provincia primero</option>`;
    selComuna.disabled = true;
    txtExpediente.value = "";
    txtSolicitante.value = "";
    doSearch();
});

btnCerrarModal.addEventListener("click", closeModal);
btnCancelarModal.addEventListener("click", closeModal);
modalOposicion.addEventListener("click", (e) => {
    if (e.target === modalOposicion) closeModal();
});

// Inicialización
document.addEventListener("DOMContentLoaded", () => {
    initHealthCheck();
    loadTiposTramite();
    loadRegiones();
    doSearch();
});
