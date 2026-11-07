from pglast import ast
from pglast.stream import RawStream

from indexpilot.errors import DomainError
from indexpilot.sql.validation import parameter_positions, validate_sql
from indexpilot.workloads.models import Parameter


def bind_parameters(
    root: ast.SelectStmt, values: dict[int, Parameter], *, allowed_schemas=("public",)
) -> tuple[str | None, list[int]]:
    positions = parameter_positions(root)
    if values.keys() - positions:
        raise DomainError(
            "unexpected_parameter", "Values were supplied for unused parameter positions."
        )
    missing = sorted(positions - values.keys())
    if missing:
        return None, missing
    clone = ast.SelectStmt(root())

    def replace(value):
        if isinstance(value, ast.ParamRef):
            parameter = values[value.number]
            constant = (
                ast.A_Const(isnull=True)
                if parameter.value is None
                else ast.A_Const(
                    val=ast.String(sval=str(parameter.value)),
                    isnull=False,
                )
            )
            return ast.TypeCast(
                arg=constant,
                typeName=ast.TypeName(
                    names=(
                        ast.String(sval="pg_catalog"),
                        ast.String(sval=parameter.type),
                    )
                ),
            )
        if isinstance(value, ast.Node):
            for field in value:
                setattr(value, field, replace(getattr(value, field)))
        elif isinstance(value, tuple):
            return tuple(replace(child) for child in value)
        return value

    rendered = RawStream()(replace(clone))
    validate_sql(rendered, allowed_schemas=allowed_schemas)
    return rendered, []
