"""Run one queued, explicitly confirmed disposable benchmark (no hidden background worker)."""

import argparse
import time

from indexpilot.benchmarks.jobs import get_job
from indexpilot.benchmarks.runner import run_next
from indexpilot.config import Settings
from indexpilot.errors import DomainError
from indexpilot.local import LocalConnectionError
from indexpilot.metadata.session import metadata_engine


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--once", action="store_true")
    modes.add_argument(
        "--serve", action="store_true", help="Foreground worker, poll once per second"
    )
    args = parser.parse_args()
    settings = Settings()
    engine = metadata_engine(settings)
    try:
        while True:
            identifier = run_next(engine, settings)
            if identifier is None:
                if args.once:
                    print("No queued benchmark.")
            else:
                job = get_job(engine, identifier)
                print(
                    f"Benchmark {identifier}: {job.status}; cleanup={job.cleanup_confirmed}",
                    flush=True,
                )
                if args.once and job.status not in ("completed", "cancelled"):
                    raise SystemExit(1)
            if args.once:
                break
            time.sleep(1)
    except KeyboardInterrupt:
        print("Worker stopped. Interrupted jobs are recovered as failed on next start.")
    except (DomainError, LocalConnectionError) as failure:
        raise SystemExit(f"Benchmark worker refused/failed ({failure.code}).") from None
    except Exception:
        raise SystemExit(
            "Benchmark worker failed; inspect the saved job status and local setup."
        ) from None
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
