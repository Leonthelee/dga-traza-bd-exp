"""tests/test_governance.py — Pruebas de cumplimiento ISO/IEC 42001 e ISO/IEC 23894.

Verifica:
1. Registro estructurado de cada consulta en formato JSONL con encadenamiento criptográfico SHA-256.
2. Cálculo y almacenamiento del hash SHA-256 de cada archivo o fragmento recuperado.
3. Mitigación de alucinaciones forzando cláusulas de abstención y registrando la distancia vectorial de similitud.
"""

import json
import pytest

from src.demo import demo_events
from src.export import markdown_rag_summary
from src.governance import (
    AuditLogger,
    HallucinationGuard,
    SYSTEM_ABSTENTION_GUARDRAIL,
    build_repository_integrity_manifest,
    compute_canonical_sha256,
    compute_file_sha256,
    compute_sha256_text,
    stamp_fragments_collection,
)
from src.oposiciones import (
    agregar_oposicion,
    fetch_oposiciones_detalle,
    search_expedientes,
)


def test_jsonl_audit_log_structure_and_tamper_evident_chain(tmp_path):
    log_file = tmp_path / "audit_iso42001.jsonl"
    logger = AuditLogger(log_path=log_file)

    # Ejecutar múltiples consultas en el módulo de oposiciones
    res_search = search_expedientes(reg_codigo=8, conn=None, audit_logger=logger)
    assert len(res_search) >= 1
    assert all(len(r.get("sha256", "")) == 64 for r in res_search)

    res_det = fetch_oposiciones_detalle("ND-0802-4437", conn=None, audit_logger=logger)
    assert len(res_det) >= 1
    assert all(len(d.get("sha256", "")) == 64 for d in res_det)

    res_add = agregar_oposicion(
        exp_codigo="ND-9999-9999",
        fecha_ingreso="15/10/2026",
        doc_nro="SSD-2026-777",
        opositor_nombre="JUNTA DE VIGILANCIA RIO BIOBIO",
        opositor_rut="76122587-1",
        conn=None,
        audit_logger=logger,
    )
    assert res_add["success"] is True
    assert len(res_add.get("sha256", "")) == 64

    # Verificar que el archivo JSONL existe y tiene 3 líneas válidas
    assert log_file.exists()
    raw_lines = [ln for ln in log_file.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(raw_lines) == 3

    parsed_lines = [json.loads(ln) for ln in raw_lines]
    assert parsed_lines[0]["operation"] == "search_expedientes"
    assert parsed_lines[1]["operation"] == "fetch_oposiciones_detalle"
    assert parsed_lines[2]["operation"] == "agregar_oposicion"

    for entry in parsed_lines:
        assert len(entry["query_sha256"]) == 64
        assert len(entry["combined_fragments_sha256"]) == 64
        assert len(entry["entry_sha256"]) == 64
        assert isinstance(entry["fragments_sha256"], list)
        assert all(len(h) == 64 for h in entry["fragments_sha256"])
        assert any("ISO/IEC 42001" in c for c in entry["standard_controls"])
        assert any("ISO/IEC 23894" in c for c in entry["standard_controls"])

    # Verificar integridad de la cadena SHA-256
    chain = logger.verify_chain()
    assert chain["valid"] is True
    assert chain["total_entries"] == 3
    assert len(chain["file_sha256"]) == 64

    # Simular adulteración de una línea en el JSONL y comprobar que verify_chain la detecta
    tampered = json.loads(raw_lines[1])
    tampered["result_count"] = 999
    raw_lines[1] = json.dumps(tampered)
    log_file.write_text("\n".join(raw_lines) + "\n", encoding="utf-8")

    broken_chain = logger.verify_chain()
    assert broken_chain["valid"] is False
    assert broken_chain["corrupted_line"] == 2


def test_sha256_file_and_fragment_hashing(tmp_path):
    sample_file = tmp_path / "evidencia.txt"
    sample_file.write_text("BD_EXP..CPA_BusquedaOpExpedientes_SNIA", encoding="utf-8")

    file_digest = compute_file_sha256(sample_file)
    assert len(file_digest) == 64
    assert file_digest == compute_sha256_text("BD_EXP..CPA_BusquedaOpExpedientes_SNIA")

    with pytest.raises(FileNotFoundError):
        compute_file_sha256(tmp_path / "no_existe.txt")

    records = [{"id": 1, "sp": "Exps_TraerRegPro"}, {"id": 2, "sp": "Exps_SolExpSel4F6"}]
    stamped, hashes, root_hash = stamp_fragments_collection(records)
    assert len(stamped) == 2
    assert len(hashes) == 2
    assert len(root_hash) == 64
    # Idempotencia: volver a calcular el hash canónico ignora el campo sha256 estampado
    assert compute_canonical_sha256(stamped[0]) == hashes[0]

    manifest = build_repository_integrity_manifest()
    assert len(manifest) >= 5
    assert all(len(item["sha256"]) == 64 and item["estado"] == "VERIFICADO" for item in manifest)


def test_hallucination_guard_vector_distance_and_forced_abstention(tmp_path):
    log_file = tmp_path / "rag_audit.jsonl"
    logger = AuditLogger(log_path=log_file)
    guard = HallucinationGuard(max_cosine_distance=0.72, audit_logger=logger)

    # 1. Consulta en dominio: debe recuperar fragmentos con distancia vectorial <= umbral y NO abstenerse
    in_domain = guard.retrieve_and_evaluate(
        "¿Qué hace el procedimiento CPA_BusquedaExpedientesOp y Exps_DatFechasExpSel en BD_EXP?",
        top_k=3,
    )
    assert in_domain["abstained"] is False
    assert in_domain["abstention_clause"] is None
    assert in_domain["min_cosine_distance"] <= 0.72
    assert in_domain["max_cosine_similarity"] >= 0.28
    assert SYSTEM_ABSTENTION_GUARDRAIL in in_domain["answer"]
    assert len(in_domain["retrieved_fragments"]) == 3
    for frag in in_domain["retrieved_fragments"]:
        assert len(frag["fragment_sha256"]) == 64
        assert len(frag["file_sha256"]) == 64
        assert 0.0 <= frag["cosine_distance"] <= 1.0
        assert 0.0 <= frag["cosine_similarity"] <= 1.0

    # 2. Consulta fuera de dominio (riesgo de alucinación): DEBE forzar cláusula de abstención y registrar distancia
    out_of_domain = guard.retrieve_and_evaluate(
        "¿Cuál es la temperatura de fusión del titanio en propulsores criogénicos interplanetarios?",
        top_k=3,
    )
    assert out_of_domain["abstained"] is True
    assert out_of_domain["abstention_clause"] is not None
    assert "ABSTENCIÓN FORZADA [ISO/IEC 23894 / ISO/IEC 42001]" in out_of_domain["answer"]
    assert out_of_domain["min_cosine_distance"] > 0.72

    # 3. Consulta vacía: abstención inmediata
    empty_q = guard.retrieve_and_evaluate("   ")
    assert empty_q["abstained"] is True
    assert empty_q["min_cosine_distance"] == 1.0

    # Verificar que las 3 evaluaciones quedaron registradas en el JSONL con sus distancias vectoriales
    entries = logger.read_entries()
    assert len(entries) == 3
    # read_entries devuelve orden inverso (más reciente primero)
    assert entries[0]["abstained"] is True  # empty_q
    assert entries[1]["abstained"] is True  # out_of_domain
    assert entries[1]["vector_metrics"]["min_cosine_distance"] == out_of_domain["min_cosine_distance"]
    assert entries[2]["abstained"] is False  # in_domain
    assert entries[2]["vector_metrics"]["min_cosine_distance"] == in_domain["min_cosine_distance"]


def test_markdown_rag_summary_includes_iso_clauses_and_sha256(tmp_path):
    logger = AuditLogger(log_path=tmp_path / "export_audit.jsonl")
    events, _ = demo_events()
    md = markdown_rag_summary(events, audit_logger=logger)

    assert "ISO/IEC 42001:2023" in md
    assert "ISO/IEC 23894:2023" in md
    assert "SHA-256 Raíz de la Evidencia Analizada:" in md
    assert "SHA-256 Fragmento" in md
    assert SYSTEM_ABSTENTION_GUARDRAIL in md

    entries = logger.read_entries()
    assert len(entries) == 1
    assert entries[0]["operation"] == "export_markdown_rag_summary"
    assert len(entries[0]["metadata"]["document_sha256"]) == 64
