# PyCommon

Common Python utilities for AWS Lambda and API operations.

## Installation

Install directly from GitHub:

```bash
pip install git+https://github.com/gaiin-platform/pycommon.git
```

## Features

- **API Utilities**: Common patterns for AWS Lambda API operations
- **Authentication & Authorization**: JWT token handling and user validation
- **Encoders**: JSON serialization with Decimal support
- **Decorators**: Environment variable validation and other utilities
- **Exception Handling**: Custom HTTP exceptions
- **LLM Integration**: Large Language Model utilities
- **Tools**: Operation decorators and utilities

## Quick Start

```python
import pycommon

# Use authentication
from pycommon import validated, get_claims

# Use encoders
from pycommon import dumps_safe, dumps_smart

# Use exceptions
from pycommon import HTTPBadRequest, HTTPUnauthorized
```

## Development

For local development:

```bash
# 1. Clone the repository
git clone https://github.com/gaiin-platform/pycommon.git
cd pycommon

# 2. Install in editable mode with development dependencies
pip install -e .[dev]
```

The `-e` flag installs in "editable" mode so your code changes take effect immediately.
The `[dev]` installs extra tools like pytest, black, mypy, etc.

Run tests:

```bash
make test
```

## License

MIT License - see LICENSE file for details. 