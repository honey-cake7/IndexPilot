"""Explicit, bounded periodic snapshots; no daemon or workload SQL execution."""

import argparse
import math
import time
import uuid

import psycopg
from indexpilot.config import Settings
from indexpilot.errors import DomainError
from indexpilot.local import LocalConnectionError
from indexpilot.metadata.session import metadata_engine
from indexpilot.workloads import service
from indexpilot.workloads.models import CollectedWorkloadInput
from sqlalchemy.exc import SQLAlchemyError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workload-id", type=uuid.UUID)
    parser.add_argument("--name", default="Periodic statement collection")
    parser.add_argument("--samples", type=int, default=2)
    parser.add_argument("--interval-seconds", type=float, default=30)
    args = parser.parse_args()
    if not 1 <= args.samples <= 1000:
        parser.error("--samples must be between 1 and 1000")
    if not math.isfinite(args.interval_seconds) or not 0.1 <= args.interval_seconds <= 3600:
        parser.error("--interval-seconds must be finite and between 0.1 and 3600")
    if not 1 <= len(args.name) <= 120:
        parser.error("--name must have 1 to 120 characters")
    engine = None
    try:
        settings = Settings()
        engine = metadata_engine(settings)
        identifier = (
            args.workload_id
            or service.create_collected(
                engine,
                settings,
                CollectedWorkloadInput(name=args.name).name,
            ).id
        )
        print(f"workload_id={identifier}")
        for position in range(args.samples):
            snapshot = service.take_snapshot(engine, settings, identifier)
            delta = service.get_delta(engine, snapshot.id, None)
            usable = sum(entry.usable for entry in delta.entries)
            print(
                f"snapshot_id={snapshot.id} entries={len(snapshot.entries)} usable_deltas={usable}"
            )
            if position + 1 < args.samples:
                time.sleep(args.interval_seconds)
    except (DomainError, LocalConnectionError, SQLAlchemyError, psycopg.Error, OSError) as error:
        raise SystemExit(
            f"Collection failed ({type(error).__name__}); verify local setup."
        ) from None
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    main()
