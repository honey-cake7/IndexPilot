"""Generate the explicitly provisioned local sample databases."""

import argparse

import psycopg
from indexpilot.demo import MARKERS
from indexpilot.demo import generate as generate
from indexpilot.demo import verify_target as verify_target
from indexpilot.local import LocalConnectionError, connect_local


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
