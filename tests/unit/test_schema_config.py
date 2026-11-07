import pytest
from indexpilot.config import Settings
from pydantic import ValidationError


@pytest.mark.parametrize(
    "schemas",
    [
        (),
        ("public", "public"),
        ("pg_catalog",),
        ("pg_temp",),
        ("information_schema",),
        ("bad\x00schema",),
        ("x" * 64,),
    ],
)
def test_analysis_schema_allowlist_rejects_unsafe_configuration(schemas):
    with pytest.raises(ValidationError):
        Settings(analysis_schemas=schemas)


def test_quoted_schema_names_are_configurable():
    assert (
        Settings(analysis_schemas=("public", "Mixed Case Schema")).analysis_schemas[1]
        == "Mixed Case Schema"
    )
