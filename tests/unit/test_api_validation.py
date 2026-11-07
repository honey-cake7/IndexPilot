import pytest
from fastapi.testclient import TestClient
from indexpilot.config import Settings
from indexpilot.main import create_app
from pydantic import ValidationError


def test_liveness_does_not_need_credentials(tmp_path):
    with TestClient(create_app(Settings(secret_dir=tmp_path))) as client:
        assert client.get("/health/live").json() == {"status": "ok"}
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "credential_file_unavailable"


def test_invalid_connection_input_is_not_echoed(tmp_path, caplog):
    with TestClient(create_app(Settings(secret_dir=tmp_path))) as client:
        response = client.post(
            "/api/v1/connections/validate",
            json={
                "target": "arbitrary",
                "password": "must-never-appear",
            },
        )
        assert response.status_code == 422
        assert "must-never-appear" not in response.text + caplog.text
        assert response.json()["error"]["request_id"] == response.headers["X-Request-ID"]
        assert client.get("/missing").status_code == 404
        assert client.get("/openapi.json").json()["info"]["title"] == "IndexPilot"


@pytest.mark.parametrize("port", [0, -1, 65536])
def test_port_validation(port):
    with pytest.raises(ValidationError):
        Settings(db_port=port)
