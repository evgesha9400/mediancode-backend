"""Canonical Shop API seed data — final desired state of all entities.

All references use symbolic names resolved to UUIDs at runtime by the runner.
"""

# ---------------------------------------------------------------------------
# Fields
# ---------------------------------------------------------------------------

PRODUCT_FIELDS = [
    {
        "name": "name",
        "type": "str",
        "constraints": [("min_length", "1"), ("max_length", "150")],
        "validators": [("Trim", None), ("Normalize Whitespace", None)],
    },
    {
        "name": "sku",
        "type": "str",
        "constraints": [("pattern", r"^[A-Z]{2}-\d{4}$")],
        "validators": [("Normalize Case", {"case": "upper"})],
    },
    {
        "name": "price",
        "type": "Decimal",
        "constraints": [("gt", "0")],
        "validators": [("Round Decimal", {"places": "2"})],
    },
    {
        "name": "sale_price",
        "type": "Decimal",
        "constraints": [("ge", "0")],
        "validators": [],
    },
    {
        "name": "sale_end_date",
        "type": "date",
        "constraints": [],
        "validators": [],
    },
    {
        "name": "weight",
        "type": "float",
        "constraints": [("ge", "0"), ("lt", "1000")],
        "validators": [("Clamp to Range", {"min_value": "0", "max_value": "1000"})],
    },
    {
        "name": "quantity",
        "type": "int",
        "constraints": [("ge", "0")],
        "validators": [],
    },
    {
        "name": "min_order_quantity",
        "type": "int",
        "constraints": [("ge", "1")],
        "validators": [],
    },
    {
        "name": "max_order_quantity",
        "type": "int",
        "constraints": [("le", "1000")],
        "validators": [],
    },
    {
        "name": "discount_percent",
        "type": "int",
        "constraints": [("ge", "0"), ("le", "100"), ("multiple_of", "5")],
        "validators": [],
    },
    {
        "name": "discount_amount",
        "type": "Decimal",
        "constraints": [("ge", "0")],
        "validators": [],
    },
    {
        "name": "in_stock",
        "type": "bool",
        "constraints": [],
        "validators": [],
    },
    {
        "name": "product_url",
        "type": "HttpUrl",
        "constraints": [],
        "validators": [],
    },
    {
        "name": "release_date",
        "type": "date",
        "constraints": [],
        "validators": [],
    },
    {
        "name": "created_at",
        "type": "datetime",
        "constraints": [],
        "validators": [],
    },
    {
        "name": "tracking_id",
        "type": "uuid",
        "constraints": [],
        "validators": [],
    },
]

CUSTOMER_FIELDS = [
    {
        "name": "id",
        "type": "int",
        "constraints": [],
        "validators": [],
    },
    {
        "name": "customer_name",
        "type": "str",
        "constraints": [("min_length", "1"), ("max_length", "100")],
        "validators": [
            ("Trim", None),
            ("Normalize Case", {"case": "title"}),
            ("Trim To Length", {"max_length": "100"}),
        ],
    },
    {
        "name": "email",
        "type": "EmailStr",
        "constraints": [],
        "validators": [],
    },
    {
        "name": "phone",
        "type": "str",
        "constraints": [("min_length", "7"), ("max_length", "15")],
        "validators": [],
    },
    {
        "name": "date_of_birth",
        "type": "date",
        "constraints": [],
        "validators": [],
    },
    {
        "name": "last_login_time",
        "type": "time",
        "constraints": [],
        "validators": [],
    },
    {
        "name": "is_active",
        "type": "bool",
        "constraints": [],
        "validators": [],
    },
    {
        "name": "registered_at",
        "type": "datetime",
        "constraints": [],
        "validators": [],
    },
]

ALL_FIELDS = PRODUCT_FIELDS + CUSTOMER_FIELDS

PRODUCT_OPTIONAL = {
    "sale_price",
    "sale_end_date",
    "max_order_quantity",
    "discount_percent",
    "discount_amount",
}

CUSTOMER_OPTIONAL = {"phone"}

# ---------------------------------------------------------------------------
# Objects
# ---------------------------------------------------------------------------

PRODUCT_OBJECT = {
    "name": "Product",
    "description": "Shop product",
    "fields": [
        {
            "field_name": "tracking_id",
            "role": "pk",
        },
        {
            "field_name": "name",
            "optional": False,
            "role": "writable",
        },
        {
            "field_name": "sku",
            "optional": False,
            "role": "writable",
        },
        {
            "field_name": "price",
            "optional": False,
            "role": "writable",
        },
        {
            "field_name": "sale_price",
            "optional": True,
            "role": "writable",
        },
        {
            "field_name": "sale_end_date",
            "optional": True,
            "role": "writable",
        },
        {
            "field_name": "weight",
            "optional": False,
            "role": "writable",
        },
        {
            "field_name": "quantity",
            "optional": False,
            "role": "writable",
        },
        {
            "field_name": "min_order_quantity",
            "optional": False,
            "role": "writable",
        },
        {
            "field_name": "max_order_quantity",
            "optional": True,
            "role": "writable",
        },
        {
            "field_name": "discount_percent",
            "optional": True,
            "role": "writable",
        },
        {
            "field_name": "discount_amount",
            "optional": True,
            "role": "writable",
        },
        {
            "field_name": "in_stock",
            "optional": False,
            "role": "writable",
        },
        {
            "field_name": "product_url",
            "optional": False,
            "role": "writable",
        },
        {
            "field_name": "release_date",
            "optional": False,
            "role": "writable",
        },
        {
            "field_name": "created_at",
            "role": "created_timestamp",
        },
    ],
    "validators": [
        {
            "template": "Field Comparison",
            "parameters": {"operator": "<"},
            "field_mappings": {
                "field_a": "min_order_quantity",
                "field_b": "max_order_quantity",
            },
        },
        {
            "template": "Mutual Exclusivity",
            "parameters": None,
            "field_mappings": {
                "field_a": "discount_percent",
                "field_b": "discount_amount",
            },
        },
        {
            "template": "All Or None",
            "parameters": None,
            "field_mappings": {
                "field_a": "sale_price",
                "field_b": "sale_end_date",
            },
        },
        {
            "template": "Conditional Required",
            "parameters": None,
            "field_mappings": {
                "trigger_field": "discount_percent",
                "dependent_field": "sale_price",
            },
        },
    ],
}

CUSTOMER_OBJECT = {
    "name": "Customer",
    "description": "Shop customer",
    "fields": [
        {
            "field_name": "id",
            "role": "pk",
        },
        {
            "field_name": "customer_name",
            "optional": False,
            "role": "writable",
        },
        {
            "field_name": "email",
            "optional": False,
            "role": "writable",
        },
        {
            "field_name": "phone",
            "optional": True,
            "role": "writable",
        },
        {
            "field_name": "date_of_birth",
            "optional": False,
            "role": "writable",
        },
        {
            "field_name": "last_login_time",
            "optional": False,
            "role": "writable",
        },
        {
            "field_name": "is_active",
            "optional": False,
            "role": "writable",
        },
        {
            "field_name": "registered_at",
            "role": "created_timestamp",
        },
    ],
    "validators": [],
}

OBJECTS = [PRODUCT_OBJECT, CUSTOMER_OBJECT]

# ---------------------------------------------------------------------------
# Relationship
# ---------------------------------------------------------------------------

RELATIONSHIP = {
    "source_object": "Customer",
    "target_object": "Product",
    "name": "products",
    "cardinality": "has_many",
}

# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

API = {
    "title": "ShopApi",
    "version": "1.0.0",
    "description": "Complete online shop API",
}

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

ENDPOINTS = [
    {
        "method": "GET",
        "path": "/products",
        "description": "List all products",
        "tag": "Products",
        "object": "Product",
        "path_params": [],
        "response_shape": "list",
    },
    {
        "method": "GET",
        "path": "/products/{tracking_id}",
        "description": "Get product by tracking ID",
        "tag": "Products",
        "object": "Product",
        "path_params": [{"name": "tracking_id", "field": "tracking_id"}],
        "response_shape": "object",
    },
    {
        "method": "POST",
        "path": "/products",
        "description": "Create a product",
        "tag": "Products",
        "object": "Product",
        "path_params": [],
        "response_shape": "object",
    },
    {
        "method": "PUT",
        "path": "/items/{tracking_id}",
        "description": "Update a product",
        "tag": "Products",
        "object": "Product",
        "path_params": [{"name": "tracking_id", "field": "tracking_id"}],
        "response_shape": "object",
    },
    {
        "method": "DELETE",
        "path": "/products/{tracking_id}",
        "description": "Delete a product",
        "tag": "Products",
        "object": None,
        "path_params": [{"name": "tracking_id", "field": "tracking_id"}],
        "response_shape": "object",
    },
    {
        "method": "GET",
        "path": "/customers",
        "description": "List all customers",
        "tag": "Customers",
        "object": "Customer",
        "path_params": [],
        "response_shape": "list",
    },
    {
        "method": "POST",
        "path": "/customers",
        "description": "Create a customer",
        "tag": "Customers",
        "object": "Customer",
        "path_params": [],
        "response_shape": "object",
    },
    {
        "method": "GET",
        "path": "/customers/{id}",
        "description": "Get customer by ID",
        "tag": "Customers",
        "object": "Customer",
        "path_params": [{"name": "id", "field": "id"}],
        "response_shape": "object",
    },
    {
        "method": "PATCH",
        "path": "/customers/{id}",
        "description": "Update a customer by ID",
        "tag": "Customers",
        "object": "Customer",
        "path_params": [{"name": "id", "field": "id"}],
        "response_shape": "object",
    },
]
