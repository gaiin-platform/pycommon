import argparse
import ast
import os
import sys
import uuid
from typing import List, Optional

import boto3
import yaml
from boto3.dynamodb.conditions import Key
from boto3.dynamodb.types import TypeSerializer
from pydantic import BaseModel, ValidationError, field_validator

dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
serializer = TypeSerializer()

IGNORED_DIRECTORIES = {"node_modules", "venv", "__pycache__"}


def op(tags=None, path="", name="", description="", params=None, method="POST"):
    # This is the actual decorator
    def decorator(func):
        def wrapper(*args, **kwargs):
            # You can do something with tags, name, description, and params here
            print(f"Path: {path}")
            print(f"Tags: {tags}")
            print(f"Name: {name}")
            print(f"Method: {method}")
            print(f"Description: {description}")
            print(f"Params: {params}")
            # Call the actual function
            result = func(*args, **kwargs)
            return result

        return wrapper

    return decorator


# Pydantic models
class OperationModel(BaseModel):
    description: str
    id: str
    includeAccessToken: bool
    method: str
    name: str
    tags: List[str]
    type: str = "built_in"  # Default for backward compatibility
    url: str
    parameters: Optional[dict] = None  # Input schema
    output: Optional[dict] = None  # Output schema
    permissions: Optional[dict] = None

    @field_validator("method")
    def validate_method(cls, v):
        allowed_methods = {"GET", "POST", "PUT", "DELETE", "PATCH"}
        if v.upper() not in allowed_methods:
            raise ValueError(f"Method must be one of {allowed_methods}")
        return v.upper()


def find_python_files(directory: str) -> List[str]:
    python_files = []
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRECTORIES]
        for file in files:
            if file.endswith(".py"):
                python_files.append(os.path.join(root, file))
    return python_files


def extract_dict(ast_node):
    """Extract dictionary from AST Dict node."""
    return {key.s: value.s for key, value in zip(ast_node.keys, ast_node.values)}


def extract_complex_dict(ast_node):
    """Extract complex dictionary from AST Dict node."""
    result = {}
    for key, value in zip(ast_node.keys, ast_node.values):
        if isinstance(value, ast.Dict):
            result[key.s] = extract_complex_dict(value)
        elif isinstance(value, ast.List):
            result[key.s] = extract_list(value)
        elif isinstance(value, ast.Constant):
            result[key.s] = value.value
        else:
            # Try to get a literal value or default to string representation
            try:
                result[key.s] = ast.literal_eval(value)
            except (ValueError, SyntaxError):
                result[key.s] = str(value)
    return result


def extract_list(ast_node):
    """Extract list from AST List node."""
    result = []
    for item in ast_node.elts:
        if isinstance(item, ast.Dict):
            result.append(extract_complex_dict(item))
        elif isinstance(item, ast.List):
            result.append(extract_list(item))
        elif isinstance(item, ast.Constant):
            result.append(item.value)
        else:
            # Try to get a literal value or default to string representation
            try:
                result.append(ast.literal_eval(item))
            except (ValueError, SyntaxError):
                result.append(str(item))
    return result


def extract_tags(op_kwargs):
    tags = op_kwargs.get("tags", [])

    # Ensure tags is a list
    if isinstance(tags, ast.List):
        # Extract elements from the ast.List
        tags = [
            elt.value if isinstance(elt, ast.Constant) else str(elt)
            for elt in tags.elts
        ]

    return tags if isinstance(tags, list) else []


def extract_ops_from_file(file_path: str) -> List[OperationModel]:
    try:
        ops_found = []
        with open(file_path, "r") as file:
            content = file.read()

        # Parse the abstract syntax tree of the file
        tree = ast.parse(content)

        # First, scan for set_op_type calls to get the default op_type for this file
        file_op_type = "built_in"  # Default
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = getattr(node.func, "id", None)
                if func_name == "set_op_type" and node.args:
                    # Extract the op_type value from set_op_type("some_type")
                    arg = node.args[0]
                    if hasattr(arg, "s"):  # String literal
                        file_op_type = arg.s
                    else:
                        file_op_type = str(arg)
                    break

        # Look for function definitions and their decorators
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for decorator in node.decorator_list:
                    # Look for decorators with parentheses (ast.Call)
                    decorator_name = None
                    if isinstance(decorator, ast.Call) and hasattr(decorator, "func"):
                        if hasattr(decorator.func, "id"):
                            decorator_name = decorator.func.id
                    elif isinstance(decorator, ast.Name):  # pragma: no cover
                        decorator_name = decorator.id

                    if decorator_name in [
                        "op",
                        "vop",
                        "api_tool",
                    ]:
                        op_kwargs = {}
                        if isinstance(decorator, ast.Call):
                            op_kwargs = {kw.arg: kw.value for kw in decorator.keywords}
                        if (
                            "path" in op_kwargs
                            and "name" in op_kwargs
                            and "description" in op_kwargs
                        ):

                            # Extract parameters (input schema)
                            parameters = None
                            if "parameters" in op_kwargs:
                                parameters = extract_complex_dict(
                                    op_kwargs["parameters"]
                                )

                            # Extract output (output schema)
                            output = None
                            if "output" in op_kwargs:
                                output = extract_complex_dict(op_kwargs["output"])

                            # Extract permissions
                            permissions = None
                            if "permissions" in op_kwargs:
                                permissions = extract_complex_dict(
                                    op_kwargs["permissions"]
                                )

                            # Extract method
                            method = "POST"
                            if "method" in op_kwargs:
                                method_value = op_kwargs["method"]
                                if hasattr(method_value, "s"):
                                    method = method_value.s
                                else:
                                    method = str(method_value)

                            # Extract tags
                            tags = extract_tags(op_kwargs)

                            # Use file_op_type (from set_op_type call) as the default
                            op_type = file_op_type

                            # Extract name and description safely
                            name = ""
                            description = ""
                            path = ""

                            if hasattr(op_kwargs["name"], "s"):
                                name = op_kwargs["name"].s
                            else:
                                name = str(op_kwargs["name"])

                            if hasattr(op_kwargs["description"], "s"):
                                description = op_kwargs["description"].s
                            else:
                                description = str(op_kwargs["description"])

                            if hasattr(op_kwargs["path"], "s"):
                                path = op_kwargs["path"].s
                            else:
                                path = str(op_kwargs["path"])

                            operation = OperationModel(
                                description=description,
                                id=name,
                                includeAccessToken=True,
                                method=method,
                                name=name,
                                type=op_type,  # Use file-level op_type
                                url=path,
                                tags=tags,
                                parameters=parameters,  # Input schema
                                output=output,  # Output schema
                                permissions=permissions,
                            )
                            ops_found.append(operation)
        return ops_found
    except Exception as e:
        print(e)
        print(f"Skipping {file_path} due to unparseable AST")
        return []


def scan_and_register_ops(
    path="./", current_user: str = "system", tags: Optional[List[str]] = None
):
    all_ops = scan_ops(path)
    response = write_ops(current_user=current_user, tags=tags, ops=all_ops)
    print(response)


def print_pretty_ops(ops: List[OperationModel]):
    for op in ops:
        print("_" * 80)
        print("Operation Details:")
        print(f"  Name       : {op.name}")
        print(f"  URL        : {op.url}")
        print(f"  Method     : {op.method}")
        print(f"  Description: {op.description}")
        print(f"  ID         : {op.id}")
        if op.parameters:
            print("  Parameters (Input Schema):")
            properties = op.parameters.get("properties", {})
            for prop_name, prop_def in properties.items():
                if isinstance(prop_def, dict):
                    description = prop_def.get("description", prop_name)
                    print(f"    - {prop_name} : {description}")
        print(f"  Include Access Token: {op.includeAccessToken}")
        print(f"  Type       : {op.type}")
        print(f"  Tags       : {op.tags}")
        print("")


def scan_ops(path=".") -> List[OperationModel]:
    python_files = find_python_files(path)
    all_ops = []

    for file_path in python_files:
        file_ops = extract_ops_from_file(file_path)
        all_ops.extend(file_ops)

    return all_ops


def scan_and_print_ops(path="."):
    all_ops = scan_ops(path)
    print_pretty_ops(all_ops)


def write_ops(
    current_user: str = "system",
    tags: Optional[List[str]] = None,
    ops: Optional[List[OperationModel]] = None,
):
    if ops is not None:
        print_pretty_ops(ops)

    # Get the DynamoDB table name from the environment variable
    table_name = os.environ.get("OPS_DYNAMODB_TABLE")
    if not table_name:
        return {
            "success": False,
            "message": "DynamoDB table name is not set in environment variables",
        }

    # Use a resource client to interact with DynamoDB
    table = dynamodb.Table(table_name)

    # Check if `ops` is provided
    if ops is None:
        return {"success": False, "message": "Operations must be provided"}

    # Validate and Serialize operations for DynamoDB
    for op in ops:
        try:
            op_dict = op.model_dump()
        except ValidationError as e:
            return {"success": False, "message": f"Operation validation failed: {e}"}

        # Check and register based on tags attached to the operation
        operation_tags = op_dict.get("tags", ["default"])
        operation_tags.append("all")

        for tag in operation_tags:
            # Check if an entry exists
            response = table.query(
                KeyConditionExpression=Key("user").eq(current_user) & Key("tag").eq(tag)
            )
            existing_items = response["Items"]

            if existing_items:
                # If an entry exists, update it by checking for op id
                for item in existing_items:
                    existing_ops = item["ops"]
                    op_exists = False

                    for index, existing_op in enumerate(existing_ops):
                        if existing_op["id"] == op_dict["id"]:
                            existing_ops[index] = op_dict
                            op_exists = True
                            break

                    if not op_exists:
                        existing_ops.append(op_dict)

                    table.update_item(
                        Key={
                            "user": current_user,
                            "tag": tag,
                        },
                        UpdateExpression="SET ops = :ops",
                        ExpressionAttributeValues={
                            ":ops": existing_ops,
                        },
                    )
                    print(
                        f"Updated item in table {table_name} for user {current_user} "
                        f"and tag {tag}"
                    )
            else:
                # If no entry exists, create a new one
                item = {
                    "id": str(uuid.uuid4()),  # Using UUID to ensure unique primary key
                    "user": current_user,
                    "tag": tag,
                    "ops": [op_dict],
                }
                table.put_item(Item=item)
                print(
                    f"Put item into table {table_name} for user {current_user} "
                    f"and tag {tag}"
                )

    return {
        "success": True,
        "message": "Successfully associated operations with provided tags and user",
    }


def resolve_ops_table(stage: Optional[str], ops_table: Optional[str]) -> Optional[str]:
    if ops_table:
        return ops_table

    env_ops_table = os.environ.get("OPS_DYNAMODB_TABLE")
    if env_ops_table:
        return env_ops_table

    if stage:
        current_dir = os.getcwd()
        var_file_name = f"{stage}-var.yml"

        # Search for var file in the current directory or one directory up
        for _ in range(2):
            var_file_path = os.path.join(current_dir, "var", var_file_name)
            if os.path.exists(var_file_path):
                try:
                    with open(var_file_path, "r") as file:
                        config = yaml.safe_load(file)
                    return config.get("OPS_DYNAMODB_TABLE")
                except (yaml.YAMLError, OSError):
                    # If there's an error reading or parsing the YAML file,
                    # continue searching
                    pass

            # Check one directory up
            current_dir = os.path.abspath(os.path.join(current_dir, os.pardir))

    return None


def main():
    parser = argparse.ArgumentParser(description="Ops management script")
    parser.add_argument("--stage", type=str, help="The staging environment")
    parser.add_argument("--dir", type=str, help="The directory to search for ops")
    parser.add_argument(
        "--ops_table", type=str, help="The value for OPS_DYNAMODB_TABLE"
    )
    parser.add_argument(
        "command", choices=["ls", "register"], help="Command to execute"
    )

    args = parser.parse_args()

    # Execute the command
    if args.command == "ls":
        scan_and_print_ops(args.dir or ".")
    elif args.command == "register":  # pragma: no cover
        # Resolve the DynamoDB table name
        ops_table = resolve_ops_table(args.stage, args.ops_table)
        if not ops_table:
            print(
                "Error: OPS_DYNAMODB_TABLE could not be resolved. Add it to your "
                "var/<stage>-var.yml file or set it as an environment variable or "
                "pass it with --ops_table <table_name>."
            )
            sys.exit(1)
        else:
            # Set the environment variable for DynamoDB operations
            os.environ["OPS_DYNAMODB_TABLE"] = ops_table
            scan_and_register_ops(args.dir or ".", current_user="system")
    else:  # pragma: no cover
        # we are excluding this section from coverage because argparse ensures that
        # the command is one of the choices, so this code should never be reached,
        # but we don't want to exclude anything from coverage above.
        raise AssertionError("Unreachable: argparse `choices` ensures coverage")


if __name__ == "__main__":
    main()
