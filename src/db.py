from contextlib import contextmanager


def odbc_value(value):
    return "{" + str(value).replace("}", "}}") + "}"


def connection_string(settings):
    items = {
        "DRIVER": settings.driver,
        "SERVER": settings.server,
        "DATABASE": "master",
        "APP": "TrazaBD_EXP_QA",
        "Encrypt": "yes" if settings.encrypt else "no",
        "TrustServerCertificate": "yes" if settings.trust_server_certificate else "no",
    }
    if settings.trusted_connection:
        items["Trusted_Connection"] = "yes"
    else:
        items.update(UID=settings.username, PWD=settings.password)
    return ";".join(f"{key}={odbc_value(value)}" for key, value in items.items()) + ";"


@contextmanager
def connect(settings):
    import pyodbc

    settings.validate()
    conn = pyodbc.connect(connection_string(settings), timeout=8, autocommit=True)
    try:
        conn.timeout = settings.query_timeout
        yield conn
    finally:
        conn.close()


def rows(conn, sql, *params):
    cursor = conn.cursor()
    try:
        cursor.execute(sql, *params)
        columns = [x[0] for x in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        cursor.close()


def execute(conn, sql, *params):
    cursor = conn.cursor()
    try:
        cursor.execute(sql, *params)
    finally:
        cursor.close()


def preflight(conn, settings):
    result = rows(conn, "SELECT CAST(@@SERVERNAME AS nvarchar(128)) server_name,\n"
                        "        CAST(SERVERPROPERTY('ProductVersion') AS nvarchar(128)) version,\n"
                        "        CAST(SERVERPROPERTY('Edition') AS nvarchar(128)) edition,\n"
                        "        HAS_PERMS_BY_NAME(NULL, 'SERVER', 'ALTER ANY EVENT SESSION') can_control,\n"
                        "        HAS_PERMS_BY_NAME(NULL, 'SERVER', 'VIEW SERVER STATE') can_read")[0]
    if result["server_name"].casefold() != settings.expected_server_name.casefold():
        raise ValueError("El servidor conectado no coincide con expected_server_name. Operación bloqueada.")
    major = int(result["version"].split(".")[0])
    if not 12 <= major <= 15:
        raise ValueError("Este piloto está diseñado para SQL Server 2014–2019. Valide otras versiones antes de habilitarlas.")
    if not result["can_control"] or not result["can_read"]:
        raise ValueError("Faltan ALTER ANY EVENT SESSION o VIEW SERVER STATE.")
    for name in settings.databases:
        if rows(conn, "SELECT DB_ID(?) id", name)[0]["id"] is None:
            raise ValueError(f"Base no encontrada o no visible: {name}")
    return result
