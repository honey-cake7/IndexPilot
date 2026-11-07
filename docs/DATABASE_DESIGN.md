# Metadata database design

Status: logical schema proposed at M0; M2 implements `monitored_database` in migration `0001`. Other entities remain planned and will be introduced with their usable features. Demo business data never belongs in metadata.

```mermaid
erDiagram
    monitored_database ||--o{ workload : has
    workload ||--o{ query_pattern : contains
    workload ||--o{ workload_snapshot : collects
    query_pattern ||--o{ query_scenario : parameterizes
    workload_snapshot ||--o{ query_statistic : contains
    query_pattern ||--o{ query_statistic : measured
    workload ||--o{ analysis_run : analyzed
    analysis_run ||--o{ index_candidate : proposes
    analysis_run ||--o{ index_evaluation : evaluates_sets
    index_evaluation ||--o{ evaluation_member : contains
    index_candidate ||--o{ evaluation_member : participates
    index_evaluation ||--o{ execution_plan : records
    query_scenario ||--o{ execution_plan : planned
    analysis_run ||--o| recommendation_set : produces
    recommendation_set ||--o{ recommendation_set_index : selects
    index_candidate ||--o{ recommendation_set_index : chosen
    recommendation_set ||--o{ benchmark_run : validates
    benchmark_run ||--o{ benchmark_measurement : samples
    analysis_run ||--o{ saved_report : exports
```

Every entity has a primary key (UUID where externally addressed; bounded integer IDs are acceptable for local child rows), creation time and appropriate foreign keys. Use timezone-aware timestamps, BIGINT bytes/counters/query IDs, finite nonnegative costs and positive finite frequencies. PostgreSQL query IDs can be signed; do not impose a positive queryid constraint.

| Entity | Main content and constraints |
| --- | --- |
| monitored_database | Unique configured target key; safe host/database/role identity and credential reference; no password or secret DSN. |
| workload | Database FK, source, name; each analysis uses an immutable revision of queries/frequencies. |
| query_pattern | Workload FK, source identity and normalized text; manual fingerprint separate from server queryid. Server identity includes database, role, queryid and top-level flag; queryid alone is insufficient. |
| query_scenario | Pattern FK, representative statement/bindings, frequency share; unresolved parameters explicitly prevent planning. Values are sensitive local data. |
| workload_snapshot | Workload FK, collection time, server start/reset/deallocation metadata, collection outcome and extension version. |
| query_statistic | Snapshot and pattern FKs with composite uniqueness; raw cumulative calls/time/rows/buffers. Derived deltas retain their predecessor and validity reason, or are recalculated from raw snapshots. |
| analysis_run | Workload revision, target schema/statistics provenance, configuration, status and algorithm version; settings frozen on completion. |
| index_candidate | Analysis FK, canonical index signature, ordered key details, reasons, estimated bytes; unique signature within analysis. |
| index_evaluation | Analysis FK, canonical set signature, estimated weighted cost and warnings; unique compatible set signature within run. |
| evaluation_member | Composite PK of evaluation and candidate FKs; estimated bytes for this evaluation when available. |
| execution_plan | Evaluation and scenario FKs; raw JSON and extracted root metrics; unique pair; FK scope ensures same analysis workload. Empty set evaluation supplies baseline plans. |
| recommendation_set | Unique analysis FK, selected evaluation FK, baseline evaluation FK, budget, heuristic penalty settings, stop reason and warning summary. |
| recommendation_set_index | Composite recommendation/candidate PK; selection order and marginal trial reference. Prevent references to another analysis. |
| benchmark_run | Recommendation FK, isolated target identity, job status, dataset seed/scale, versions, conditions and error code. |
| benchmark_measurement | Run FK, configuration arm, repetition, scenario/operation, sample or aggregate value, explicit metric/unit and sampling method. |
| saved_report | Analysis FK, report format/version and immutable rendered artifact or safe managed artifact reference; no arbitrary filesystem path. |

Store PostgreSQL plan trees and frozen settings as JSONB because their internal structure varies; relational keys and membership remain normalized. Do not store comma-separated query IDs or selected indexes. Ordered index keys are structured data, not an unordered set.

Separating patterns from observations prevents rewriting SQL text for every snapshot. Separating candidate indexes from evaluations handles an index participating in many trial combinations. Set membership tables implement many-to-many relationships without duplicating candidate definitions. Benchmark measurements belong to runs because conditions and configuration arms matter as much as a latency number.

Use database constraints for uniqueness, nonnegative bytes, valid job states and FK scope wherever practical; application validation also rejects NaN/Infinity. Index FKs used for history queries, collection-time ordering and `(run_id, arm, repetition)`. Use migrations and transaction rollback tests. Deletion is explicit and scoped; preserve historical analyses by default, and do not cascade-delete benchmark evidence unexpectedly.

The e-commerce demo has separate `users`, `products`, `orders`, `order_items` and `payments` tables. Orders reference users; items reference orders and products; payments reference orders. Primary/unique constraints provide required indexes, while additional performance indexes are deliberately absent for experiments. Foreign keys do not automatically create indexes on their referencing columns.
