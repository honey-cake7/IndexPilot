"""Conservative syntactic admission policy, not permission to execute a statement."""

from collections.abc import Iterator

from pglast import ast, enums, parse_sql, parser
from pglast.stream import RawStream

from indexpilot.errors import DomainError

MAX_SQL_BYTES = 65_536
ALLOWED_NODES = {
    "SelectStmt",
    "ResTarget",
    "ColumnRef",
    "A_Star",
    "A_Const",
    "Integer",
    "Float",
    "String",
    "Boolean",
    "RangeVar",
    "Alias",
    "JoinExpr",
    "A_Expr",
    "BoolExpr",
    "NullTest",
    "BooleanTest",
    "SortBy",
    "TypeCast",
    "TypeName",
    "FuncCall",
    "ParamRef",
}
BUILTIN_TYPES = {
    "int2",
    "int4",
    "int8",
    "numeric",
    "float4",
    "float8",
    "text",
    "varchar",
    "date",
    "timestamp",
    "timestamptz",
    "bool",
}
PURE_AGGREGATES = {"count", "sum", "avg", "min", "max"}


def sql_size(sql: str) -> int:
    if "\x00" in sql:
        raise DomainError("invalid_sql", "SQL must not contain NUL characters.")
    try:
        return len(sql.encode("utf-8"))
    except UnicodeEncodeError:
        raise DomainError("invalid_encoding", "SQL must contain valid UTF-8 text.") from None


def nodes(root: ast.Node) -> Iterator[ast.Node]:
    stack = [(root, 0)]
    count = 0
    while stack:
        value, depth = stack.pop()
        if depth > 64 or count > 4000:
            raise DomainError("sql_too_complex", "SQL exceeds supported nesting or node limits.")
        if isinstance(value, ast.Node):
            count += 1
            yield value
            stack.extend((getattr(value, field), depth + 1) for field in reversed(tuple(value)))
        elif isinstance(value, tuple | list):
            stack.extend((child, depth) for child in reversed(value))


def validate_sql(sql: str) -> ast.SelectStmt:
    if not sql.strip() or sql_size(sql) > MAX_SQL_BYTES:
        raise DomainError("invalid_sql_size", "Provide nonempty SQL of at most 65536 UTF-8 bytes.")
    try:
        statements = parse_sql(sql)
    except (parser.ParseError, RecursionError, ValueError):
        raise DomainError("invalid_sql", "SQL is not valid PostgreSQL syntax.") from None
    if len(statements) != 1 or not isinstance(statements[0].stmt, ast.SelectStmt):
        raise DomainError(
            "unsupported_sql", "Each query must contain exactly one supported SELECT."
        )
    root = statements[0].stmt
    for node in nodes(root):
        if type(node).__name__ not in ALLOWED_NODES:
            raise DomainError(
                "unsupported_sql", f"Unsupported SQL construct: {type(node).__name__}."
            )
        if isinstance(node, ast.SelectStmt):
            if (
                node.withClause
                or node.intoClause
                or node.lockingClause
                or node.valuesLists
                or node.windowClause
                or node.op != enums.SetOperation.SETOP_NONE
            ):
                raise DomainError(
                    "unsupported_sql",
                    "CTEs, INTO, locks, windows and set operations are unsupported.",
                )
        if isinstance(node, ast.RangeVar):
            if node.catalogname or node.schemaname not in (None, "public"):
                raise DomainError(
                    "unsupported_sql", "Only public-schema relations are admitted initially."
                )
        if isinstance(node, ast.JoinExpr) and (node.isNatural or node.usingClause):
            raise DomainError(
                "unsupported_sql", "Use explicit JOIN ON conditions instead of NATURAL/USING."
            )
        if isinstance(node, ast.A_Expr):
            names = tuple(part.sval for part in node.name or ())
            if (
                node.kind != enums.A_Expr_Kind.AEXPR_OP
                or len(names) != 1
                or names[0]
                not in {
                    "=",
                    "<>",
                    "!=",
                    "<",
                    "<=",
                    ">",
                    ">=",
                    "+",
                    "-",
                    "*",
                    "/",
                    "%",
                }
            ):
                raise DomainError(
                    "unsupported_sql", "Only supported unqualified built-in operators are admitted."
                )
        if isinstance(node, ast.TypeName):
            names = tuple(part.sval for part in node.names or ())
            if (
                not names
                or names[-1] not in BUILTIN_TYPES
                or len(names) > 2
                or (len(names) == 2 and names[0] != "pg_catalog")
                or node.arrayBounds
                or node.setof
                or node.pct_type
                or node.typmods
            ):
                raise DomainError(
                    "unsupported_sql", "Only supported scalar built-in casts are admitted."
                )
        if isinstance(node, ast.FuncCall):
            names = tuple(part.sval for part in node.funcname)
            if (
                names[-1] not in PURE_AGGREGATES
                or len(names) > 2
                or (len(names) == 2 and names[0] != "pg_catalog")
                or node.over
                or node.agg_filter
                or node.agg_order
                or node.agg_within_group
            ):
                raise DomainError(
                    "unsafe_function", "Only simple count/sum/avg/min/max aggregates are admitted."
                )
        if isinstance(node, ast.ParamRef) and not 1 <= node.number <= 100:
            raise DomainError(
                "invalid_parameter", "Parameter positions must be between $1 and $100."
            )
    return root


def parameter_positions(root: ast.SelectStmt) -> set[int]:
    return {node.number for node in nodes(root) if isinstance(node, ast.ParamRef)}


def normalized_sql(root: ast.SelectStmt) -> str:
    clone = ast.SelectStmt(root())
    counter = max(parameter_positions(root), default=0)

    def replace(value):
        nonlocal counter
        if isinstance(value, ast.A_Const):
            counter += 1
            return ast.ParamRef(number=counter)
        if isinstance(value, ast.Node):
            for field in value:
                setattr(value, field, replace(getattr(value, field)))
        elif isinstance(value, tuple):
            return tuple(replace(child) for child in value)
        return value

    return RawStream()(replace(clone))


def split_workload(sql: str) -> tuple[str, ...]:
    if sql_size(sql) > MAX_SQL_BYTES:
        raise DomainError(
            "invalid_sql_size", "Workload files may contain at most 65536 UTF-8 bytes."
        )
    try:
        statements = parser.split(sql, with_parser=True)
    except (parser.ParseError, RecursionError, ValueError):
        raise DomainError(
            "invalid_sql", "Workload file contains invalid PostgreSQL syntax."
        ) from None
    if not 1 <= len(statements) <= 100:
        raise DomainError("invalid_workload_size", "Provide between 1 and 100 statements.")
    return statements
