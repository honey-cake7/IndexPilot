# Executed validation evidence

[clean-checkout.json](clean-checkout.json) records an actual fresh local Git clone of `ea0114dd9b90f5fab714748d5c4137621205b5e8`. It used a new virtual environment, locked npm install, independently generated credentials and a newly initialized PostgreSQL/HypoPG volume on port 55434 with project `indexpilot-m12-mwb3ncpt`.

The sequential checker passed 425 backend tests, 29 frontend component tests and six actual Chromium/API/PG scenarios. Every requested check exited zero. The artifact includes the actual report UUID/content hash read through two API process starts, elapsed check durations, clean Git status and verification that the development demo/bench public fingerprints and index names were unchanged. It contains no passwords, connection strings, database rows or raw logs. Durations and UUIDs are observations, not expected constants.

That Windows run reused the pinned image's build cache; it did not establish fresh Linux image behavior. The first [Linux CI attempt](https://github.com/honey-cake7/IndexPilot/actions/runs/42889329543) exposed POSIX secret permissions during initialization. Fix `f2863f530ffc086517b10c33186e2387e068fc0a` preserves host mode 0600, supplies private postgres-owned tmpfs copies, checks failed reads and waits for TCP readiness. A fresh strict-POSIX probe verified startup/authentication and 0700/0400 container-copy modes.

[linux-ci.json](linux-ci.json) records the actual [successful Linux run](https://github.com/honey-cake7/IndexPilot/actions/runs/42890235259) at that fix: both jobs passed, including fresh provisioning, migration reversal/re-upgrade, **425 backend / 29 component / six real browser** cases and the report restart check. Counts were read from the completed job log. No failed run is relabeled as passing.

See [VALIDATION.md](../../docs/VALIDATION.md) to repeat the checks, [EVALUATION.md](../../docs/EVALUATION.md) for findings/limits, and [PROGRESS.md](../../docs/PROGRESS.md) for final commit/run verification. CI artifacts retain only bounded check/browser evidence for seven days; those are not database backups.
