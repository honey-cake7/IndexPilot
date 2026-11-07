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
