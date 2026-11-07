from dataclasses import dataclass

from pglast import ast, enums
from pglast.stream import RawStream
from psycopg import Connection

from indexpilot.errors import DomainError
from indexpilot.sql.models import (
    ColumnUsage,
    OrderFeature,
    PredicateFeature,
    RelationBinding,
    ResolvedColumn,
    SQLAnalysis,
)
from indexpilot.sql.safety import require_safe_casts, require_safe_table
from indexpilot.sql.validation import nodes, validate_sql
from indexpilot.workloads.manual import prepare_query
from indexpilot.workloads.models import QueryInput


@dataclass
class Binding:
    alias: str
    explicit_alias: bool
    table: object


class Resolver:
    def __init__(self, connection: Connection, *, allowed_schemas=("public",)):
        self.connection = connection
        self.allowed_schemas = allowed_schemas
        self.bindings = {}
        self.tables = {}
        self.usage = {}
        self.predicates = []
        self.warnings = []

    def bind_from(self, node):
        if isinstance(node, ast.JoinExpr):
            if node.alias:
                raise DomainError(
                    "unsupported_alias", "Aliases on whole JOIN expressions are unsupported."
                )
            self.bind_from(node.larg)
            self.bind_from(node.rarg)
            return
        if not isinstance(node, ast.RangeVar) or (node.alias and node.alias.colnames):
            raise DomainError(
                "unsupported_alias",
                "Only ordinary table aliases without column renaming are supported.",
            )
        schema = node.schemaname or "public"
        alias = node.alias.aliasname if node.alias else node.relname
        if alias in self.bindings:
            raise DomainError(
                "ambiguous_relation", "A table alias is repeated; assign distinct aliases."
            )
        if len(self.bindings) >= 16:
            raise DomainError(
                "query_too_large", "At most 16 table references are supported per query."
            )
        key = (schema, node.relname)
        if key not in self.tables:
            self.tables[key] = require_safe_table(
                self.connection, schema, node.relname, allowed_schemas=self.allowed_schemas
            )
        self.bindings[alias] = Binding(alias, node.alias is not None, self.tables[key])
        node.schemaname = schema
        node.inh = False

    def column(self, node: ast.ColumnRef, context: str):
        fields = node.fields
        star = isinstance(fields[-1], ast.A_Star)
        parts = [part.sval for part in fields if isinstance(part, ast.String)]
        qualifier = parts if star else parts[:-1]
        name = None if star else parts[-1]
        if len(qualifier) == 0:
            candidates = list(self.bindings.values())
        elif len(qualifier) == 1:
            candidates = [self.bindings[qualifier[0]]] if qualifier[0] in self.bindings else []
        elif len(qualifier) == 2:
            candidates = [
                binding
                for binding in self.bindings.values()
                if not binding.explicit_alias
                and (binding.table.schema_name, binding.table.name) == tuple(qualifier)
            ]
        else:
            raise DomainError(
                "unsupported_column_reference", "Use column, alias.column or schema.table.column."
            )
        if star:
            if context != "projection" or (qualifier and len(candidates) != 1) or not candidates:
                raise DomainError(
                    "unsupported_star",
                    "Whole-row expressions are supported only as projection stars.",
                )
            for binding in candidates:
                for column in binding.table.columns:
                    self.record(binding, column, context)
            if qualifier:
                node.fields = (ast.String(sval=candidates[0].alias), ast.A_Star())
            return None
        matches = [
            (binding, column)
            for binding in candidates
            for column in binding.table.columns
            if column.name == name
        ]
        if len(matches) != 1:
            code = "ambiguous_column" if len(matches) > 1 else "column_not_found"
            raise DomainError(
                code, "Column reference is ambiguous or absent from the inspected relations."
            )
        binding, column = matches[0]
        node.fields = (ast.String(sval=binding.alias), ast.String(sval=column.name))
        return self.record(binding, column, context)

    def record(self, binding, column, context):
        resolved = ResolvedColumn(
            relation_oid=binding.table.oid,
            schema_name=binding.table.schema_name,
            table=binding.table.name,
            alias=binding.alias,
            name=column.name,
            type_oid=column.type_oid,
        )
        key = (binding.alias, column.name)
        if key not in self.usage:
            self.usage[key] = ColumnUsage(column=resolved, contexts=[])
        if context not in self.usage[key].contexts:
            self.usage[key].contexts.append(context)
        return resolved

    def expression(self, value, context):
        if isinstance(value, ast.ColumnRef):
            self.column(value, context)
            return
        if isinstance(value, ast.Node):
            for field in value:
                self.expression(getattr(value, field), context)
        elif isinstance(value, tuple):
            for child in value:
                self.expression(child, context)

    def predicate_features(self, value, context, conjunction=True, join_type=None):
        if isinstance(value, ast.BoolExpr):
            safe = conjunction and value.boolop == enums.BoolExprType.AND_EXPR
            for child in value.args:
                self.predicate_features(child, context, safe, join_type)
            return
        if not isinstance(value, ast.A_Expr):
            return
        operator = value.name[-1].sval
        if operator not in {"=", "<>", "!=", "<", "<=", ">", ">="}:
            return
        left, right = value.lexpr, value.rexpr
        if not isinstance(left, ast.ColumnRef) and isinstance(right, ast.ColumnRef):
            left, right = right, left
            operator = {"<": ">", "<=": ">=", ">": "<", ">=": "<="}.get(operator, operator)
        if not isinstance(left, ast.ColumnRef):
            self.warnings.append("A computed predicate is not a direct-column indexing pattern.")
            return
        column = self.column(left, context)
        other = self.column(right, context) if isinstance(right, ast.ColumnRef) else None
        literal = (
            not any(isinstance(node, (ast.ColumnRef, ast.FuncCall)) for node in nodes(right))
            if right
            else False
        )
        other_kind = "column" if other else "literal" if literal else "expression"
        kind = (
            "join"
            if other and other.alias != column.alias
            else "column_comparison"
            if other
            else "equality"
            if operator == "="
            else "range"
            if operator in {"<", "<=", ">", ">="}
            else "other"
        )
        self.predicates.append(
            PredicateFeature(
                column=column,
                operator=operator,
                other_column=other,
                other_kind=other_kind,
                kind=kind,
                context=context,
                conjunction_only=conjunction,
                join_type=join_type,
            )
        )

    def joins(self, node):
        if isinstance(node, ast.JoinExpr):
            self.joins(node.larg)
            self.joins(node.rarg)
            self.expression(node.quals, "join")
            self.predicate_features(node.quals, "join", join_type=node.jointype.name)

    def output_expression(self, value, root, *, group=False):
        if isinstance(value, ast.A_Const) and isinstance(value.val, ast.Integer):
            position = value.val.ival
            if not 1 <= position <= len(root.targetList) or any(
                isinstance(node, ast.A_Star) for node in nodes(root.targetList[position - 1].val)
            ):
                raise DomainError(
                    "unsupported_order_position",
                    "Sort/group positions require explicit non-star outputs.",
                )
            return type(root.targetList[position - 1].val)(root.targetList[position - 1].val())
        if (
            isinstance(value, ast.ColumnRef)
            and len(value.fields) == 1
            and isinstance(value.fields[0], ast.String)
        ):
            name = value.fields[0].sval
            input_exists = any(
                column.name == name
                for binding in self.bindings.values()
                for column in binding.table.columns
            )
            outputs = [target.val for target in root.targetList if target.name == name]
            if outputs and not (group and input_exists):
                if len(outputs) != 1:
                    raise DomainError("ambiguous_column", "Output alias is ambiguous.")
                return type(outputs[0])(outputs[0]())
        return value

    def resolve(self, root):
        for source in root.fromClause or ():
            self.bind_from(source)
        for target in root.targetList or ():
            self.expression(target.val, "projection")
        for source in root.fromClause or ():
            self.joins(source)
        self.expression(root.whereClause, "filter")
        self.predicate_features(root.whereClause, "filter")
        self.expression(root.havingClause, "having")
        groups = tuple(
            self.output_expression(value, root, group=True) for value in root.groupClause or ()
        )
        root.groupClause = groups or None
        self.expression(groups, "group")
        self.expression(root.distinctClause, "distinct")
        orders = []
        for order in root.sortClause or ():
            order.node = self.output_expression(order.node, root)
            self.expression(order.node, "order")
            column = (
                self.column(order.node, "order") if isinstance(order.node, ast.ColumnRef) else None
            )
            descending = order.sortby_dir == enums.SortByDir.SORTBY_DESC
            nulls_first = order.sortby_nulls == enums.SortByNulls.SORTBY_NULLS_FIRST or (
                order.sortby_nulls == enums.SortByNulls.SORTBY_NULLS_DEFAULT and descending
            )
            orders.append(
                OrderFeature(
                    column=column,
                    expression=RawStream()(order.node),
                    direction="desc" if descending else "asc",
                    nulls_first=nulls_first,
                )
            )
        for value in (root.limitCount, root.limitOffset):
            if value and any(
                isinstance(node, (ast.ColumnRef, ast.FuncCall)) for node in nodes(value)
            ):
                raise DomainError(
                    "unsupported_limit", "LIMIT/OFFSET must be constant built-in expressions."
                )
        for node in nodes(root):
            if isinstance(node, ast.A_Expr):
                node.name = (ast.String(sval="pg_catalog"), node.name[-1])
            elif isinstance(node, ast.FuncCall):
                node.funcname = (ast.String(sval="pg_catalog"), node.funcname[-1])
            elif isinstance(node, ast.TypeName):
                node.names = (ast.String(sval="pg_catalog"), node.names[-1])
        return SQLAnalysis(
            canonical_sql=RawStream()(root),
            relations=[
                RelationBinding(
                    alias=binding.alias,
                    schema_name=binding.table.schema_name,
                    table=binding.table.name,
                    relation_oid=binding.table.oid,
                )
                for binding in self.bindings.values()
            ],
            columns=list(self.usage.values()),
            predicates=self.predicates,
            order_by=orders,
            tables=list(self.tables.values()),
            warnings=list(dict.fromkeys(self.warnings)),
        )


def resolve_query(
    connection: Connection, query: QueryInput, *, allowed_schemas=("public",)
) -> SQLAnalysis:
    prepared = prepare_query(query, allowed_schemas=allowed_schemas)
    if prepared.missing_parameters:
        raise DomainError(
            "missing_parameters", "Provide all representative parameters before planning."
        )
    root = validate_sql(prepared.representative, allowed_schemas=allowed_schemas)
    connection.execute("SET LOCAL search_path = pg_catalog")
    require_safe_casts(connection)
    return Resolver(connection, allowed_schemas=allowed_schemas).resolve(root)
