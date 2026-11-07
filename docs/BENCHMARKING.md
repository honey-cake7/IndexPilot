# Benchmark protocol

Status: methodology only at M0. **No benchmark has run and no performance numbers are available.**

## Isolation

Use only the explicitly configured disposable benchmark database with its dedicated owner. Verify identity and marker before any DDL/DML; refuse demo, metadata and all monitored target identities. A benchmark request must explicitly confirm isolated physical index creation. Only persisted, validated candidate definitions may be used. Do not accept arbitrary SQL DDL from a request. Never drop primary/unique constraint indexes.

## Comparable experiments

Generate deterministic users, products, orders, order items and payments using a recorded seed, scale and fixed time anchor. Skewed user/order distribution and selective/nonselective date ranges should expose realistic trade-offs; document the distribution. Refresh planner statistics after generation. Copy/reseed into identical starting states for each experiment arm.

Compare:

1. Baseline: only indexes required by schema constraints.
2. Per-query baseline: independently useful singleton recommendations, deduplicated; disclose storage and any budget mismatch.
3. IndexPilot: jointly evaluated workload-aware set within the configured budget.

Record versions of PostgreSQL, HypoPG, pgbench and the application; hardware/OS/container limits; planner settings; row counts; relation/index bytes; seed; workload SQL/parameters/frequencies; budget; connections; client count; scale; repetitions; warmup and run length. Keep workload parameter distribution identical between arms. Rotate arm order across repetitions to reduce ordering bias. State that cache flushing is not performed unless an explicit reproducible cold-cache protocol exists; warm-cache results are valid when labeled.

Use pgbench for controlled throughput and transaction samples. Report measured TPS with the exact transaction definition; do not label multi-statement transaction latency as individual-query latency. If per-query latency is needed, use single-query scripts or separately instrument approved benchmark execution. Individual transaction logs support mean/median/p95 calculations; aggregate pg_stat_statements means do not support percentiles. Retain raw local artifacts excluded from Git and small sanitized result summaries with collection method/provenance.

Measure inserts, updates and deletes on restored equivalent datasets with and without additional indexes. Account for MVCC/dead tuples, vacuum and cache differences; do not carry mutation state from one arm to another. Report write latency/TPS changes and storage. Save failed/time-limited runs as failed rather than silently excluding unfavorable results. Explain repeated-run variability; do not claim significance without a suitable statistical method.

## Estimates versus actuals

HypoPG reports relative planner costs and estimated sizes. Physical experiments report measured milliseconds, TPS and actual bytes. Show both, with separate labels; there is no general conversion from a planner cost unit to milliseconds. Flag per-query regressions using a declared threshold, even if total throughput improves. Do not promise IndexPilot always wins.

Executed commands, actual result values and result commit links will be added only after M9 verification. See [roadmap M9](ROADMAP.md#m9--isolated-benchmarks-and-regression-analysis-h).
