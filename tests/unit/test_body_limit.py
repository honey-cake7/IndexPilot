import asyncio

from fastapi.testclient import TestClient
from indexpilot.api.body_limit import BodyLimitMiddleware
from indexpilot.main import create_app


def test_body_limit_rejects_actual_bytes_without_content_length():
    async def run():
        called = False
        output = []
        messages = iter(
            [
                {"type": "http.request", "body": b"123", "more_body": True},
                {"type": "http.request", "body": b"456", "more_body": False},
            ]
        )

        async def receive():
            return next(messages)

        async def send(message):
            output.append(message)

        async def downstream(scope, receive, send):
            nonlocal called
            called = True

        await BodyLimitMiddleware(downstream, max_bytes=5)(
            {"type": "http", "state": {"request_id": "test"}},
            receive,
            send,
        )
        assert not called
        assert output[0]["status"] == 413

    asyncio.run(run())


def test_large_api_body_is_rejected_before_database_access(tmp_path):
    from indexpilot.config import Settings

    with TestClient(create_app(Settings(secret_dir=tmp_path))) as client:
        response = client.post("/api/v1/workloads/manual", content=b"x" * 1_048_577)
        assert response.status_code == 413
        assert response.json()["error"]["request_id"] == response.headers["X-Request-ID"]
