# PyCommon

Common Python utilities for AWS Lambda and API operations with comprehensive validation, authorization, and testing framework.

## Installation

Install directly from GitHub:

```bash
pip install git+https://github.com/gaiin-platform/pycommon.git
```

## Features

- **API Utilities**: Common patterns for AWS Lambda API operations
- **Authentication & Authorization**: JWT token handling and user validation with `@validated` decorator
- **Encoders**: JSON serialization with Decimal support
- **Decorators**: Environment variable validation and other utilities
- **Exception Handling**: Custom HTTP exceptions
- **LLM Integration**: Large Language Model utilities
- **Tools**: Operation decorators and utilities
- **Comprehensive Testing**: 100% test coverage requirement with pytest

## Quick Start

```python
import pycommon

# Use authentication
from pycommon import validated, get_claims

# Use encoders
from pycommon import dumps_safe, dumps_smart

# Use exceptions
from pycommon import HTTPBadRequest, HTTPUnauthorized

# Use API utilities
from pycommon.api import get_credentials, send_email, verify_user_as_admin
```

## Development Setup

### 1. Clone and Install

```bash
# Clone the repository
git clone https://github.com/gaiin-platform/pycommon.git
cd pycommon

# Install in editable mode with development dependencies
pip install -e .[dev]
```

The `-e` flag installs in "editable" mode so your code changes take effect immediately.
The `[dev]` installs extra tools like pytest, black, flake8, etc.

### 2. Development Commands

We use a Makefile for common development tasks:

```bash
# Run all tests (required to pass)
make test

# Run tests with coverage report (must maintain 100% coverage)
make coverage

# Format code with black (required before commits)
make format

# Run linting with flake8 (must pass)
make lint

# Clean up coverage files
make clean

# See all available commands
make help
```

## Code Quality Standards

### Testing Requirements

**Every new file MUST have corresponding tests with 100% coverage.**

#### Example: Adding a New API Function

If you add a new file like `pycommon/api/auth_admin.py`:

```python
# pycommon/api/auth_admin.py
def verify_user_as_admin(access_token: str, purpose: str) -> bool:
    """
    Verify if the authenticated user has admin privileges.
    
    Args:
        access_token: Bearer token for authentication
        purpose: The purpose/context for admin verification
        
    Returns:
        bool: True if user is verified as admin, False otherwise
    """
    # Implementation here...
```

You MUST create `tests/test_apis/test_auth_admin.py`:

```python
# tests/test_apis/test_auth_admin.py
import os
from unittest.mock import MagicMock, patch
from pycommon.api.auth_admin import verify_user_as_admin

@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.auth_admin.requests.post")
def test_verify_user_as_admin_success(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True, "isAdmin": True}
    mock_post.return_value = mock_response

    result = verify_user_as_admin("test_token", "admin_check")
    assert result is True

# Add more tests for all code paths...
```

#### Test Coverage Requirements

- **100% line coverage** - Every line must be tested
- **All code paths** - Test success, failure, and exception cases
- **Edge cases** - Test boundary conditions and error scenarios
- **Mocking** - Mock external dependencies (requests, boto3, etc.)

#### Test Structure

```
tests/
├── test_api_utils.py           # Tests for pycommon/api_utils.py
├── test_authz.py              # Tests for pycommon/authz.py
├── test_encoders.py           # Tests for pycommon/encoders.py
└── test_apis/                 # Tests for pycommon/api/ modules
    ├── test_auth_admin.py     # Tests for pycommon/api/auth_admin.py
    ├── test_credentials.py    # Tests for pycommon/api/credentials.py
    └── test_ses_email.py      # Tests for pycommon/api/ses_email.py
```

### Code Formatting and Linting

#### Before Every Commit:

```bash
# Format your code
make format

# Check linting
make lint

# Run tests
make test

# Verify coverage
make coverage
```

#### Standards:

- **Black formatting** - All code must be formatted with black
- **Flake8 compliance** - No linting errors allowed
- **Type hints** - Use type hints for function parameters and returns
- **Docstrings** - All public functions must have docstrings

## Implementation Guidelines

### Adding New API Functions

1. **Create the function** in appropriate `pycommon/api/` file
2. **Add comprehensive tests** in `tests/test_apis/`
3. **Update imports** in `pycommon/api/__init__.py` if needed
4. **Run quality checks**:
   ```bash
   make format
   make lint
   make test
   make coverage
   ```

### Function Documentation

Every function must have proper docstrings:

```python
def example_function(param1: str, param2: int) -> bool:
    """
    Brief description of what the function does.

    Args:
        param1: Description of first parameter
        param2: Description of second parameter

    Returns:
        bool: Description of return value

    Raises:
        ValueError: When parameter validation fails
        HTTPException: When API call fails
    """
```

### Error Handling

- Use appropriate exception types from `pycommon.exceptions`
- Log errors with descriptive messages
- Return meaningful error responses
- Handle network timeouts and API failures gracefully

### Testing Best Practices

#### Mock External Dependencies

```python
# Mock HTTP requests
@patch("pycommon.api.auth_admin.requests.post")
def test_api_call(mock_post):
    mock_post.return_value.status_code = 200
    # Test implementation

# Mock environment variables
@patch.dict(os.environ, {"API_BASE_URL": "http://test.com"})
def test_with_env_var():
    # Test implementation

# Mock AWS services
@patch("pycommon.api.credentials.boto3.session.Session")
def test_aws_call(mock_session):
    # Test implementation
```

#### Test All Code Paths

```python
def test_success_case():
    # Test when everything works

def test_failure_case():
    # Test when API returns error

def test_exception_case():
    # Test when network/parsing fails

def test_edge_cases():
    # Test boundary conditions
```

## Validation and Authorization System

PyCommon provides a comprehensive validation system for Lambda functions:

### Schema-Based Validation

```python
from pycommon.authz import validated, setup_validated

# Define your schema
schema = {
    "type": "object",
    "properties": {
        "accountId": {"type": "string"},
        "charge": {"type": "number"}
    },
    "required": ["accountId", "charge"]
}

# Use the validator
@validated("create_charge")
def lambda_handler(event, context, user, name, data):
    # Your validated data is in 'data'
    return {"success": True}
```

### Authentication Types

- **OAuth Tokens (JWT)**: Standard Bearer tokens
- **API Keys**: Prefixed with `amp-`, with rate limiting

### Access Control

Use `APIAccessType` enum for granular permissions:

```python
from pycommon.const import APIAccessType

# Available access types:
# FULL_ACCESS, CHAT, ASSISTANTS, FILE_UPLOAD, SHARE, etc.
```

## Contributing

### Pull Request Process

1. **Create feature branch** from main
2. **Implement changes** following guidelines above
3. **Add comprehensive tests** (100% coverage required)
4. **Run quality checks**:
   ```bash
   make format
   make lint  
   make test
   make coverage
   ```
5. **Submit PR** with clear description
6. **Address review feedback**

### Quality Gates

All PRs must pass:

- ✅ **100% test coverage** (`make coverage`)
- ✅ **All tests passing** (`make test`)
- ✅ **Code formatting** (`make format`)
- ✅ **Linting clean** (`make lint`)
- ✅ **Type hints** for new functions
- ✅ **Docstrings** for public APIs

## Environment Variables

Required for testing and development:

```bash
# OAuth configuration
OAUTH_ISSUER_BASE_URL=https://your-oauth-provider.com
OAUTH_AUDIENCE=your-audience

# DynamoDB tables
ACCOUNTS_DYNAMO_TABLE=accounts-table
API_KEYS_DYNAMODB_TABLE=api-keys-table
COST_CALCULATIONS_DYNAMO_TABLE=cost-calculations-table

# API endpoints
API_BASE_URL=https://your-api.com
```

## License

MIT License - see LICENSE file for details. 