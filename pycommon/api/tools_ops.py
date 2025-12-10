"""
Auto-registration module for Lambda operations.

Handles discovery and registration of @api_tool decorated functions within
Lambda environments.
"""

import os
from typing import Any, Dict, List, Optional

from pycommon.dal.providers.aws.resource_perms import DynamoDBOperation
from pycommon.decorators import required_env_vars
from pycommon.logger import getLogger
from pycommon.tools.ops import (
    OperationModel,
    extract_ops_from_file,
    find_python_files,
    write_ops,
)

logger = getLogger("tools_ops")


@required_env_vars(
    {
        "OPS_DYNAMODB_TABLE": [
            DynamoDBOperation.PUT_ITEM,
            DynamoDBOperation.UPDATE_ITEM,
            DynamoDBOperation.SCAN,
        ]
    }
)
def api_tools_register_handler(
    include_dirs: List[str] = None,
    command: str = "ls",
    data: Optional[Dict[str, Any]] = None,
    current_user: str = "system",
) -> Dict[str, Any]:
    """
    Simple function for listing or registering @api_tool operations.

    Args:
        include_dirs: List of directories to include in scanning
        command: "ls" or "register"
        data: Optional configuration data
        current_user: User performing the operation

    Returns:
        Properly formatted HTTP response
    """
    if include_dirs is None:
        include_dirs = []
    if data is None:
        data = {}

    try:
        # Route to appropriate function
        if command == "ls":
            logger.info("Listing operations")
            result = list_lambda_ops(include_dirs)
        elif command == "register":
            logger.info("Registering operations")
            result = register_lambda_ops(include_dirs, data, current_user)
        else:
            result = {
                "success": False,
                "error": f"Unknown command: {command}. Use 'ls' or 'register'",
                "operations_count": 0,
            }

        # Return the result directly (no HTTP wrapper)
        return result

    except Exception as e:
        return {
            "success": False,
            "error": f"Handler failed: {str(e)}",
            "operations_count": 0,
        }


def register_lambda_ops(
    include_dirs: List[str],
    data: Optional[Dict[str, Any]] = None,
    current_user: str = "system",
) -> Dict[str, Any]:
    """
    Register all @api_tool operations found in the specified directories.

    Args:
        include_dirs: List of directories to include in scanning
        data: Optional configuration data
        current_user: User performing the registration

    Returns:
        Dictionary with registration results

    Note:
        OPS_DYNAMODB_TABLE environment variable is validated by @required_env_vars
        decorator on the parent function.
    """
    if data is None:
        data = {}

    additional_tags = data.get("additional_tags", [])

    try:
        # Environment variable guaranteed by @required_env_vars decorator
        table_name = os.environ["OPS_DYNAMODB_TABLE"]

        logger.info(f"Register: Using DynamoDB table: {table_name}")

        # Scan specified directories
        code_dir = "/var/task"  # Lambda runtime directory
        logger.info(f"Register: Scanning directory: {code_dir}")
        logger.info(f"Register: Including directories: {include_dirs}")

        # Check if directory exists (same as list function)
        if not os.path.exists(code_dir):
            logger.warning(f"Register: Directory {code_dir} does not exist!")
            # Fallback to current working directory
            code_dir = os.getcwd()
            logger.info(f"Register: Using current working directory: {code_dir}")

        all_ops = _scan_lambda_codebase(code_dir, include_dirs)
        logger.info(f"Register: Found {len(all_ops)} operations after scanning")

        if not all_ops:
            return {
                "success": True,
                "message": "No operations found",
                "operations_count": 0,
                "operations": [],
            }

        # Use simple tags
        tags = ["all"] + additional_tags

        logger.info(
            f"Register: About to register {len(all_ops)} operations with "
            f"tags: {tags}"
        )
        for op in all_ops:
            logger.debug(f"  - {op.name} ({op.url})")

        # Register using existing write_ops function
        write_ops(current_user=current_user, tags=tags, ops=all_ops)

        return {
            "success": True,
            "message": f"Successfully registered {len(all_ops)} operations",
            "operations_count": len(all_ops),
            "operations": [
                {
                    "name": op.name,
                    "url": op.url,
                    "method": op.method,
                    "type": op.type,
                }
                for op in all_ops
            ],
        }

    except Exception as e:
        logger.error(f"Register: Error occurred: {str(e)}")
        return {
            "success": False,
            "error": f"Registration failed: {str(e)}",
            "operations_count": 0,
        }


def list_lambda_ops(include_dirs: List[str]) -> Dict[str, Any]:
    """
    List all @api_tool operations found in the specified directories.

    Args:
        include_dirs: List of directories to include in scanning

    Returns:
        Dictionary with discovered operations
    """
    try:
        # Scan specified directories
        code_dir = "/var/task"  # Lambda runtime directory
        logger.info(f"Scanning directory: {code_dir}")
        logger.info(f"Including directories: {include_dirs}")

        # Check if directory exists
        if not os.path.exists(code_dir):
            logger.warning(f"Directory {code_dir} does not exist!")
            # Fallback to current working directory
            code_dir = os.getcwd()
            logger.info(f"Using current working directory: {code_dir}")

        all_ops = _scan_lambda_codebase(code_dir, include_dirs)
        logger.info(f"Found {len(all_ops)} operations after scanning")

        if not all_ops:
            return {
                "success": True,
                "message": "No operations found",
                "operations_count": 0,
                "operations": [],
                "debug_info": {
                    "scanned_directory": code_dir,
                    "included_dirs": include_dirs,
                },
            }

        # Format operations for display
        formatted_ops = []
        for op in all_ops:
            op_info = {
                "name": op.name,
                "url": op.url,
                "method": op.method,
                "description": op.description,
                "type": op.type,
                "tags": op.tags,
                "id": op.id,
            }
            if op.parameters:
                op_info["parameters"] = op.parameters
            if op.output:
                op_info["output"] = op.output
            if op.permissions:
                op_info["permissions"] = op.permissions
            formatted_ops.append(op_info)

        return {
            "success": True,
            "message": f"Found {len(all_ops)} operations",
            "operations_count": len(all_ops),
            "operations": formatted_ops,
        }

    except Exception as e:
        logger.error(f"Error in list_lambda_ops: {str(e)}")
        return {
            "success": False,
            "error": f"Listing failed: {str(e)}",
            "operations_count": 0,
        }


def _scan_lambda_codebase(
    directory: str, include_dirs: List[str]
) -> List[OperationModel]:
    """
    Scan codebase for operations, including specified directories.
    Reuses existing tools/ops.py functions.

    Args:
        directory: Root directory to scan (typically /var/task for Lambda)
        include_dirs: List of directories to include in scanning.
                     If empty, scans all files except those in excluded directories.

    Returns:
        List of OperationModel objects found

    Raises:
        Exception: If file system operations or AST parsing fails
    """
    logger.info(f"Starting scan of directory: {directory}")

    # Get all Python files using existing function
    all_python_files = find_python_files(directory)
    logger.info(f"Found {len(all_python_files)} Python files total")

    # Directories to exclude when include_dirs is empty (exclusion-based approach)
    EXCLUDED_DIRS = {
        "schemata",
        "node_modules",
        "__pycache__",
        ".git",
        ".serverless",
        "venv",
        "env",
        ".pytest_cache",
        ".vscode",
        ".idea",
        "tests",
    }

    # Filter files based on include_dirs
    filtered_files = []

    if not include_dirs:
        # Exclusion-based: include all files except those in excluded directories
        for file_path in all_python_files:
            should_exclude = False
            for exclude_dir in EXCLUDED_DIRS:
                if f"/{exclude_dir}/" in file_path or file_path.endswith(
                    f"/{exclude_dir}"
                ):
                    should_exclude = True
                    break

            if not should_exclude:
                filtered_files.append(file_path)
                logger.debug(f"Including file: {file_path}")

        logger.info(f"Using exclusion-based filtering (excluded: {EXCLUDED_DIRS})")
    else:
        # Inclusion-based: only include files in specified directories
        for file_path in all_python_files:
            should_include = False
            for include_dir in include_dirs:
                if f"/{include_dir}/" in file_path or file_path.endswith(
                    f"/{include_dir}"
                ):
                    should_include = True
                    break

            if should_include:
                filtered_files.append(file_path)
                logger.debug(f"Including file: {file_path}")

    logger.info(f"After filtering, scanning {len(filtered_files)} files for operations")

    # Extract operations from each file using existing function
    all_ops: List[OperationModel] = []
    for file_path in filtered_files:
        try:
            logger.debug(f"Extracting operations from: {file_path}")
            file_ops = extract_ops_from_file(file_path)
            logger.debug(f"Found {len(file_ops)} operations in {file_path}")
            for op in file_ops:
                logger.debug(
                    f"  - Operation: {op.name} ({op.method} {op.url}) "
                    f"tags: {op.tags}"
                )
                logger.debug(f"Pretty format: {op.name} ({op.method} {op.url})")
            all_ops.extend(file_ops)
        except Exception as e:
            logger.warning(f"Warning: Could not parse {file_path}: {e}")

    logger.info(f"Total operations found: {len(all_ops)}")
    return all_ops
