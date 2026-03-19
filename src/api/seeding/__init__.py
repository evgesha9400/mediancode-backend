"""Shop API seeding module.

Public API:
    seed_shop(client) -> SeedResult   — Create Shop API structure
    clean_shop(client) -> None        — Delete Shop namespace subtree
    SeedResult                        — Dataclass with created entity IDs
    SeedError                         — Raised on API call failure
"""

from api.seeding.runner import SeedError, SeedResult, clean_shop, seed_shop

__all__ = ["seed_shop", "clean_shop", "SeedResult", "SeedError"]
