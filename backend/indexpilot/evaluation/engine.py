import time

from indexpilot.errors import DomainError
from indexpilot.evaluation.cache import RunCache
from indexpilot.evaluation.costs import cost_reduction, weighted_cost
from indexpilot.evaluation.models import QueryEstimate, SetEstimate
from indexpilot.plans.explanations import explain_plan
from indexpilot.plans.parser import parse_explain, walk_plan
from indexpilot.plans.service import PLANNER_SETTINGS

SETTINGS = (
    *PLANNER_SETTINGS,
    "enable_sort",
    "enable_incremental_sort",
    "enable_hashagg",
    "enable_material",
    "enable_memoize",
    "parallel_setup_cost",
    "parallel_tuple_cost",
    "plan_cache_mode",
    "hypopg.enabled",
    "hypopg.use_real_oids",
)


class EvaluationBudget:
    def __init__(self, connection, *, seconds, statement_timeout_ms):
        self.connection = connection
        self.deadline = time.monotonic() + seconds
        self.statement_timeout_ms = statement_timeout_ms

    def check(self):
        remaining = int((self.deadline - time.monotonic()) * 1000)
        if remaining <= 0:
            raise DomainError(
                "evaluation_timeout", "The evaluation planning budget was exceeded.", 504
            )
        self.connection.execute(
            "SELECT set_config('statement_timeout',%s,true)",
            (str(min(remaining, self.statement_timeout_ms)),),
        )


def current_settings(connection):
    return dict(
        connection.execute(
            "SELECT name,setting FROM pg_settings WHERE name=ANY(%s)", (list(SETTINGS),)
        )
    )


class WorkloadEvaluator:
    def __init__(self, connection, session, queries, candidates, budget):
        self.connection = connection
        self.session = session
        self.queries = tuple(query.model_copy(deep=True) for query in queries)
        self.candidates = {
            identifier: value.model_copy(deep=True) for identifier, value in candidates.items()
        }
        self.budget = budget
        self.cache = RunCache()
        self.settings = current_settings(connection)
        self.failed = False

    def evaluate(self, candidate_ids=frozenset()):
        if self.failed:
            raise DomainError(
                "evaluation_aborted", "This evaluation context failed and must be discarded.", 409
            )
        try:
            return self._evaluate(candidate_ids)
        except BaseException:
            self.failed = True
            raise

    def _evaluate(self, candidate_ids):
        key = frozenset(candidate_ids)
        if key - self.candidates.keys():
            raise DomainError("invalid_candidate_set", "Index set contains unknown candidates.")
        self.budget.check()
        if self.connection.closed or current_settings(self.connection) != self.settings:
            raise DomainError(
                "evaluation_context_changed", "Planner settings changed during evaluation.", 409
            )
        self.session.reset()
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        if key and self.cache.get(frozenset()) is None:
            self.evaluate(frozenset())
        self.cache.require_room(key)
        indexes = []
        estimates = []
        try:
            for identifier in sorted(key, key=str):
                self.budget.check()
                indexes.append(self.session.create(identifier, self.candidates[identifier]))
            names = {index.hypothetical_name: index.candidate_id for index in indexes}
            baseline = self.cache.get(frozenset())
            old = {query.source_plan_id: query for query in baseline.queries} if baseline else {}
            for query in self.queries:
                self.budget.check()
                raw = self.connection.execute(
                    "EXPLAIN (FORMAT JSON,VERBOSE TRUE,COSTS TRUE,SETTINGS TRUE) "
                    + query.analysis.canonical_sql,
                    prepare=False,
                ).fetchone()[0]
                document = explain_plan(parse_explain(raw), query.analysis.tables)
                used = sorted(
                    {
                        names[node.index_name]
                        for _, node in walk_plan(document.root)
                        if node.index_name in names
                    },
                    key=str,
                )
                previous = (
                    old[query.source_plan_id].plan.root.total_cost
                    if old
                    else document.root.total_cost
                )
                cost = document.root.total_cost
                estimates.append(
                    QueryEstimate(
                        source_plan_id=query.source_plan_id,
                        frequency=query.frequency,
                        plan=document,
                        raw_explain=raw,
                        used_candidate_ids=used,
                        baseline_cost=previous,
                        estimated_improvement_pct=cost_reduction(previous, cost),
                        regression=cost > previous
                        if cost is not None and previous is not None
                        else None,
                    )
                )
            weighted = weighted_cost(
                (query.frequency, query.plan.root.total_cost) for query in estimates
            )
            base_cost = baseline.weighted_cost if baseline else weighted
            complete = all(index.estimated_size_bytes is not None for index in indexes)
            size = sum(index.estimated_size_bytes for index in indexes) if complete else None
            if size is not None and size > 2**63 - 1:
                complete, size = False, None
            warnings = [
                "Planner costs and hypothetical bytes are estimates; execution was not measured."
            ]
            if not complete:
                warnings.append(
                    "Some sizes are unknown; this set cannot automatically satisfy a hard budget."
                )
            if weighted is None:
                warnings.append(
                    "A workload cost is missing/overflowed; weighted improvement is unavailable."
                )
            if base_cost == 0:
                warnings.append("Baseline cost is zero; relative improvement is undefined.")
            if any(query.regression for query in estimates):
                warnings.append(
                    "At least one query has a higher estimated cost with this index set."
                )
            result = SetEstimate(
                candidate_ids=sorted(key, key=str),
                indexes=indexes,
                queries=estimates,
                weighted_cost=weighted,
                baseline_weighted_cost=base_cost,
                estimated_improvement_pct=cost_reduction(base_cost, weighted),
                estimated_size_bytes=size,
                storage_complete=complete,
                warnings=warnings,
            )
        except BaseException:
            self.failed = True
            raise
        finally:
            try:
                self.session.cleanup()
            except BaseException:
                self.failed = True
                raise
        self.cache.put(key, result)
        return result.model_copy(deep=True)
