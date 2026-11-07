from collections.abc import Iterator

from pydantic import ValidationError

from indexpilot.errors import DomainError
from indexpilot.plans.models import PlanDocument, PlanNode

MAPPING = {
    "Node Type": "node_type",
    "Relation Name": "relation_name",
    "Schema": "schema_name",
    "Alias": "alias",
    "Index Name": "index_name",
    "Startup Cost": "startup_cost",
    "Total Cost": "total_cost",
    "Plan Rows": "estimated_rows",
    "Plan Width": "estimated_width",
    "Index Cond": "index_condition",
    "Recheck Cond": "recheck_condition",
    "Filter": "filter_condition",
    "Sort Key": "sort_keys",
    "Group Key": "group_keys",
    "Parent Relationship": "parent_relationship",
    "Subplan Name": "subplan_name",
    "Join Type": "join_type",
    "Parallel Aware": "parallel_aware",
}
JOIN_KEYS = ("Hash Cond", "Merge Cond", "Join Filter")


def walk_plan(root: PlanNode) -> Iterator[tuple[str, PlanNode]]:
    stack = [("0", root)]
    while stack:
        path, node = stack.pop()
        yield path, node
        stack.extend(
            (f"{path}.{index}", child) for index, child in reversed(list(enumerate(node.children)))
        )


def parse_explain(raw) -> PlanDocument:
    count = 0

    def parse_node(value, depth=0):
        nonlocal count
        count += 1
        if depth > 64 or count > 5000 or not isinstance(value, dict):
            raise ValueError("Plan exceeds supported shape/complexity")
        if any(key.startswith("Actual ") for key in value):
            raise ValueError("Execution metrics are not accepted as estimated plans")
        fields = {field: value[key] for key, field in MAPPING.items() if key in value}
        fields["join_conditions"] = {key: value[key] for key in JOIN_KEYS if key in value}
        children = value.get("Plans", [])
        if not isinstance(children, list):
            raise ValueError("Plan children must be a list")
        return PlanNode(**fields, children=[parse_node(child, depth + 1) for child in children])

    try:
        if (
            not isinstance(raw, list)
            or len(raw) != 1
            or not isinstance(raw[0], dict)
            or "Execution Time" in raw[0]
        ):
            raise ValueError("Expected one plain JSON EXPLAIN document")
        root = parse_node(raw[0]["Plan"])
        return PlanDocument(
            root=root,
            node_count=count,
            observations=[],
            warnings=[
                "Planner costs and rows are estimates, not measured milliseconds or row counts.",
                "Use the root total cost; summing parent and child totals double-counts work.",
            ],
        )
    except (ValueError, KeyError, TypeError, ValidationError, RecursionError):
        raise DomainError(
            "invalid_plan", "PostgreSQL returned an unsupported or malformed estimated plan.", 502
        ) from None
