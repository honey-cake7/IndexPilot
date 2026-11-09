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

## M6: planner experiments, session memory and honest estimates

HypoPG gives PostgreSQL an imaginary index definition. It lets EXPLAIN consider that index without constructing a real disk index. Another connection cannot see it. `evaluation/session.py` therefore holds one connection through reset, creation, planning and cleanup; changing connections halfway would invalidate the experiment.

A transaction and a connection are different lifetimes. A real test showed that rolling back the transaction still left the imaginary index in that connection's memory. Explicit HypoPG reset is necessary. After a statement timeout, PostgreSQL first requires rollback to recover from the failed transaction, then we call and verify reset. If cleanup fails, we close the connection rather than reuse uncertain state. Read-only transactions can allow these session-memory functions while still prohibiting physical table/index writes.

The baseline is the current planner result with no hypothetical indexes, retaining all existing real indexes. A saved plan from yesterday could reflect different statistics or settings, so the evaluator captures a fresh baseline for today's trial. Representative values also matter: the typed literal for user 101 stays the same across baseline and candidate trials, even when it originally arrived as `$1`.

For arithmetic only, two queries with frequencies 10 and 1 and costs 20 and 100 contribute `10*20 + 1*100 = 300` planner units. This is a weighted comparison score, not 300 milliseconds. Lower estimated cost may suggest an index worth testing, but only later execution benchmarks can establish a speedup.

Two indexes that help the same filter may compete for the same plan. Their individual percentage benefits cannot be added. `engine.py` creates both together and asks PostgreSQL again. It also flags an individual query whose estimated cost rises even if the weighted total falls. This supplies evidence for M7's selection algorithm; it does not itself select a recommendation.

Unknown storage is not zero storage. If the size function is inaccessible, the member and whole-set byte estimates remain null. Only the empty hypothetical set legitimately costs zero additional hypothetical bytes. Likewise, percentage improvement over a zero baseline is undefined, so it is null rather than a division error or a made-up gain.

Normalized evaluation tables preserve one frozen query per run and one plan per query/set pair. Candidate membership uses foreign keys. Later GET requests can explain a historical experiment without rerunning it against a changed database. Generation's old `not_evaluated` field stays a generation snapshot; the separate evaluation record holds the newer evidence.

## M7: choosing a workload index set under a budget

An index can help a rare query greatly and still matter less than a smaller improvement to a frequently run query. The optimizer adds each query's frequency times its root cost. Unit examples reverse the frequencies of two queries and verify that the chosen index reverses too. Those arithmetic examples test the decision rule; real PostgreSQL plans test the database behavior.

Marginal gain means the improvement from what is already selected. After choosing index A, we ask PostgreSQL about A plus B, rather than reusing B's original standalone gain. If A already supplies the useful access path, B may add no benefit. `optimizer/greedy.py` repeats this question, ranks positive net gain per extra estimated byte and records why alternatives were passed over. Equal ratios prefer larger absolute gain and then canonical identity for deterministic results.

A hard estimated-byte budget can legitimately produce an empty set. In the actual local example, a 1 MiB budget selected one index estimated at 286,720 bytes; zero bytes selected none. Both outcomes were saved and reloaded. The estimated plan cost changed from 320.12 to 28.05 for the selected case, but no submitted query was executed, so this is not a latency result.

The optional write penalty is a configurable preference against maintenance cost, not a measured model of PostgreSQL writes. It raises the selection objective while the read-cost estimate stays visible separately. Users must interpret weights on the same scenario/observation basis as frequencies. An optional per-query limit can refuse a query regression even when the total improves; a percentage increase from a zero-cost baseline is undefined and is conservatively refused when the limit is enabled.

Greedy selection is a practical search rule, not proof of the best possible answer. It can miss two indexes that help only together. A complete round compares every available next addition; the evaluation cap cannot quietly privilege the first visited candidate. One final fresh planning call is reserved, and changed costs/storage prevent saving an uncertain selection. The saved trace shows decisions made at each step; the final total gain does not belong independently to every chosen index.

Normalized optimizer records link choices to the plans that justified them. Selected order has its own constrained rows. Both those records and the evaluation evidence commit in one transaction, so a failed membership insert cannot leave a half-saved optimization. Recommendation explanations, physical benchmarking and the dashboard still come later.

## M8: keeping an explanation faithful to its evidence

A recommendation is a historical snapshot, not a fresh claim about today's database. M8 copies the chosen definitions, settings, representative queries, plans and observation times from a completed optimization. Later source changes do not silently rewrite it. Foreign keys keep the origin traceable, while copied values preserve what was explained. A repeated save returns the existing snapshot.

Query contribution and index contribution answer different questions. A query's final weighted reduction is its frequency times its before/after root-cost difference. That describes the complete final index set. An index's marginal gain describes the moment it was added to the preceding selected set. Assigning the final whole-set improvement independently to every selected index would double-count interacting benefits.

Confidence should follow the available evidence. Real PostgreSQL planner estimates justify an estimated comparison; they do not establish measured latency. M8 exposes missing statistics, captured ANALYZE times, regression warnings and unmeasured write overhead. It uses planner_estimate rather than a made-up confidence percentage, and leaves the benchmark outcome null until actual measurements exist.

Normalization prevents mismatched evidence: a relevant-query link must reference both an index and a query within the same recommendation. Composite foreign keys enforce that scope in PostgreSQL. One transaction saves all the children, so failure after staging the header/query rows cannot leave a partial recommendation. Tests exercise these constraints and rollback against the real database.

SQL export is text, not execution. Quoted identifiers preserve names containing quotes, spaces and semicolons as identifiers; tests parse the output into exactly the intended CREATE INDEX statement. The export uses the frozen proposal and still needs human review against current schema, space and locking conditions. Nothing in M8 builds a physical index or runs a benchmark.

## M9: testing estimates against actual execution

Planner cost is a relative estimate. M9 measures elapsed transactions with pgbench and stores each individual microsecond sample. A read transaction includes one SELECT plus BEGIN/COMMIT/protocol overhead, so its milliseconds are not isolated server execution time. A p95 can be calculated from those samples; an aggregate statement mean alone cannot supply it. The same distinction applies to throughput: TPS counts the defined transactions.

Fair comparisons require the same starting rows. Every arm/operation gets a newly generated schema at the same seed/scale; row hashes verify equivalence. Write probes commit real inserts, indexed-column updates and deletes, then the next experiment starts fresh instead of inheriting dead tuples/mutations. Arm order rotates. This still does not flush OS/PostgreSQL caches or eliminate background activity, so results are labeled local warm-cache measurements.

The published two-query experiment shows a real trade-off. IndexPilot reduced mixed-read mean latency from 0.3604 to 0.2117 ms using 114,688 measured index main-fork bytes within a 300,000 estimated-byte budget. The per-query set was faster at 0.1209 ms but used 475,136 bytes. IndexPilot's update mean and the per-query delete mean regressed, each dominated by one slower repetition. All repetitions are retained; we do not attribute the outliers to indexes alone or claim a universal win.

Isolation is more than a database name. M9 verifies server/database/role/marker, rejects monitored aliases and checks a nonce through the actual container transport. DDL/DML is confined to owned generated schemas. Unknown external dependencies stop cleanup instead of being destroyed with CASCADE. Durable queued/running/terminal states and explicit cleanup confirmation make failures visible after restart.

Long-lived statistics are part of real development. When local statement history exceeded an older test's capture bound, the collector correctly refused interval inference. Raising an explicit bounded test capture preserved both the real history and the safety rule. Resetting all statistics or pretending truncated captures were complete would have hidden the problem.

## M10: presenting database evidence accurately

A dashboard is another client of the database engine. TypeScript checks the request contract, but cannot prove that an index works: PostgreSQL/HypoPG and actual pgbench runs supply that evidence. The generated client catches field mismatches without duplicating backend models by hand. A full workflow test connects the form to saved PostgreSQL records; component fixtures test loading/errors without claiming to measure database behavior.

A budget slider changes an input, not history. For example, a 1 MiB optimizer result remains a 1 MiB result after typing zero. A new optimizer request saves a different ID and may select no indexes. Both outcomes remain available. Planner costs are frequency-weighted root costs; adding the child-node costs would double-count work. The plan tree therefore shows estimates without summing its children.

A chart must state its units and measurement population. The measured chart uses only the selected pgbench phase and reports the mean of repetition means, repetition count and range. The update phase is a different experiment from the mixed-read phase. Missing measurements do not become zeros. A single successful run checks the workflow; it does not establish repeatable performance superiority.

Accessibility is testable behavior. Real browser checks found low-contrast labels, scrollable tables lacking keyboard focus, and narrow layouts allowing descendants to widen the page. Correct colors, focusable scroll regions, positioned hidden table captions and grid minimum widths fixed those findings without hiding the data. Native inputs, visible focus, a skip link and a keyboard-operable mobile drawer let users complete the same workflow without hover.
