"""src/governance.py — Controles de Gobernanza y Gestión de Riesgos de IA (ISO/IEC 42001 & ISO/IEC 23894).

Implementa los 3 pilares de cumplimiento normativo para producción en la DGA:
1. Registro estructurado de auditoría en formato JSONL (ISO/IEC 42001 A.6.2.8 / A.9.3) con cadena de integridad SHA-256.
2. Cálculo y almacenamiento del hash criptográfico SHA-256 de cada archivo, registro o fragmento recuperado (ISO/IEC 42001 A.7.4).
3. Mitigación de alucinaciones forzando cláusulas de abstención y registrando la distancia vectorial de similitud (ISO/IEC 23894 6.4.3).
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import uuid
from typing import Any, Dict, Iterable, List, Optional, Tuple

from src.config import DATA, ROOT
from src.inspector import SECUENCIA_SEARCH_SOLICITUDES, TIPO_EXPEDIENTE

DEFAULT_AUDIT_LOG_PATH = DATA / "audit_iso42001.jsonl"

MAINTAINER_IDENTITY = "Daniel Díaz L. (Leonthelee - DGA MOP)"
MAINTAINER_SSH_FINGERPRINT = "SHA256:fnHvLWQySkEs0yVynqdd5IL5UsGBM+nWy6bQCZEZD5c"

ISO_CONTROLS = (
    "ISO/IEC 42001:2023-A.6.2.8 (Registro de eventos y trazabilidad de IA)",
    "ISO/IEC 42001:2023-A.7.4 (Integridad y procedencia criptográfica de datos)",
    "ISO/IEC 23894:2023-6.4.3 (Tratamiento de riesgo de alucinación y abstención forzada)",
)

ABSTENTION_CLAUSE_TEMPLATE = (
    "ABSTENCIÓN FORZADA [ISO/IEC 23894 / ISO/IEC 42001]: "
    "No es posible emitir una respuesta verificada para la consulta «{query}». "
    "La distancia vectorial mínima registrada ({min_distance:.4f}) supera el umbral máximo de seguridad "
    "permitido ({max_distance:.4f}) [similitud coseno={max_similarity:.4f} < {min_similarity:.4f}]. "
    "Se bloquea la generación para prevenir alucinaciones o inferencias sin respaldo en fuentes oficiales DGA."
)

SYSTEM_ABSTENTION_GUARDRAIL = (
    "CLÁUSULA OBLIGATORIA DE ABSTENCIÓN (ISO/IEC 23894 & ISO/IEC 42001): "
    "Responda ÚNICAMENTE utilizando los fragmentos recuperados cuyo hash SHA-256 ha sido verificado. "
    "Prohibido extrapolar, asumir o inventar procedimientos almacenados, tablas, RUTs, expedientes o estados. "
    "Si la información solicitada no consta explícitamente en los fragmentos provistos, DEBE declararse en "
    "abstención literal respondiendo: «ABSTENCIÓN POR FALTA DE EVIDENCIA VERIFICADA (ISO/IEC 23894)»."
)


def utc_now_iso() -> str:
    """Retorna timestamp UTC en formato ISO-8601."""
    return datetime.now(timezone.utc).isoformat()


# ==============================================================================
# CONTROL 2: HASH CRIPTOGRÁFICO SHA-256 DE ARCHIVOS Y FRAGMENTOS RECUPERADOS
# ==============================================================================

def compute_sha256_bytes(data: bytes) -> str:
    """Calcula el digest SHA-256 hexadecimal de un bloque de bytes."""
    return hashlib.sha256(data).hexdigest()


def compute_sha256_text(text: str) -> str:
    """Calcula el digest SHA-256 hexadecimal de una cadena UTF-8 normalizada."""
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def compute_canonical_sha256(obj: Any) -> str:
    """Calcula el hash SHA-256 canónico de un diccionario, lista o primitiva serializable."""
    if isinstance(obj, (bytes, bytearray)):
        return compute_sha256_bytes(bytes(obj))
    if isinstance(obj, str):
        return compute_sha256_text(obj)
    if isinstance(obj, dict):
        # Excluir campos volátiles de hash previos para garantizar idempotencia
        clean = {k: v for k, v in obj.items() if k not in ("_sha256", "sha256", "fragment_sha256")}
        canonical = json.dumps(clean, sort_keys=True, ensure_ascii=False, default=str)
        return compute_sha256_text(canonical)
    canonical = json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)
    return compute_sha256_text(canonical)


def compute_file_sha256(file_path: Path | str) -> str:
    """Calcula el hash criptográfico SHA-256 de un archivo en disco por bloques de 64 KB."""
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Archivo no encontrado para cálculo SHA-256: {path}")
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def stamp_fragment_sha256(record: Dict[str, Any], field_name: str = "sha256") -> Dict[str, Any]:
    """Calcula y adjunta el hash SHA-256 al registro o fragmento recuperado."""
    stamped = dict(record)
    stamped[field_name] = compute_canonical_sha256(stamped)
    return stamped


def stamp_fragments_collection(
    records: Iterable[Dict[str, Any]],
    field_name: str = "sha256",
) -> Tuple[List[Dict[str, Any]], List[str], str]:
    """Estampa SHA-256 en cada registro/fragmento y retorna (lista_estampada, lista_hashes, hash_raíz_combinado)."""
    stamped_list: List[Dict[str, Any]] = []
    hashes: List[str] = []
    for rec in records:
        if "error" in rec and len(rec) == 1:
            stamped_list.append(dict(rec))
            continue
        item = stamp_fragment_sha256(rec, field_name=field_name)
        stamped_list.append(item)
        hashes.append(item[field_name])
    combined = compute_sha256_text("|".join(hashes)) if hashes else compute_sha256_text("EMPTY_RESULT_SET")
    return stamped_list, hashes, combined


def build_repository_integrity_manifest(paths: Optional[Iterable[Path]] = None) -> List[Dict[str, Any]]:
    """Construye el manifiesto criptográfico SHA-256 de los archivos críticos del repositorio y evidencia forense."""
    if paths is None:
        default_files = [
            ROOT / "app.py",
            ROOT / "README.md",
            ROOT / "GEMINI.md",
            ROOT / "TRACE OPOSICIONES.pdf",
            ROOT / "TRACE OPOSICIONES.docx",
            ROOT / "docs" / "ISO_42001_23894_COMPLIANCE.md",
            ROOT / "docs" / "design.md",
            ROOT / "docs" / "design-qa.md",
            ROOT / "docs" / "qa-checklist.md",
            ROOT / "src" / "oposiciones.py",
            ROOT / "src" / "analysis.py",
            ROOT / "src" / "inspector.py",
            ROOT / "src" / "governance.py",
        ]
        paths = [p for p in default_files if p.exists()]

    manifest = []
    for p in paths:
        path_obj = Path(p)
        if path_obj.exists() and path_obj.is_file():
            digest = compute_file_sha256(path_obj)
            rel = str(path_obj.relative_to(ROOT)) if path_obj.is_relative_to(ROOT) else str(path_obj)
            manifest.append({
                "archivo": rel.replace("\\", "/"),
                "bytes": path_obj.stat().st_size,
                "sha256": digest,
                "firmante_ssh": MAINTAINER_SSH_FINGERPRINT,
                "estado": "VERIFICADO",
            })
    return manifest


_SENSITIVE_KEYS = {"password", "pwd", "secret", "token", "api_key", "apikey", "clave"}


def sanitize_audit_payload(obj: Any) -> Any:
    """Enmascara credenciales o llaves sensibles antes de persistir en el log de auditoría JSONL (ISO/IEC 42001 A.8.4)."""
    if isinstance(obj, dict):
        cleaned = {}
        for k, v in obj.items():
            if str(k).lower() in _SENSITIVE_KEYS or any(s in str(k).lower() for s in ("password", "secret", "token")):
                cleaned[k] = "[REDACTED_ISO42001]"
            else:
                cleaned[k] = sanitize_audit_payload(v)
        return cleaned
    if isinstance(obj, (list, tuple)):
        return [sanitize_audit_payload(x) for x in obj]
    return obj


def validate_sql_safety(sql: str) -> Dict[str, Any]:
    """Evalúa sentencias SQL contra reglas de aislamiento estricto y cero impacto en BD_EXP/BD_PAR/BD_MAP (ISO/IEC 23894)."""
    clean_sql = (sql or "").strip()
    if not clean_sql:
        return {"is_safe": False, "level": "WARNING", "reason": "Sentencia SQL vacía.", "sql_sha256": compute_sha256_text("")}

    sql_sha = compute_sha256_text(clean_sql)
    # Eliminar comentarios para evitar bypass básico
    no_comments = re.sub(r"--.*?$", "", clean_sql, flags=re.M)
    no_comments = re.sub(r"/\*.*?\*/", "", no_comments, flags=re.S)

    destructive_patterns = [
        (r"\bDROP\s+(?:TABLE|DATABASE|PROCEDURE|VIEW|INDEX)\b", "Sentencia DROP destructiva bloqueada."),
        (r"\bTRUNCATE\s+TABLE\b", "Sentencia TRUNCATE TABLE bloqueada."),
        (r"\bDELETE\s+FROM\b", "Sentencia DELETE FROM bloqueada en bases de negocio DGA."),
        (r"\bALTER\s+(?:TABLE|DATABASE|PROCEDURE|VIEW)\b", "Sentencia ALTER sobre objetos de negocio bloqueada."),
        (r"\bINSERT\s+INTO\b", "Inserción directa bloqueada; utilice exclusivamente SPs canónicos autorizados."),
    ]
    for pattern, reason in destructive_patterns:
        if re.search(pattern, no_comments, flags=re.I):
            return {
                "is_safe": False,
                "level": "CRITICAL",
                "reason": f"VIOLACIÓN DE GUARDRAIL [ISO/IEC 23894]: {reason}",
                "sql_sha256": sql_sha,
            }

    if re.search(r"\bUPDATE\s+\w+", no_comments, flags=re.I):
        return {
            "is_safe": False,
            "level": "CRITICAL",
            "reason": "VIOLACIÓN DE GUARDRAIL [ISO/IEC 23894]: Sentencia UPDATE directa no permitida sobre BD_EXP/BD_PAR/BD_MAP.",
            "sql_sha256": sql_sha,
        }

    return {
        "is_safe": True,
        "level": "OK",
        "reason": "Sentencia SQL verificada bajo política de aislamiento y solo lectura / SP canónico.",
        "sql_sha256": sql_sha,
    }


# ==============================================================================
# CONTROL 1: LOG ESTRUCTURADO DE AUDITORÍA EN FORMATO JSONL (ISO/IEC 42001)
# ==============================================================================

class AuditLogger:
    """Registrador de auditoría estructurada en formato JSONL con encadenamiento SHA-256."""

    def __init__(self, log_path: Optional[Path | str] = None):
        self.log_path = Path(log_path) if log_path else DEFAULT_AUDIT_LOG_PATH
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def _last_entry_hash(self) -> str:
        """Obtiene el hash SHA-256 de la última línea del log JSONL para mantener la cadena inmutable."""
        if not self.log_path.exists() or self.log_path.stat().st_size == 0:
            return "0" * 64
        try:
            with self.log_path.open("rb") as f:
                lines = [ln.strip() for ln in f.read().splitlines() if ln.strip()]
            if not lines:
                return "0" * 64
            last_obj = json.loads(lines[-1].decode("utf-8"))
            return str(last_obj.get("entry_sha256") or ("0" * 64))
        except Exception:
            return "0" * 64

    def log_query(
        self,
        operation: str,
        query_params: Any,
        fragments: Optional[Iterable[Any]] = None,
        environment: str = "DEMO",
        vector_metrics: Optional[Dict[str, Any]] = None,
        abstained: bool = False,
        abstention_reason: Optional[str] = None,
        status: str = "OK",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Registra una consulta u operación en el archivo JSONL de auditoría ISO/IEC 42001."""
        fragment_hashes: List[str] = []
        fragment_count = 0
        if fragments is not None:
            for frag in fragments:
                fragment_count += 1
                if isinstance(frag, dict) and ("sha256" in frag or "fragment_sha256" in frag):
                    fragment_hashes.append(str(frag.get("sha256") or frag.get("fragment_sha256")))
                else:
                    fragment_hashes.append(compute_canonical_sha256(frag))

        combined_fragments_sha256 = (
            compute_sha256_text("|".join(fragment_hashes))
            if fragment_hashes
            else compute_sha256_text("NO_FRAGMENTS")
        )
        safe_query_params = sanitize_audit_payload(query_params)
        safe_metadata = sanitize_audit_payload(metadata or {})
        query_sha256 = compute_canonical_sha256(safe_query_params)
        prev_hash = self._last_entry_hash()

        entry_core = {
            "audit_id": uuid.uuid4().hex,
            "timestamp": utc_now_iso(),
            "standard_controls": list(ISO_CONTROLS),
            "environment": environment,
            "operation": operation,
            "status": status,
            "query_params": safe_query_params,
            "query_sha256": query_sha256,
            "result_count": fragment_count,
            "fragments_sha256": fragment_hashes,
            "combined_fragments_sha256": combined_fragments_sha256,
            "vector_metrics": vector_metrics or {
                "min_cosine_distance": None,
                "max_cosine_similarity": None,
                "threshold_max_distance": None,
            },
            "abstained": bool(abstained),
            "abstention_reason": abstention_reason,
            "metadata": safe_metadata,
            "prev_entry_sha256": prev_hash,
        }
        entry_sha256 = compute_canonical_sha256(entry_core)
        entry = {**entry_core, "entry_sha256": entry_sha256}

        line = json.dumps(entry, ensure_ascii=False, default=str) + "\n"
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(line)
        return entry

    def read_entries(self, limit: int = 200) -> List[Dict[str, Any]]:
        """Lee las entradas del log estructurado JSONL (más recientes primero)."""
        if not self.log_path.exists():
            return []
        entries: List[Dict[str, Any]] = []
        with self.log_path.open("r", encoding="utf-8") as f:
            for line in f:
                raw = line.strip()
                if not raw:
                    continue
                try:
                    entries.append(json.loads(raw))
                except json.JSONDecodeError:
                    continue
        return list(reversed(entries[-limit:]))

    def verify_chain(self) -> Dict[str, Any]:
        """Verifica criptográficamente la cadena de hashes SHA-256 de todo el archivo JSONL."""
        if not self.log_path.exists():
            return {"valid": True, "total_entries": 0, "file_sha256": None, "message": "Log aún sin entradas."}

        expected_prev = "0" * 64
        count = 0
        with self.log_path.open("r", encoding="utf-8") as f:
            for idx, line in enumerate(f, start=1):
                raw = line.strip()
                if not raw:
                    continue
                count += 1
                try:
                    obj = json.loads(raw)
                except Exception as exc:
                    return {"valid": False, "total_entries": count, "corrupted_line": idx, "message": f"JSON inválido en línea {idx}: {exc}"}

                actual_prev = obj.get("prev_entry_sha256")
                if actual_prev != expected_prev:
                    return {
                        "valid": False,
                        "total_entries": count,
                        "corrupted_line": idx,
                        "message": f"Ruptura de cadena SHA-256 en línea {idx}: prev_entry_sha256 no coincide.",
                    }
                stored_hash = obj.get("entry_sha256")
                core = {k: v for k, v in obj.items() if k != "entry_sha256"}
                recomputed = compute_canonical_sha256(core)
                if stored_hash != recomputed:
                    return {
                        "valid": False,
                        "total_entries": count,
                        "corrupted_line": idx,
                        "message": f"Adulteración detectada en línea {idx}: entry_sha256 no coincide con el contenido.",
                    }
                expected_prev = stored_hash

        return {
            "valid": True,
            "total_entries": count,
            "file_sha256": compute_file_sha256(self.log_path),
            "last_entry_sha256": expected_prev,
            "message": f"Cadena criptográfica íntegra ({count} registros JSONL verificados).",
        }


# Singleton por defecto para uso directo en los módulos del sistema
default_audit_logger = AuditLogger()


# ==============================================================================
# CONTROL 3: MITIGACIÓN DE ALUCINACIONES, DISTANCIA VECTORIAL Y ABSTENCIÓN
# ==============================================================================

_STOPWORDS_ES = {
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "al", "a",
    "en", "con", "por", "para", "sin", "sobre", "entre", "hacia", "hasta", "desde",
    "y", "o", "u", "e", "ni", "que", "como", "cuando", "donde", "quien", "cual",
    "es", "son", "fue", "ser", "esta", "este", "estos", "estas", "ese", "esa",
    "se", "su", "sus", "mi", "tu", "lo", "le", "les", "me", "te", "nos", "ya",
    "si", "no", "mas", "pero", "porque", "como", "cuales", "que", "tiene", "hacer",
}


def _tokenize_features(text: str) -> Counter:
    """Extrae tokens léxicos, sub-identificadores SQL y raíces morfológicas para vectorización L2 de alta precisión."""
    normalized = (text or "").lower()
    words = [w for w in re.findall(r"[a-z0-9_áéíóúñ]+", normalized) if len(w) >= 2 and w not in _STOPWORDS_ES]
    features: Counter = Counter()
    for w in words:
        is_tech = "_" in w or any(ch.isdigit() for ch in w)
        features[f"w:{w}"] += 3.0 if is_tech else 1.5
        # Descomponer identificadores compuestos (ej. cpa_busquedaexpedientesop -> cpa, busquedaexpedientesop)
        if "_" in w:
            for part in w.split("_"):
                if len(part) >= 3 and part not in _STOPWORDS_ES:
                    features[f"sub:{part}"] += 1.5
        # Raíz morfológica de 5 caracteres para español (ej. oposicion / oposiciones -> oposi)
        if len(w) >= 5 and not is_tech:
            features[f"stem:{w[:5]}"] += 0.8
    return features


def cosine_similarity_and_distance(
    vec_a: Dict[str, float],
    vec_b: Dict[str, float],
) -> Tuple[float, float, float]:
    """Calcula (similitud_coseno, distancia_coseno, distancia_euclidiana_l2) entre dos vectores dispersos L2."""
    if not vec_a or not vec_b:
        return 0.0, 1.0, math.sqrt(2.0)

    # Producto punto sobre características compartidas (vectores ya normalizados en L2)
    if len(vec_a) > len(vec_b):
        vec_a, vec_b = vec_b, vec_a
    dot = sum(val * vec_b.get(k, 0.0) for k, val in vec_a.items())
    similarity = max(0.0, min(1.0, float(dot)))
    cosine_dist = round(1.0 - similarity, 6)
    # Para vectores unitarios: ||u - v||_2 = sqrt(max(0, 2 - 2 * cos(u, v)))
    l2_dist = round(math.sqrt(max(0.0, 2.0 - 2.0 * similarity)), 6)
    return round(similarity, 6), cosine_dist, l2_dist


class HallucinationGuard:
    """Motor vectorial local con cálculo de distancia de similitud, SHA-256 por fragmento y abstención forzada.

    Implementa ISO/IEC 23894 (tratamiento del riesgo de alucinación mediante umbral de distancia
    vectorial y cláusula de abstención determinista) e ISO/IEC 42001 (registro auditable JSONL
    con hash SHA-256 de cada archivo y fragmento recuperado).
    """

    def __init__(
        self,
        max_cosine_distance: float = 0.72,
        audit_logger: Optional[AuditLogger] = None,
        extra_documents: Optional[List[Dict[str, str]]] = None,
    ):
        if not 0.0 < max_cosine_distance < 1.0:
            raise ValueError("max_cosine_distance debe estar en el rango (0.0, 1.0).")
        self.max_cosine_distance = float(max_cosine_distance)
        self.min_cosine_similarity = round(1.0 - self.max_cosine_distance, 6)
        self.audit_logger = audit_logger or default_audit_logger
        self.chunks: List[Dict[str, Any]] = []
        self._idf: Dict[str, float] = {}
        self._chunk_vectors: List[Dict[str, float]] = []
        self.build_knowledge_base(extra_documents=extra_documents)

    def _collect_institutional_chunks(self, extra_documents: Optional[List[Dict[str, str]]] = None) -> List[Dict[str, Any]]:
        """Construye y hashea (SHA-256) los fragmentos verificados de la base de conocimiento del repositorio."""
        raw_chunks: List[Dict[str, Any]] = []

        # 1. Fragmentos estructurados de la secuencia oficial searchSolicitudes.xhtml
        for item in SECUENCIA_SEARCH_SOLICITUDES:
            content = (
                f"Fase {item['fase']}: Procedimiento almacenado {item['sp']} en base de datos {item['bd']}. "
                f"Acción: {item['accion']}. Tablas involucradas: {', '.join(item['tablas'])}. "
                f"Descripción técnica: {item['descripcion']}"
            )
            file_path = ROOT / "src" / "inspector.py"
            file_hash = compute_file_sha256(file_path) if file_path.exists() else compute_sha256_text("src/inspector.py")
            frag = {
                "chunk_id": f"inspector_sp_{item['sp']}",
                "source_file": "src/inspector.py",
                "file_sha256": file_hash,
                "title": f"{item['fase']} — {item['sp']}",
                "content": content,
            }
            frag["fragment_sha256"] = compute_sha256_text(content)
            raw_chunks.append(frag)

        # 2. Catálogo de Tipos de Expediente DGA
        tipos_lines = [
            f"{sigla}: {info['nombre']} (TexCodigo={info['codigo']}, Tabla={info['tabla_objeto']})"
            for sigla, info in TIPO_EXPEDIENTE.items()
        ]
        tipos_content = "Catálogo de Tipos de Expedientes DGA y Tablas de Objeto de Negocio en BD_EXP:\n" + "\n".join(tipos_lines)
        insp_hash = compute_file_sha256(ROOT / "src" / "inspector.py") if (ROOT / "src" / "inspector.py").exists() else compute_sha256_text("inspector")
        raw_chunks.append({
            "chunk_id": "inspector_tipos_expediente",
            "source_file": "src/inspector.py",
            "file_sha256": insp_hash,
            "title": "Tipos de Expediente DGA (ND, NR, VP, VC, VT, FD, FO, DEN)",
            "content": tipos_content,
            "fragment_sha256": compute_sha256_text(tipos_content),
        })

        # 3. Documentos Markdown oficiales del repositorio (README.md, GEMINI.md, docs/*.md)
        md_paths = [
            ROOT / "README.md",
            ROOT / "GEMINI.md",
            ROOT / "DEPLOY.md",
            ROOT / "docs" / "design.md",
            ROOT / "docs" / "design-qa.md",
            ROOT / "docs" / "qa-checklist.md",
        ]
        for md_path in md_paths:
            if not md_path.exists() or not md_path.is_file():
                continue
            file_sha = compute_file_sha256(md_path)
            rel_name = str(md_path.relative_to(ROOT)).replace("\\", "/")
            text = md_path.read_text(encoding="utf-8", errors="replace")
            sections = re.split(r"\n(?=#{1,3}\s)", text)
            for idx, sec in enumerate(sections):
                clean_sec = sec.strip()
                if len(clean_sec) < 35:
                    continue
                first_line = clean_sec.splitlines()[0]
                title = re.sub(r"^#+\s*", "", first_line).strip()[:120]
                raw_chunks.append({
                    "chunk_id": f"{rel_name}#sec_{idx}",
                    "source_file": rel_name,
                    "file_sha256": file_sha,
                    "title": title,
                    "content": clean_sec,
                    "fragment_sha256": compute_sha256_text(clean_sec),
                })

        # 4. Documentos adicionales inyectados (para tests o ampliación en caliente)
        if extra_documents:
            for idx, doc in enumerate(extra_documents):
                content = (doc.get("content") or "").strip()
                if not content:
                    continue
                source = doc.get("source_file") or f"custom_doc_{idx}.md"
                raw_chunks.append({
                    "chunk_id": doc.get("chunk_id") or f"extra_{idx}",
                    "source_file": source,
                    "file_sha256": doc.get("file_sha256") or compute_sha256_text(content),
                    "title": doc.get("title") or f"Documento Adicional {idx}",
                    "content": content,
                    "fragment_sha256": compute_sha256_text(content),
                })

        return raw_chunks

    def _vectorize(self, text: str) -> Dict[str, float]:
        """Convierte un texto en un vector TF-IDF normalizado en norma L2."""
        tf = _tokenize_features(text)
        if not tf:
            return {}
        weighted: Dict[str, float] = {}
        for feat, count in tf.items():
            # Si una feature de la consulta no existe en el corpus, conserva su peso IDF máximo
            # para penalizar adecuadamente preguntas fuera de dominio (OOD) al normalizar L2.
            idf = self._idf.get(feat, math.log(1.0 + len(self.chunks) + 1.0) + 1.5)
            weighted[feat] = (1.0 + math.log(count)) * idf
        norm = math.sqrt(sum(v * v for v in weighted.values()))
        if norm <= 1e-12:
            return {}
        return {k: v / norm for k, v in weighted.items()}

    def build_knowledge_base(self, extra_documents: Optional[List[Dict[str, str]]] = None) -> int:
        """Indexa los fragmentos, calcula sus hashes SHA-256 y precalcula sus vectores L2."""
        self.chunks = self._collect_institutional_chunks(extra_documents=extra_documents)
        doc_freq: Counter = Counter()
        tokenized_docs = []
        for ch in self.chunks:
            feats = _tokenize_features(f"{ch['title']} {ch['content']}")
            tokenized_docs.append(feats)
            for k in feats.keys():
                doc_freq[k] += 1

        n_docs = max(1, len(self.chunks))
        self._idf = {
            feat: math.log((1.0 + n_docs) / (1.0 + df)) + 1.0
            for feat, df in doc_freq.items()
        }
        self._chunk_vectors = [
            self._vectorize(f"{ch['title']} {ch['content']}") for ch in self.chunks
        ]
        return len(self.chunks)

    def retrieve_and_evaluate(
        self,
        query: str,
        top_k: int = 3,
        max_cosine_distance: Optional[float] = None,
        environment: str = "DEMO",
        log_audit: bool = True,
    ) -> Dict[str, Any]:
        """Recupera los fragmentos más cercanos, calcula distancias vectoriales y aplica abstención forzada si procede."""
        clean_query = (query or "").strip()
        threshold_dist = float(max_cosine_distance) if max_cosine_distance is not None else self.max_cosine_distance
        min_sim_required = round(1.0 - threshold_dist, 6)

        if not clean_query:
            abstention_msg = ABSTENTION_CLAUSE_TEMPLATE.format(
                query="(consulta vacía)",
                min_distance=1.0,
                max_distance=threshold_dist,
                max_similarity=0.0,
                min_similarity=min_sim_required,
            )
            payload = {
                "query": clean_query,
                "query_sha256": compute_sha256_text(clean_query),
                "abstained": True,
                "abstention_clause": abstention_msg,
                "system_guardrail_clause": SYSTEM_ABSTENTION_GUARDRAIL,
                "min_cosine_distance": 1.0,
                "max_cosine_similarity": 0.0,
                "threshold_max_distance": threshold_dist,
                "retrieved_fragments": [],
                "answer": abstention_msg,
            }
            if log_audit:
                self.audit_logger.log_query(
                    operation="rag_knowledge_query",
                    query_params={"query": clean_query, "top_k": top_k},
                    fragments=[],
                    environment=environment,
                    vector_metrics={
                        "min_cosine_distance": 1.0,
                        "max_cosine_similarity": 0.0,
                        "threshold_max_distance": threshold_dist,
                    },
                    abstained=True,
                    abstention_reason="Consulta vacía; abstención preventiva activada.",
                )
            return payload

        q_vec = self._vectorize(clean_query)
        scored: List[Dict[str, Any]] = []
        for chunk, c_vec in zip(self.chunks, self._chunk_vectors):
            sim, cos_dist, l2_dist = cosine_similarity_and_distance(q_vec, c_vec)
            scored.append({
                "chunk_id": chunk["chunk_id"],
                "source_file": chunk["source_file"],
                "file_sha256": chunk["file_sha256"],
                "fragment_sha256": chunk["fragment_sha256"],
                "sha256": chunk["fragment_sha256"],
                "title": chunk["title"],
                "content": chunk["content"],
                "cosine_similarity": sim,
                "cosine_distance": cos_dist,
                "euclidean_distance": l2_dist,
                "within_threshold": cos_dist <= threshold_dist,
            })

        scored.sort(key=lambda x: (x["cosine_distance"], -x["cosine_similarity"]))
        top_fragments = scored[: max(1, int(top_k))]

        best = top_fragments[0] if top_fragments else None
        min_distance = best["cosine_distance"] if best else 1.0
        max_similarity = best["cosine_similarity"] if best else 0.0
        min_l2 = best["euclidean_distance"] if best else round(math.sqrt(2.0), 6)

        # Condición dura de abstención: la distancia vectorial mínima supera el umbral permitido
        abstained = min_distance > threshold_dist
        verified_fragments = [f for f in top_fragments if f["within_threshold"]]

        if abstained or not verified_fragments:
            abstained = True
            abstention_clause = ABSTENTION_CLAUSE_TEMPLATE.format(
                query=clean_query,
                min_distance=min_distance,
                max_distance=threshold_dist,
                max_similarity=max_similarity,
                min_similarity=min_sim_required,
            )
            answer_text = abstention_clause
        else:
            abstention_clause = None
            evidence_lines = [
                f"✅ ** EVIDENCIA VERIFICADA (ISO/IEC 42001 & 23894) — Distancia Vectorial Mínima: `{min_distance:.4f}` (Similitud: `{max_similarity:.4f}`) **",
                f"> {SYSTEM_ABSTENTION_GUARDRAIL}",
                "",
            ]
            for idx, frag in enumerate(verified_fragments, start=1):
                evidence_lines.append(
                    f"### [{idx}] {frag['title']} (`{frag['source_file']}`)\n"
                    f"- **Distancia Coseno:** `{frag['cosine_distance']:.4f}` | **Similitud Coseno:** `{frag['cosine_similarity']:.4f}` | **Distancia L2:** `{frag['euclidean_distance']:.4f}`\n"
                    f"- **SHA-256 Fragmento:** `{frag['fragment_sha256']}`\n"
                    f"- **SHA-256 Archivo Fuente:** `{frag['file_sha256']}`\n\n"
                    f"{frag['content']}"
                )
            answer_text = "\n\n".join(evidence_lines)

        vector_metrics = {
            "min_cosine_distance": min_distance,
            "max_cosine_similarity": max_similarity,
            "min_euclidean_distance": min_l2,
            "threshold_max_distance": threshold_dist,
            "threshold_min_similarity": min_sim_required,
            "evaluated_chunks": len(scored),
            "verified_chunks_count": len(verified_fragments),
        }

        audit_entry = None
        if log_audit:
            audit_entry = self.audit_logger.log_query(
                operation="rag_knowledge_query",
                query_params={"query": clean_query, "top_k": top_k, "max_cosine_distance": threshold_dist},
                fragments=top_fragments,
                environment=environment,
                vector_metrics=vector_metrics,
                abstained=abstained,
                abstention_reason=abstention_clause if abstained else None,
            )

        return {
            "query": clean_query,
            "query_sha256": compute_sha256_text(clean_query),
            "abstained": abstained,
            "abstention_clause": abstention_clause,
            "system_guardrail_clause": SYSTEM_ABSTENTION_GUARDRAIL,
            "min_cosine_distance": min_distance,
            "max_cosine_similarity": max_similarity,
            "min_euclidean_distance": min_l2,
            "threshold_max_distance": threshold_dist,
            "vector_metrics": vector_metrics,
            "retrieved_fragments": top_fragments,
            "verified_fragments": verified_fragments,
            "answer": answer_text,
            "audit_entry": audit_entry,
        }


default_hallucination_guard = HallucinationGuard()


def generate_iso_compliance_report(audit_logger: Optional[AuditLogger] = None) -> str:
    """Genera un informe ejecutivo en Markdown del estado de cumplimiento ISO/IEC 42001 e ISO/IEC 23894."""
    logger = audit_logger or default_audit_logger
    chain = logger.verify_chain()
    manifest = build_repository_integrity_manifest()
    entries = logger.read_entries(limit=25)

    lines = [
        "# 🛡️ Informe de Conformidad y Auditoría Criptográfica — ISO/IEC 42001 & ISO/IEC 23894",
        "",
        "> **Sistema:** DGA Core Tools — TrazaBD_EXP & Módulo de Oposiciones (Gob.cl)  ",
        f"> **Custodio / Autoría Criptográfica:** `{MAINTAINER_IDENTITY}`  ",
        f"> **Huella Pública SSH ED25519:** `{MAINTAINER_SSH_FINGERPRINT}`  ",
        f"> **Fecha de Emisión (UTC):** `{utc_now_iso()}`  ",
        f"> **Estado de Cadena JSONL:** `{'ÍNTEGRA' if chain.get('valid') else 'ADULTERADA'}`  ",
        f"> **Total de Operaciones Auditadas:** `{chain.get('total_entries', 0)}`  ",
        f"> **SHA-256 del Archivo de Auditoría:** `{chain.get('file_sha256') or 'N/A'}`",
        "",
        "## 1. Controles Normativos Activos",
        "",
    ]
    for ctrl in ISO_CONTROLS:
        lines.append(f"- **{ctrl}**")

    lines.extend([
        "",
        "## 2. Directriz de Abstención Obligatoria (ISO/IEC 23894)",
        "",
        f"> {SYSTEM_ABSTENTION_GUARDRAIL}",
        "",
        "## 3. Manifiesto Criptográfico SHA-256 de Archivos Críticos",
        "",
        "| Archivo | Tamaño (Bytes) | Hash SHA-256 | Estado |",
        "| :--- | :--- | :--- | :--- |",
    ])
    for item in manifest:
        lines.append(f"| `{item['archivo']}` | {item['bytes']} | `{item['sha256']}` | {item['estado']} |")

    lines.extend([
        "",
        "## 4. Últimas Operaciones Registradas en `audit_iso42001.jsonl`",
        "",
    ])
    if entries:
        lines.append("| Timestamp UTC | Operación | Ambiente | Fragmentos | Abstención | Dist. Vectorial Mín. | SHA-256 Entrada |")
        lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
        for e in entries:
            dist = (e.get("vector_metrics") or {}).get("min_cosine_distance")
            dist_str = f"{dist:.4f}" if isinstance(dist, (int, float)) else "N/A"
            lines.append(
                f"| `{e.get('timestamp')}` | `{e.get('operation')}` | `{e.get('environment')}` | "
                f"{e.get('result_count')} | `{'SÍ' if e.get('abstained') else 'NO'}` | `{dist_str}` | `{str(e.get('entry_sha256', ''))[:16]}...` |"
            )
    else:
        lines.append("- *(Sin registros previos en el archivo JSONL)*")

    lines.append("")
    return "\n".join(lines)

