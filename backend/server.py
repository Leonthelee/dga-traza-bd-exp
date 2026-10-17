"""API REST Backend — Módulo de Oposiciones DGA Gob.cl
Dirección General de Aguas — Ministerio de Obras Públicas
Framework: FastAPI / Uvicorn (Arquitectura Desacoplada Kit Digital Gob.cl 2026)
"""

import os
import sys
from typing import Any, Dict, List, Optional
from contextlib import asynccontextmanager

# Agregar raíz al sys.path para importar src
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import src.oposiciones as op
from src.config import load_settings
from src.db import connect


# Modelos Pydantic para Validaciones Estrictas
class OposicionPayload(BaseModel):
    exp_codigo: str = Field(..., max_length=15, description="Código de Expediente (ej: ND-0802-4437)")
    fecha_ingreso: str = Field(..., description="Fecha de Ingreso en formato DD/MM/AAAA")
    doc_nro: str = Field(..., max_length=20, description="Número de Documento o Folio")
    opositor_nombre: str = Field(..., min_length=2, max_length=250, description="Nombre o Razón Social del Opositor")
    opositor_rut: str = Field(..., max_length=15, description="RUT de la Persona u Organización Opositora")
    observaciones: Optional[str] = Field("", max_length=500, description="Observaciones adicionales")


def get_db_connection():
    """Obtiene contexto de conexión SQL Server si está configurado y alcanzable."""
    try:
        settings = load_settings()
        if not settings.is_live:
            return None
        return connect(settings)
    except Exception:
        return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicialización de servicios
    yield


app = FastAPI(
    title="DGA • API Módulo de Oposiciones",
    description="Backend desacoplado para consulta y registro de oposiciones a solicitudes de derechos de aguas (Kit Digital Gob.cl)",
    version="1.0.0",
    lifespan=lifespan,
)

# Middleware de Seguridad y CORS (Permitir frontend desacoplado)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", summary="Estado del Servicio Backend y Base de Datos")
def health():
    db_ctx = get_db_connection()
    db_online = False
    if db_ctx:
        try:
            with db_ctx as conn:
                db_online = conn is not None
        except Exception:
            db_online = False

    return {
        "status": "healthy",
        "service": "dga-modulo-oposiciones-backend",
        "version": "1.0.0",
        "institution": "Dirección General de Aguas — MOP",
        "database_connected": db_online,
    }


# ============================================================================
# Catálogos Institucionales en Cascada (BD_PAR)
# ============================================================================

@app.get("/api/catalogo/tipos-tramite", summary="Listar Tipos de Trámite / Proceso")
def get_tipos_tramite():
    db_ctx = get_db_connection()
    if db_ctx:
        try:
            with db_ctx as conn:
                return {"success": True, "data": op.fetch_tipos_tramite(conn)}
        except Exception:
            pass
    return {"success": True, "data": op.fetch_tipos_tramite(None)}


@app.get("/api/catalogo/regiones", summary="Listar 16 Regiones de Chile (Orden 1 a 16)")
def get_regiones():
    db_ctx = get_db_connection()
    if db_ctx:
        try:
            with db_ctx as conn:
                return {"success": True, "data": op.fetch_regiones(conn)}
        except Exception:
            pass
    return {"success": True, "data": op.fetch_regiones(None)}


@app.get("/api/catalogo/provincias", summary="Listar Provincias según Región")
def get_provincias(reg_codigo: int = Query(..., description="Código de la Región")):
    db_ctx = get_db_connection()
    if db_ctx:
        try:
            with db_ctx as conn:
                return {"success": True, "data": op.fetch_provincias(reg_codigo, conn)}
        except Exception:
            pass
    return {"success": True, "data": op.fetch_provincias(reg_codigo, None)}


@app.get("/api/catalogo/comunas", summary="Listar Comunas según Región y Provincia")
def get_comunas(
    reg_codigo: int = Query(..., description="Código de la Región"),
    pro_codigo: int = Query(..., description="Código de la Provincia"),
):
    db_ctx = get_db_connection()
    if db_ctx:
        try:
            with db_ctx as conn:
                return {"success": True, "data": op.fetch_comunas(reg_codigo, pro_codigo, conn)}
        except Exception:
            pass
    return {"success": True, "data": op.fetch_comunas(reg_codigo, pro_codigo, None)}


# ============================================================================
# Búsqueda y Gestión de Oposiciones (BD_EXP)
# ============================================================================

@app.get("/api/oposiciones/search", summary="Búsqueda de Solicitudes y Expedientes con Oposiciones")
def search_oposiciones(
    reg_codigo: Optional[int] = Query(None, description="Filtrar por Código de Región"),
    pro_codigo: Optional[int] = Query(None, description="Filtrar por Código de Provincia"),
    com_codigo: Optional[int] = Query(None, description="Filtrar por Código de Comuna"),
    tipo_tramite: Optional[str] = Query(None, description="Filtrar por Tipo de Trámite"),
    exp_llave: Optional[str] = Query(None, description="Filtrar por Código de Expediente"),
    solicitante: Optional[str] = Query(None, description="Filtrar por Nombre o RUT del Solicitante"),
):
    db_ctx = get_db_connection()
    results = []
    if db_ctx:
        try:
            with db_ctx as conn:
                results = op.search_expedientes(
                    conn=conn,
                    reg_codigo=reg_codigo,
                    pro_codigo=pro_codigo,
                    com_codigo=com_codigo,
                    tipo_tramite=tipo_tramite,
                    exp_llave=exp_llave,
                    solicitante=solicitante,
                )
        except Exception as exc:
            return {"success": False, "error": str(exc), "data": []}
    else:
        results = op.search_expedientes(
            conn=None,
            reg_codigo=reg_codigo,
            pro_codigo=pro_codigo,
            com_codigo=com_codigo,
            tipo_tramite=tipo_tramite,
            exp_llave=exp_llave,
            solicitante=solicitante,
        )

    # Métricas agregadas
    con_opo = sum(
        1 for r in results
        if (r.get("NumOposicionesRaw", 0) > 0) or (" - Sí" in str(r.get("NumOposiciones", "")))
    )

    return {
        "success": True,
        "total": len(results),
        "con_oposiciones": con_opo,
        "en_tramite": len(results) - con_opo,
        "data": results,
    }


@app.get("/api/oposiciones/detalle", summary="Consultar Detalle de Oposiciones de un Expediente")
def get_detalle_oposiciones(exp_codigo: str = Query(..., description="Código del Expediente")):
    db_ctx = get_db_connection()
    if db_ctx:
        try:
            with db_ctx as conn:
                items = op.fetch_oposiciones_detalle(exp_codigo, conn)
                return {"success": True, "exp_codigo": exp_codigo, "data": items}
        except Exception as exc:
            return {"success": False, "error": str(exc), "data": []}

    items = op.fetch_oposiciones_detalle(exp_codigo, None)
    return {"success": True, "exp_codigo": exp_codigo, "data": items}



@app.post("/api/oposiciones/agregar", summary="Registrar Oposición Oficial en BD_EXP")
def post_agregar_oposicion(payload: OposicionPayload):
    # 1. Validación estricta Módulo 11 del RUT
    if not op.validate_rut(payload.opositor_rut):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El RUT '{payload.opositor_rut}' no es válido según algoritmo Módulo 11 oficial chileno.",
        )

    db_ctx = get_db_connection()
    if db_ctx:
        try:
            with db_ctx as conn:
                resp = op.agregar_oposicion(
                    exp_codigo=payload.exp_codigo,
                    fecha_ingreso=payload.fecha_ingreso,
                    doc_nro=payload.doc_nro,
                    opositor_nombre=payload.opositor_nombre,
                    opositor_rut=payload.opositor_rut,
                    observaciones=payload.observaciones,
                    conn=conn,
                )
                if not resp.get("success"):
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=resp.get("message"))
                return resp
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error transaccional SQL al registrar oposición: {exc}",
            )
    else:
        # Modo simulación controlada
        resp = op.agregar_oposicion(
            exp_codigo=payload.exp_codigo,
            fecha_ingreso=payload.fecha_ingreso,
            doc_nro=payload.doc_nro,
            opositor_nombre=payload.opositor_nombre,
            opositor_rut=payload.opositor_rut,
            observaciones=payload.observaciones,
            conn=None,
        )
        if not resp.get("success"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=resp.get("message"))
        return resp
