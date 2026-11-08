# Learning notes

## M0: how to think about IndexPilot

An index is an extra data structure that helps PostgreSQL find rows without reading every table page. Imagine a book index: it is helpful when you need a few topics, but looking up nearly every page through the index may be slower than reading the book in order. This is why a sequential scan is not automatically a mistake.

A B-Tree on `(user_id, created_at)` groups entries first by user, then by date within that user. It can suit “orders for this user since a date, ordered by date.” Reversing columns changes which contiguous ranges are easy to find. Candidate generation must therefore understand predicate roles and column order rather than just collect column names.

PostgreSQL's planner compares strategies using estimated costs and statistics. EXPLAIN shows that choice as a tree: scans find rows, joins combine them, sorts order them. Parent node costs already include child work, so IndexPilot will use the root total rather than add every node and double-count. The units are relative costs, not milliseconds; actual timing needs an execution experiment.

HypoPG lets the planner consider an index that has no physical data structure. It can answer “would this change the estimated plan?” It cannot answer “how many milliseconds faster is it?” Its hypothetical state belongs to a single session, so the evaluator must hold one connection throughout an experiment.

The workload is the set of queries **and how frequently they run**. Improving a query executed thousands of times may matter more than a larger improvement on a rare query. Two useful indexes may compete or work together. That is why the optimizer will replan combinations, instead of adding separate percentage improvements.

Normalization also applies to IndexPilot's own database: store a query pattern once, then attach many timestamped observations. Store a candidate once per analysis, then link it to many evaluated sets. Foreign keys describe those relationships and prevent orphaned results. The [ER diagram](DATABASE_DESIGN.md) shows the intended design; migrations will make it real in later milestones.

The first milestone creates the engineering contract, not the application. The next milestone must prove the database environment and deterministic sample data work before any performance feature can be credible.

## M1: constraints, roles and reproducibility in real PostgreSQL

The sample `order_items` table uses `(order_id, line_number)` as a composite primary key: line 1 can appear in many different orders but cannot appear twice in the same order. A foreign key ensures every referenced order and product exists. `orders.total` and `payments.amount` are generated from actual item values, so the sample has internally consistent money values rather than unrelated random numbers.

The analyzer's default read-only setting is a convenience, not the security boundary: sessions can change it. Our integration test turns it off and still gets permission denied on DELETE and CREATE. PostgreSQL privileges provide that boundary. TEMP privilege is revoked too, rather than assuming “no public schema CREATE” covers all writes.

The same seed and scale yield the same row values; changing the seed changes them. This lets two benchmark configurations start from comparable data. It does not promise identical plan costs or timing: ANALYZE samples statistics, physical layout changes and caches depend on the environment. Deterministic input is one part of a reproducible experiment.

The HypoPG integration test creates an index in one read-only connection and proves another connection sees none. The first connection's plan can use it without any physical index being created. That is why the later evaluation engine must hold the same connection for the entire index-set experiment.

## M2: transactions, capability probes and migrations

A connection is a session; a transaction is a group of work within that session. PostgreSQL marks a transaction failed after many SQL errors. Capability checks use savepoints so a denied probe can roll back its own part while other inspection continues. This is visible in `db/capabilities.py`.

An extension can be available to install, installed in a database, configured correctly, and usable by the current role; these are separate facts. Reading a global configuration setting may require broader privileges than using the extension. IndexPilot checks the actual pg_stat_statements view instead of requesting unnecessary settings access.

Alembic migration 0001 makes the metadata schema versioned. Upgrading creates `monitored_database`; downgrading removes it, so downgrade testing belongs on a disposable database. A database CHECK constraint rejects port 0 even if a caller bypasses Python validation. Independent database constraints protect the stored data, while Pydantic provides earlier user-facing validation.

## M3: patterns, representative values and cumulative counters

`user_id=101` and `user_id=202` have the same query shape, but can touch different numbers of orders. `workloads/manual.py` groups structural patterns while `query_scenario` preserves the actual examples and their frequencies. Grouping is useful for organization; it does not prove equal selectivity or performance.

An AST represents SQL as structured nodes. A `$1` placeholder is a ParamRef; a quoted value is a literal node. `workloads/parameters.py` replaces the former with the latter and a built-in cast. A value containing a quote or semicolon remains one literal. Plain text substitution could accidentally alter quoted text or introduce a second statement. M3 only parses/saves these examples; M4 still needs to resolve their database meaning before planning.

pg_stat_statements counters accumulate. If calls go from 100 to 120 and execution time from 1,000 to 1,100 milliseconds, the interval has 20 calls and a 5 ms mean, not the cumulative mean of about 9.17 ms. `workloads/deltas.py` performs this subtraction. With no calls, the interval mean is unknown/null; aggregate totals cannot reveal p95 latency.

A reset can make counters decrease, while an evicted/recreated entry can lose history. PostgreSQL 18 supplies per-entry stats_since as well as global reset/deallocation metadata. The calculator checks both; it refuses uncertain intervals instead of assuming missing history was zero. Integration tests exercised a real targeted reset and confirmed that a min/max-only reset leaves the cumulative interval usable.

## M4: SQL meaning, statistics and plan trees

Parsing identifies syntax; resolution identifies database objects. In `SELECT id FROM orders o JOIN users u ...`, both tables have an id, so guessing would be wrong. `sql/resolution.py` requires `o.id` or `u.id` and attaches the real relation OID, column and type. Quoted names and schemas are preserved. Schema names must also be part of pattern identity: two schemas can contain entirely different orders tables.

`schema/catalogs.py` reads PostgreSQL's catalogs. An index's key order, collation and operator class affect its meaning; INCLUDE columns are payload rather than searchable leading keys. A partial predicate or expression changes which queries can use an index. M4 captures those distinctions so M5 can avoid incorrect duplicate detection.

Statistics are sampled summaries. A negative n_distinct means a fraction of estimated table rows, not a negative count. A uniform equality estimate can be a useful rough description, but a popular user may have many more orders than average. That is why representative values matter and the planner's actual estimates are retained.

EXPLAIN produces a tree. A Sort can have a Hash Join child, which has scan children. `plans/parser.py` keeps that structure and conditions instead of treating every scan as an independent query. The root total includes child work; adding every cost would double-count. Index-only scans may still visit the heap for visibility checks. A sequential scan on a small table or for many matching rows can be sensible.

The explicit plan endpoint uses EXPLAIN without ANALYZE, so its output is not measured latency. PostgreSQL can still evaluate constant expressions during planning: `SELECT 1/0` fails even without running a workload. Read-only settings therefore need a real SQL/catalog safety policy, not just a check that the text starts with SELECT. Tests install deliberately failing functions in isolated fixture objects and verify they are rejected before planning.

## M5: column order, duplication and bounded search

For `WHERE user_id=101 AND created_at>=... ORDER BY created_at DESC`, fixing the user first groups that user's date entries together. The generator can propose user/date keys with the requested date ordering. It also keeps simpler alternatives because only the planner evaluation can determine whether the wider index earns its storage/write cost. PostgreSQL 18 can use skip scans in some cases, so equality-first is a useful initial heuristic rather than a universal rule.

Two indexes listing the same columns may differ in key order, NULL placement, collation, operator class, predicate or INCLUDE payload. A partial index on paid orders cannot automatically replace a full index for every order. `candidates/deduplication.py` rejects exact usable duplicates, distinguishes unique-index coverage, and warns about overlaps without assuming every prefix makes a smaller index useless.

Candidate generation is not optimization. The generator knows which query patterns motivated each definition, but has not measured its hypothetical cost, storage or write penalty. Combinations are bounded to avoid factorial search. M6 will ask PostgreSQL about those alternatives; M7 will consider the whole frequency-weighted workload.

The evidence migration demonstrates normalization: one candidate can help several query patterns, and one query can motivate several candidates. A membership table with foreign keys expresses that relationship. Preserving the prototype batch through migration verifies that schema evolution does not require throwing away collected work.
