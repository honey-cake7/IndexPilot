from psycopg import Connection, Error
from pydantic import BaseModel


class ExtensionStatus(BaseModel):
    available: bool
    installed: bool
    version: str | None = None
    configured: bool | None
    accessible: bool


class Capabilities(BaseModel):
    database: str
    role: str
    server_version: str
    supported_version: bool
    read_only: bool
    superuser: bool
    can_connect: bool
    can_read_orders: bool
    can_create_schema_objects: bool
    can_create_temp: bool
    hypopg: ExtensionStatus
    pg_stat_statements: ExtensionStatus
    warnings: list[str]


def inspect_capabilities(connection: Connection) -> Capabilities:
    database, role, version, version_num, read_only = connection.execute(
        "SELECT current_database(), current_user, current_setting('server_version'), "
        "current_setting('server_version_num')::int, current_setting('transaction_read_only')='on'"
    ).fetchone()
    (superuser,) = connection.execute(
        "SELECT rolsuper FROM pg_roles WHERE rolname=current_user"
    ).fetchone()
    can_connect, create, temp = connection.execute(
        "SELECT has_database_privilege(current_database(),'CONNECT'), "
        "has_schema_privilege('public','CREATE'), "
        "has_database_privilege(current_database(),'TEMP')"
    ).fetchone()
    (orders,) = connection.execute(
        "SELECT coalesce(has_table_privilege(to_regclass('public.orders'),'SELECT'), false)"
    ).fetchone()
    installed = dict(connection.execute("SELECT extname, extversion FROM pg_extension"))
    available = {row[0] for row in connection.execute("SELECT name FROM pg_available_extensions")}
    extensions = {}
    warnings = []
    for name in ("hypopg", "pg_stat_statements"):
        configured = (True if name == "hypopg" else None) if name in installed else False
        accessible = False
        if name in installed:
            # Savepoints keep a failed permission/preload probe from aborting the outer transaction.
            try:
                with connection.transaction():
                    if name == "hypopg":
                        accessible = connection.execute(
                            "SELECT coalesce(has_function_privilege("
                            "to_regprocedure('public.hypopg_create_index(text)'), 'EXECUTE'),false)"
                        ).fetchone()[0]
                    else:
                        connection.execute("SELECT 1 FROM public.pg_stat_statements LIMIT 1")
                        configured = True
                        accessible = True
            except Error as error:
                if error.sqlstate == "55000":
                    configured = False
                accessible = False
        extensions[name] = ExtensionStatus(
            available=name in available,
            installed=name in installed,
            version=installed.get(name),
            configured=configured,
            accessible=accessible,
        )
        if not accessible:
            warnings.append(f"{name} is unavailable, unconfigured or not accessible to this role.")
    if superuser or create or temp:
        warnings.append("Analysis role has broader privileges than the least-privilege demo role.")
    if not 180000 <= version_num < 190000:
        warnings.append("Only PostgreSQL 18 has been verified by this version of IndexPilot.")
    return Capabilities(
        database=database,
        role=role,
        server_version=version,
        supported_version=180000 <= version_num < 190000,
        read_only=read_only,
        superuser=superuser,
        can_connect=can_connect,
        can_read_orders=orders,
        can_create_schema_objects=create,
        can_create_temp=temp,
        hypopg=extensions["hypopg"],
        pg_stat_statements=extensions["pg_stat_statements"],
        warnings=warnings,
    )
