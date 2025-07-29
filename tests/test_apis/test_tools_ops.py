# =============================================================================
# Tests for api/tools_ops.py
# =============================================================================

import os
import tempfile
from unittest.mock import call, patch

from pycommon.api.tools_ops import (
    _scan_lambda_codebase,
    api_tools_register_handler,
    list_lambda_ops,
    register_lambda_ops,
)
from pycommon.tools.ops import OperationModel


class TestApiToolsRegisterHandler:
    """Test cases for the api_tools_register_handler function."""

    def test_api_tools_register_handler_ls_command(self):
        """Test handler with 'ls' command."""
        include_dirs = ["service"]

        with patch("pycommon.api.tools_ops.list_lambda_ops") as mock_list:
            mock_list.return_value = {
                "success": True,
                "message": "Found 2 operations",
                "operations_count": 2,
                "operations": [],
            }

            result = api_tools_register_handler(include_dirs=include_dirs, command="ls")

            assert result["success"] is True
            assert result["message"] == "Found 2 operations"
            assert result["operations_count"] == 2
            mock_list.assert_called_once_with(include_dirs)

    def test_api_tools_register_handler_register_command(self):
        """Test handler with 'register' command."""
        include_dirs = ["service"]
        data = {"additional_tags": ["test"]}
        current_user = "test_user"

        with patch("pycommon.api.tools_ops.register_lambda_ops") as mock_register:
            mock_register.return_value = {
                "success": True,
                "message": "Successfully registered 1 operations",
                "operations_count": 1,
                "operations": [],
            }

            result = api_tools_register_handler(
                include_dirs=include_dirs,
                command="register",
                data=data,
                current_user=current_user,
            )

            assert result["success"] is True
            assert result["operations_count"] == 1
            mock_register.assert_called_once_with(include_dirs, data, current_user)

    def test_api_tools_register_handler_invalid_command(self):
        """Test handler with invalid command."""
        result = api_tools_register_handler(include_dirs=["service"], command="invalid")

        assert result["success"] is False
        assert "Unknown command: invalid" in result["error"]
        assert result["operations_count"] == 0

    def test_api_tools_register_handler_exception(self):
        """Test handler when an exception occurs."""
        with patch("pycommon.api.tools_ops.list_lambda_ops") as mock_list:
            mock_list.side_effect = Exception("Test error")

            result = api_tools_register_handler(include_dirs=["service"], command="ls")

            assert result["success"] is False
            assert "Handler failed: Test error" in result["error"]
            assert result["operations_count"] == 0

    def test_api_tools_register_handler_default_parameters(self):
        """Test handler with default parameters."""
        with patch("pycommon.api.tools_ops.list_lambda_ops") as mock_list:
            mock_list.return_value = {"success": True, "operations_count": 0}

            result = api_tools_register_handler()

            # Should default to empty include_dirs and ls command
            mock_list.assert_called_once_with([])
            assert result["success"] is True

    def test_api_tools_register_handler_prints_debug_info(self, capsys):
        """Test that handler prints appropriate debug information."""
        with patch("pycommon.api.tools_ops.list_lambda_ops") as mock_list:
            mock_list.return_value = {"success": True, "operations_count": 0}

            api_tools_register_handler(command="ls")
            captured = capsys.readouterr()

            assert "Listing operations" in captured.out

        with patch("pycommon.api.tools_ops.register_lambda_ops") as mock_register:
            mock_register.return_value = {"success": True, "operations_count": 0}

            api_tools_register_handler(command="register")
            captured = capsys.readouterr()

            assert "Registering operations" in captured.out


class TestRegisterLambdaOps:
    """Test cases for the register_lambda_ops function."""

    def test_register_lambda_ops_no_table_env_var(self):
        """Test register when OPS_DYNAMODB_TABLE is not set."""
        with patch.dict(os.environ, {}, clear=True):
            result = register_lambda_ops(["service"])

            assert result["success"] is False
            assert "OPS_DYNAMODB_TABLE environment variable not set" in result["error"]
            assert result["operations_count"] == 0

    @patch("pycommon.api.tools_ops._scan_lambda_codebase")
    @patch("pycommon.api.tools_ops.write_ops")
    def test_register_lambda_ops_success(self, mock_write_ops, mock_scan, capsys):
        """Test successful registration of operations."""
        # Mock environment variable
        with patch.dict(os.environ, {"OPS_DYNAMODB_TABLE": "test-table"}):
            # Mock operations
            mock_op = OperationModel(
                description="Test operation",
                id="test_op",
                includeAccessToken=True,
                method="POST",
                name="Test Operation",
                type="built_in",
                url="/test",
                tags=["test"],
            )
            mock_scan.return_value = [mock_op]
            mock_write_ops.return_value = {"success": True}

            result = register_lambda_ops(
                include_dirs=["service"],
                data={"additional_tags": ["custom"]},
                current_user="test_user",
            )

            assert result["success"] is True
            assert result["operations_count"] == 1
            assert "Successfully registered 1 operations" in result["message"]
            assert len(result["operations"]) == 1
            assert result["operations"][0]["name"] == "Test Operation"

            # Verify write_ops was called with correct parameters
            mock_write_ops.assert_called_once_with(
                current_user="test_user", tags=["all", "custom"], ops=[mock_op]
            )

            # Check debug output
            captured = capsys.readouterr()
            assert "Register: Using DynamoDB table: test-table" in captured.out
            assert "Register: About to register 1 operations" in captured.out

    @patch("os.path.exists")
    @patch("pycommon.api.tools_ops._scan_lambda_codebase")
    @patch("pycommon.api.tools_ops.write_ops")
    def test_register_lambda_ops_success_var_task_exists(
        self, mock_write_ops, mock_scan, mock_exists, capsys
    ):
        """Test successful registration when /var/task directory exists."""
        # Mock environment variable
        with patch.dict(os.environ, {"OPS_DYNAMODB_TABLE": "test-table"}):
            mock_exists.return_value = True  # /var/task exists
            mock_op = OperationModel(
                description="Test operation",
                id="test_op",
                includeAccessToken=True,
                method="POST",
                name="Test Operation",
                type="built_in",
                url="/test",
                tags=["test"],
            )
            mock_scan.return_value = [mock_op]
            mock_write_ops.return_value = {"success": True}

            result = register_lambda_ops(["service"])

            assert result["success"] is True
            assert result["operations_count"] == 1

            # Verify scan was called with /var/task (no fallback)
            mock_scan.assert_called_once_with("/var/task", ["service"])

            # Check that no fallback message appears
            captured = capsys.readouterr()
            assert "Register: Directory /var/task does not exist!" not in captured.out
            assert "Register: Using current working directory:" not in captured.out

    @patch("pycommon.api.tools_ops._scan_lambda_codebase")
    def test_register_lambda_ops_no_operations_found(self, mock_scan):
        """Test register when no operations are found."""
        with patch.dict(os.environ, {"OPS_DYNAMODB_TABLE": "test-table"}):
            mock_scan.return_value = []

            result = register_lambda_ops(["service"])

            assert result["success"] is True
            assert result["operations_count"] == 0
            assert result["message"] == "No operations found"
            assert result["operations"] == []

    @patch("pycommon.api.tools_ops._scan_lambda_codebase")
    def test_register_lambda_ops_exception(self, mock_scan, capsys):
        """Test register when an exception occurs."""
        with patch.dict(os.environ, {"OPS_DYNAMODB_TABLE": "test-table"}):
            mock_scan.side_effect = Exception("Scan error")

            result = register_lambda_ops(["service"])

            assert result["success"] is False
            assert "Registration failed: Scan error" in result["error"]
            assert result["operations_count"] == 0

            # Check error was logged
            captured = capsys.readouterr()
            assert "Register: Error occurred: Scan error" in captured.out

    @patch("os.path.exists")
    @patch("os.getcwd")
    @patch("pycommon.api.tools_ops._scan_lambda_codebase")
    def test_register_lambda_ops_fallback_directory(
        self, mock_scan, mock_getcwd, mock_exists, capsys
    ):
        """Test register falls back to current directory
        when /var/task doesn't exist."""
        with patch.dict(os.environ, {"OPS_DYNAMODB_TABLE": "test-table"}):
            mock_exists.return_value = False
            mock_getcwd.return_value = "/current/dir"
            mock_scan.return_value = []

            result = register_lambda_ops(["service"])

            # Check fallback logic was used
            captured = capsys.readouterr()
            assert "Register: Directory /var/task does not exist!" in captured.out
            assert (
                "Register: Using current working directory: /current/dir"
                in captured.out
            )

            # Verify scan was called with fallback directory
            mock_scan.assert_called_once_with("/current/dir", ["service"])
            assert result["success"] is True

    def test_register_lambda_ops_default_data(self):
        """Test register with default data parameter."""
        with patch.dict(os.environ, {}, clear=True):
            result = register_lambda_ops(["service"])

            # Should handle None data gracefully
            assert result["success"] is False  # Due to missing env var


class TestListLambdaOps:
    """Test cases for the list_lambda_ops function."""

    @patch("pycommon.api.tools_ops._scan_lambda_codebase")
    def test_list_lambda_ops_success(self, mock_scan, capsys):
        """Test successful listing of operations."""
        # Mock operations
        mock_op = OperationModel(
            description="Test operation",
            id="test_op",
            includeAccessToken=True,
            method="POST",
            name="Test Operation",
            type="built_in",
            url="/test",
            tags=["test"],
            parameters={"type": "object"},
            output={"type": "string"},
            permissions={"read": True},
        )
        mock_scan.return_value = [mock_op]

        result = list_lambda_ops(["service"])

        assert result["success"] is True
        assert result["operations_count"] == 1
        assert "Found 1 operations" in result["message"]
        assert len(result["operations"]) == 1

        op_info = result["operations"][0]
        assert op_info["name"] == "Test Operation"
        assert op_info["url"] == "/test"
        assert op_info["method"] == "POST"
        assert op_info["description"] == "Test operation"
        assert op_info["type"] == "built_in"
        assert op_info["tags"] == ["test"]
        assert op_info["id"] == "test_op"
        assert op_info["parameters"] == {"type": "object"}
        assert op_info["output"] == {"type": "string"}
        assert op_info["permissions"] == {"read": True}

        # Check debug output
        captured = capsys.readouterr()
        assert "Scanning directory: /var/task" in captured.out
        assert "Including directories: ['service']" in captured.out

    @patch("os.path.exists")
    @patch("os.getcwd")
    @patch("pycommon.api.tools_ops._scan_lambda_codebase")
    def test_list_lambda_ops_no_operations(self, mock_scan, mock_getcwd, mock_exists):
        """Test listing when no operations are found."""
        mock_exists.return_value = True  # Make /var/task exist
        mock_scan.return_value = []

        result = list_lambda_ops(["service"])

        assert result["success"] is True
        assert result["operations_count"] == 0
        assert result["message"] == "No operations found"
        assert result["operations"] == []
        assert "debug_info" in result
        assert result["debug_info"]["scanned_directory"] == "/var/task"
        assert result["debug_info"]["included_dirs"] == ["service"]

    @patch("pycommon.api.tools_ops._scan_lambda_codebase")
    def test_list_lambda_ops_operation_without_optional_fields(self, mock_scan):
        """Test listing operation without optional fields."""
        mock_op = OperationModel(
            description="Test operation",
            id="test_op",
            includeAccessToken=True,
            method="POST",
            name="Test Operation",
            type="built_in",
            url="/test",
            tags=["test"],
        )
        mock_scan.return_value = [mock_op]

        result = list_lambda_ops(["service"])

        op_info = result["operations"][0]
        assert "parameters" not in op_info
        assert "output" not in op_info
        assert "permissions" not in op_info
        assert result["success"] is True

    @patch("pycommon.api.tools_ops._scan_lambda_codebase")
    def test_list_lambda_ops_exception(self, mock_scan, capsys):
        """Test listing when an exception occurs."""
        mock_scan.side_effect = Exception("Scan error")

        result = list_lambda_ops(["service"])

        assert result["success"] is False
        assert "Listing failed: Scan error" in result["error"]
        assert result["operations_count"] == 0

        # Check error was logged
        captured = capsys.readouterr()
        assert "Error in list_lambda_ops: Scan error" in captured.out

    @patch("os.path.exists")
    @patch("os.getcwd")
    @patch("pycommon.api.tools_ops._scan_lambda_codebase")
    def test_list_lambda_ops_fallback_directory(
        self, mock_scan, mock_getcwd, mock_exists, capsys
    ):
        """Test listing falls back to current directory when /var/task doesn't exist."""
        mock_exists.return_value = False
        mock_getcwd.return_value = "/current/dir"
        mock_scan.return_value = []

        result = list_lambda_ops(["service"])

        # Check fallback logic was used
        captured = capsys.readouterr()
        assert "Directory /var/task does not exist!" in captured.out
        assert "Using current working directory: /current/dir" in captured.out

        # Verify scan was called with fallback directory
        mock_scan.assert_called_once_with("/current/dir", ["service"])
        assert result["success"] is True


class TestScanLambdaCodebase:
    """Test cases for the _scan_lambda_codebase function."""

    @patch("pycommon.api.tools_ops.find_python_files")
    @patch("pycommon.api.tools_ops.extract_ops_from_file")
    @patch("pycommon.api.tools_ops.print_pretty_ops")
    def test_scan_lambda_codebase_success(
        self, mock_print_pretty, mock_extract, mock_find_files, capsys
    ):
        """Test successful scanning of lambda codebase."""
        # Mock file discovery
        mock_find_files.return_value = [
            "/var/task/service/handler.py",
            "/var/task/service/utils.py",
            "/var/task/other/file.py",
        ]

        # Mock operation extraction
        mock_op = OperationModel(
            description="Test operation",
            id="test_op",
            includeAccessToken=True,
            method="POST",
            name="Test Operation",
            type="built_in",
            url="/test",
            tags=["test"],
        )
        mock_extract.side_effect = [
            [mock_op],  # service/handler.py
            [],  # service/utils.py
            [],  # other/file.py (excluded)
        ]

        result = _scan_lambda_codebase("/var/task", ["service"])

        assert len(result) == 1
        assert result[0].name == "Test Operation"

        # Verify only service files were processed
        assert mock_extract.call_count == 2
        mock_extract.assert_has_calls(
            [call("/var/task/service/handler.py"), call("/var/task/service/utils.py")]
        )

        # Check debug output
        captured = capsys.readouterr()
        assert "Starting scan of directory: /var/task" in captured.out
        assert "Found 3 Python files total" in captured.out
        assert "Including file: /var/task/service/handler.py" in captured.out
        assert "Including file: /var/task/service/utils.py" in captured.out
        assert "After filtering, scanning 2 files for operations" in captured.out
        assert "Found 1 operations in /var/task/service/handler.py" in captured.out
        assert "Total operations found: 1" in captured.out

    @patch("pycommon.api.tools_ops.find_python_files")
    @patch("pycommon.api.tools_ops.extract_ops_from_file")
    def test_scan_lambda_codebase_extraction_error(
        self, mock_extract, mock_find_files, capsys
    ):
        """Test scanning when extraction fails for some files."""
        mock_find_files.return_value = [
            "/var/task/service/good.py",
            "/var/task/service/bad.py",
        ]

        mock_op = OperationModel(
            description="Test operation",
            id="test_op",
            includeAccessToken=True,
            method="POST",
            name="Test Operation",
            type="built_in",
            url="/test",
            tags=["test"],
        )

        # First file succeeds, second fails
        mock_extract.side_effect = [[mock_op], Exception("Parse error")]

        result = _scan_lambda_codebase("/var/task", ["service"])

        # Should still return the successful operation
        assert len(result) == 1
        assert result[0].name == "Test Operation"

        # Check warning was logged
        captured = capsys.readouterr()
        assert (
            "Warning: Could not parse /var/task/service/bad.py: Parse error"
            in captured.out
        )

    @patch("pycommon.api.tools_ops.find_python_files")
    def test_scan_lambda_codebase_no_matching_files(self, mock_find_files, capsys):
        """Test scanning when no files match include directories."""
        mock_find_files.return_value = [
            "/var/task/other/file.py",
            "/var/task/different/file.py",
        ]

        result = _scan_lambda_codebase("/var/task", ["service"])

        assert len(result) == 0

        # Check debug output
        captured = capsys.readouterr()
        assert "After filtering, scanning 0 files for operations" in captured.out
        assert "Total operations found: 0" in captured.out

    @patch("pycommon.api.tools_ops.find_python_files")
    def test_scan_lambda_codebase_include_patterns(self, mock_find_files):
        """Test that include directory patterns work correctly."""
        mock_find_files.return_value = [
            "/var/task/service/handler.py",  # Should be included
            "/var/task/service/subdir/file.py",  # Should be included
            "/var/task/serviceX/file.py",  # Should NOT be included
            "/var/task/other/service",
            "/var/task/different/file.py",  # Should NOT be included
        ]

        with patch("pycommon.api.tools_ops.extract_ops_from_file") as mock_extract:
            mock_extract.return_value = []

            _scan_lambda_codebase("/var/task", ["service"])

            # Should process 3 files: service dir files and file ending with service
            assert mock_extract.call_count == 3
            expected_files = [
                "/var/task/service/handler.py",
                "/var/task/service/subdir/file.py",
                "/var/task/other/service",
            ]
            for expected_file in expected_files:
                mock_extract.assert_any_call(expected_file)

    @patch("pycommon.api.tools_ops.find_python_files")
    def test_scan_lambda_codebase_empty_include_dirs_uses_exclusion(
        self, mock_find_files, capsys
    ):
        """Test that empty include_dirs uses exclusion-based filtering."""
        mock_find_files.return_value = [
            "/var/task/root_file.py",  # Root-level file - included
            "/var/task/service/handler.py",  # Subdirectory file - included
            "/var/task/schemata/schema.py",  # In excluded dir - NOT included
            "/var/task/node_modules/lib.py",  # In excluded dir - NOT included
            "/var/task/tests/test_file.py",  # In excluded dir - NOT included
            "/var/task/__pycache__/cache.py",  # In excluded dir - NOT included
        ]

        with patch("pycommon.api.tools_ops.extract_ops_from_file") as mock_extract:
            mock_extract.return_value = []

            _scan_lambda_codebase("/var/task", [])  # Empty include_dirs

            # Should process only non-excluded files
            assert mock_extract.call_count == 2
            mock_extract.assert_any_call("/var/task/root_file.py")
            mock_extract.assert_any_call("/var/task/service/handler.py")

            # Should NOT process excluded files
            excluded_calls = [
                "/var/task/schemata/schema.py",
                "/var/task/node_modules/lib.py",
                "/var/task/tests/test_file.py",
                "/var/task/__pycache__/cache.py",
            ]
            for excluded_file in excluded_calls:
                assert call(excluded_file) not in mock_extract.call_args_list

            # Check debug output
            captured = capsys.readouterr()
            assert "Using exclusion-based filtering" in captured.out

    def test_scan_lambda_codebase_integration_with_real_files(self):
        """Integration test with real temporary files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create service directory with operation
            service_dir = os.path.join(temp_dir, "service")
            os.makedirs(service_dir)

            handler_file = os.path.join(service_dir, "handler.py")
            with open(handler_file, "w") as f:
                f.write(
                    """
from pycommon.api.ops import api_tool

@api_tool(
    path="/test",
    name="Test Operation",
    description="A test operation"
)
def test_function():
    return "success"
"""
                )

            # Create other directory that should be excluded
            other_dir = os.path.join(temp_dir, "other")
            os.makedirs(other_dir)

            other_file = os.path.join(other_dir, "excluded.py")
            with open(other_file, "w") as f:
                f.write(
                    """
from pycommon.api.ops import api_tool

@api_tool(
    path="/excluded",
    name="Excluded Operation",
    description="Should not be found"
)
def excluded_function():
    return "excluded"
"""
                )

            result = _scan_lambda_codebase(temp_dir, ["service"])

            # Should only find the operation in service directory
            assert len(result) == 1
            assert result[0].name == "Test Operation"
            assert result[0].url == "/test"
