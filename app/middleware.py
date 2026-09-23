import logging
import time

logger = logging.getLogger("app.access")

INTERNAL_SERVER_ERROR = 500


class AccessLogMiddleware:
    """Чиста ASGI-мідлвара: метод, шлях, статус і тривалість кожного запиту."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        started_at = time.perf_counter()
        status_code = INTERNAL_SERVER_ERROR

        async def send_with_status_capture(message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_with_status_capture)
        finally:
            elapsed_ms = (time.perf_counter() - started_at) * 1000
            query = scope.get("query_string", b"").decode()
            path = scope["path"] + (f"?{query}" if query else "")
            logger.info("%s %s %s %.2fms", scope["method"], path, status_code, elapsed_ms)
