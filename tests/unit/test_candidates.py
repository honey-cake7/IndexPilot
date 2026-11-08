import uuid

import indexpilot.candidates.generator as generator_module
import pytest
from indexpilot.candidates.deduplication import compare_existing
from indexpilot.candidates.generator import CandidateSource, generate_candidates
from indexpilot.candidates.models import CandidateRequest, GenerationOptions, OperatorClass
from indexpilot.candidates.sql import candidate_key, definition
from indexpilot.schema.models import ColumnInfo, ColumnStatistics, IndexInfo, IndexKey, TableInfo
from indexpilot.sql.models import (
    OrderFeature,
    PredicateFeature,
    RelationBinding,
    ResolvedColumn,
    SQLAnalysis,
)
from pglast import ast, parse_sql
from pydantic import ValidationError

CLASSES = {
    20: OperatorClass(oid=3124, schema_name="pg_catalog", name="int8_ops"),
    1184: OperatorClass(oid=3127, schema_name="pg_catalog", name="timestamptz_ops"),
    25: OperatorClass(oid=3126, schema_name="pg_catalog", name="text_ops"),
}


def table(
    oid=100, schema="public", name="orders", names=("user_id", "created_at", "status", "region")
):
    columns = []
    for position, name_ in enumerate(names, start=1):
        type_oid = 1184 if name_ == "created_at" else 25 if name_ == "status" else 20
        distinct = 4 if name_ == "status" else 100
        columns.append(
            ColumnInfo(
                number=position,
                name=name_,
                type_oid=type_oid,
                type_schema="pg_catalog",
                type_name={20: "int8", 25: "text", 1184: "timestamptz"}[type_oid],
                formatted_type="test type",
                type_kind="b",
                not_null=False,
                generated="",
                identity="",
                default_expression=None,
                collation_oid=100 if type_oid == 25 else 0,
                collation_schema="pg_catalog" if type_oid == 25 else None,
                collation_name="default" if type_oid == 25 else None,
                statistics=ColumnStatistics(
                    null_fraction=0,
                    average_width=8,
                    n_distinct=distinct,
                    estimated_distinct_values=distinct,
                    uniform_equality_selectivity=1 / distinct,
                    correlation=None,
                    most_common_frequencies=None,
                    most_common_values=None,
                    histogram_bounds=None,
                ),
            )
        )
    return TableInfo(
        oid=oid,
        schema_name=schema,
        name=name,
        kind="r",
        persistence="p",
        access_method="heap",
        estimated_rows=1000,
        estimated_pages=10,
        table_bytes=81920,
        indexes_bytes=0,
        total_bytes=81920,
        row_security=False,
        has_rules=False,
        inheritance=False,
        can_select=True,
        can_use_schema=True,
        last_analyze=None,
        last_autoanalyze=None,
        columns=columns,
        indexes=[],
        constraints=[],
        warnings=[],
    )


def column(table_, name, alias="o"):
    model = next(column for column in table_.columns if column.name == name)
    return ResolvedColumn(
        relation_oid=table_.oid,
        schema_name=table_.schema_name,
        table=table_.name,
        alias=alias,
        name=name,
        type_oid=model.type_oid,
    )


def predicate(table_, name, operator="=", **changes):
    return PredicateFeature(
        **dict(
            {
                "column": column(table_, name),
                "operator": operator,
                "other_column": None,
                "other_kind": "literal",
                "kind": "equality" if operator == "=" else "range",
                "context": "filter",
                "conjunction_only": True,
                "join_type": None,
            },
            **changes,
        )
    )


def source(table_, predicates=(), order=(), number=1, *, extra=()):
    tables = [table_, *extra]
    bindings = [
        RelationBinding(
            alias="o" if i == 0 else "u",
            schema_name=t.schema_name,
            table=t.name,
            relation_oid=t.oid,
        )
        for i, t in enumerate(tables)
    ]
    return CandidateSource(
        uuid.UUID(int=number),
        SQLAnalysis(
            canonical_sql="SELECT ...",
            relations=bindings,
            columns=[],
            predicates=list(predicates),
            order_by=list(order),
            tables=tables,
            warnings=[],
        ),
    )


def generate(sources, tables, **options):
    return generate_candidates(
        sources, {t.oid: t for t in tables}, CLASSES, GenerationOptions(**options)
    )


def index_for(candidate, **changes):
    keys = [
        IndexKey(
            position=i,
            column=key.column,
            attribute_number=key.attribute_number,
            expression=key.column,
            operator_class_oid=key.operator_class.oid,
            operator_class_schema=key.operator_class.schema_name,
            operator_class_name=key.operator_class.name,
            operator_class_default=True,
            collation_oid=key.collation_oid,
            collation_schema=key.collation_schema,
            collation_name=key.collation_name,
            descending=key.descending,
            nulls_first=key.nulls_first,
        )
        for i, key in enumerate(candidate.keys, start=1)
    ]
    return IndexInfo(
        **dict(
            {
                "oid": 999,
                "name": "existing",
                "schema_name": candidate.schema_name,
                "method": "btree",
                "definition": "test-only index metadata",
                "primary": False,
                "unique": False,
                "valid": True,
                "ready": True,
                "live": True,
                "nulls_not_distinct": False,
                "predicate": None,
                "expressions": None,
                "keys": keys,
                "included_columns": [],
                "size_bytes": 8192,
                "scans": 0,
                "tuples_read": 0,
                "tuples_fetched": 0,
            },
            **changes,
        )
    )


def test_equality_range_and_order_direction():
    t = table()
    q = source(
        t,
        [predicate(t, "user_id"), predicate(t, "created_at", ">=")],
        [
            OrderFeature(
                column=column(t, "created_at"),
                expression="o.created_at DESC",
                direction="desc",
                nulls_first=True,
            )
        ],
    )
    result = generate([q], [t])
    combined = next(
        candidate
        for candidate in result.proposed
        if [key.column for key in candidate.definition.keys] == ["user_id", "created_at"]
        and candidate.definition.keys[1].descending
    )
    assert not combined.definition.keys[0].descending and combined.definition.keys[1].nulls_first
    assert any(item.reason == "equality_order" for item in combined.evidence)
    assert any(item.reason == "equality_range" for c in result.proposed for item in c.evidence)
    assert all(
        c.estimated_size_bytes is None and c.estimated_improvement_pct is None
        for c in result.proposed
    )


def test_two_bounded_equality_orders_and_no_arbitrary_permutations():
    t = table(names=("a", "b", "c", "d"))
    result = generate([source(t, [predicate(t, name) for name in ("a", "b", "c", "d")])], [t])
    composites = [
        tuple(key.column for key in c.definition.keys)
        for c in result.proposed
        if len(c.definition.keys) > 1
    ]
    assert sorted(composites) == [("a", "b", "c"), ("b", "a", "c")]
    assert all(len(c.definition.keys) <= 3 for c in result.proposed)


def test_duplicate_query_patterns_merge_evidence_and_remain_deterministic():
    t = table()
    first, second = (
        source(t, [predicate(t, "user_id")], number=1),
        source(t, [predicate(t, "user_id")], number=2),
    )
    a = generate([first, second], [t])
    b = generate([second, first], [t])
    assert a.model_dump() == b.model_dump()
    assert len(a.proposed) == 1 and len(a.proposed[0].evidence) == 2


def test_inner_join_columns_on_both_sides_and_outer_join_exclusion():
    orders, users = table(), table(oid=101, name="users", names=("id",))
    join = predicate(
        orders,
        "user_id",
        kind="join",
        other_kind="column",
        context="join",
        other_column=column(users, "id", "u"),
        join_type="JOIN_INNER",
    )
    result = generate([source(orders, [join], extra=[users])], [orders, users])
    assert {c.definition.table_name for c in result.proposed} == {"orders", "users"}
    outer = join.model_copy(update={"join_type": "JOIN_LEFT"})
    result = generate([source(orders, [outer], extra=[users])], [orders, users])
    assert result.proposed == [] and any("Outer-join" in text for text in result.warnings)


def test_or_not_and_expression_predicates_do_not_form_filter_candidates():
    t = table()
    q = source(
        t,
        [
            predicate(t, "user_id", conjunction_only=False),
            predicate(t, "region", other_kind="expression"),
        ],
    )
    result = generate([q], [t])
    assert not result.proposed and any("OR/NOT" in text for text in result.warnings)


@pytest.mark.parametrize(
    "change",
    [
        {"method": "hash"},
        {"valid": False},
        {"ready": False},
        {"live": False},
        {"predicate": "user_id>0"},
        {"expressions": "lower(user_id)"},
        {"included_columns": ["status"]},
    ],
)
def test_partial_expression_covering_and_unusable_indexes_are_not_exact(change):
    t = table()
    candidate = definition(t, [candidate_key(t.columns[0], CLASSES[20])])
    reason, _, _ = compare_existing(candidate, [index_for(candidate, **change)])
    assert reason is None


@pytest.mark.parametrize(
    "changes",
    [
        {"operator_class_oid": 123},
        {"collation_oid": 999},
        {"descending": True},
        {"nulls_first": True},
    ],
)
def test_semantically_distinct_key_signatures_are_not_exact(changes):
    t = table()
    candidate = definition(t, [candidate_key(t.columns[0], CLASSES[20])])
    existing = index_for(candidate)
    existing.keys[0] = existing.keys[0].model_copy(update=changes)
    assert compare_existing(candidate, [existing])[0] is None


def test_exact_duplicate_and_unique_coverage_have_different_reasons():
    t = table()
    candidate = definition(t, [candidate_key(t.columns[0], CLASSES[20])])
    assert compare_existing(candidate, [index_for(candidate)])[0] == "exact_duplicate"
    assert (
        compare_existing(candidate, [index_for(candidate, unique=True, primary=True)])[0]
        == "covered_by_unique_index"
    )
    t.indexes = [index_for(candidate)]
    result = generate([source(t, [predicate(t, "user_id")])], [t])
    assert result.proposed == [] and result.rejected[0].rejection_reason == "exact_duplicate"


def test_prefix_and_backward_equivalence_are_warnings_not_exact_deduplication():
    t = table()
    candidate = definition(t, [candidate_key(t.columns[0], CLASSES[20])])
    longer = definition(t, [*candidate.keys, candidate_key(t.columns[1], CLASSES[1184])])
    reason, _, warnings = compare_existing(candidate, [index_for(longer)])
    assert reason is None and any("prefix" in message for message in warnings)
    reversed_ = index_for(candidate)
    reversed_.keys[0] = reversed_.keys[0].model_copy(
        update={"descending": True, "nulls_first": True}
    )
    reason, _, warnings = compare_existing(candidate, [reversed_])
    assert reason is None and any("backward" in message for message in warnings)


def test_output_limit_unknown_opclasses_and_width_limit():
    t = table()
    q = source(t, [predicate(t, "user_id"), predicate(t, "created_at", ">=")])
    result = generate([q], [t], max_candidates=1, max_columns=1)
    assert len(result.proposed) == 1 and any(
        c.rejection_reason == "candidate_limit" for c in result.rejected
    )
    result = generate_candidates([q], {t.oid: t}, {}, GenerationOptions())
    assert not result.proposed and any("operator class" in text for text in result.warnings)


def test_quoted_identifiers_and_deterministic_name_length():
    t = table(schema='odd";schema', name='表";orders', names=('user";id',))
    candidate = definition(t, [candidate_key(t.columns[0], CLASSES[20])])
    statement = parse_sql(candidate.ddl)[0].stmt
    assert isinstance(statement, ast.IndexStmt)
    assert statement.relation.schemaname == t.schema_name and statement.relation.relname == t.name
    assert statement.indexParams[0].name == 'user";id'
    assert len(candidate.index_name.encode()) <= 63
    assert candidate == definition(t, candidate.keys)
    assert (
        definition(t.model_copy(update={"oid": 999}), candidate.keys).signature
        != candidate.signature
    )


@pytest.mark.parametrize(
    "body",
    [
        {"plan_ids": []},
        {"plan_ids": [str(uuid.UUID(int=1))] * 2},
        {"plan_ids": [str(uuid.UUID(int=1))], "max_columns": 4},
        {"plan_ids": [str(uuid.UUID(int=1))], "max_candidates": 33},
    ],
)
def test_request_bounds(body):
    with pytest.raises(ValidationError):
        CandidateRequest.model_validate(body)


def test_pool_and_attempt_limits_are_real_bounds():
    tables = []
    sources = []
    for number in range(1, 101):
        t = table(
            oid=number, name=f"orders_{number}", names=("a", "b", "c", "d", "e", "f", "g", "h")
        )
        tables.append(t)
        sources.append(
            source(
                t,
                [
                    *[predicate(t, name) for name in ("a", "b", "c", "d")],
                    *[predicate(t, name, ">=") for name in ("e", "f", "g", "h")],
                ],
                number=number,
            )
        )
    result = generate(sources, tables)
    assert result.search_truncated and result.unique_considered <= 512 and result.attempts <= 4096
    assert len(result.proposed) <= 32


def test_hard_attempt_limit_includes_repeated_aliases(monkeypatch):
    constructed = 0
    actual_definition = generator_module.definition

    def tracked_definition(*args):
        nonlocal constructed
        constructed += 1
        return actual_definition(*args)

    monkeypatch.setattr(generator_module, "definition", tracked_definition)
    t = table(names=("a", "b", "c", "d", "e", "f", "g", "h"))
    template = source(t)
    aliases = [f"t{number}" for number in range(16)]
    relations = [
        template.analysis.relations[0].model_copy(update={"alias": alias}) for alias in aliases
    ]
    predicates = []
    for alias in aliases:
        for name in ("a", "b", "c", "d", "e", "f", "g", "h"):
            model = predicate(t, name, "=" if name in ("a", "b", "c", "d") else ">=")
            predicates.append(
                model.model_copy(
                    update={"column": model.column.model_copy(update={"alias": alias})}
                )
            )
    analysis = template.analysis.model_copy(
        update={"relations": relations, "predicates": predicates}
    )
    sources = [CandidateSource(uuid.UUID(int=number), analysis) for number in range(1, 101)]
    result = generate(sources, [t])
    assert result.search_truncated and result.attempts == 4096
    assert constructed == 4096


def test_single_key_limit_does_not_claim_a_composite_pattern():
    t = table()
    result = generate(
        [source(t, [predicate(t, "user_id"), predicate(t, "region")])], [t], max_columns=1
    )
    assert all(len(row.definition.keys) == 1 for row in result.proposed)
    assert all(
        evidence.reason != "composite_equality"
        for row in result.proposed
        for evidence in row.evidence
    )
