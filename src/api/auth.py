# src/api/auth.py
"""Clerk JWT authentication and user extraction."""

from functools import lru_cache
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient, PyJWKClientError

from api.settings import Settings, get_settings


class ClerkAuthenticator:
    """Validates Clerk JWT tokens and extracts user information.

    :ivar settings: Application settings containing Clerk configuration.
    :ivar jwks_client: PyJWT JWKS client for fetching public keys.
    """

    def __init__(self, settings: Settings) -> None:
        """Initialize the authenticator with application settings.

        :param settings: Application settings with Clerk configuration.
        """
        self.settings = settings
        self._jwks_client: PyJWKClient | None = None

    @property
    def jwks_client(self) -> PyJWKClient:
        """Get or create the JWKS client.

        :returns: PyJWT JWKS client for the Clerk Frontend API.
        """
        if self._jwks_client is None:
            jwks_url = f"{self.settings.clerk_frontend_api_url}/.well-known/jwks.json"
            self._jwks_client = PyJWKClient(jwks_url, cache_keys=True)
        return self._jwks_client

    def validate_token(self, token: str) -> dict:
        """Validate a JWT token and return the decoded payload.

        :param token: The JWT token string.
        :returns: Decoded token payload.
        :raises HTTPException: If token is invalid or expired.
        """
        try:
            signing_key = self.jwks_client.get_signing_key_from_jwt(token)

            decode_options = {
                "verify_signature": True,
                "verify_exp": True,
                "verify_iat": True,
                "require": ["sub", "exp", "iat"],
            }

            # Only validate audience if configured
            decode_kwargs: dict = {
                "algorithms": ["RS256"],
                "issuer": self.settings.clerk_frontend_api_url,
                "options": decode_options,
            }
            if self.settings.clerk_jwt_audience:
                decode_kwargs["audience"] = self.settings.clerk_jwt_audience

            payload = jwt.decode(
                token,
                signing_key.key,
                **decode_kwargs,
            )

            return payload

        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
            )
        except jwt.InvalidTokenError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {str(e)}",
            )
        except PyJWKClientError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to verify token - authentication service unavailable",
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Token verification failed: {str(e)}",
            )

    def get_user_id(self, token: str) -> str:
        """Extract user ID from a validated JWT token.

        :param token: The JWT token string.
        :returns: The user ID (sub claim) from the token.
        """
        payload = self.validate_token(token)
        return payload["sub"]


@lru_cache
def get_authenticator() -> ClerkAuthenticator:
    """Get cached ClerkAuthenticator instance.

    :returns: Singleton ClerkAuthenticator instance.
    """
    return ClerkAuthenticator(get_settings())


security = HTTPBearer()


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    authenticator: Annotated[ClerkAuthenticator, Depends(get_authenticator)],
) -> str:
    """FastAPI dependency to get the current authenticated user ID.

    :param credentials: HTTP Bearer token credentials.
    :param authenticator: Clerk authenticator instance.
    :returns: The authenticated user ID.
    :raises HTTPException: If authentication fails.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    return authenticator.get_user_id(credentials.credentials)


# Type alias for dependency injection
CurrentUser = Annotated[str, Depends(get_current_user)]
