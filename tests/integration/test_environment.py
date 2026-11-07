import psycopg
import pytest
from indexpilot.local import connect_local
from psycopg import sql

from scripts.generate_demo import generate, verify_target

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def bench():
    with connect_local("bench") as connection:
        generate(connection, target="bench", orders=1000, seed=42, reset=True)
        connection.commit()
        yield connection
        connection.rollback()
        generate(connection, target="bench", orders=10_000, seed=42, reset=True)


def fingerprint(connection):
    result = {}
    for table, order in (
        ("users", "id"),
        ("products", "id"),
        ("orders", "id"),
        ("order_items", "order_id, line_number"),
        ("payments", "id"),
    ):
        query = sql.SQL("SELECT md5(string_agg(row_to_json(t)::text, ',' ORDER BY {})) FROM {} t")
        result[table] = connection.execute(
            query.format(sql.SQL(order), sql.Identifier("public", table))
        ).fetchone()[0]
    return result


@pytest.mark.parametrize("role", ["meta", "demo", "analyzer", "bench"])
def test_versions_and_extensions(role):
    with connect_local(role) as connection:
        assert int(connection.execute("SHOW server_version_num").fetchone()[0]) // 10000 == 18
        extensions = dict(connection.execute("SELECT extname, extversion FROM pg_extension"))
        assert "pg_stat_statements" in extensions
        if role in ("demo", "analyzer", "bench"):
            assert extensions["hypopg"] == "1.4.3"


def test_seed_scale_and_integrity(bench):
    counts = [
        bench.execute(f"SELECT count(*) FROM public.{table}").fetchone()[0]
        for table in ("users", "products", "orders", "order_items", "payments")
    ]
    assert counts == [200, 100, 1000, 2000, 1000]
    assert (
        bench.execute(
            "SELECT count(*) FROM public.orders o JOIN "
            "(SELECT order_id,sum(quantity*unit_price) total FROM public.order_items "
            "GROUP BY order_id) i "
            "ON o.id=i.order_id WHERE o.total <> i.total"
        ).fetchone()[0]
        == 0
    )
    first = fingerprint(bench)
    generate(bench, target="bench", orders=1000, seed=42, reset=True)
    assert fingerprint(bench) == first
    generate(bench, target="bench", orders=1000, seed=43, reset=True)
    assert fingerprint(bench) != first
    generate(bench, target="bench", orders=2000, seed=42, reset=True)
    assert bench.execute("SELECT count(*) FROM public.orders").fetchone()[0] == 2000
    generate(bench, target="bench", orders=1000, seed=42, reset=True)
    bench.commit()


def test_generation_refuses_existing_data_without_reset(bench):
    before = fingerprint(bench)
    with pytest.raises(ValueError, match="Dataset exists"):
        generate(bench, target="bench", orders=1000, seed=1)
    assert fingerprint(bench) == before


def test_generation_refuses_metadata_and_wrong_target(bench):
    with pytest.raises(ValueError, match="isolation marker"):
        verify_target(bench, "demo")
    with connect_local("meta") as connection:
        with pytest.raises(ValueError, match="isolation marker"):
            generate(connection, target="demo", orders=1000, seed=42, reset=True)
        assert connection.execute("SELECT to_regclass('public.orders')").fetchone()[0] is None


def test_analyzer_cannot_write_even_after_disabling_readonly():
    with connect_local("analyzer", autocommit=True) as connection:
        assert connection.execute("SHOW default_transaction_read_only").fetchone()[0] == "on"
        connection.execute("SET default_transaction_read_only=off")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute("DELETE FROM public.orders WHERE false")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute("CREATE TABLE public.should_not_exist(id integer)")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute("CREATE TEMP TABLE should_not_exist(id integer)")
        assert connection.execute("SELECT count(*) FROM public.orders").fetchone()[0] == 10_000


def test_analyzer_plans_and_reads_real_statistics():
    with connect_local("analyzer") as connection:
        plan = connection.execute(
            "EXPLAIN (FORMAT JSON) SELECT id FROM public.orders WHERE user_id=101"
        ).fetchone()[0][0]["Plan"]
        assert plan["Node Type"] == "Seq Scan"
        assert plan["Total Cost"] > 0
        assert plan["Relation Name"] == "orders"
        assert (
            connection.execute(
                "SELECT count(*) FROM pg_stat_statements WHERE dbid = "
                "(SELECT oid FROM pg_database WHERE datname=current_database())"
            ).fetchone()[0]
            > 0
        )


def test_hypopg_works_with_readonly_role_and_is_session_local():
    with connect_local("analyzer") as first, connect_local("analyzer") as second:
        first.execute("SELECT hypopg_reset()")
        index_oid = first.execute(
            "SELECT indexrelid FROM hypopg_create_index('CREATE INDEX ON public.orders(user_id)')"
        ).fetchone()[0]
        assert first.execute("SELECT hypopg_relation_size(%s)", (index_oid,)).fetchone()[0] > 0
        assert first.execute("SELECT count(*) FROM hypopg_list_indexes").fetchone()[0] == 1
        assert second.execute("SELECT count(*) FROM hypopg_list_indexes").fetchone()[0] == 0
        plan = first.execute(
            "EXPLAIN (FORMAT JSON) SELECT id FROM public.orders WHERE user_id=101"
        ).fetchone()[0][0]["Plan"]
        assert plan["Node Type"] in ("Bitmap Heap Scan", "Index Scan")
        first.execute("SELECT hypopg_reset()")
        assert first.execute("SELECT count(*) FROM hypopg_list_indexes").fetchone()[0] == 0
