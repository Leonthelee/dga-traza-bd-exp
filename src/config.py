from dataclasses import dataclass
from pathlib import Path, PureWindowsPath, PurePosixPath
import tomllib

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


@dataclass(frozen=True)
class Settings:
    server: str
    expected_server_name: str
    xel_directory: str
    databases: tuple[str, ...]
    login_filter: str
    environment: str = "QA"
    driver: str = "ODBC Driver 18 for SQL Server"
    trusted_connection: bool = True
    username: str = ""
    password: str = ""
    encrypt: bool = True
    trust_server_certificate: bool = False
    query_timeout: int = 20

    def validate(self):
        if self.environment not in ("QA", "PROD"):
            raise ValueError("Esta versión solo admite environment = 'QA' o 'PROD'.")
        if not self.server or not self.expected_server_name:
            raise ValueError("Configure servidor y expected_server_name.")
        if not self.login_filter.strip():
            raise ValueError("Se requiere login_filter para limitar la captura.")
        if not self.databases or any(not x.strip() for x in self.databases):
            raise ValueError("Configure las bases esperadas (ej. BD_EXP, BD_PAR, BD_MAP).")
        if self.xel_directory not in (".", "DEFAULT"):
            if not ((PureWindowsPath(self.xel_directory).is_absolute()
                     or PurePosixPath(self.xel_directory).is_absolute())
                    and not any(c in self.xel_directory for c in "*?\n\r")):
                raise ValueError("xel_directory debe ser una ruta absoluta válida o 'DEFAULT'.")
        if not self.trusted_connection and not (self.username and self.password):
            raise ValueError("Configure usuario y contraseña o autenticación integrada.")
        if not 1 <= self.query_timeout <= 60:
            raise ValueError("query_timeout debe estar entre 1 y 60 segundos.")


def load_settings(path=None):
    file = Path(path) if path else ROOT / ".streamlit" / "secrets.toml"
    if not file.exists():
        raise ValueError("Falta .streamlit/secrets.toml. Copie secrets.example.toml y configure QA.")
    with file.open("rb") as f:
        values = tomllib.load(f)["sql"]
    values["databases"] = tuple(values.get("databases", []))
    settings = Settings(**values)
    settings.validate()
    return settings
