# User Isolation Audit

## Current State: Core Entities Are Already Isolated

The main data entities already filter by user correctly:

| Entity | Isolation Method | Status |
|---|---|---|
| Namespaces | `namespace.user_id == user_id` | Correct |
| APIs | via namespace join | Correct |
| Fields | via namespace join | Correct |
| Objects | via namespace join | Correct |
| Endpoints | via api -> namespace join | Correct |

Every service layer method (`list_for_user`, `get_by_id_for_user`) joins through `Namespace` and filters by `user_id OR global_namespace_id`. Write operations check ownership.

## Issues Found

### 1. Types & Field Constraints leak data when `namespace_id` is omitted

- `src/api/routers/types.py` -- when no `namespace_id` query param is passed, the query is just `select(TypeModel)` with zero filtering. Returns ALL rows.
- `src/api/routers/field_constraints.py` -- same problem.
- Currently low-risk (only global/seeded data exists), but becomes a real leak once custom types are supported.
- Also: `get_field_counts_by_type` and `get_field_counts_by_constraint` count ALL users' fields, not just the current user's.

### 2. Validators router is dead code

- `src/api/routers/validators.py` imports non-existent models (`FieldValidator`, `ValidatorModel`) and is not registered in `main.py`. Can be deleted.

### 3. No `users` table

- User identity is stored as inline text strings (`user_id` columns). No local record of email, name, or plan.

### 4. No Clerk webhook integration

- Zero webhook code exists.

### 5. No default namespace auto-provisioning

- The schema supports one-default-per-user (partial unique index exists), but no code creates it on first login.

## Architecture Clarifications

### How user_id Is Resolved

The server extracts `user_id` from the JWT token — the client never sends it.

The chain in `src/api/auth.py`:

1. `HTTPBearer()` (line 115) extracts `Authorization: Bearer <token>` from the request header
2. `get_current_user()` (lines 118-135) passes the raw JWT to `authenticator.get_user_id()`
3. `get_user_id()` (lines 96-103) calls `validate_token()` which cryptographically verifies the JWT against Clerk's public JWKS keys, then returns `payload["sub"]` — Clerk's user ID string (e.g. `user_2abc123`)
4. `CurrentUser = Annotated[str, Depends(get_current_user)]` (line 139) — every router declares `user_id: CurrentUser` and FastAPI injects it automatically

The client cannot impersonate another user because the JWT is signed by Clerk's private key. No `user_id` field exists in any request body or query parameter.

### Industry Standard for Public Paid APIs

What we have now is already correct for a frontend-consumed SaaS API. For a public developer API, the standard layers are:

| Tier | Mechanism | Use Case | Examples |
|---|---|---|---|
| Current | Clerk JWT (`sub` claim) | Own frontend | What we have now |
| Public API | **API keys** (`sk_live_...`) | Third-party developers | Stripe, OpenAI, GitHub |
| Enterprise | **OAuth2 Client Credentials** | Machine-to-machine | Google Cloud, AWS |

In all tiers, the server **never trusts a client-supplied user ID**. Identity is always resolved server-side — from a verified JWT, a hashed API key lookup, or an OAuth token. Rate limiting and billing are layered on top by identifying the caller from whichever auth mechanism they used.

### Webhook Security (Svix HMAC Signatures)

Webhooks use a different but equally secure auth mechanism: **HMAC signature verification** via Svix.

Clerk (via Svix) sends every webhook with these headers:

```
svix-id: msg_2abc123...
svix-timestamp: 1710000000
svix-signature: v1,K5oZfzN95Z3mnHNmzLM+bKXOjpYqnZxMhJ0epF6UJWM=
```

The signature is an HMAC-SHA256 hash of the message ID + timestamp + body, signed with a shared secret that only Clerk and our server know. Our server verifies it:

```python
from svix.webhooks import Webhook, WebhookVerificationError

wh = Webhook(settings.clerk_webhook_secret)
try:
    payload = wh.verify(body.decode(), headers)
except WebhookVerificationError:
    raise HTTPException(status_code=400, detail="Invalid signature")
```

Without the signing secret, an attacker cannot produce a valid signature. The timestamp check also prevents replay attacks. This is the exact same mechanism Stripe, GitHub, and Twilio use.

It is not "no auth" — it is **server-to-server auth via shared secret** instead of user-session auth via JWT.

## Recommendations (Prioritized)

### Priority 1 -- Fix the leaks (no migration needed)

1. Add user filtering to types and field_constraints routers (or extract them into proper service classes matching the existing pattern)
2. Scope the field-count aggregate queries to current user
3. Delete the stale validators router

### Priority 2 -- Users table + default namespace (migration needed)

4. Add a `users` table (`id`, `clerk_id`, `email`, `name`, `created_at`, `updated_at`)
5. Add first-login provisioning (create default namespace on first request)

### Priority 3 -- Clerk webhook sync

6. Add `POST /webhooks/clerk` endpoint in `src/api/routers/webhooks.py`
7. Handle `user.created`, `user.updated`, `user.deleted` events
8. Use `svix` for signature verification

### Priority 4 -- Constraint tightening

9. Backfill `users` rows from existing `user_id` values
10. Add FK constraints from `user_id` columns to `users.clerk_id`
11. Enforce `NOT NULL` on `user_id` for user-created entities

### Package Organization

Keep everything in `src/api/`:

```
src/api/
  routers/webhooks.py    # Clerk webhook handler (Svix signature verification)
  services/user.py       # User sync logic
```
