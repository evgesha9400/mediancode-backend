# Design: Comprehensive Shop API E2E Test

## Overview

One new test file `tests/test_api/test_e2e_shop_full.py` containing a single class
`TestShopApiFullE2E` that covers the entire flow:

    CRUD -> Generate -> Verify ZIP -> Run Generated Code -> Validate Constraints/Validators -> Cleanup

## Phases

```
Phase 1-13:  CRUD (same as existing test_e2e_shop.py)
Phase 14:    Call generate endpoint -> receive ZIP
Phase 15:    Verify ZIP structure (files, no __pycache__, .py compiles)
Phase 16:    Load generated app -> test all 7 endpoints return valid responses
Phase 17:    Product field constraint validation (boundaries)
Phase 18:    Customer field constraint validation
Phase 19:    Product model validator validation (4 validators)
Phase 20:    Customer model validator validation (At Least One Required)
Phase 21-25: Cleanup (delete in reverse dependency order)
```

## Key Design Decisions

### 1. CRUD phases identical to test_e2e_shop.py

Same field definitions, entity creation, and updates. The generated code is based on
the exact same entities.

### 2. Generation via HTTP endpoint

`POST /apis/{api_id}/generate` returns a ZIP. We verify the HTTP response (200,
content-type), then unzip to a temp directory.

### 3. ZIP verification

Covers what `test_generation_unit.py` currently tests plus more: file existence,
`__pycache__` exclusion, Python compilability.

### 4. Generated app loaded via load_app

Reuses the existing helper from `tests/test_api_craft/conftest.py` (importlib-based
dynamic loading). `TestClient` stored as class variable.

### 5. Constraints based on what the API actually creates

Key differences from the YAML-based tests:

| Aspect               | YAML spec                        | API-created                          |
|----------------------|----------------------------------|--------------------------------------|
| Objects              | 6 separate models                | 2 (Product, Customer)                |
| SKU pattern          | `^[A-Z0-9-]+$`                   | `^[A-Z]{2}-\d{4}$`                   |
| Name max_length      | 200                              | 150 (updated in phase 5)             |
| List response        | ProductList envelope              | `list[Product]` (useEnvelope=False)  |
| Mutual Exclusivity   | discount_percent XOR is_on_sale   | discount_percent XOR discount_amount |
| All Or None          | is_on_sale + sale_start           | sale_price + sale_end_date           |
| Conditional Required | discount_percent -> is_on_sale    | discount_percent -> sale_price       |
| Customer MV          | none                             | At Least One Required (email/phone)  |
| PUT path             | /products/{tracking_id}           | /items/{tracking_id} (phase 13)      |

### 6. Valid payloads

POST /products requires all required Product fields (tracking_id, name, sku, price,
weight, quantity, min_order_quantity, in_stock, product_url, release_date, created_at)
because the same object is used for both request and response.

PATCH /customers/{email} requires all required Customer fields (customer_name,
date_of_birth, last_login_time, is_active, registered_at) plus at least email or phone.

## Phase Details

### Phases 1-13: CRUD

Exact same logic as `test_e2e_shop.py`:
1. Read catalogues (types, constraints, FV templates, MV templates)
2. Create namespace
3. Create 23 fields with constraints and validators
4. Read and verify fields
5. Update fields (max_length change, add Trim To Length validator)
6. Create objects (Product 16 fields + 4 MVs, Customer 7 fields + 1 MV)
7. Read and verify objects
8. Update object (make min_order_quantity required)
9. Create API
10. Update API description
11. Create 7 endpoints with UUID path params
12. Read and verify endpoints
13. Update endpoint path (UUID-in-JSONB regression)

### Phase 14: Generate

- `POST /apis/{api_id}/generate` -> 200
- Verify `Content-Type: application/zip`
- Verify `Content-Disposition` header contains filename
- Store ZIP bytes

### Phase 15: ZIP Structure

- Extract to temp dir (stored as `cls.generated_dir`)
- Required files: `src/models.py`, `src/views.py`, `src/main.py`, `src/path.py`,
  `pyproject.toml`, `Makefile`, `Dockerfile`
- No `__pycache__` in ZIP names
- All `.py` files compile without error

### Phase 16: Endpoint Connectivity

- Load app via `load_app`, create TestClient (`cls.gen_client`)
- GET /health -> 200 "OK"
- GET /products -> 200, JSON array
- GET /products/{tracking_id} -> 200, JSON object with Product fields
- POST /products -> 200 with valid payload
- PUT /items/{tracking_id} -> 200 with valid payload
- DELETE /products/{tracking_id} -> 200 or 204
- GET /customers -> 200, JSON array
- PATCH /customers/{email} -> 200 with valid payload

### Phase 17: Product Constraints (11 tests)

- name empty -> 422 (min_length=1)
- name too long -> 422 (max_length=150)
- sku invalid pattern -> 422 (`^[A-Z]{2}-\d{4}$`)
- price zero -> 422 (gt=0)
- price negative -> 422 (gt=0)
- quantity negative -> 422 (ge=0)
- min_order_quantity zero -> 422 (ge=1)
- max_order_quantity over 1000 -> 422 (le=1000)
- discount_percent not multiple of 5 -> 422
- discount_percent over 100 -> 422 (le=100)
- weight negative -> 422 (ge=0)

### Phase 18: Customer Constraints (2 tests)

- customer_name empty -> 422 (min_length=1)
- phone too short -> 422 (min_length=7)

### Phase 19: Product Model Validators (4 tests)

- min_order_quantity >= max_order_quantity -> 422 (Field Comparison)
- Both discount_percent and discount_amount set -> 422 (Mutual Exclusivity)
- sale_price without sale_end_date -> 422 (All Or None)
- discount_percent without sale_price -> 422 (Conditional Required)

### Phase 20: Customer Model Validator (1 test)

- Neither email nor phone -> 422 (At Least One Required)

### Phases 21-25: Cleanup

Delete in reverse dependency order:
21. Delete endpoints
22. Delete API
23. Delete objects
24. Delete fields
25. Delete namespace

## What This Supersedes

Once passing, this test fully covers:
- `test_e2e_shop.py` (CRUD phases)
- `test_shop_codegen.py` (generated code verification)
- `test_generation_unit.py` (ZIP structure, helper functions tested implicitly)
