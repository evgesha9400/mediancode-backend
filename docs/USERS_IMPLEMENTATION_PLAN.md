# Users & Credit Tracking — Implementation Plan

## Decisions

| Question | Decision |
|----------|----------|
| Beta credits | Environment-level flag (`BETA_MODE=true`) — all users skip credit checks |
| User fields | Core identity: clerk_id, email, first_name, last_name, username, image_url |
| Data sync | Clerk webhooks (`user.created`, `user.updated`) |
| ProvisionedUser return type | `UserModel` object (replaces raw `str`) |
| Credit cost | 1 credit per generation (variable later) |
| Credit addition | Deferred |

---

## Progress Tracker

- [x] Phase 1: Users Table & Model
- [x] Phase 2: Settings Update
- [x] Phase 3: UserService
- [x] Phase 4: deps.py + Router Updates
- [x] Phase 5: Credit Check on Generation
- [x] Phase 6: Webhook Endpoint + svix dependency
- [x] Phase 7: Tests
- [x] Phase 8: Format & Verify

---

## Phase 1: Users Table & Model

**Status:** `DONE`

> **Verification notes (2026-02-18):**
> - `Integer` present in SQLAlchemy imports at `database.py:8`.
> - `UserModel` class at `database.py:34-68` with all specified columns (id, clerk_id, email, first_name, last_name, username, image_url, credits_remaining, credits_used, created_at, updated_at). Placed before `Namespace` class as specified.
> - `UserModel` exported in `models/__init__.py` (import line 15, `__all__` line 30).
> - Users table included in initial schema migration `4141ad7f2255` (lines 28-58) with unique index on `clerk_id`.

### Steps

- [x] 1.1 Add `Integer` to SQLAlchemy imports in `src/api/models/database.py`
- [x] 1.2 Add `UserModel` class to `src/api/models/database.py`
- [x] 1.3 Export `UserModel` from `src/api/models/__init__.py`
- [x] 1.4 Create Alembic migration *(folded into initial schema migration `4141ad7f2255` — no separate migration needed)*
- [x] 1.5 Reset local DB and run migration

### Agent Prompt

```
Read docs/USERS_IMPLEMENTATION_PLAN.md for full context — you are implementing Phase 1.

Do the following:

1. Read `src/api/models/database.py`. Add `Integer` to the SQLAlchemy imports. Then add a `UserModel` class following the exact same patterns as the existing models (UUID PK via `generate_uuid`, timestamps via `utc_now`):

   Table name: "users"
   Columns:
   - id: UUID PK (default=generate_uuid)
   - clerk_id: TEXT NOT NULL, unique, indexed
   - email: TEXT, nullable
   - first_name: TEXT, nullable
   - last_name: TEXT, nullable
   - username: TEXT, nullable
   - image_url: TEXT, nullable
   - credits_remaining: INTEGER NOT NULL, default=0
   - credits_used: INTEGER NOT NULL, default=0
   - created_at: TIMESTAMPTZ NOT NULL (default=utc_now)
   - updated_at: TIMESTAMPTZ NOT NULL (default=utc_now, onupdate=utc_now)

   No relationships. Place the class BEFORE the Namespace class.

2. Read `src/api/models/__init__.py`. Add `UserModel` to the imports and `__all__`.

3. Create a NEW migration file at `src/api/migrations/versions/c2d3e4f5g6h7_add_users_table.py`.
   - Revises: `b1a2c3d4e5f6`
   - Upgrade: Create `users` table, create unique index on `clerk_id`, then backfill:
     ```sql
     INSERT INTO users (id, clerk_id, credits_remaining, credits_used, created_at, updated_at)
     SELECT gen_random_uuid(), user_id, 0, 0, NOW(), NOW()
     FROM namespaces
     WHERE user_id IS NOT NULL
     GROUP BY user_id
     ON CONFLICT (clerk_id) DO NOTHING;
     ```
   - Downgrade: Drop `users` table.
   - Follow the exact style of existing migration files in `src/api/migrations/versions/`.

4. Reset the local database and run migrations:
   ```
   docker compose down -v && docker compose up -d
   sleep 2
   poetry run alembic upgrade head
   ```

5. Run `poetry run black src/` to format.

After completing, update docs/USERS_IMPLEMENTATION_PLAN.md:
- Check off all Phase 1 steps (replace `- [ ]` with `- [x]`)
- Set Phase 1 Status to `DONE`
- Check off Phase 1 in the Progress Tracker
```

### Reference

```
users
─────
id                 UUID PK            default: gen_random_uuid()
clerk_id           TEXT NOT NULL       UNIQUE, indexed
email              TEXT                nullable
first_name         TEXT                nullable
last_name          TEXT                nullable
username           TEXT                nullable
image_url          TEXT                nullable
credits_remaining  INTEGER NOT NULL    default: 0
credits_used       INTEGER NOT NULL    default: 0
created_at         TIMESTAMPTZ NOT NULL
updated_at         TIMESTAMPTZ NOT NULL
```

---

## Phase 2: Settings Update

**Status:** `DONE`

> **Verification notes (2026-02-18):**
> - `settings.py:67-69` has all three fields: `beta_mode: bool = True`, `default_credits: int = 0`, `clerk_webhook_secret: str = ""`.
> - Docstring updated with descriptions for all three fields.

### Steps

- [x] 2.1 Add `beta_mode`, `default_credits`, `clerk_webhook_secret` to `src/api/settings.py`
- [x] 2.2 Format with black

### Agent Prompt

```
Read docs/USERS_IMPLEMENTATION_PLAN.md for full context — you are implementing Phase 2.

Do the following:

1. Read `src/api/settings.py`. Add these three fields to the `Settings` class (after the existing fields, before `@property`):

   ```python
   beta_mode: bool = True          # Skip credit checks when True
   default_credits: int = 0        # Credits granted to new users (0 during beta)
   clerk_webhook_secret: str = ""  # Svix signing secret for Clerk webhooks
   ```

2. Run `poetry run black src/` to format.

After completing, update docs/USERS_IMPLEMENTATION_PLAN.md:
- Check off all Phase 2 steps
- Set Phase 2 Status to `DONE`
- Check off Phase 2 in the Progress Tracker
```

---

## Phase 3: UserService

**Status:** `DONE`

> **Verification notes (2026-02-18):**
> - `user_provisioning.py` no longer exists; `user.py` is present with complete `UserService` class.
> - All 6 methods implemented: `ensure_provisioned`, `_provision_user`, `get_by_clerk_id`, `upsert_from_clerk`, `deduct_credit`, `has_credits`.
> - `services/__init__.py` does not export `UserService` (it never exported `UserProvisioningService` either, so no change was needed).
> - `deps.py` import was updated as a side effect (required to avoid broken import after rename).

### Steps

- [x] 3.1 Rename `src/api/services/user_provisioning.py` → `src/api/services/user.py`
- [x] 3.2 Rewrite as `UserService` with all new methods
- [x] 3.3 Update `src/api/services/__init__.py` export (if applicable) *(not applicable — was never exported)*
- [x] 3.4 Format with black

### Agent Prompt

```
Read docs/USERS_IMPLEMENTATION_PLAN.md for full context — you are implementing Phase 3.

Do the following:

1. Read `src/api/services/user_provisioning.py` to understand the current implementation.

2. Rename the file: `git mv src/api/services/user_provisioning.py src/api/services/user.py`

3. Rewrite `src/api/services/user.py` as `UserService` (replacing `UserProvisioningService`). The class must have these methods:

   ```python
   class UserService:
       def __init__(self, db: AsyncSession) -> None:
           self.db = db

       async def ensure_provisioned(self, clerk_id: str) -> UserModel:
           """Fast path: lookup by clerk_id. If not found, create user + default namespace.
           Returns UserModel (not None like the old service)."""

       async def _provision_user(self, clerk_id: str) -> UserModel:
           """Creates user row + default namespace in a savepoint.
           - Create UserModel with clerk_id, credits from settings.default_credits
           - Create default namespace (name="Global", locked=True, is_default=True)
           - Preserve existing race-condition handling (savepoint + IntegrityError catch)
           - On IntegrityError, re-fetch and return the existing user"""

       async def get_by_clerk_id(self, clerk_id: str) -> UserModel | None:
           """Lookup user by Clerk ID."""

       async def upsert_from_clerk(self, clerk_data: dict) -> UserModel:
           """Create or update user from Clerk webhook payload.
           clerk_data has keys: id, email, first_name, last_name, username, image_url.
           If user exists (by clerk_id=clerk_data["id"]), update profile fields.
           If not, create new user with profile fields + default_credits from settings."""

       async def deduct_credit(self, user: UserModel) -> bool:
           """Atomically decrement credits_remaining, increment credits_used.
           When settings.beta_mode is True, return True without deducting.
           Otherwise: UPDATE users SET credits_remaining = credits_remaining - 1,
           credits_used = credits_used + 1 WHERE id = :id AND credits_remaining > 0.
           Return rowcount > 0."""

       async def has_credits(self, user: UserModel, settings: Settings) -> bool:
           """Returns True if settings.beta_mode is True OR user.credits_remaining > 0."""
   ```

   Import `UserModel` from `api.models.database`, `Settings` and `get_settings` from `api.settings`.

4. Read `src/api/services/__init__.py`. If `UserProvisioningService` is exported there, update to `UserService` from `api.services.user`. If not exported, leave it alone.

5. Run `poetry run black src/` to format.

After completing, update docs/USERS_IMPLEMENTATION_PLAN.md:
- Check off all Phase 3 steps
- Set Phase 3 Status to `DONE`
- Check off Phase 3 in the Progress Tracker
```

### Key Behaviors

- `ensure_provisioned` returns `UserModel` (not `None`)
- On first provisioning (no webhook data yet), creates user with `clerk_id` only — profile fields stay `NULL` until webhook fires
- `deduct_credit` is a no-op returning `True` when `beta_mode=True`
- Race-condition handling preserved (savepoint + IntegrityError catch)

---

## Phase 4: deps.py + Router Updates

**Status:** `DONE`

> **Verification notes (2026-02-18):**
> - `deps.py` now imports `UserModel` from `api.models.database`, returns `UserModel` from `get_provisioned_user`, and `ProvisionedUser` is `Annotated[UserModel, ...]`.
> - All 7 routers updated: parameter renamed from `user_id: ProvisionedUser` to `user: ProvisionedUser`, all service calls pass `user.clerk_id`, all ownership checks compare against `user.clerk_id`.

### Steps

- [x] 4.1 Update `src/api/deps.py` — return `UserModel`, import `UserService`
- [x] 4.2 Update `src/api/routers/apis.py` — `user_id` → `user`, pass `user.clerk_id`
- [x] 4.3 Update `src/api/routers/namespaces.py` — same pattern
- [x] 4.4 Update `src/api/routers/types.py` — same pattern
- [x] 4.5 Update `src/api/routers/field_constraints.py` — same pattern
- [x] 4.6 Update `src/api/routers/objects.py` — same pattern + ownership checks
- [x] 4.7 Update `src/api/routers/fields.py` — same pattern + ownership checks
- [x] 4.8 Update `src/api/routers/endpoints.py` — same pattern + ownership checks via parent API
- [x] 4.9 Format with black

### Agent Prompt

```
Read docs/USERS_IMPLEMENTATION_PLAN.md for full context — you are implementing Phase 4.

Do the following:

1. Read `src/api/deps.py`. Make these changes:
   - Change import from `api.services.user_provisioning import UserProvisioningService` → `api.services.user import UserService`
   - Add import: `from api.models.database import UserModel`
   - Change `get_provisioned_user` to return `UserModel`:
     ```python
     async def get_provisioned_user(user_id: CurrentUser, db: DbSession) -> UserModel:
         service = UserService(db)
         return await service.ensure_provisioned(user_id)

     ProvisionedUser = Annotated[UserModel, Depends(get_provisioned_user)]
     ```

2. Update ALL 7 routers. For each one, read the file first, then apply this pattern:
   - Rename parameter `user_id: ProvisionedUser` → `user: ProvisionedUser` in every endpoint function signature
   - Replace every usage of `user_id` that was the ProvisionedUser value with `user.clerk_id`
   - Update ownership checks: `thing.user_id != user_id` → `thing.user_id != user.clerk_id`

   The 7 routers to update:
   a. `src/api/routers/apis.py` — all endpoints
   b. `src/api/routers/namespaces.py` — all endpoints
   c. `src/api/routers/types.py` — all endpoints
   d. `src/api/routers/field_constraints.py` — all endpoints
   e. `src/api/routers/objects.py` — all endpoints + ownership checks
   f. `src/api/routers/fields.py` — all endpoints + ownership checks (`field.user_id != user_id` → `field.user_id != user.clerk_id`)
   g. `src/api/routers/endpoints.py` — all endpoints + ownership checks via parent API (`api.user_id != user_id` → `api.user_id != user.clerk_id`)

   BE THOROUGH. Read each file. Find every occurrence of the old `user_id` parameter. Miss nothing.

3. Run `poetry run black src/` to format.

After completing, update docs/USERS_IMPLEMENTATION_PLAN.md:
- Check off all Phase 4 steps
- Set Phase 4 Status to `DONE`
- Check off Phase 4 in the Progress Tracker
```

---

## Phase 5: Credit Check on Generation

**Status:** `DONE`

> **Verification notes (2026-02-18):**
> - `generate_api_code` in `apis.py` now imports `UserService` and `get_settings`.
> - Credit check (`has_credits`) runs before generation; raises 402 if insufficient.
> - Credit deduction (`deduct_credit`) runs after successful ZIP generation, before returning `StreamingResponse`.

### Steps

- [x] 5.1 Add credit gate + deduction to `generate_api_code` in `src/api/routers/apis.py`
- [x] 5.2 Format with black

### Agent Prompt

```
Read docs/USERS_IMPLEMENTATION_PLAN.md for full context — you are implementing Phase 5.

Do the following:

1. Read `src/api/routers/apis.py`. Find the `generate_api_code` endpoint. Add:
   - Import `UserService` from `api.services.user` and `get_settings` from `api.settings` (if not already imported)
   - Credit check BEFORE the existing generation logic:
     ```python
     settings = get_settings()
     if not await UserService(db).has_credits(user, settings):
         raise HTTPException(status_code=402, detail="Insufficient credits")
     ```
   - Credit deduction AFTER successful ZIP generation but BEFORE returning the StreamingResponse:
     ```python
     await UserService(db).deduct_credit(user)
     ```
   - The parameter is already `user: ProvisionedUser` from Phase 4.

2. Run `poetry run black src/` to format.

After completing, update docs/USERS_IMPLEMENTATION_PLAN.md:
- Check off all Phase 5 steps
- Set Phase 5 Status to `DONE`
- Check off Phase 5 in the Progress Tracker
```

### Credit Deduction Timing

Deduct **after** successful generation, not before. If generation fails, the user shouldn't lose a credit. The `has_credits` check at the top prevents the "generate then fail to deduct" race — worst case, a user gets one extra generation under extreme concurrency.

---

## Phase 6: Webhook Endpoint + svix dependency

**Status:** `DONE`

> **Verification notes (2026-02-18):**
> - `svix (>=1.0.0,<2.0.0)` added to `pyproject.toml` dependencies; `poetry.lock` updated and installed.
> - `src/api/routers/webhooks.py` created with `POST /clerk` endpoint: Svix signature verification, handles `user.created`/`user.updated`, extracts user data, calls `UserService.upsert_from_clerk`.
> - `webhooks_router` exported from `routers/__init__.py` and registered in `main.py` with `prefix=f"{api_v1_prefix}/webhooks"`.

### Steps

- [x] 6.1 Add `svix` dependency to `pyproject.toml`
- [x] 6.2 Run `poetry lock && poetry install`
- [x] 6.3 Create `src/api/routers/webhooks.py`
- [x] 6.4 Add `webhooks_router` export to `src/api/routers/__init__.py`
- [x] 6.5 Register webhook router in `src/api/main.py`
- [x] 6.6 Format with black

### Agent Prompt

```
Read docs/USERS_IMPLEMENTATION_PLAN.md for full context — you are implementing Phase 6.

Do the following:

1. Read `pyproject.toml`. Add `"svix (>=1.0.0,<2.0.0)"` to the `dependencies` list, matching the existing format.

2. Run: `poetry lock && poetry install`

3. Create `src/api/routers/webhooks.py` with a Clerk webhook endpoint:

   ```
   POST /clerk  (router prefix will be /v1/webhooks from main.py)
   ```

   Requirements:
   - NO auth dependency (Clerk calls this externally, not users)
   - Verify request via Svix webhook signature using `clerk_webhook_secret` from Settings
   - Accept raw body bytes for signature verification
   - Handle event types: `user.created`, `user.updated`
   - Extract user data from Clerk payload: `{ id: data.id, email: data.email_addresses[0].email_address, first_name: data.first_name, last_name: data.last_name, username: data.username, image_url: data.image_url }`
   - Call `UserService.upsert_from_clerk(clerk_data)` to create/update user
   - Return 200 on success, 400 on signature failure
   - Ignore unhandled event types (return 200 silently)
   - Follow the existing router patterns in the codebase (read one of the existing routers for style reference)

4. Read `src/api/routers/__init__.py`. Add `webhooks_router` to imports and `__all__`:
   ```python
   from api.routers.webhooks import router as webhooks_router
   ```

5. Read `src/api/main.py`. Register the webhook router:
   ```python
   app.include_router(webhooks_router, prefix=f"{api_v1_prefix}/webhooks")
   ```
   Place it after the existing router registrations.

6. Run `poetry run black src/` to format.

After completing, update docs/USERS_IMPLEMENTATION_PLAN.md:
- Check off all Phase 6 steps
- Set Phase 6 Status to `DONE`
- Check off Phase 6 in the Progress Tracker
```

### Webhook Flow

```
Clerk event → POST /v1/webhooks/clerk
  1. Verify Svix signature (reject if invalid)
  2. Parse event type
  3. Extract user data: { id, email_addresses[0].email_address, first_name, last_name, username, image_url }
  4. Call UserService.upsert_from_clerk(data)
  5. Return 200
```

---

## Phase 7: Tests

**Status:** `DONE`

> **Verification notes (2026-02-18):**
> - `test_user_provisioning.py` renamed to `test_user.py` via `git mv`.
> - All existing tests updated to capture `ensure_provisioned()` return value and assert `isinstance(user, UserModel)` and `user.clerk_id` matches input.
> - `test_credits.py` created with 6 integration tests covering `has_credits` and `deduct_credit` (beta mode, with credits, no credits, deduction success/failure).
> - `test_webhooks.py` created with 3 integration tests covering `upsert_from_clerk` (create, update, idempotent).
> - No other test files reference `UserProvisioningService` or `user_provisioning`.
> - All 142 tests pass.

### Steps

- [x] 7.1 Rename `tests/test_api/test_services/test_user_provisioning.py` → `test_user.py`, update imports
- [x] 7.2 Update existing tests in `test_user.py` for `UserModel` return type
- [x] 7.3 Create `tests/test_api/test_services/test_credits.py`
- [x] 7.4 Create `tests/test_api/test_services/test_webhooks.py`
- [x] 7.5 Update any other test files affected by `ProvisionedUser` type change
- [x] 7.6 Format with black

### Agent Prompt

```
Read docs/USERS_IMPLEMENTATION_PLAN.md for full context — you are implementing Phase 7.

Do the following:

1. Rename the existing test file:
   `git mv tests/test_api/test_services/test_user_provisioning.py tests/test_api/test_services/test_user.py`

2. Read `tests/test_api/test_services/test_user.py`. Update:
   - Change import `UserProvisioningService` → `UserService` from `api.services.user`
   - Replace all occurrences of `UserProvisioningService` with `UserService`
   - Update existing tests: `ensure_provisioned` now returns a `UserModel`, so add assertions that:
     a. Return value is a `UserModel` instance
     b. `user.clerk_id` matches the input clerk_id
     c. The user row exists in the `users` table
   - Add cleanup for `users` table in the cleanup fixture (delete from users WHERE clerk_id IN test user IDs)
   - Import `UserModel` from `api.models.database`

3. Create `tests/test_api/test_services/test_credits.py` with these tests (all marked `@pytest.mark.integration`):
   - `test_has_credits_in_beta_mode` — with beta_mode=True, has_credits returns True even with 0 credits
   - `test_has_credits_with_credits` — with beta_mode=False and credits_remaining > 0, returns True
   - `test_has_credits_no_credits` — with beta_mode=False and credits_remaining=0, returns False
   - `test_deduct_credit_beta_mode` — in beta mode, deduct_credit returns True without changing credits
   - `test_deduct_credit_success` — with credits_remaining > 0, deducts 1, increments credits_used
   - `test_deduct_credit_insufficient` — with credits_remaining=0, returns False

   Use the existing test patterns from `test_user.py` (fixtures, db_session, cleanup).
   Mock or override settings for beta_mode tests.

4. Create `tests/test_api/test_services/test_webhooks.py` with these tests (all marked `@pytest.mark.integration`):
   - `test_upsert_from_clerk_creates_user` — new clerk_id creates user with profile fields
   - `test_upsert_from_clerk_updates_user` — existing clerk_id updates profile fields
   - `test_upsert_from_clerk_idempotent` — calling twice with same data doesn't duplicate

   Use `UserService.upsert_from_clerk()` directly (service-level tests, not HTTP-level).

5. Read all other test files under `tests/test_api/test_services/` to check if any reference `UserProvisioningService` or `user_provisioning`. Update those imports too.

6. Run `poetry run black src/ tests/` to format.

After completing, update docs/USERS_IMPLEMENTATION_PLAN.md:
- Check off all Phase 7 steps
- Set Phase 7 Status to `DONE`
- Check off Phase 7 in the Progress Tracker
```

---

## Phase 8: Format & Verify

**Status:** `DONE`

> **Verification notes (2026-02-18):**
> - `poetry run black src/ tests/` reports all 72 files unchanged.
> - `make test` passes with 142 tests (1 deselected).
> - Fresh migration (`docker compose down -v && docker compose up -d && alembic upgrade head`) runs clean with no errors.

### Steps

- [x] 8.1 Run `poetry run black src/ tests/`
- [x] 8.2 Run `make test` — all tests pass
- [x] 8.3 Manual smoke test: verify migration runs clean on fresh DB

### Agent Prompt

```
Read docs/USERS_IMPLEMENTATION_PLAN.md for full context — you are implementing Phase 8 (final verification).

Do the following:

1. Run `poetry run black src/ tests/` — fix any formatting issues.

2. Run `make test` — all tests must pass. If any fail:
   - Read the failing test and the relevant source code
   - Fix the issue
   - Re-run until all tests pass

3. Verify a clean migration run:
   ```
   docker compose down -v && docker compose up -d
   sleep 2
   poetry run alembic upgrade head
   ```
   Confirm no errors.

After completing, update docs/USERS_IMPLEMENTATION_PLAN.md:
- Check off all Phase 8 steps
- Set Phase 8 Status to `DONE`
- Check off Phase 8 in the Progress Tracker
```

---

## File Change Summary

| File | Phase | Action | Description |
|------|-------|--------|-------------|
| `src/api/models/database.py` | 1 | Edit | Add `UserModel`, add `Integer` import |
| `src/api/models/__init__.py` | 1 | Edit | Export `UserModel` |
| `src/api/migrations/versions/<new>.py` | 1 | Create | Users table + backfill |
| `src/api/settings.py` | 2 | Edit | Add `beta_mode`, `default_credits`, `clerk_webhook_secret` |
| `src/api/services/user_provisioning.py` | 3 | Rename → `user.py` | Expand to `UserService` |
| `src/api/services/__init__.py` | 3 | Edit | Update export (if applicable) |
| `src/api/deps.py` | 4 | Edit | Return `UserModel`, import `UserService` |
| `src/api/routers/apis.py` | 4, 5 | Edit | `user.clerk_id` + credit check on generate |
| `src/api/routers/namespaces.py` | 4 | Edit | `user.clerk_id` |
| `src/api/routers/types.py` | 4 | Edit | `user.clerk_id` |
| `src/api/routers/field_constraints.py` | 4 | Edit | `user.clerk_id` |
| `src/api/routers/objects.py` | 4 | Edit | `user.clerk_id` + ownership checks |
| `src/api/routers/fields.py` | 4 | Edit | `user.clerk_id` + ownership checks |
| `src/api/routers/endpoints.py` | 4 | Edit | `user.clerk_id` + ownership checks via parent API |
| `pyproject.toml` | 6 | Edit | Add `svix (>=1.0.0,<2.0.0)` |
| `src/api/routers/webhooks.py` | 6 | Create | Clerk webhook endpoint |
| `src/api/routers/__init__.py` | 6 | Edit | Add `webhooks_router` export |
| `src/api/main.py` | 6 | Edit | Register webhook router |
| `tests/test_api/test_services/test_user_provisioning.py` | 7 | Rename → `test_user.py` | Update imports + assertions |
| `tests/test_api/test_services/test_credits.py` | 7 | Create | Credit deduction + beta bypass tests |
| `tests/test_api/test_services/test_webhooks.py` | 7 | Create | Webhook upsert tests |

---

## Not In Scope (Deferred)

- Credit addition API endpoints
- Organization/team support
- FK constraints from existing `user_id TEXT` columns to `users` table
- Variable credit costs per generation
- Stripe/payment integration
