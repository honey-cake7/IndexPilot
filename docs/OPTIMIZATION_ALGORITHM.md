# Workload-aware optimization

Status: the selection algorithm below remains planned for M7; no optimizer or measured performance results yet. M5 supplies bounded [candidate batches](CANDIDATES.md). M6 now implements [HypoPG set evaluations](HYPOTHETICAL_EVALUATION.md), fresh baselines, frequency-weighted C(S), estimated B(S) and per-query regression flags. It evaluates requested sets directly; it does not select a storage-budget solution or calculate a write penalty.

For index set S, let `c(q, S)` be PostgreSQL's estimated root total plan cost for a representative query and `f(q)` its execution frequency. Define:

```
C(S) = sum(f(q) * c(q, S) for q in workload)
B(S) = sum(estimated_bytes(i) for i in S)
P(S) = write_penalty_cost_per_mib * sum(write_weight(i) * estimated_mib(i) for i in S)
J(S) = C(S) + P(S)
```

`P` is an optional, explicitly heuristic penalty in equivalent weighted planner-cost units, not measured write latency. Default zero; workload frequencies and write weights must share a declared observation interval or user-supplied scenario. Without measured writes there is no claim of quantified write overhead. Storage bytes remain a hard constraint independent of this penalty.

Initialize `S = {}` and obtain the real baseline `C({})`. For every remaining candidate i that fits the budget, ask the HypoPG evaluator for **the whole set** `S ∪ {i}`. Compute marginal net gain `J(S) - J(S ∪ {i})`. Reject nonpositive gain and unknown/nonpositive size estimates for automatic hard-budget selection. Rank positive feasible candidates by net gain per additional estimated byte; deterministic ties use larger absolute gain, then canonical signature. Select the best and repeat. Always recompute remaining trial costs relative to the new set. Stop when no feasible positive gain remains, the candidate cap is reached, or a bounded evaluation limit is reached; report that reason.

Re-evaluate the final set and validate its storage before persistence. If storage changes with combined evaluation, use the combined result rather than optimistic singleton sizes. An evaluation failure is an error/unknown result, never a zero cost. Reject non-finite/negative frequency, cost and size inputs. Handle baseline zero by returning no relative percentage (`null` plus explanation) instead of dividing by zero.

```
estimated_read_improvement_pct = 100 * (C({}) - C(S)) / C({})
```

Do not substitute J into this read-improvement formula. Show objective and read cost separately. Record per-query changes, flag regressions even when total workload improves, and allow an optional per-query regression limit. Unknown or zero baseline query cost cannot support a relative regression ratio; retain absolute change.

Example arithmetic for learning only: if query A has frequency 100 and estimated cost 50, its contribution is 5,000 relative units. A frequency-1 query of cost 1,000 contributes 1,000. Helping the expensive-looking single query is not automatically the best workload decision. These numbers are not benchmark evidence.

## Interactions, limits and evidence

Two indexes can overlap in usefulness or enable a combined bitmap plan. Their isolated benefits cannot be added. Every scored trial is a complete PostgreSQL planning experiment in a fresh/reset hypothetical configuration with the same queries, representative values and planner settings.

For n candidates and k selected indexes, greedy selection performs at most roughly `k*n` set evaluations, each planning all m representative query scenarios, plus final verification. Caching identical compatible sets reduces repeated work. Limit candidate width, count, query count and evaluation count rather than enumerating arbitrary permutations.

The strategy is understandable but not globally optimal: it can miss a pair with no individual benefit or prefer a locally attractive large index. An optional exhaustive solver for n ≤ 10 evaluates at most `2^n` sets and provides an experimental optimum under the same estimated objective. It is not an optimum for actual latency. The per-query benchmark baseline independently chooses useful singleton candidates, deduplicates them and reports its storage even if it exceeds IndexPilot's budget; comparisons must disclose this difference. Also report a budget-matched variant where feasible.

Store the trial set, weighted cost, bytes, penalty, marginal score, rejected reason and affected queries. Explanations use selection-step marginal changes; they must not attribute the final total gain independently to every selected index.
