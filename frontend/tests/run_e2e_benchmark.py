"""Execute only the just-confirmed e2e benchmark on an otherwise idle queue."""

import sys
import uuid

from indexpilot.benchmarks.runner import run_next
from indexpilot.config import Settings
from indexpilot.metadata.models import BenchmarkJob
from indexpilot.metadata.session import metadata_engine
from sqlalchemy import or_, select
from sqlalchemy.orm import Session


def main():
    identifier = uuid.UUID(sys.argv[1])
    settings = Settings()
    engine = metadata_engine(settings)
    try:
        with Session(engine) as db:
            active = list(
                db.scalars(
                    select(BenchmarkJob).where(
                        or_(
                            BenchmarkJob.status.in_(["queued", "running"]),
                            BenchmarkJob.cleanup_confirmed.is_(False),
                        )
                    )
                )
            )
            if len(active) != 1 or active[0].id != identifier or active[0].status != "queued":
                raise SystemExit("E2E requires an idle queue except its own confirmed job.")
        if run_next(engine, settings) != identifier:
            raise SystemExit("The E2E job was not claimed; inspect the saved queue.")
        with Session(engine) as db:
            job = db.get(BenchmarkJob, identifier)
            if job.status != "completed" or not job.cleanup_confirmed:
                raise SystemExit("The E2E benchmark did not complete with verified cleanup.")
        print("Actual E2E benchmark completed with verified cleanup.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
