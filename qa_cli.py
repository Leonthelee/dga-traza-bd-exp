"""Recovery commands for an existing capture. Never starts a new trace."""
import argparse
from src.store import Store
from src.config import load_settings
from src.service import recover, error_text

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("command", choices=["list", "stop"])
parser.add_argument("id", nargs="?")
args = parser.parse_args()
store = Store()
if args.command == "list":
    for capture in store.list():
        print(capture["id"], capture["status"], capture["message"])
else:
    if not args.id:
        parser.error("stop requiere el id de captura")
    settings = load_settings()
    try:
        recover(settings, store, args.id)
        print("Parada verificada en SQL Server.")
    except Exception as exc:
        raise SystemExit(error_text(exc, settings))
