from starlette.responses import JSONResponse


class BodyLimitMiddleware:
    """Bound actual bytes before JSON/multipart parsing, including chunked uploads."""

    def __init__(self, app, max_bytes=1_048_576):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        messages, size = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            size += len(message.get("body", b""))
            if size > self.max_bytes:
                response = JSONResponse(
                    status_code=413,
                    content={
                        "error": {
                            "code": "request_too_large",
                            "message": "Request body exceeds 1 MiB.",
                            "request_id": scope.get("state", {}).get("request_id"),
                        }
                    },
                )
                return await response(scope, receive, send)
            messages.append(message)
            if not message.get("more_body", False):
                break
        iterator = iter(messages)

        async def replay():
            return next(iterator, None) or await receive()

        return await self.app(scope, replay, send)
