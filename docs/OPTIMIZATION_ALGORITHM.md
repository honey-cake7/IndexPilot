# Workload-aware optimization

Implemented in M7 using M5 [candidate batches](CANDIDATES.md) and the M6 [HypoPG evaluator](HYPOTHETICAL_EVALUATION.md). A pure greedy selector ranks actual complete-set planner estimates under an estimated-byte budget. It supports optional heuristic write penalties and per-query regression limits, saves normalized selection/trial history and verifies the final set with a fresh EXPLAIN. No execution-speed benchmark or global-optimum claim is made. The optional exhaustive solver remains unimplemented.

## Run the working API

Keep PostgreSQL running, execute `uv run alembic upgrade head` (revision 0007), and restart the backend. Open `http://127.0.0.1:8000/docs`. Following the [candidate example](CANDIDATES.md) to obtain `$batch`, use:

```powershell
$request = @{
  batch_id = $batch.id
  storage_budget_bytes = 1048576
  max_selected_indexes = 8
  max_evaluations = 128
  max_query_regression_pct = 0
  write_penalty_cost_per_mib = 0
} | ConvertTo-Json
$optimization = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/optimizations `
  -ContentType application/json -Body $request
$optimization.result | Select-Object selected_candidate_ids, stop_reason, evaluations, estimated_read_improvement_pct
$optimization.result.final_score
$optimization.result.trials | Select-Object step, added_candidate_id, chosen, reason, marginal_net_gain, additional_bytes, gain_per_byte
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/optimizations/$($optimization.id)"
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/v1/optimizations?limit=20&offset=0'
```

`storage_budget_bytes` is a required integer from 0 to 2^63−1. This constrains **additional HypoPG-estimated index bytes**, excluding existing physical indexes. It is not a guarantee about eventual disk consumption. The request uses all proposed candidates and all source queries in that batch. Saved plan frequencies and representative values are unchanged; create new source plans/batches to change them. Source plans remain limited to 100 and proposed candidates to 32.

Defaults: at most eight selected indexes (allowed 0–32); 128 evaluator calls (allowed 2–1024, including baseline and mandatory fresh final verification); no per-query regression limit; write penalty zero. A regression limit of zero refuses any estimated query-cost increase against baseline. `max_query_regression_pct` permits a finite nonnegative percentage up to 1,000,000. `write_penalty_cost_per_mib` permits 0–10^12. Optional `write_weights` maps proposed candidate UUIDs to finite weights 0–10^9; missing weights default to one. Weights apply to per-set estimated bytes, not inferred write activity.

`frequency_basis` defaults to `user_supplied_scenario` and labels the common observation/scenario basis for query frequencies and optional write weights. Changing the label does not rescale either input. No table write rate, write latency or write amplification is measured. Positive heuristic penalties therefore require deliberate user interpretation.

POST returns HTTP 201 with `options`, `result`, `evaluation_run_id`, frozen context and `cleanup_confirmed`. Result includes baseline/final raw plans, objective components, selected order, candidate outcomes, complete-round trials, per-query changes and stop reason. Every chosen trial records that step's marginal gain; do not assign the entire final improvement to each index independently. GET reloads saved evidence without connecting to the target. Candidate batches retain their original generation-time status.

## Objective and selection

For index set S, let `c(q, S)` be PostgreSQL's estimated root total plan cost for a representative query and `f(q)` its execution frequency. Define:

```
C(S) = sum(f(q) * c(q, S) for q in workload)
B(S) = sum(estimated_bytes(i) for i in S)
P(S) = write_penalty_cost_per_mib * sum(write_weight(i) * estimated_mib(i) for i in S)
J(S) = C(S) + P(S)
```

`P` is an optional, explicitly heuristic penalty in equivalent weighted planner-cost units, not measured write latency. Default zero; workload frequencies and write weights must share a declared observation interval or user-supplied scenario. Without measured writes there is no claim of quantified write overhead. Storage bytes remain a hard constraint independent of this penalty.

Initialize `S = {}` and obtain the real baseline `C({})`. For every remaining candidate i, ask the HypoPG evaluator for **the whole set** `S ∪ {i}` and check its actual combined estimated bytes against the budget. Compute marginal net gain `J(S) - J(S ∪ {i})`. Reject nonpositive gain and unknown/nonpositive size estimates for automatic hard-budget selection. Rank positive feasible candidates by net gain per additional estimated byte; deterministic ties use larger absolute gain, then canonical signature (UUID is the final stable fallback). Select the best and repeat. Always recompute remaining trial costs relative to the new set. Stop when no feasible positive gain remains, the candidate cap is reached, or a bounded evaluation limit is reached; report that reason.

Re-evaluate the final set and validate its storage before persistence. Combined trials use their actual member/total sizes rather than adding historical singleton estimates. Zero or negative incremental bytes are conservatively rejected rather than dividing by zero. The final evaluator call bypasses its cache and replans every query; changed per-query costs, objective or total bytes relative to the accepted trial abort publication and require a retry. Final budget/regression checks and positive net gain over baseline must still pass. An evaluation failure is an error/unknown result, never a zero cost. Invalid/nonfinite inputs are rejected; missing estimates stay unknown. Handle baseline zero by returning no relative percentage (`null` plus explanation) instead of dividing by zero.

```
estimated_read_improvement_pct = 100 * (C({}) - C(S)) / C({})
```

Do not substitute J into this read-improvement formula. Show objective and read cost separately. Record per-query changes, flag regressions even when total workload improves, and allow an optional per-query regression limit relative to the original baseline. Unknown or zero baseline query cost cannot support a relative regression ratio; retain absolute change. With an enabled limit, any positive increase from a zero-cost query baseline is refused as an undefined regression ratio. An unknown workload baseline fails the run rather than supplying a fabricated comparison.

Example arithmetic for learning only: if query A has frequency 100 and estimated cost 50, its contribution is 5,000 relative units. A frequency-1 query of cost 1,000 contributes 1,000. Helping the expensive-looking single query is not automatically the best workload decision. These numbers are not benchmark evidence.

## Interactions, limits and evidence

Two indexes can overlap in usefulness or enable a combined bitmap plan. Their isolated benefits cannot be added. Every scored trial is a complete PostgreSQL planning experiment in a fresh/reset hypothetical configuration with the same queries, representative values and planner settings.

For n candidates and k selected indexes, greedy selection performs at most roughly `k*n` set evaluations, each planning all m representative query scenarios, plus final verification. Caching identical compatible sets reduces repeated work. Limit candidate width, count, query count and evaluation count rather than enumerating arbitrary permutations.

One final uncached call is always reserved. A round starts only if the remaining evaluation allowance can cover every remaining candidate plus final verification; an incomplete round cannot bias selection toward whichever candidate happened to be visited first. Consequently a very small limit can validly return an empty set without exploring any trial. Stop reasons are `no_candidates`, `candidates_exhausted`, `no_feasible_gain`, `index_limit` and `evaluation_limit`. `search_complete=false` marks a configured cap; true means the bounded greedy procedure finished, not that all subsets or the global optimum were examined. No partial recommendation is returned on timeout, invalid context or database failure.

The same cooperative planning budget as M6 applies (default 30 seconds), with independent cleanup timeouts. This is not a hard HTTP deadline. The M6 API retains its 65-set cache default; optimizer runs allocate a private cache bounded by `max_evaluations`. No estimate cache survives the held connection or run.

The strategy is understandable but not globally optimal: it can miss a pair with no individual benefit or prefer a locally attractive large index. A future optional exhaustive solver for n ≤ 10 could evaluate at most `2^n` sets and provide an experimental optimum under the same estimated objective, not actual latency. It is not implemented in M7. The planned per-query benchmark baseline will independently choose useful singleton candidates, deduplicate them and report its storage even if it exceeds IndexPilot's budget; comparisons must disclose this difference. Also report a budget-matched variant where feasible.

Store the trial set, weighted cost, bytes, penalty, marginal score, rejected reason and affected queries. Explanations use selection-step marginal changes; they must not attribute the final total gain independently to every selected index.

## Persistence and failures

Migration 0007 adds optimization_run, optimization_candidate and optimization_trial. One run links to its M6 evaluation history and final set. Candidate outcomes/selection order are foreign-keyed rows, and each trial links to the normalized evaluated set and added candidate. Scores and variable settings remain structured JSON; raw plans/query context are reused from M6. One metadata transaction saves the evaluation evidence and optimizer records together; failure rolls everything back. This is optimizer history, while M8's richer recommendation explanations/artifacts remain planned.

Missing/inaccessible required HypoPG functions return 503 with a saved unavailable **evaluation** UUID, and no optimization selection. Other planning/verification failures return safe domain errors with failed evaluation evidence and no partial comparisons. Invalid requests are rejected before planning. These runs are synchronous and local-only; there is no background optimizer job. HypoPG cleanup/discard rules and trusted-server limitations remain those described in M6.

## Executed evidence

The original five-candidate local batch was optimized with a **1,048,576-byte budget**. Saved run `0752ddd7-94ae-49a0-abb0-cc42f0f3f34c` selected one index estimated at **286,720 bytes**, with weighted planner cost **320.12 → 28.05**, after 11 evaluator calls. Zero-budget run `9161af78-1544-4381-855a-5deed6cc1272` selected none and retained cost 320.12. Both verified cleanup and exact saved reload equality. These are actual local observations, not fixed expected outputs or measured latency gains.

`uv run pytest --integration -q` passed **301 tests** (203 unit, 98 PostgreSQL/API). M7 adds 50 unit arithmetic cases and 11 integration cases. Unit fixtures cover frequency reversal, overlapping/complementary alternatives, marginal recomputation, exact/zero budgets, unknown/nonpositive sizes/costs, final drift, deterministic ties, regression boundaries/zero baselines, limits and heuristic penalties. Real PostgreSQL/API tests cover whole-workload selection, exact estimated-byte boundaries, unknown size permissions, missing HypoPG access, write penalties, fresh cache bypass, safe failures, history/restart retrieval, concurrent reads with a one-connection pool and atomic save rollback. Fixture-only schema/data and temporary permission changes are restored; evaluation creates no physical target indexes. See [PROGRESS.md](PROGRESS.md) for publication status.
