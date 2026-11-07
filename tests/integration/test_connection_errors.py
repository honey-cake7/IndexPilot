import traceback
from pathlib import Path

import pytest
from indexpilot.local import LocalConnectionError, connect_local

pytestmark = pytest.mark.integration


def test_connection_failure_hides_driver_credentials(monkeypatch):
    monkeypatch.setenv("INDEXPILOT_DB_PORT", "1")
    with pytest.raises(LocalConnectionError) as captured:
        connect_local("analyzer")
    rendered = "".join(traceback.format_exception(captured.value))
    secret = Path(".secrets/analyzer_password").read_text().strip()
    assert secret not in rendered
    assert "psycopg.connect(" not in rendered
    assert "verify service" in str(captured.value)
