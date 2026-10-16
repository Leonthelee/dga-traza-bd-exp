# 🛡️ PROTOCOLO DE DESARROLLO Y CENTINELA — DGA-TRAZA-BD-EXP

> **DGA Core Tools - by Daniel Díaz L. & AI Engine Antigravity**  
> Repositorio satélite para trazabilidad y profiling forense de `BD_EXP`, `BD_PAR` y `BD_MAP`.

---

## 🎯 Directrices para Asistentes de IA (Antigravity / Gemini / Claude)

1. **Aislamiento Estricto y Cero Impacto:**
   - La herramienta NUNCA debe ejecutar sentencias DDL ni DML modificatorias (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`) sobre las bases de negocio (`BD_EXP`, `BD_PAR`, `BD_MAP`).
   - Solo se permite la creación de sesiones de Extended Events (`CREATE EVENT SESSION TrazaQA_*`) y consultas de catálogo en `master` y `sys`.
   - Toda la persistencia de eventos se realiza localmente en SQLite (`data/qa.sqlite3`).

2. **Estándares Visuales (Kit Digital Gob.cl):**
   - Azul Primario Gobierno: `#006FB3`
   - Texto Principal: `#0A132D`
   - Fondos: `#F8F9FA` / `#FFFFFF`
   - Zero-CDN: Ningún componente o estilo debe depender de servidores externos.

3. **Integración con RAG (`dga-bpm-orchestrator`):**
   - El resultado del análisis de procedimientos debe poder sincronizarse directamente en:
     `../dga-bpm-orchestrator/backend/knowledge/05_trazabilidad_sp_bd_exp.md`.

4. **Disciplina de Testing:**
   - Toda modificación en `src/` debe contar con sus pruebas en `tests/`.
   - Ejecutar suite antes de cerrar cambios:
     ```powershell
     $env:PYTHONPATH="."; .\.venv\Scripts\python.exe -m pytest -v
     ```

5. **Controles Normativos de Producción (ISO/IEC 42001 & ISO/IEC 23894):**
   - **Auditoría JSONL (`data/audit_iso42001.jsonl`):** Toda consulta o recuperación de datos debe registrarse mediante `src/governance.py` (`AuditLogger`) manteniendo la cadena de integridad SHA-256.
   - **Trazabilidad Criptográfica SHA-256:** Cada archivo y fragmento/registro recuperado debe calcular y conservar su hash SHA-256 (`compute_file_sha256`, `stamp_fragments_collection`).
   - **Mitigación de Alucinaciones y Abstención:** Toda consulta RAG o inferencia técnica debe registrar su distancia vectorial de similitud (`cosine_distance`) y forzar cláusulas de abstención (`SYSTEM_ABSTENTION_GUARDRAIL` / `ABSTENCIÓN FORZADA`) cuando la distancia supere el umbral permitido.

