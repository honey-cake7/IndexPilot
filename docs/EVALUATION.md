# Engineering evaluation

IndexPilot implements the requested local PostgreSQL demonstration through workload input/collection, safe plan/catalog analysis, candidate generation, HypoPG set evaluation, budget selection, explainable recommendations, isolated physical measurements, a nine-view dashboard, history and durable reports. Completion means the bounded local scenario works and is reproducible; it does not imply unrestricted SQL support or production readiness.

## Measured findings

The published experiment is job `38ced867-7cfc-429f-9a3a-bc4ee90e51d6`, with [conditions and all repetition results](../sample/benchmarks/local-results.json) and a [saved report export](../sample/reports/README.md). It used two queries at relative frequencies 100/25, 10,000 orders, seed 42, three rotated repetitions, one client, 20 read warmups and 200 measured transactions per phase. There are 54 measurements and 10,800 individual transaction samples. Cleanup was verified.

Mean committed transaction latency across the three equal-size repetitions:

| Phase | Baseline | Per-query set | IndexPilot set |
| --- | ---: | ---: | ---: |
| Mixed read transaction | 0.3604 ms | 0.1209 ms | 0.2117 ms |
| Latest paid orders | 0.5275 ms | 0.1425 ms | 0.5415 ms |
| Orders by user | 0.3086 ms | 0.1128 ms | 0.1133 ms |
| Insert | 2.3684 ms | 2.2840 ms | 2.3189 ms |
| Update | 2.2787 ms | 2.3154 ms | 5.3443 ms |
| Delete | 2.3827 ms | 5.0028 ms | 2.3481 ms |
| Initial additional index main-fork bytes | 0 | 475,136 | 114,688 |

The hard selection budget was **300,000 estimated bytes**. IndexPilot chose `user_id`; the per-query baseline added both `user_id` and `(status, created_at)` and exceeded that budget. The per-query baseline was faster for mixed reads, but is not a budget-matched competitor. IndexPilot's mixed-read mean improved 41.26% locally and did not improve every query. Its update mean and the per-query delete mean triggered the declared 10% regression threshold, each dominated by one slower repetition. The evidence retains those observations instead of selecting only favorable runs. The experiment does not identify the cause of the outliers or prove that indexes alone caused those differences.

### Cost model and storage

Saved weighted root planner cost changed from **39,270 to 12,562** (68.01% estimated reduction). The measured mixed-read mean changed by 41.26%. These are different quantities with different semantics: planner cost does not include all client/protocol/transaction overhead, cache behavior or concurrency. Their percentages are not a calibrated conversion and one workload cannot establish a general prediction error distribution.

HypoPG estimated **286,720 bytes** for the selected index, while its initial measured main fork was **114,688 bytes**, a 2.5x difference here. The actual initial size still fit this experiment's budget. An estimated-byte constraint is not a filesystem-capacity guarantee. Index growth, non-main forks, existing constraint indexes and changed data/statistics must be considered separately; the benchmark records actual sizes and fit flags.

### What affects conclusions

- Query frequency and representative parameter values change the estimated objective and plan selectivity. Unit arithmetic tests show frequency reversal; real HypoPG tests verify weighted root costs and exact/one-byte-below budget boundaries.
- Data volume, distribution, PostgreSQL statistics, planner settings and existing usable indexes can change candidates, estimates and choices. Saved provenance captures observations, not a permanently frozen target. The final set is replanned uncached and drift aborts selection.
- Read phases use warmups; writes restore deterministic starting rows per arm/operation. Rotated order and fingerprints improve comparability but do not flush operating-system/PostgreSQL caches or eliminate background load.
- A read transaction includes SELECT plus BEGIN/COMMIT/protocol overhead. Reported TPS and p95 apply to the documented transactions; p95 uses actual samples, not aggregate pg_stat_statements means.
- Three local repetitions expose variation but do not establish statistical significance, cold-cache behavior, WAL impact, long-run write amplification or performance on another host. Small one-repetition browser jobs verify workflow, not performance superiority.

## Algorithm assessment

The greedy optimizer evaluates whole interacting sets, recomputes marginal net gain per additional byte after each selection, enforces known total estimated storage and optional regression/heuristic-write constraints, and records every trial/rejection and search stop. It does not sum singleton benefits or treat unknown size as free storage.

It can miss complementary pairs with no individual gain or a better set behind an initially attractive choice. Bounded evaluation/index limits can leave alternatives unexplored. The synthetic complementary-pair unit test demonstrates that limitation; it is not a database effectiveness measurement. The optional exhaustive solver remains unimplemented and is outside the essential path. No claim of global optimality is made.

The unconstrained per-query benchmark baseline independently evaluates useful singleton choices, deduplicates the union and records actual bytes. This makes the comparison transparent rather than silently granting both algorithms the same label while hiding unequal storage.

## Operational and privacy limits

Ordinary analysis uses validated non-ANALYZE EXPLAIN through a restricted local role. SQL grammar, relation kinds, functions, operators and index types are intentionally bounded. Arbitrary DSNs, automatic production deployment, arbitrary physical benchmarking targets, authentication/multi-tenancy and public hosting are not implemented. The demo's cluster-wide statistics role is appropriate only for the dedicated local cluster; it is not a production privilege recommendation.

Physical writes require explicit confirmation and the separately marked benchmark database/owner, server-side transport configuration, nonce verification, bounded jobs, owned namespaces and checked cleanup. Custom Compose project configuration selects the local transport, not an API-provided target. Unknown dependencies block cleanup instead of being dropped with CASCADE. Timeouts/failures/cancellation remain visible and cannot become completed comparisons.

Reports are immutable through the API and preserve a versioned metadata snapshot. Direct DBA edits are outside that boundary. Original SQL can contain literals; representative bound SQL requires opt-in and no automatic literal-redaction guarantee is made. Reports are not database backups. Offset history pagination can shift when new records arrive. Repository/runtime secret files, raw logs and database volumes are excluded from published artifacts.

## Completion evidence

Executed validation: a fresh local Git clone with a new environment, credentials and database volume passed **425 backend tests (293 unit, 132 actual PG/API), 29 frontend component tests and six real browser scenarios**. Its Git tree stayed clean, saved report bytes matched across two API process starts, and development demo/bench public fingerprints/index names were unchanged. [Actual clean-checkout record](../sample/validation/clean-checkout.json).

The first fresh Linux attempt failed because the postgres initializer could not read mode-0600 host secrets. A strict POSIX reproduction exposed failed reads masked by exported command substitutions. Private tmpfs copies, checked reads and final TCP readiness fixed it. The [corrected Linux run](https://github.com/honey-cake7/IndexPilot/actions/runs/42890235259) passed both jobs with the same **425 / 29 / 6** counts, including fresh image build/provisioning, migrations, physical benchmarks and real process restart. [CI evidence](../sample/validation/linux-ci.json). The earlier failed run remains visible; a cached Windows image was not used as proof of Linux initialization.

The following maps the original 18 completion requirements to concrete code/tests or saved evidence. Final clean-checkout and CI run identities are recorded in [PROGRESS.md](PROGRESS.md); [VALIDATION.md](VALIDATION.md) gives the exact commands.

| Requirement | Evidence |
| --- | --- |
| 1. Start from documented setup | Locked setup in README/VALIDATION; fresh Git checkout, credentials and volume; CI provisions the pinned image. |
| 2. Connect to demo PostgreSQL | `test_backend.py` live capabilities/readiness; `verify_environment.py` checks actual versions/roles/extensions. |
| 3. Submit or collect workload | `test_workloads.py` manual/upload/pg_stat_statements snapshots, reset/eviction-aware deltas; browser submits SQL/files. |
| 4. Analyze actual plans | `test_plan_analysis.py` real recursive EXPLAIN JSON, joins/scans/sorts and saved scenario plans. |
| 5. Identify patterns/statistics | SQL resolution/catalog tests and captured table/column/statistics timestamps; parameter/selectivity admission checks. |
| 6. Generate valid indexes | `test_candidates.py` schema-aware B-Tree generation, quoted definitions, usable-duplicate handling and actual HypoPG admission. |
| 7. Evaluate with HypoPG | `test_hypopg_evaluation.py` real singleton/combined sets, session isolation and finally cleanup. |
| 8. Compare baseline/hypothetical costs | Persisted root-cost comparisons; M9 original/planner evidence and immutable recommendation queries. |
| 9. Select within budget | `test_optimizer.py` exact and one-byte-below real boundaries, unknown-size refusal, final verification; browser saves 1 MiB and zero runs. |
| 10. Display explanations | Actual recommendation page/index/query reasons, saved SQL artifact and browser assertions/screenshots. |
| 11. Create isolated real indexes | Three-arm worker tests verify marked identities/nonce/owned schemas and preserved public indexes. |
| 12. Run comparable before/after work | Actual pgbench arm rotations, restored seeded datasets, fingerprints, warmups, transaction logs and samples. |
| 13. Display performance/regressions | Measured phase chart values checked against stored metrics; published read/write regressions retained. |
| 14. Save history | PostgreSQL persistence, filtered history pagination/tie tests and browser reopening original records. |
| 15. Generate report | Versioned saved JSON/Markdown export, explicit privacy/missing-evidence policy and actual sample/report browser download. |
| 16. Automated tests pass | Sequential checker and pinned CI jobs; counts/results recorded only after successful execution. |
| 17. Installation/run instructions | README, DEVELOPMENT, FRONTEND, REPORTS and VALIDATION; fresh-checkout verification. |
| 18. Publish completed changes | Actual commit links, push/remote-SHA checks and CI run links in PROGRESS. |

Missing HypoPG is tested against a real database without the extension. Restricted execute/size privileges are tested with actual revoke/restore operations. Invalid credentials/ports, SQL side effects, unknown types/operators, scope errors, cancellation, interruption recovery and cleanup refusal have explicit failure-path tests. Passing those tests validates the bounded behavior; it does not certify unrestricted production safety.
