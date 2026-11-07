import pytest
from indexpilot.errors import DomainError
from indexpilot.plans.explanations import explain_plan
from indexpilot.plans.parser import parse_explain, walk_plan


def plan(node_type="Seq Scan", **fields):
    return {
        "Node Type": node_type,
        "Startup Cost": 0,
        "Total Cost": 10,
        "Plan Rows": 5,
        "Plan Width": 8,
        **fields,
    }


def test_recursive_plan_preserves_conditions_and_root_cost():
    raw = [
        {
            "Plan": plan(
                "Sort",
                **{
                    "Total Cost": 100,
                    "Sort Key": ["o.created_at DESC"],
                    "Plans": [
                        plan(
                            "Hash Join",
                            **{
                                "Hash Cond": "o.user_id = u.id",
                                "Join Filter": "o.id > u.id",
                                "Plans": [
                                    plan(
                                        "Bitmap Heap Scan",
                                        **{
                                            "Relation Name": "orders",
                                            "Schema": "public",
                                            "Recheck Cond": "user_id = 101",
                                            "Filter": "status = 'paid'",
                                            "Plans": [
                                                plan(
                                                    "Bitmap Index Scan",
                                                    **{
                                                        "Index Name": "some_index",
                                                        "Index Cond": "user_id = 101",
                                                    },
                                                ),
                                            ],
                                        },
                                    ),
                                    plan(
                                        "Hash",
                                        **{
                                            "Plans": [
                                                plan("Seq Scan", **{"Relation Name": "users"})
                                            ]
                                        },
                                    ),
                                ],
                            },
                        ),
                    ],
                },
            )
        }
    ]
    result = parse_explain(raw)
    assert result.node_count == 6
    assert result.root.total_cost == 100
    join = result.root.children[0]
    assert join.join_conditions["Hash Cond"] == "o.user_id = u.id"
    assert join.children[0].filter_condition == "status = 'paid'"
    assert join.children[0].children[0].index_condition == "user_id = 101"
    assert len(list(walk_plan(result.root))) == 6
    assert result.cost_unit == "planner_cost" and not result.execution_measured


@pytest.mark.parametrize(
    "node_type",
    [
        "Seq Scan",
        "Index Scan",
        "Index Only Scan",
        "Bitmap Heap Scan",
        "Bitmap Index Scan",
        "Nested Loop",
        "Hash Join",
        "Merge Join",
        "Sort",
        "Incremental Sort",
        "Gather",
        "Result",
    ],
)
def test_node_types_and_optional_fields(node_type):
    parsed = parse_explain([{"Plan": {"Node Type": node_type}}])
    assert parsed.root.node_type == node_type and parsed.root.total_cost is None
    assert parsed.root.children == []
    if node_type not in {"Gather", "Result"}:
        assert explain_plan(parsed, []).observations


@pytest.mark.parametrize(
    "raw",
    [
        [],
        {},
        [{"Plan": {}}],
        [{"Plan": plan(**{"Total Cost": -1})}],
        [{"Plan": plan(**{"Total Cost": float("nan")})}],
        [{"Plan": plan(**{"Actual Rows": 10})}],
        [{"Plan": plan(), "Execution Time": 3}],
        [{"Plan": plan(**{"Plans": {}})}],
    ],
)
def test_invalid_or_measured_plans_are_rejected(raw):
    with pytest.raises(DomainError) as failure:
        parse_explain(raw)
    assert failure.value.code == "invalid_plan"


def test_nested_initplan_metadata_and_zero_cost():
    raw = [
        {
            "Plan": plan(
                "Result",
                **{
                    "Total Cost": 0,
                    "Plans": [
                        plan(
                            "Index Only Scan",
                            **{"Parent Relationship": "InitPlan", "Subplan Name": "InitPlan 1"},
                        )
                    ],
                },
            )
        }
    ]
    root = parse_explain(raw).root
    assert root.total_cost == 0
    assert root.children[0].parent_relationship == "InitPlan"


def test_depth_limit_is_explicit():
    root = plan()
    current = root
    for _ in range(66):
        child = plan()
        current["Plans"] = [child]
        current = child
    with pytest.raises(DomainError):
        parse_explain([{"Plan": root}])
