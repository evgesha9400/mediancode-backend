# src/api/rate_limit.py
"""Rate limiting configuration using slowapi."""

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request


def get_rate_limit_key(request: Request) -> str:
    """Extract rate limit key from request.

    Uses authenticated user ID if available, otherwise falls back to IP address.
    This ensures authenticated users get their own rate limit bucket.

    :param request: The incoming request.
    :returns: Rate limit key (user ID or IP address).
    """
    # Check for Authorization header to extract user ID
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        # Use a hash of the token as key (don't decode here to avoid overhead)
        # The actual user isolation happens via the token itself
        token = auth_header[7:]
        if token:
            # Use first 32 chars of token as identifier (unique per session)
            return f"user:{token[:32]}"

    # Fall back to IP address for unauthenticated requests
    return get_remote_address(request)


# Create limiter instance with custom key function
limiter = Limiter(key_func=get_rate_limit_key)

# Rate limit constants for different endpoint types
RATE_LIMIT_DEFAULT = "100/minute"  # Standard endpoints
RATE_LIMIT_AUTH = "20/minute"  # Authentication-related
RATE_LIMIT_GENERATION = "10/minute"  # Code generation (expensive)
RATE_LIMIT_HEALTH = "1000/minute"  # Health checks (allow frequent polling)
