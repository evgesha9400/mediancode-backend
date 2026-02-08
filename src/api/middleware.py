# src/api/middleware.py
"""Custom middleware for security and request handling."""

from starlette.types import ASGIApp, Message, Receive, Scope, Send


class SecurityHeadersMiddleware:
    """Add security headers to all responses.

    Implements OWASP recommended security headers to protect against
    common web vulnerabilities like clickjacking, MIME sniffing, and XSS.

    Uses pure ASGI implementation instead of BaseHTTPMiddleware to avoid
    known issues where BaseHTTPMiddleware can cause 500 responses to
    bypass outer middleware (including CORSMiddleware).
    """

    SECURITY_HEADERS: list[tuple[bytes, bytes]] = [
        (b"x-frame-options", b"DENY"),
        (b"x-content-type-options", b"nosniff"),
        (b"x-xss-protection", b"1; mode=block"),
        (b"referrer-policy", b"strict-origin-when-cross-origin"),
        (b"strict-transport-security", b"max-age=31536000; includeSubDomains"),
        (
            b"permissions-policy",
            b"accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
            b"magnetometer=(), microphone=(), payment=(), usb=()",
        ),
        (
            b"content-security-policy",
            b"default-src 'none'; frame-ancestors 'none'",
        ),
    ]

    def __init__(self, app: ASGIApp) -> None:
        """Initialize with the inner ASGI application.

        :param app: The next ASGI application in the middleware chain.
        """
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Process ASGI requests and inject security headers into responses.

        :param scope: ASGI connection scope.
        :param receive: ASGI receive callable.
        :param send: ASGI send callable.
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_security_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend(self.SECURITY_HEADERS)
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_security_headers)
