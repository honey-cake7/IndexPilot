from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient
from indexpilot.config import Settings
from indexpilot.db.capabilities import inspect_capabilities
from indexpilot.db.connections import target_connection
from indexpilot.local import connect_local
from indexpilot.main import create_app
from indexpilot.metadata.models import MonitoredDatabase
from indexpilot.metadata.session import metadata_engine
from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.integration


def test_live_capabilities_and_readiness():
    with TestClient(create_app()) as client:
        assert client.get("/health/ready").status_code == 200
        response = client.post("/api/v1/connections/validate", json={"target": "demo"})
        assert response.status_code == 200
        data = response.json()
        assert data["supported_version"] and data["read_only"]
        assert data["hypopg"]["accessible"] and data["pg_stat_statements"]["accessible"]
        assert data["can_read_orders"]
        assert not data["superuser"] and not data["can_create_schema_objects"]
        assert "password" not in response.text.lower()


def test_missing_extension_is_reported_not_fabricated():
    with connect_local("meta") as connection:
        data = inspect_capabilities(connection)
        assert not data.hypopg.installed
        assert not data.hypopg.accessible
        assert data.warnings


def test_invalid_credentials_and_unreachable_database(tmp_path, caplog):
    (tmp_path / "analyzer_password").write_text("wrong-password")
    with TestClient(create_app(Settings(secret_dir=tmp_path))) as client:
        response = client.get("/api/v1/connections/demo")
        assert response.status_code == 503
        assert response.json()["error"]["code"] in ("authentication_failed", "connection_failed")
        assert "wrong-password" not in response.text + caplog.text
    with TestClient(create_app(Settings(db_port=1, connect_timeout=1))) as client:
        assert client.get("/api/v1/connections/demo").status_code == 503


def test_statement_timeout_and_permission_boundaries():
    with target_connection(Settings(statement_timeout_ms=100)) as connection:
        with pytest.raises(psycopg.errors.QueryCanceled):
            connection.execute("SELECT pg_sleep(1)")
        connection.rollback()
    with target_connection(Settings()) as connection:
        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
            connection.execute("CREATE TABLE public.cannot_create(id integer)")
        connection.rollback()


def test_metadata_constraints_and_safe_engine_url():
    engine = metadata_engine(Settings())
    try:
        assert Path(".secrets/meta_password").read_text().strip() not in str(engine.url)
        with engine.begin() as connection:
            with pytest.raises(IntegrityError), connection.begin_nested():
                connection.execute(
                    insert(MonitoredDatabase).values(
                        target_key="invalid-port",
                        host="localhost",
                        port=0,
                        database_name="indexpilot_demo",
                        role_name="indexpilot_analyzer",
                        credential_reference="analyzer_password",
                    )
                )
    finally:
        engine.dispose()
