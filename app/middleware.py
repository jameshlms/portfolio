from fastapi.middleware import Middleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import settings


class VaryHtmxMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_vary(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.append("Vary", "HX-Request")
            await send(message)

        await self.app(scope, receive, send_with_vary)


# noinspection PyTypeChecker
middleware: list[Middleware] = [
    Middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts),
    Middleware(VaryHtmxMiddleware),
    Middleware(GZipMiddleware),
]
"""List of middlewares, ordered from first to receive requests (index 0) to last to receive responses (index N)"""
