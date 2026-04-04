# tests/test_auth.py
"""Unit tests for Clerk JWT authentication."""

from types import SimpleNamespace

import jwt

from api.auth import ClerkAuthenticator
from api.settings import Settings


class TestClerkAuthenticator:
    """Exercise focused JWT validation behavior."""

    def test_validate_token_allows_small_clock_skew(self, monkeypatch) -> None:
        """Pass JWT leeway to PyJWT while keeping iat validation enabled."""
        authenticator = ClerkAuthenticator(
            Settings(clerk_frontend_api_url="https://clerk.example.com")
        )
        authenticator._jwks_client = SimpleNamespace(
            get_signing_key_from_jwt=lambda token: SimpleNamespace(key="signing-key")
        )

        captured_kwargs: dict = {}

        def fake_decode(token, key, **kwargs):
            captured_kwargs.update(kwargs)
            return {"sub": "user_123", "exp": 9999999999, "iat": 9999999990}

        monkeypatch.setattr(jwt, "decode", fake_decode)

        payload = authenticator.validate_token("jwt-token")

        assert payload["sub"] == "user_123"
        assert captured_kwargs["options"]["verify_iat"] is True
        assert captured_kwargs["leeway"] == 5
