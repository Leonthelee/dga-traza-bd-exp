"""CLI de Control QA, Recuperación XE y Auditoría Criptográfica ISO/IEC 42001 & 23894."""
import argparse
import json
from src.store import Store
from src.config import load_settings
from src.service import recover, error_text
from src.governance import (
    build_repository_integrity_manifest,
    default_audit_logger,
    default_hallucination_guard,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=["list", "stop", "audit-verify", "manifest", "rag-query"],
        help="Comando a ejecutar (list, stop, audit-verify, manifest, rag-query)",
    )
    parser.add_argument("target", nargs="?", help="ID de captura (para stop) o texto de consulta (para rag-query)")
    args = parser.parse_args(argv)

    if args.command == "list":
        store = Store()
        for capture in store.list():
            print(capture["id"], capture["status"], capture["message"])
    elif args.command == "stop":
        if not args.target:
            parser.error("stop requiere el id de captura")
        store = Store()
        settings = load_settings()
        try:
            recover(settings, store, args.target)
            print("Parada verificada en SQL Server.")
        except Exception as exc:
            raise SystemExit(error_text(exc, settings))
    elif args.command == "audit-verify":
        status = default_audit_logger.verify_chain()
        print(json.dumps(status, ensure_ascii=False, indent=2))
        if not status.get("valid"):
            raise SystemExit(1)
    elif args.command == "manifest":
        manifest = build_repository_integrity_manifest()
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
    elif args.command == "rag-query":
        if not args.target:
            parser.error("rag-query requiere el texto de la consulta")
        res = default_hallucination_guard.retrieve_and_evaluate(args.target)
        print(json.dumps({
            "query": res["query"],
            "query_sha256": res["query_sha256"],
            "abstained": res["abstained"],
            "min_cosine_distance": res["min_cosine_distance"],
            "max_cosine_similarity": res["max_cosine_similarity"],
            "answer": res["answer"],
        }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

