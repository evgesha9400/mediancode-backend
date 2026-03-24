"""CLI entrypoint for Shop API seeding.

Usage:
    PYTHONPATH=src:tests poetry run python -m seeding --target local --user-email user@example.com
    PYTHONPATH=src:tests poetry run python -m seeding --base-url https://api.dev.mediancode.com/v1 \
        --user-email user@example.com --mode apply
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

import httpx

TARGET_URLS = {
    "local": "http://localhost:8001/v1",
    "dev": "https://api.dev.mediancode.com/v1",
    "prod": "https://api.mediancode.com/v1",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m seeding",
        description="Seed the Shop API structure via REST API calls.",
    )
    url_group = parser.add_mutually_exclusive_group(required=True)
    url_group.add_argument(
        "--base-url", help="Target API base URL (e.g., http://localhost:8001/v1)"
    )
    url_group.add_argument(
        "--target",
        choices=["local", "dev", "prod"],
        help="Target environment alias",
    )
    parser.add_argument("--user-email", required=True, help="Clerk user email")
    parser.add_argument(
        "--bearer-token", help="Skip Clerk JWT flow, use this token directly"
    )
    parser.add_argument(
        "--mode",
        choices=["replace", "apply", "delete"],
        default="replace",
        help="Seeding mode (default: replace)",
    )
    return parser.parse_args(argv)


def _load_clerk_secret_key() -> str | None:
    """Load CLERK_SECRET_KEY from environment or .env.local."""
    key = os.environ.get("CLERK_SECRET_KEY")
    if key:
        return key
    env_file = os.path.join(os.path.dirname(__file__), "..", "..", ".env.local")
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line.startswith("CLERK_SECRET_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


async def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    base_url = args.base_url or TARGET_URLS[args.target]

    # Resolve auth
    if args.bearer_token:
        token = args.bearer_token
    else:
        from seeding.clerk_auth import ClerkAuthError, mint_clerk_jwt

        clerk_key = _load_clerk_secret_key()
        if not clerk_key:
            print(
                "Error: CLERK_SECRET_KEY not found in environment or .env.local",
                file=sys.stderr,
            )
            sys.exit(1)

        print(f"Minting Clerk JWT for {args.user_email}...")
        try:
            token = await mint_clerk_jwt(args.user_email, clerk_key)
        except ClerkAuthError as e:
            print(f"Auth error: {e}", file=sys.stderr)
            sys.exit(1)
        print("JWT acquired.")

    from seeding.runner import SeedError, clean_shop, seed_shop

    async with httpx.AsyncClient(
        base_url=base_url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30.0,
    ) as client:
        try:
            if args.mode == "delete":
                await clean_shop(client, log=print)
                print("Done.")

            elif args.mode == "replace":
                await clean_shop(client, log=print)
                result = await seed_shop(client, log=print)
                print(
                    f"Done. Namespace: {result.namespace_id}, "
                    f"API: {result.api_id}, "
                    f"{len(result.field_ids)} fields, "
                    f"{len(result.object_ids)} objects, "
                    f"{len(result.endpoint_ids)} endpoints."
                )

            elif args.mode == "apply":
                print(
                    "Error: --mode apply is not yet implemented. "
                    "Use --mode replace (delete + recreate) or --mode delete.",
                    file=sys.stderr,
                )
                sys.exit(1)

        except SeedError as e:
            print(f"Seed error: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
