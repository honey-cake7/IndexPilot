"""Deterministically populate only IndexPilot's marked local sample databases."""

import argparse
from pathlib import Path

import psycopg
from indexpilot.local import LocalConnectionError, connect_local

ANCHOR = "2026-01-01T00:00:00+00:00"
MARKERS = {
    "demo": ("indexpilot_demo", "indexpilot_demo_owner", "indexpilot:demo:v1"),
    "bench": (
        "indexpilot_bench",
        "indexpilot_bench_owner",
        "indexpilot:disposable-benchmark:v1",
    ),
}


def verify_target(connection: psycopg.Connection, target: str) -> None:
    actual = connection.execute(
        "SELECT current_database(), current_user, "
        "shobj_description(oid, 'pg_database') FROM pg_database WHERE datname=current_database()"
    ).fetchone()
    if actual != MARKERS[target]:
        raise ValueError("Refusing data generation: database, owner or isolation marker differs.")


def generate(
    connection: psycopg.Connection, *, target: str, orders: int, seed: int, reset: bool = False
) -> dict[str, int]:
    if not 100 <= orders <= 1_000_000:
        raise ValueError("orders must be between 100 and 1000000")
    if not 0 <= seed <= 2_147_483_647:
        raise ValueError("seed must fit a nonnegative PostgreSQL integer")
    verify_target(connection, target)
    schema = Path(__file__).resolve().parents[1] / "sample" / "schema.sql"
    with connection.transaction():
        connection.execute("SELECT pg_advisory_xact_lock(918273645)")
        connection.execute(schema.read_text(encoding="utf-8"), prepare=False)
        populated = connection.execute("SELECT EXISTS(SELECT 1 FROM public.orders)").fetchone()[0]
        if populated and not reset:
            raise ValueError("Dataset exists. Use --reset only to replace this marked sample data.")
        # Fixed table names and no CASCADE: unknown dependent objects must block reset.
        connection.execute(
            "TRUNCATE public.payments, public.order_items, public.orders, "
            "public.products, public.users, public.indexpilot_dataset"
        )
        users, products = max(200, orders // 10), max(100, orders // 20)
        connection.execute(
            "INSERT INTO public.users SELECT n, 'user-' || n || '@example.test', "
            "'region-' || mod(n + %s::bigint, 8) FROM generate_series(1, %s::bigint) n",
            (seed, users),
        )
        connection.execute(
            "INSERT INTO public.products SELECT n, 'category-' || mod(n + %s::bigint, 12), "
            "(100 + mod(n * 37 + %s::bigint, 49900)) / 100.0 "
            "FROM generate_series(1, %s::bigint) n",
            (seed, seed, products),
        )
        # Hash-derived uniforms squared concentrate orders on a smaller group of users.
        connection.execute(
            "INSERT INTO public.orders "
            "SELECT n, 1 + floor(power(('x' || substr(md5(n::text || ':' || %s::text), 1, 8))"
            "::bit(32)::bigint / 4294967296.0, 2) * %s)::bigint, "
            "%s::timestamptz - make_interval(secs => mod(n * 7919 + %s::bigint, 31536000)), "
            "(ARRAY['pending','paid','shipped','cancelled'])[1 + mod(n, 4)::int], 1 "
            "FROM generate_series(1, %s::bigint) n",
            (seed, users, ANCHOR, seed, orders),
        )
        connection.execute(
            "INSERT INTO public.order_items "
            "SELECT o.id, line, p.id, 1 + mod(o.id + line, 3), p.price "
            "FROM public.orders o CROSS JOIN generate_series(1, 2) line "
            "JOIN public.products p ON p.id = 1 + mod(o.id * 13 + line + %s::bigint, %s)",
            (seed, products),
        )
        connection.execute(
            "UPDATE public.orders o SET total = a.total FROM "
            "(SELECT order_id, sum(quantity * unit_price) AS total FROM public.order_items "
            "GROUP BY order_id) a WHERE o.id = a.order_id"
        )
        connection.execute(
            "INSERT INTO public.payments "
            "SELECT id, id, total, CASE WHEN status = 'cancelled' THEN 'failed' "
            "ELSE 'captured' END FROM public.orders"
        )
        connection.execute(
            "INSERT INTO public.indexpilot_dataset VALUES (true, %s, %s, %s, 1)",
            (seed, orders, ANCHOR),
        )
        for table in ("users", "products", "orders", "order_items", "payments"):
            connection.execute(
                psycopg.sql.SQL("ANALYZE public.{}").format(psycopg.sql.Identifier(table))
            )
    return {"users": users, "products": products, "orders": orders, "order_items": 2 * orders}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=MARKERS, default="demo")
    parser.add_argument("--orders", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--reset", action="store_true", help="Replace only marked sample data")
    args = parser.parse_args()
    try:
        with connect_local(args.target) as connection:
            result = generate(
                connection, target=args.target, orders=args.orders, seed=args.seed, reset=args.reset
            )
        print(
            f"Generated {args.target} dataset: {result}; payments={args.orders}; seed={args.seed}"
        )
    except (psycopg.Error, LocalConnectionError, ValueError, OSError) as error:
        # Raw database errors can include connection details or SQL values.
        raise SystemExit(
            f"Generation failed ({type(error).__name__}); check local setup/inputs."
        ) from None


if __name__ == "__main__":
    main()
