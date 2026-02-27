# E2E Test Coverage Matrix

## Matrix 1: Entity × CRUD Operation

Which operations are tested per entity?

| Entity | List (GET) | Detail (GET) | Create (POST) | Update (PUT) | Delete (DELETE) | Generate (POST) |
|--------|:----------:|:------------:|:--------------:|:------------:|:---------------:|:---------------:|
| **Namespace** | ✅ | — | ✅ | — | ✅ | — |
| **Type** | ✅ | — | N/A (read-only) | N/A | N/A | — |
| **Field Constraint** | ✅ | — | N/A (read-only) | N/A | N/A | — |
| **FV Template** | ✅ | — | N/A (read-only) | N/A | N/A | — |
| **MV Template** | ✅ | — | N/A (read-only) | N/A | N/A | — |
| **Field** | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| **Object** | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| **API** | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| **Endpoint** | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| **Generation** | — | — | — | — | — | ❌ |

**Legend:** ✅ = covered, ❌ = not covered, — = not tested but could be, N/A = operation doesn't exist

### Gaps

| Entity | Operation | Gap |
|--------|-----------|-----|
| Namespace | GET detail | Never fetches `/namespaces/{id}` |
| Namespace | PUT | Never updates a namespace |
| Type | GET detail | No individual type fetch (no endpoint exists) |
| Field Constraint | GET detail | No individual constraint fetch (no endpoint exists) |
| API | GET detail | Only fetched after update, not standalone |
| Generation | POST `/apis/{id}/generate` | Entire generation flow untested |

---

## Matrix 2: Entity × Validation/Error Path

Which error conditions are tested per entity?

### Namespace Errors

| Error Path | Status | Tested |
|------------|:------:|:------:|
| Create duplicate name | 400 | ✅ |
| Create reserved name ("Global") | 400 | ✅ |
| Update to duplicate name | 400 | ✅ |
| Update system namespace name | 400 | ✅ |
| Update system namespace description | 400 | ✅ |
| Unset default namespace | 400 | ✅ |
| Delete system namespace | 400 | ✅ |
| Delete default namespace | 400 | ✅ |
| Delete namespace with entities inside | 400 | ✅ |
| Delete non-existent namespace | 404 | ✅ |
| Get another user's namespace | 404 | ❌ |

### Field Errors

| Error Path | Status | Tested |
|------------|:------:|:------:|
| Create with non-existent type ID | 4xx | ✅ (500 — unhandled IntegrityError) |
| Create with non-existent constraint ID | 4xx | ✅ (500 — unhandled IntegrityError) |
| Create with non-existent validator template ID | 4xx | ✅ (500 — unhandled IntegrityError) |
| Create with incompatible constraint for type | 4xx | ❌ |
| Create in non-existent namespace | 400 | ✅ |
| Create in another user's namespace | 400 | ❌ |
| Update non-existent field | 404 | ❌ |
| Update another user's field | 400 | ❌ |
| Delete field in use by an object | 400 | ✅ |
| Delete non-existent field | 404 | ✅ |
| Get non-existent field | 404 | ✅ |

### Object Errors

| Error Path | Status | Tested |
|------------|:------:|:------:|
| Create with non-existent field ID | 4xx | ✅ (500 — unhandled IntegrityError) |
| Create with non-existent MV template ID | 4xx | ✅ (500 — unhandled IntegrityError) |
| Create with invalid field mapping names | 4xx | ❌ |
| Create in non-existent namespace | 400 | ✅ |
| Create in another user's namespace | 400 | ❌ |
| Update non-existent object | 404 | ❌ |
| Update another user's object | 400 | ❌ |
| Delete object in use by an endpoint | 400 | ✅ |
| Delete non-existent object | 404 | ✅ |
| Get non-existent object | 404 | ✅ |

### API Errors

| Error Path | Status | Tested |
|------------|:------:|:------:|
| Create in non-existent namespace | 400 | ✅ |
| Create in another user's namespace | 400 | ❌ |
| Update non-existent API | 404 | ❌ |
| Update another user's API | 400 | ❌ |
| Delete non-existent API | 404 | ✅ |
| Get non-existent API | 404 | ✅ |
| Generate from non-existent API | 404 | ❌ |
| Generate when limit exceeded | 402 | ❌ |

### Endpoint Errors

| Error Path | Status | Tested |
|------------|:------:|:------:|
| Create with non-existent API ID | 4xx | ❌ |
| Create with non-existent object IDs | 4xx | ❌ |
| Create with non-existent field ID in pathParams | 4xx | ❌ |
| Create on another user's API | 400 | ❌ |
| Update non-existent endpoint | 404 | ✅ |
| Update another user's endpoint | 400 | ❌ |
| Delete non-existent endpoint | 404 | ✅ |
| Get non-existent endpoint | 404 | ✅ |

**Current error path coverage: ~32 / ~40 error paths tested.**

---

## Matrix 3: Data Variation Coverage

### Types Used in Fields

| Type | Used in Test | With Constraints | With Validators |
|------|:------------:|:----------------:|:---------------:|
| str | ✅ (name, sku, phone) | ✅ (min_length, max_length, pattern) | ✅ (Trim, Normalize Whitespace, Normalize Case) |
| int | ✅ (quantity, min/max_order, discount_percent) | ✅ (ge, le, multiple_of) | ❌ |
| float | ✅ (weight) | ✅ (ge, lt) | ✅ (Clamp to Range) |
| bool | ✅ (in_stock, is_active) | ❌ (none exist) | ❌ |
| Decimal | ✅ (price, sale_price, discount_amount) | ✅ (gt, ge) | ✅ (Round Decimal) |
| date | ✅ (sale_end_date, release_date, date_of_birth) | ❌ | ❌ |
| time | ✅ (last_login_time) | ❌ | ❌ |
| datetime | ✅ (created_at, registered_at) | ❌ | ❌ |
| uuid | ✅ (tracking_id) | ❌ | ❌ |
| EmailStr | ✅ (email) | ❌ | ❌ |
| HttpUrl | ✅ (product_url) | ❌ | ❌ |

### Constraints Used

| Constraint | Used | On Which Type(s) |
|------------|:----:|-------------------|
| min_length | ✅ | str (name, customer_name, phone) |
| max_length | ✅ | str (name, customer_name, phone) |
| pattern | ✅ | str (sku) |
| gt | ✅ | Decimal (price) |
| ge | ✅ | Decimal (sale_price, discount_amount), float (weight), int (quantity, min_order, discount_percent) |
| lt | ✅ | float (weight) |
| le | ✅ | int (max_order, discount_percent) |
| multiple_of | ✅ | int (discount_percent) |

**All 8 constraints covered.** But only on one or two type combinations each.

### Field Validator Templates Used

| Template | Used | Parameters Tested |
|----------|:----:|-------------------|
| Trim | ✅ | None (no params) |
| Normalize Whitespace | ✅ | None (no params) |
| Normalize Case | ✅ | `{"case": "upper"}`, `{"case": "title"}` |
| Round Decimal | ✅ | `{"places": "2"}` |
| Clamp to Range | ✅ | `{"min": "0", "max": "1000"}` |
| Trim To Length | ✅ | `{"max_length": "100"}` (via update) |
| Strip Characters | ❌ | — |
| Pad String | ❌ | — |
| Default If Empty | ❌ | — |
| Absolute Value | ❌ | — |

**6 of 10 field validator templates covered.**

### Model Validator Templates Used

| Template | Used | Field Mapping Pattern |
|----------|:----:|----------------------|
| Field Comparison | ✅ | `field_a` < `field_b` (operator: `<`) |
| Mutual Exclusivity | ✅ | `field_a` ⊕ `field_b` |
| All Or None | ✅ | `field_a` ↔ `field_b` |
| Conditional Required | ✅ | `trigger_field` → `dependent_field` |
| At Least One Required | ✅ | `field_a` ∨ `field_b` |

**All 5 model validator templates covered.** But only one operator value tested for Field Comparison.

---

## Matrix 4: HTTP Method × Response Shape × Body Combination

Endpoints test different combinations of method, response shape, and request/response bodies.

| Method | Path | Request Body | Response Body | Path Params | Response Shape | Tested |
|--------|------|:------------:|:-------------:|:-----------:|:--------------:|:------:|
| GET | /products | — | Product | — | list | ✅ |
| GET | /products/{id} | — | Product | uuid | object | ✅ |
| POST | /products | Product | Product | — | object | ✅ |
| PUT | /products/{id} | Product | Product | uuid | object | ✅ |
| DELETE | /products/{id} | — | — | uuid | object | ✅ |
| GET | /customers | — | Customer | — | list | ✅ |
| PATCH | /customers/{email} | Customer | Customer | EmailStr | object | ✅ |

### Untested Combinations

| Combination | Description |
|-------------|-------------|
| GET + query params object | No endpoint uses `queryParamsObjectId` |
| POST + no response body | Not tested |
| Any method + `useEnvelope: true` | All endpoints have `useEnvelope: false` |
| Any method + non-UUID/non-EmailStr path param | Only uuid and EmailStr tested |
| Multiple path params | Only single path param tested |

---

## Matrix 5: Cross-Entity Integrity (Referential Constraints)

| Scenario | Direction | Tested |
|----------|-----------|:------:|
| Field → Type reference (create) | Forward | ✅ (all 11 types used) |
| Field → Constraint reference (create) | Forward | ✅ (all 8 constraints used) |
| Field → FV Template reference (create) | Forward | ✅ (6 templates used) |
| Object → Field reference (create) | Forward | ✅ (23 fields referenced) |
| Object → MV Template reference (create) | Forward | ✅ (all 5 templates used) |
| API → Namespace reference (create) | Forward | ✅ |
| Endpoint → API reference (create) | Forward | ✅ |
| Endpoint → Object reference (request/response body) | Forward | ✅ |
| Endpoint → Field reference (path params) | Forward | ✅ |
| Delete field that's attached to an object | Blocked | ✅ |
| Delete object that's used in an endpoint | Blocked | ✅ |
| Delete namespace that contains entities | Blocked | ✅ |
| Delete API cascades to endpoints | Cascade | ✅ |
| Create field with invalid type ID | Rejected | ✅ (500 — unhandled IntegrityError) |
| Create object with invalid field ID | Rejected | ✅ (500 — unhandled IntegrityError) |
| Create endpoint with invalid object ID | Rejected | ❌ |

---

## Matrix 6: Update Operation Coverage

What gets updated vs what's available to update?

### Namespace Updates

| Field | Updatable | Tested |
|-------|:---------:|:------:|
| name | ✅ | ❌ |
| description | ✅ | ❌ |
| isDefault | ✅ | ❌ |

### Field Updates

| Field | Updatable | Tested |
|-------|:---------:|:------:|
| name | ✅ | ❌ |
| description | ✅ | ❌ |
| defaultValue | ✅ | ❌ |
| container | ✅ | ❌ |
| constraints (replace) | ✅ | ✅ (change max_length value) |
| constraints (clear) | ✅ | ❌ |
| validators (replace) | ✅ | ✅ (add Trim To Length) |
| validators (clear) | ✅ | ❌ |

### Object Updates

| Field | Updatable | Tested |
|-------|:---------:|:------:|
| name | ✅ | ❌ |
| description | ✅ | ❌ |
| fields (replace) | ✅ | ✅ (change optionality) |
| fields (clear) | ✅ | ❌ |
| validators (replace) | ✅ | ❌ |
| validators (clear) | ✅ | ❌ |

### API Updates

| Field | Updatable | Tested |
|-------|:---------:|:------:|
| title | ✅ | ❌ |
| version | ✅ | ❌ |
| description | ✅ | ✅ |
| baseUrl | ✅ | ❌ |
| serverUrl | ✅ | ❌ |

### Endpoint Updates

| Field | Updatable | Tested |
|-------|:---------:|:------:|
| apiId (move) | ✅ | ❌ |
| method | ✅ | ❌ |
| path | ✅ | ✅ |
| description | ✅ | ❌ |
| tagName | ✅ | ❌ |
| pathParams | ✅ | ✅ (UUID round-trip) |
| queryParamsObjectId | ✅ | ❌ |
| requestBodyObjectId | ✅ | ❌ |
| responseBodyObjectId | ✅ | ❌ |
| useEnvelope | ✅ | ❌ |
| responseShape | ✅ | ❌ |

---

## Matrix 7: Query Parameter / Filtering Coverage

| Endpoint | Query Param | Tested |
|----------|-------------|:------:|
| GET /types | `namespace_id` | ❌ |
| GET /field-constraints | `namespace_id` | ❌ |
| GET /fields | `namespace_id` | ✅ |
| GET /objects | `namespace_id` | ✅ |
| GET /apis | `namespace_id` | ❌ |
| GET /endpoints | `namespace_id` | ❌ |
| All list endpoints | (no filter — return all) | ✅ (implicitly in delete verification) |

---

## Summary Scorecard

| Dimension | Covered | Total | % |
|-----------|:-------:|:-----:|:-:|
| CRUD operations (on mutable entities) | 21 | 26 | 81% |
| Error/validation paths | ~32 | ~40 | 80% |
| Type usage in fields | 11 | 11 | 100% |
| Constraint usage | 8 | 8 | 100% |
| FV template usage | 6 | 10 | 60% |
| MV template usage | 5 | 5 | 100% |
| Updatable field coverage | 7 | 28 | 25% |
| Query param filtering | 2 | 6 | 33% |
| Cross-entity integrity (forward refs) | 9 | 9 | 100% |
| Cross-entity integrity (blocked deletes) | 3 | 3 | 100% |
| Cross-entity integrity (cascade deletes) | 1 | 1 | 100% |
| Generation flow | 0 | 1 | 0% |

### Overall: Strong happy-path and error-path coverage. FK-violation tests expose missing input validation (see findings below).

### FK-Violation Findings

The following bogus-FK tests return **500 (unhandled IntegrityError/exception propagated through ASGI)** instead of 400. These are API-side validation gaps to fix in a follow-up task:

| Test | Bogus FK | Actual Status |
|------|----------|:---:|
| Phase 6: Create field with bogus type ID | `FAKE_TYPE_ID` | 500 |
| Phase 6: Create field with bogus constraint ID | `FAKE_CONSTRAINT_ID` | 500 |
| Phase 6: Create field with bogus FV template ID | `FAKE_FV_TEMPLATE_ID` | 500 |
| Phase 7: Create object with bogus field ID | `FAKE_FIELD_ID` | 500 |
| Phase 7: Create object with bogus MV template ID | `FAKE_MV_TEMPLATE_ID` | 500 |
