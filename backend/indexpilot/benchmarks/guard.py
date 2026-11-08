import re

from indexpilot.errors import DomainError
from indexpilot.local import connect_local

LOCK_KEY = 918273645
TABLES = ("users", "products", "orders", "order_items", "payments", "indexpilot_dataset")


def refuse():
    return DomainError(
        "unsafe_benchmark_target", "Benchmark database identity or isolation differs.", 409
    )


def identity(connection):
    row = connection.execute(
        "SELECT current_database(),current_user,d.oid::bigint,"
        "shobj_description(d.oid,'pg_database'),inet_server_addr()::text,inet_server_port(),"
        "pg_postmaster_start_time()::text FROM pg_database d WHERE datname=current_database()"
    ).fetchone()
    return dict(
        zip(
            ("database", "role", "database_oid", "marker", "address", "port", "server_start"),
            row,
            strict=True,
        )
    )


def same_database(left, right):
    return all(
        left[key] == right[key] for key in ("address", "port", "server_start", "database_oid")
    )


def verify(connection, *, expected=None, monitored=()):
    actual = identity(connection)
    if (actual["database"], actual["role"], actual["marker"]) != (
        "indexpilot_bench",
        "indexpilot_bench_owner",
        "indexpilot:disposable-benchmark:v1",
    ) or (expected is not None and actual != expected):
        raise refuse()
    if any(same_database(actual, target) for target in monitored):
        raise refuse()
    return actual


def isolation(connection, settings):
    monitored = []
    for role in ("meta", "analyzer"):
        with connect_local(role, settings=settings) as other:
            monitored.append(identity(other))
    return verify(connection, monitored=monitored)


def namespace(job_id):
    return "ipb_" + job_id.hex


def require_namespace(name):
    if re.fullmatch(r"ipb_[0-9a-f]{32}", name) is None:
        raise DomainError(
            "unsafe_benchmark_namespace", "Only this job's generated namespace is allowed.", 409
        )
