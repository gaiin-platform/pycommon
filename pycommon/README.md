# PyCommon Validation and Authorization System for Each Service

This README explains how to use the pycommon library for request validation and authorization in your Lambda functions.

## Overview

The pycommon system provides a decorator-based approach to validate incoming requests and check user permissions. It consists of several key components that work together to ensure secure and validated API endpoints.

## Setup Requirements

### 1. Install PyCommon

Add the GitHub dependency to your `requirements.txt`:

```txt
git+https://github.com/gaiin-platform/pycommon.git@pre-release/v0.0.1
```

> **Note: This GitHub dependency URL is subject to change.**

### 2. Required Environment Variables

The system requires several environment variables to be set:

- `OAUTH_ISSUER_BASE_URL` - OAuth provider's base URL
- `OAUTH_AUDIENCE` - OAuth audience identifier
- `ACCOUNTS_DYNAMO_TABLE` - DynamoDB table for user accounts
- `API_KEYS_DYNAMODB_TABLE` - DynamoDB table for API keys
- `COST_CALCULATIONS_DYNAMO_TABLE` - DynamoDB table for rate limiting

## Core Components

### 1. Schema Definitions

Each endpoint must have its schema defined in a separate file within the `schemata/` folder.

**Example: `schemata/add_charge_schema.py`**
```python
add_charge_schema = {
    "type": "object",
    "properties": {
        "accountId": {"type": "string"},
        "charge": {"type": "number"},
        "description": {"type": "string"},
        "details": {"type": "object"},
    },
    "required": ["accountId", "charge", "description", "details"],
}
```

### 2. Validation Rules Registration

Register your schema in `schemata/schema_validation_rules.py`:

```python
from .add_charge_schema import add_charge_schema

rules = {
    "validators": {
        "/state/accounts/charge": {"create_charge": add_charge_schema},
        # ... other routes
    },
    "api_validators": {
        "/state/accounts/charge": {"create_charge": add_charge_schema},
        # ... other routes for API access
    },
}
```

**Key Points:**
- `validators`: Used for OAuth token-based access
- `api_validators`: Used for API key-based access
- The path must match your endpoint exactly
- The operation name (e.g., `"create_charge"`) must match what you use in the `@validated` decorator

### 3. Permission Definitions

Define permissions in `schemata/permissions.py`:

```python
def can_save(user, data):
    return True  # Implement your permission logic

permissions_by_state_type = {
    "/state/accounts/charge": {"create_charge": can_save},
    # ... other routes
}
```

### 4. Function Implementation

In your Lambda function file, import the required components and use the decorator:

```python
from pycommon.authz import validated, setup_validated
from schemata.schema_validation_rules import rules
from schemata.permissions import get_permission_checker

# Initialize the validation system
setup_validated(rules, get_permission_checker)

@validated("create_charge")
def charge_request(event, context, user, name, data):
    account_id = data["data"]["accountId"]
    charge = data["data"]["charge"]
    description = data["data"]["description"]
    details = data["data"]["details"]
    
    # Your business logic here
    return create_charge(account_id, charge, description, user, details)
```

## How the @validated Decorator Works

The `@validated("operation_name")` decorator creates a connection between:

1. **The operation string** (e.g., `"create_charge"`)
2. **The validation rules** in `schema_validation_rules.py`
3. **The permission functions** in `permissions.py`

### Example Mapping:

```python
# In your function
@validated("create_charge")
def charge_request(event, context, user, name, data):
    # ...

# In schema_validation_rules.py
rules = {
    "validators": {
        "/state/accounts/charge": {"create_charge": add_charge_schema}
    }
}

# In permissions.py
permissions_by_state_type = {
    "/state/accounts/charge": {"create_charge": can_save}
}
```

When a request comes to `/state/accounts/charge`, the system:
1. Extracts the path from the request
2. Looks up the schema using the path + operation name
3. Validates the request data against the schema
4. Checks permissions using the path + operation name
5. Calls your function if everything passes

## API Access Types

### Adding Custom Access Types

If you need to restrict certain endpoints to specific API access types:

```python
from pycommon.authz import validated, setup_validated, add_api_access_types
from pycommon.const import APIAccessType

# Add additional access types
add_api_access_types([APIAccessType.FILE_UPLOAD.value])

setup_validated(rules, get_permission_checker)
```

### Available Access Types

From `pycommon.const`:
- `FULL_ACCESS` - Full system access
- `CHAT` - Chat functionality
- `ASSISTANTS` - AI assistants
- `FILE_UPLOAD` - File upload operations
- `SHARE` - Sharing functionality
- `DUAL_EMBEDDING` - Dual embedding features

## Authentication Types

The system supports two authentication methods:

### 1. OAuth Tokens (JWT)
- Standard Bearer tokens
- Validated against OAuth provider
- User permissions based on accounts

### 2. API Keys
- Prefixed with `amp-`
- Rate limiting and access type controls

## Rate Limiting

Rate limiting is automatically handled based on:
- User account settings
- API key configurations
- Configurable periods: Unlimited, Daily, Hourly, Monthly

## Error Handling

The system automatically handles:
- **401 Unauthorized**: Invalid or missing tokens
- **400 Bad Request**: Schema validation failures
- **403 Forbidden**: Permission denied

## Best Practices

1. **One schema per file**: Keep each endpoint schema in its own file
2. **Consistent naming**: Use the same operation name across validation rules, permissions, and decorators
3. **Minimal permissions**: Only grant necessary permissions in permission functions
4. **Environment variables**: Always use environment variables for sensitive configuration
5. **Error logging**: The system provides detailed logging for debugging

This system provides a robust, secure, and maintainable way to handle API validation and authorization in your Lambda functions.



