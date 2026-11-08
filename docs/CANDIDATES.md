# B-Tree index candidate generation

Implemented in M5. The generator proposes bounded, explainable index definitions from M4's resolved query features. It refreshes table/index metadata, rejects exact existing duplicates, saves decisions and links every proposal to source plans. Candidate benefits, storage requirements and write costs are **not evaluated yet**; HypoPG cost comparison belongs to M6 and workload optimization to M7.

## Try the working API

With PostgreSQL running, migrate and restart the backend:

```powershell
uv sync --locked
uv run alembic upgrade head
uv run uvicorn indexpilot.main:app --host 127.0.0.1 --port 8000
```

Use `/docs` or PowerShell:

```powershell
$query = @{
  sql = 'SELECT id FROM public.orders WHERE user_id=101 AND created_at >= TIMESTAMPTZ ''2025-01-01 UTC'' ORDER BY created_at DESC'
  frequency = 100
} | ConvertTo-Json
$plan = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/plans `
  -ContentType application/json -Body $query
$request = @{ plan_ids = @($plan.id); max_columns = 3; max_candidates = 32 } | ConvertTo-Json
$batch = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/candidates `
  -ContentType application/json -Body $request
$batch.proposed | ForEach-Object { $_.definition.ddl }
$batch.rejected | Select-Object rejection_reason, existing_indexes
```

This flow was exercised against the real local database. Results depend on current indexes; a new installation may differ from a database where indexes were deliberately added. The application returns proposed DDL for review and never executes physical CREATE INDEX.

| Method/path | Purpose |
| --- | --- |
| POST `/api/v1/candidates` | Generate/save a batch from 1–100 distinct saved plan UUIDs. |
| GET `/api/v1/candidates/{id}` | Reload definitions, query evidence, rejection reasons, overlap warnings and generation settings. |
| GET `/api/v1/candidates` | List batches using `limit` (1–100) and `offset`. |

All source plans must belong to the configured target. Additional application schemas follow the existing allowlist. Old plan columns must still have the same relation OID, attribute number, type and collation. Changed identities/types require new analysis; missing or unsupported relations return explicit errors. Existing indexes are refreshed rather than trusted from historical plan snapshots. No HypoPG extension is needed by the generation endpoint itself.

## Patterns and bounds

The pure generator accepts resolved features and catalogs, independently of FastAPI:

- Direct constant equalities produce lookup keys; supported inner equality joins contribute lookup keys on both sides.
- Co-occurring equalities produce at most two column-order alternatives. Constant equalities precede parameterized join equalities in the default order. A coarse uniform-selectivity statistic and stable column-name ties bound ordering; missing statistics fall back deterministically, not to invented selectivity.
- Equality/join prefixes can precede one range key. The generator does not enumerate all permutations or arbitrary column subsets.
- Compatible ORDER BY columns retain direction and NULL placement. Constant-equality columns can precede the remaining ordering keys because their values are fixed within that query.
- OR/NOT branches, computed predicates, outer-join lookup combinations and cross-relation/computed ordering patterns are excluded from these initial patterns. An admitted query can legitimately produce no candidates.

Default and hard maximum key width is **three columns**; default and hard maximum proposed count is **32**. Users may choose smaller values. Per relation alias, up to four equality/join and four range columns are retained, with two range alternatives used in composites. Full ordering wider than the requested key width is not advertised as a full-order match.

Sources are enumerated round-robin in stable plan-ID order. Global work is capped at **4,096 proposal attempts** and **512 unique definitions**. Hitting an internal bound sets `search_truncated` and warns that definitions/evidence may be incomplete. After duplicate checks, surviving candidates are prioritized by distinct source-plan coverage, structural reason, width and signature. Excess survivors are saved as `candidate_limit` rejections. This priority is a transparent search heuristic, not a frequency-weighted optimizer or measured benefit score.

## Safe definitions and index identity

`candidates/sql.py` quotes schema, table, index, column, collation and operator-class identifiers with psycopg. Names are deterministic ASCII slugs plus a signature digest and fit PostgreSQL's identifier limit. Definitions include explicit B-Tree opclasses and ordering/null placement. Default operator classes come from PostgreSQL, including a verified built-in binary varchar-to-text mapping for text_ops. Unsupported class resolution skips the column explicitly.

No request accepts arbitrary index DDL. Definition signatures include the physical relation identity, schema/table, key identities/types, opclasses, collations and ordering. The current generator produces ordinary nonunique full B-Tree indexes only: no partial predicates, expression keys or INCLUDE payload. Those existing-index forms are inspected for correct comparisons, not generated as advanced proposals. A deployment tool must still handle name conflicts and approval deliberately; M5 is not a deployment engine.

## Exact duplication versus overlap

Only valid, ready, live B-Tree indexes can suppress a proposal. Exact comparison requires matching key count/order, attribute numbers, opclasses, collations, direction and NULL placement, with no predicate, expression or extra INCLUDE columns. A same-signature ordinary nonunique index yields `exact_duplicate`.

A matching unique/primary index already supplies the lookup path, so the proposal is rejected as `covered_by_unique_index`, not mislabeled an identical constraint definition. Partial/expression indexes never stand in for a general full-column index. A covering index, longer prefix match, or fully reversed ordering produces an overlap warning and is retained for later evaluation. Prefix coverage alone does not establish that a smaller index is useless; storage and planning trade-offs remain unmeasured.

Index definitions are candidates, not proven recommendations. Each decision returns `evaluation_status: not_evaluated`; estimated size and improvement are null. Nothing is inferred from low existing-index usage or a sequential scan alone.

## Persistence and verification

Migration 0004 adds batches, source-plan membership and candidate decisions. Migration 0005 normalizes per-candidate evidence into foreign-keyed candidate/plan/alias/reason rows, preserving the prototype data created while developing the endpoint. Definitions remain structured immutable JSON; query relationships are relational. A data-bearing evidence downgrade/upgrade preserved the complete saved batch. Both migrations were also reversed/reapplied on the separate disposable metadata database with no schema drift.

M5 verification executed **204 tests**, including 27 candidate unit cases and 11 new real PostgreSQL/API cases. Coverage includes key ordering, joins, exact/unique/partial/expression/covering/opclass distinctions, backward/prefix overlap, Unicode/quoted identifiers, source merging, bounds, fresh indexes, changed schemas, persistence and empty results. Integration tests passed generated definitions through session-local HypoPG and reset them; they asserted physical index counts were unchanged. That validates syntax and supported definitions, not planner benefit or actual performance. Fixture-only physical indexes used to exercise catalog changes were created/removed in isolated test-owned schemas.

Sources: PostgreSQL documents [multicolumn B-Tree behavior](https://www.postgresql.org/docs/18/indexes-multicolumn.html), [ordering and backward scans](https://www.postgresql.org/docs/18/indexes-ordering.html), and [index key/catalog identity](https://www.postgresql.org/docs/18/catalog-pg-index.html). In PostgreSQL 18, skip scans can also make nonleading predicates useful; the generator's equality-first rule is a bounded heuristic rather than a claim that other orders are unusable.
