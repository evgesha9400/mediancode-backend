"""Clerk JWT minting for live API seeding.

Uses CLERK_SECRET_KEY to:
1. Find user by email
2. Get their active session
3. Mint a JWT from that session
"""

from __future__ import annotations

import httpx

CLERK_API_BASE = "https://api.clerk.com/v1"


class ClerkAuthError(Exception):
    """Raised when Clerk JWT minting fails."""


async def mint_clerk_jwt(email: str, clerk_secret_key: str) -> str:
    """Mint a Clerk session JWT for the given user email.

    Args:
        email: The user's email address (must exist in Clerk).
        clerk_secret_key: The CLERK_SECRET_KEY (sk_live_... or sk_test_...).

    Returns:
        A JWT string suitable for Authorization: Bearer headers.

    Raises:
        ClerkAuthError: If the user is not found, has no active sessions,
            or token minting fails.
    """
    headers = {"Authorization": f"Bearer {clerk_secret_key}"}

    async with httpx.AsyncClient(timeout=10.0) as client:
        # 1. Find user by email
        resp = await client.get(
            f"{CLERK_API_BASE}/users",
            params={"email_address": [email]},
            headers=headers,
        )
        if resp.status_code != 200:
            raise ClerkAuthError(
                f"Failed to search users: HTTP {resp.status_code} — {resp.text}"
            )
        users = resp.json()
        if not users:
            raise ClerkAuthError(f"No Clerk user found with email: {email}")
        user_id = users[0]["id"]

        # 2. Get active sessions
        resp = await client.get(
            f"{CLERK_API_BASE}/sessions",
            params={"user_id": user_id, "status": "active"},
            headers=headers,
        )
        if resp.status_code != 200:
            raise ClerkAuthError(
                f"Failed to list sessions: HTTP {resp.status_code} — {resp.text}"
            )
        sessions = resp.json()
        if not sessions:
            raise ClerkAuthError(
                f"No active Clerk session for user {email}. "
                "The user must be logged in via the frontend."
            )
        session_id = sessions[0]["id"]

        # 3. Mint JWT
        resp = await client.post(
            f"{CLERK_API_BASE}/sessions/{session_id}/tokens",
            json={},
            headers=headers,
        )
        if resp.status_code != 200:
            raise ClerkAuthError(
                f"Failed to mint JWT: HTTP {resp.status_code} — {resp.text}"
            )
        token_data = resp.json()
        jwt = token_data.get("jwt") or token_data.get("token")
        if not jwt:
            raise ClerkAuthError(f"No JWT in Clerk response: {token_data}")
        return jwt
