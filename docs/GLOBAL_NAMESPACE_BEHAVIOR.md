# Global Namespace Behavior

Authoritative specification for namespace types, seed data, visibility rules, and write permissions.

## Namespace Types

There are exactly three kinds of namespaces. No other kinds exist.

### 1. System Namespace

| Property | Value |
|----------|-------|
| `id` | `00000000-0000-0000-0000-000000000001` (fixed) |
| `user_id` | `NULL` |
| `name` | `"Global"` |
| `locked` | `True` |
| `is_default` | `False` |

The system namespace is the single source of truth for seed data (types and field constraints). It is never duplicated, never visible in user-facing namespace listings, and fully immutable.

### 2. Per-User Global Namespace

| Property | Value |
|----------|-------|
| `id` | Auto-generated UUID |
| `user_id` | Clerk user ID |
| `name` | `"Global"` |
| `locked` | `True` |
| `is_default` | `True` |

Created lazily on the user's first authenticated request. Starts empty. Each user has exactly one (enforced by partial unique index `ix_namespaces_one_default_per_user`).

### 3. Project Namespace

| Property | Value |
|----------|-------|
| `id` | Auto-generated UUID |
| `user_id` | Clerk user ID |
| `name` | User-chosen name |
| `locked` | `False` |
| `is_default` | `False` |

Regular namespaces created by users to organize project work. No limit on count.

## Seed Data

Stored once in the system namespace. 16 entities total.

### 8 Types

| Name | `python_type` | `parent_type_id` | `import_path` |
|------|---------------|-------------------|---------------|
| `str` | `str` | `NULL` | `NULL` |
| `int` | `int` | `NULL` | `NULL` |
| `float` | `float` | `NULL` | `NULL` |
| `bool` | `bool` | `NULL` | `NULL` |
| `datetime` | `datetime.datetime` | `NULL` | `from datetime import datetime` |
| `uuid` | `uuid.UUID` | `NULL` | `from uuid import UUID` |
| `EmailStr` | `EmailStr` | `str` | `from pydantic import EmailStr` |
| `HttpUrl` | `HttpUrl` | `str` | `from pydantic import HttpUrl` |

Fixed UUIDs: `00000000-0000-0000-0001-000000000001` through `...0008`.

### 8 Field Constraints

| Name | `parameter_types` | `compatible_types` |
|------|-------------------|--------------------|
| `max_length` | `["int"]` | `["str", "uuid"]` |
| `min_length` | `["int"]` | `["str", "uuid"]` |
| `pattern` | `["str"]` | `["str", "uuid"]` |
| `gt` | `["int", "float"]` | `["int", "float"]` |
| `ge` | `["int", "float"]` | `["int", "float"]` |
| `lt` | `["int", "float"]` | `["int", "float"]` |
| `le` | `["int", "float"]` | `["int", "float"]` |
| `multiple_of` | `["int", "float"]` | `["int", "float"]` |

Fixed UUIDs: `00000000-0000-0000-0002-000000000001` through `...0010`.

## Visibility Rules

### What each user sees

When a user queries **types** or **field constraints**, they receive the union of:
- All seed entities from the system namespace
- All entities from their own namespaces (Global + project)

When a user queries **namespaces**, they see only their own namespaces. The system namespace is never returned.

When a user queries **fields, objects, APIs, endpoints, validators**, they see only entities in their own namespaces. These entity types never exist in the system namespace.

### Service OR clause requirements

| Service | Includes system namespace? | Reason |
|---------|---------------------------|--------|
| `TypeService` | **Yes** | Returns seed types |
| `FieldConstraintService` | **Yes** | Returns seed constraints |
| `NamespaceService` | **No** | System namespace hidden from users |
| `FieldService` | **No** | Fields only exist in user namespaces |
| `ObjectService` | **No** | Objects only exist in user namespaces |
| `ApiService` | **No** | APIs only exist in user namespaces |
| `EndpointService` | **No** | Endpoints only exist in user namespaces |

## Write Permission Rules

### Entity creation inside namespaces

| Target namespace | Create entities inside it? | Why |
|------------------|---------------------------|-----|
| System namespace (`user_id=NULL`) | **Forbidden** | Seed data is immutable |
| User's Global namespace (`locked=True`, `user_id=<uid>`) | **Allowed** | `locked` only protects namespace metadata |
| Project namespace (`locked=False`, `user_id=<uid>`) | **Allowed** | Normal user namespace |

The ownership filter `Namespace.user_id == user_id` implicitly excludes the system namespace (where `user_id IS NULL`). No separate system namespace check is needed.

### Namespace metadata mutation

| Action | System namespace | User's Global namespace | Project namespace |
|--------|-----------------|------------------------|-------------------|
| Rename | Forbidden (`locked`) | Forbidden (`locked`) | Allowed |
| Delete | Forbidden (`locked`) | Forbidden (`locked`) | Allowed |
| Change description | Forbidden (`locked`) | Forbidden (`locked`) | Allowed |

### Seed data immutability

Seed data is immutable. The enforcement mechanism:

> **Any write operation (create, update, delete) MUST be rejected if the target entity's namespace has `user_id IS NULL`.**

No `is_seed` or `is_system` column exists or is needed. The namespace's `user_id` is the sole discriminator.

## Cross-Namespace References

Entities can reference types and constraints from any namespace visible to the user:

- A field in a project namespace can use a seed type (e.g. `str`) from the system namespace
- A field can attach a seed constraint (e.g. `max_length`) from the system namespace
- A field can use a custom type from the user's Global namespace
- An object can reference fields from any of the user's namespaces

FK references are by UUID. The service layer validates that the referenced entity is accessible to the user (exists in system namespace OR in one of the user's namespaces).

## Provisioning

### Behavior

On every authenticated request, the `ProvisionedUser` dependency ensures the user has a Global namespace:

1. **Fast path** (all requests after the first): query for `is_default=True` namespace for this user. If found, return immediately.
2. **Slow path** (first request only): insert one namespace row. No data is copied.

### Invariants

- Provisioning creates exactly one row: the user's Global namespace.
- Provisioning never copies types or constraints. Seed data is accessed via the OR clause at query time.
- The provisioned namespace starts empty.
- Concurrent provisioning attempts for the same user are safe (savepoint + `IntegrityError` catch).
- The partial unique index `ix_namespaces_one_default_per_user` guarantees at most one default namespace per user.

## Entity Residence Rules

| Entity type | Can exist in system namespace? | Can exist in user namespaces? |
|-------------|-------------------------------|-------------------------------|
| Types | Yes (seed data) | Yes (custom types) |
| Field constraints | Yes (seed data) | Yes (custom constraints) |
| Fields | No | Yes |
| Objects | No | Yes |
| APIs | No | Yes |
| Endpoints | No | Yes |
| Field validators | No | Yes |
| Model validators | No | Yes |

## Settings

`system_namespace_id` in `src/api/settings.py` holds the system namespace UUID (`00000000-0000-0000-0000-000000000001`). Environment variable: `SYSTEM_NAMESPACE_ID`. Used by service read queries for the OR clause.
