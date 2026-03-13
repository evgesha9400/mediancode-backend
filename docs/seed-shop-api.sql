-- Seed Shop API for the user identified by email aleshiner@mail.ru
-- Recreates the same setup as test_e2e_shop_full.py (final state)
-- Plain SQL — runs in any PostgreSQL client.

BEGIN;

-- Resolve the target user by email
-- All subsequent CTEs reference this.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM users WHERE email = 'aleshiner@mail.ru') THEN
    RAISE EXCEPTION 'User with email aleshiner@mail.ru not found. Create the user first (e.g. sign in via Clerk).';
  END IF;
END $$;

-- 1. Namespace (clear any existing default first)
UPDATE namespaces SET is_default = false
WHERE user_id = (SELECT id FROM users WHERE email = 'aleshiner@mail.ru') AND is_default = true;

INSERT INTO namespaces (id, user_id, name, is_default)
VALUES (gen_random_uuid(), (SELECT id FROM users WHERE email = 'aleshiner@mail.ru'), 'Shop', true);

-- 2. Fields (23 total)
-- We need stable IDs to reference later, so we use WITH clauses per group.

WITH u AS (
  SELECT id FROM users WHERE email = 'aleshiner@mail.ru'
),
ns AS (
  SELECT n.id FROM namespaces n JOIN u ON n.user_id = u.id WHERE n.name = 'Shop'
),
sys_ns AS (
  SELECT id FROM namespaces WHERE user_id IS NULL LIMIT 1
),
types AS (
  SELECT t.name, t.id FROM types t JOIN sys_ns ON t.namespace_id = sys_ns.id
),
t AS (
  SELECT
    (SELECT id FROM types WHERE name = 'str')      AS str,
    (SELECT id FROM types WHERE name = 'int')      AS int,
    (SELECT id FROM types WHERE name = 'float')    AS float,
    (SELECT id FROM types WHERE name = 'bool')     AS bool,
    (SELECT id FROM types WHERE name = 'datetime') AS datetime,
    (SELECT id FROM types WHERE name = 'uuid')     AS uuid,
    (SELECT id FROM types WHERE name = 'EmailStr') AS email,
    (SELECT id FROM types WHERE name = 'HttpUrl')  AS httpurl,
    (SELECT id FROM types WHERE name = 'Decimal')  AS decimal,
    (SELECT id FROM types WHERE name = 'date')     AS date,
    (SELECT id FROM types WHERE name = 'time')     AS time
)
INSERT INTO fields (id, namespace_id, user_id, name, type_id)
SELECT gen_random_uuid(), ns.id, u.id, v.name, v.type_id
FROM u, ns, (VALUES
  ('name',               (SELECT str      FROM t)),
  ('sku',                (SELECT str      FROM t)),
  ('price',              (SELECT decimal  FROM t)),
  ('sale_price',         (SELECT decimal  FROM t)),
  ('sale_end_date',      (SELECT date     FROM t)),
  ('weight',             (SELECT float    FROM t)),
  ('quantity',           (SELECT int      FROM t)),
  ('min_order_quantity', (SELECT int      FROM t)),
  ('max_order_quantity', (SELECT int      FROM t)),
  ('discount_percent',   (SELECT int      FROM t)),
  ('discount_amount',    (SELECT decimal  FROM t)),
  ('in_stock',           (SELECT bool     FROM t)),
  ('product_url',        (SELECT httpurl  FROM t)),
  ('release_date',       (SELECT date     FROM t)),
  ('created_at',         (SELECT datetime FROM t)),
  ('tracking_id',        (SELECT uuid     FROM t)),
  ('customer_name',      (SELECT str      FROM t)),
  ('email',              (SELECT email    FROM t)),
  ('phone',              (SELECT str      FROM t)),
  ('date_of_birth',      (SELECT date     FROM t)),
  ('last_login_time',    (SELECT time     FROM t)),
  ('is_active',          (SELECT bool     FROM t)),
  ('registered_at',      (SELECT datetime FROM t))
) AS v(name, type_id);

-- 3. Field constraints
WITH u AS (
  SELECT id FROM users WHERE email = 'aleshiner@mail.ru'
),
ns AS (
  SELECT n.id FROM namespaces n JOIN u ON n.user_id = u.id WHERE n.name = 'Shop'
),
f AS (
  SELECT f.name, f.id FROM fields f JOIN ns ON f.namespace_id = ns.id
),
sys_ns AS (
  SELECT id FROM namespaces WHERE user_id IS NULL LIMIT 1
),
c AS (
  SELECT fc.name, fc.id FROM field_constraints fc JOIN sys_ns ON fc.namespace_id = sys_ns.id
)
INSERT INTO applied_constraints (id, constraint_id, field_id, value)
SELECT gen_random_uuid(),
       (SELECT id FROM c WHERE c.name = v.cname),
       (SELECT id FROM f WHERE f.name = v.fname),
       v.val
FROM (VALUES
  ('name',               'min_length',  '1'),
  ('name',               'max_length',  '150'),
  ('sku',                'pattern',     '^[A-Z]{2}-\d{4}$'),
  ('price',              'gt',          '0'),
  ('sale_price',         'ge',          '0'),
  ('weight',             'ge',          '0'),
  ('weight',             'lt',          '1000'),
  ('quantity',           'ge',          '0'),
  ('min_order_quantity', 'ge',          '1'),
  ('max_order_quantity', 'le',          '1000'),
  ('discount_percent',   'ge',          '0'),
  ('discount_percent',   'le',          '100'),
  ('discount_percent',   'multiple_of', '5'),
  ('discount_amount',    'ge',          '0'),
  ('customer_name',      'min_length',  '1'),
  ('customer_name',      'max_length',  '100'),
  ('phone',              'min_length',  '7'),
  ('phone',              'max_length',  '15')
) AS v(fname, cname, val);

-- 4. Field validators
WITH u AS (
  SELECT id FROM users WHERE email = 'aleshiner@mail.ru'
),
ns AS (
  SELECT n.id FROM namespaces n JOIN u ON n.user_id = u.id WHERE n.name = 'Shop'
),
f AS (
  SELECT f.name, f.id FROM fields f JOIN ns ON f.namespace_id = ns.id
)
INSERT INTO applied_field_validators (id, field_id, template_id, parameters, position)
SELECT gen_random_uuid(),
       (SELECT id FROM f WHERE f.name = v.fname),
       (SELECT id FROM field_validator_templates WHERE name = v.tname),
       v.params::jsonb,
       v.pos
FROM (VALUES
  ('name',          'Trim',                 NULL,                                    0),
  ('name',          'Normalize Whitespace', NULL,                                    1),
  ('sku',           'Normalize Case',       '{"case": "upper"}',                     0),
  ('price',         'Round Decimal',        '{"places": "2"}',                       0),
  ('weight',        'Clamp to Range',       '{"min_value": "0", "max_value": "1000"}', 0),
  ('customer_name', 'Trim',                 NULL,                                    0),
  ('customer_name', 'Normalize Case',       '{"case": "title"}',                     1),
  ('customer_name', 'Trim To Length',       '{"max_length": "100"}',                 2)
) AS v(fname, tname, params, pos);

-- 5. Objects
WITH u AS (
  SELECT id FROM users WHERE email = 'aleshiner@mail.ru'
),
ns AS (
  SELECT n.id FROM namespaces n JOIN u ON n.user_id = u.id WHERE n.name = 'Shop'
)
INSERT INTO objects (id, namespace_id, user_id, name, description)
SELECT gen_random_uuid(), ns.id, u.id, v.name, v.descr
FROM u, ns, (VALUES
  ('Product',  'Shop product'),
  ('Customer', 'Shop customer')
) AS v(name, descr);

-- 6. Fields on objects
WITH u AS (
  SELECT id FROM users WHERE email = 'aleshiner@mail.ru'
),
ns AS (
  SELECT n.id FROM namespaces n JOIN u ON n.user_id = u.id WHERE n.name = 'Shop'
),
f AS (
  SELECT f.name, f.id FROM fields f JOIN ns ON f.namespace_id = ns.id
),
o AS (
  SELECT o.name, o.id FROM objects o JOIN ns ON o.namespace_id = ns.id
)
INSERT INTO fields_on_objects (id, object_id, field_id, optional, position, is_pk, appears)
SELECT gen_random_uuid(),
       (SELECT id FROM o WHERE o.name = v.obj),
       (SELECT id FROM f WHERE f.name = v.fname),
       v.opt,
       v.pos,
       v.pk,
       v.appears
FROM (VALUES
  -- Product (16 fields)
  ('Product', 'name',               false, 0,  false, 'both'),
  ('Product', 'sku',                false, 1,  false, 'both'),
  ('Product', 'price',              false, 2,  false, 'both'),
  ('Product', 'sale_price',         true,  3,  false, 'both'),
  ('Product', 'sale_end_date',      true,  4,  false, 'both'),
  ('Product', 'weight',             false, 5,  false, 'both'),
  ('Product', 'quantity',           false, 6,  false, 'both'),
  ('Product', 'min_order_quantity', false, 7,  false, 'both'),
  ('Product', 'max_order_quantity', true,  8,  false, 'both'),
  ('Product', 'discount_percent',   true,  9,  false, 'both'),
  ('Product', 'discount_amount',    true,  10, false, 'both'),
  ('Product', 'in_stock',           false, 11, false, 'both'),
  ('Product', 'product_url',        false, 12, false, 'both'),
  ('Product', 'release_date',       false, 13, false, 'both'),
  ('Product', 'created_at',         false, 14, false, 'response'),
  ('Product', 'tracking_id',        false, 15, true,  'both'),
  -- Customer (7 fields)
  ('Customer', 'customer_name',     false, 0,  false, 'both'),
  ('Customer', 'email',             false, 1,  true,  'both'),
  ('Customer', 'phone',             true,  2,  false, 'both'),
  ('Customer', 'date_of_birth',     false, 3,  false, 'both'),
  ('Customer', 'last_login_time',   false, 4,  false, 'both'),
  ('Customer', 'is_active',         false, 5,  false, 'both'),
  ('Customer', 'registered_at',     false, 6,  false, 'response')
) AS v(obj, fname, opt, pos, pk, appears);

-- 7. Model validators
WITH u AS (
  SELECT id FROM users WHERE email = 'aleshiner@mail.ru'
),
ns AS (
  SELECT n.id FROM namespaces n JOIN u ON n.user_id = u.id WHERE n.name = 'Shop'
),
o AS (
  SELECT o.name, o.id FROM objects o JOIN ns ON o.namespace_id = ns.id
)
INSERT INTO applied_model_validators (id, object_id, template_id, parameters, field_mappings, position)
SELECT gen_random_uuid(),
       (SELECT id FROM o WHERE o.name = v.obj),
       (SELECT id FROM model_validator_templates WHERE name = v.tname),
       v.params::jsonb,
       v.mappings::jsonb,
       v.pos
FROM (VALUES
  ('Product', 'Field Comparison',
   '{"operator": "<"}',
   '{"field_a": "min_order_quantity", "field_b": "max_order_quantity"}', 0),
  ('Product', 'Mutual Exclusivity',
   NULL,
   '{"field_a": "discount_percent", "field_b": "discount_amount"}', 1),
  ('Product', 'All Or None',
   NULL,
   '{"field_a": "sale_price", "field_b": "sale_end_date"}', 2),
  ('Product', 'Conditional Required',
   NULL,
   '{"trigger_field": "discount_percent", "dependent_field": "sale_price"}', 3),
  ('Customer', 'At Least One Required',
   NULL,
   '{"field_a": "email", "field_b": "phone"}', 0)
) AS v(obj, tname, params, mappings, pos);

-- 8. Relationships (Customer has_many Products, Product references Customer)
WITH u AS (
  SELECT id FROM users WHERE email = 'aleshiner@mail.ru'
),
ns AS (
  SELECT n.id FROM namespaces n JOIN u ON n.user_id = u.id WHERE n.name = 'Shop'
),
o AS (
  SELECT o.name, o.id FROM objects o JOIN ns ON o.namespace_id = ns.id
),
rel_fwd AS (
  INSERT INTO object_relationships (id, source_object_id, target_object_id, name, cardinality, is_inferred, position)
  VALUES (
    gen_random_uuid(),
    (SELECT id FROM o WHERE name = 'Customer'),
    (SELECT id FROM o WHERE name = 'Product'),
    'products',
    'has_many',
    false,
    0
  )
  RETURNING id
),
rel_inv AS (
  INSERT INTO object_relationships (id, source_object_id, target_object_id, name, cardinality, is_inferred, inverse_id, position)
  VALUES (
    gen_random_uuid(),
    (SELECT id FROM o WHERE name = 'Product'),
    (SELECT id FROM o WHERE name = 'Customer'),
    'customer',
    'references',
    true,
    (SELECT id FROM rel_fwd),
    0
  )
  RETURNING id
)
UPDATE object_relationships SET inverse_id = (SELECT id FROM rel_inv)
WHERE id = (SELECT id FROM rel_fwd);

-- 9. API
WITH u AS (
  SELECT id FROM users WHERE email = 'aleshiner@mail.ru'
),
ns AS (
  SELECT n.id FROM namespaces n JOIN u ON n.user_id = u.id WHERE n.name = 'Shop'
)
INSERT INTO apis (id, namespace_id, user_id, title, version, description, base_url, server_url, created_at, updated_at)
SELECT gen_random_uuid(), ns.id, u.id,
       'ShopApi', '1.0.0', 'Complete online shop API', '', '', now(), now()
FROM u, ns;

-- 10. Endpoints (9)
WITH u AS (
  SELECT id FROM users WHERE email = 'aleshiner@mail.ru'
),
ns AS (
  SELECT n.id FROM namespaces n JOIN u ON n.user_id = u.id WHERE n.name = 'Shop'
),
a AS (
  SELECT a.id FROM apis a JOIN u ON a.user_id = u.id WHERE a.title = 'ShopApi'
),
f AS (
  SELECT f.name, f.id FROM fields f JOIN ns ON f.namespace_id = ns.id
),
o AS (
  SELECT o.name, o.id FROM objects o JOIN ns ON o.namespace_id = ns.id
),
product_id  AS (SELECT id FROM o WHERE name = 'Product'),
customer_id AS (SELECT id FROM o WHERE name = 'Customer'),
tracking_id AS (SELECT id FROM f WHERE name = 'tracking_id'),
email_id    AS (SELECT id FROM f WHERE name = 'email')
INSERT INTO api_endpoints (id, api_id, method, path, description, tag_name, path_params,
                           object_id, use_envelope, response_shape)
VALUES
  -- GET /products (list)
  (gen_random_uuid(), (SELECT id FROM a), 'GET', '/products',
   'List all products', 'Products', '[]',
   (SELECT id FROM product_id), false, 'list'),

  -- GET /products/{tracking_id}
  (gen_random_uuid(), (SELECT id FROM a), 'GET', '/products/{tracking_id}',
   'Get product by tracking ID', 'Products',
   (SELECT json_build_array(json_build_object('name', 'tracking_id', 'fieldId', id::text))::jsonb FROM tracking_id),
   (SELECT id FROM product_id), false, 'object'),

  -- POST /products
  (gen_random_uuid(), (SELECT id FROM a), 'POST', '/products',
   'Create a product', 'Products', '[]',
   (SELECT id FROM product_id), false, 'object'),

  -- PUT /items/{tracking_id}
  (gen_random_uuid(), (SELECT id FROM a), 'PUT', '/items/{tracking_id}',
   'Update a product', 'Products',
   (SELECT json_build_array(json_build_object('name', 'tracking_id', 'fieldId', id::text))::jsonb FROM tracking_id),
   (SELECT id FROM product_id), false, 'object'),

  -- DELETE /products/{tracking_id}
  (gen_random_uuid(), (SELECT id FROM a), 'DELETE', '/products/{tracking_id}',
   'Delete a product', 'Products',
   (SELECT json_build_array(json_build_object('name', 'tracking_id', 'fieldId', id::text))::jsonb FROM tracking_id),
   NULL, false, 'object'),

  -- GET /customers (list)
  (gen_random_uuid(), (SELECT id FROM a), 'GET', '/customers',
   'List all customers', 'Customers', '[]',
   (SELECT id FROM customer_id), false, 'list'),

  -- POST /customers
  (gen_random_uuid(), (SELECT id FROM a), 'POST', '/customers',
   'Create a customer', 'Customers', '[]',
   (SELECT id FROM customer_id), false, 'object'),

  -- GET /customers/{email}
  (gen_random_uuid(), (SELECT id FROM a), 'GET', '/customers/{email}',
   'Get customer by email', 'Customers',
   (SELECT json_build_array(json_build_object('name', 'email', 'fieldId', id::text))::jsonb FROM email_id),
   (SELECT id FROM customer_id), false, 'object'),

  -- PATCH /customers/{email}
  (gen_random_uuid(), (SELECT id FROM a), 'PATCH', '/customers/{email}',
   'Update a customer by email', 'Customers',
   (SELECT json_build_array(json_build_object('name', 'email', 'fieldId', id::text))::jsonb FROM email_id),
   (SELECT id FROM customer_id), false, 'object');

COMMIT;
