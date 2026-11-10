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


@pytest.mark.parametrize("name", ["", "../indexpilot", "--help", "UPPER", "x; echo", "x" * 64])
def test_compose_project_is_trusted_bounded_configuration(name):
    with pytest.raises(ValidationError):
        Settings(compose_project=name)


def test_pgbench_uses_configured_project_as_one_argument():
    import uuid

    from indexpilot.benchmarks.pgbench import ContainerClient

    identifier = uuid.uuid4()
    client = ContainerClient(
        identifier, lambda: None, settings=Settings(compose_project="indexpilot-ci")
    )
    position = client.prefix.index("--project-name")
    assert client.prefix[position + 1] == "indexpilot-ci"
    assert client.folder == "/tmp/indexpilot_bench_" + identifier.hex
