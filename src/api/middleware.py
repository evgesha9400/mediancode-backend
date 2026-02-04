# src/api/middleware.py
"""Custom middleware for security and request handling."""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses.

    Implements OWASP recommended security headers to protect against
    common web vulnerabilities like clickjacking, MIME sniffing, and XSS.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request and add security headers to response.

        :param request: The incoming request.
        :param call_next: The next middleware/handler in chain.
        :returns: Response with security headers added.
        """
        response = await call_next(request)

        # Prevent clickjacking attacks
        response.headers["X-Frame-Options"] = "DENY"

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Enable XSS filter in older browsers
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Control referrer information
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Enforce HTTPS (Railway/load balancer handles TLS termination)
        # max-age=31536000 = 1 year, includeSubDomains for all subdomains
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )

        # Restrict browser features/APIs
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
            "magnetometer=(), microphone=(), payment=(), usb=()"
        )

        # Content Security Policy for API responses
        # Since this is an API (not serving HTML), we use a restrictive policy
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; frame-ancestors 'none'"
        )

        return response
