# Learning notes

## M0: how to think about IndexPilot

An index is an extra data structure that helps PostgreSQL find rows without reading every table page. Imagine a book index: it is helpful when you need a few topics, but looking up nearly every page through the index may be slower than reading the book in order. This is why a sequential scan is not automatically a mistake.

A B-Tree on `(user_id, created_at)` groups entries first by user, then by date within that user. It can suit “orders for this user since a date, ordered by date.” Reversing columns changes which contiguous ranges are easy to find. Candidate generation must therefore understand predicate roles and column order rather than just collect column names.

PostgreSQL's planner compares strategies using estimated costs and statistics. EXPLAIN shows that choice as a tree: scans find rows, joins combine them, sorts order them. Parent node costs already include child work, so IndexPilot will use the root total rather than add every node and double-count. The units are relative costs, not milliseconds; actual timing needs an execution experiment.

HypoPG lets the planner consider an index that has no physical data structure. It can answer “would this change the estimated plan?” It cannot answer “how many milliseconds faster is it?” Its hypothetical state belongs to a single session, so the evaluator must hold one connection throughout an experiment.

The workload is the set of queries **and how frequently they run**. Improving a query executed thousands of times may matter more than a larger improvement on a rare query. Two useful indexes may compete or work together. That is why the optimizer will replan combinations, instead of adding separate percentage improvements.

Normalization also applies to IndexPilot's own database: store a query pattern once, then attach many timestamped observations. Store a candidate once per analysis, then link it to many evaluated sets. Foreign keys describe those relationships and prevent orphaned results. The [ER diagram](DATABASE_DESIGN.md) shows the intended design; migrations will make it real in later milestones.

The first milestone creates the engineering contract, not the application. The next milestone must prove the database environment and deterministic sample data work before any performance feature can be credible.
