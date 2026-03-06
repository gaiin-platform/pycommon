"""
Test suite for pycommon.logger module.

This module tests the logger functionality including environment variable handling,
logger creation, log level configuration, and default values.
"""

import importlib.util
import logging
import os
import sys
from pathlib import Path
from unittest.mock import patch

# Direct import of logger module to avoid AWS dependencies
# Get the path relative to this test file
test_dir = Path(__file__).parent.parent
logger_path = test_dir / "pycommon" / "logger.py"

spec = importlib.util.spec_from_file_location("pycommon.logger", str(logger_path))
logger_module = importlib.util.module_from_spec(spec)
sys.modules["pycommon.logger"] = logger_module
spec.loader.exec_module(logger_module)
getLogger = logger_module.getLogger


class TestLogger:
    """Test cases for the logger module."""

    def test_getLogger_default_values(self):
        """Test getLogger with default environment variables."""
        with patch.dict(os.environ, {}, clear=True):
            logger = getLogger("test_module")

            assert logger.name == "amplify-test_module"
            assert logger.level == logging.INFO

    def test_getLogger_custom_service_name(self):
        """Test getLogger with custom SERVICE_NAME environment variable."""
        with patch.dict(os.environ, {"SERVICE_NAME": "my_service"}, clear=True):
            logger = getLogger("test_module")

            assert logger.name == "my_service-test_module"
            assert logger.level == logging.INFO

    def test_getLogger_custom_log_level(self):
        """Test getLogger with custom LOG_LEVEL environment variable."""
        with patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}, clear=True):
            logger = getLogger("test_module")

            assert logger.name == "amplify-test_module"
            assert logger.level == logging.DEBUG

    def test_getLogger_both_custom_env_vars(self):
        """Test getLogger with both custom environment variables."""
        with patch.dict(
            os.environ,
            {"SERVICE_NAME": "custom_service", "LOG_LEVEL": "ERROR"},
            clear=True,
        ):
            logger = getLogger("test_module")

            assert logger.name == "custom_service-test_module"
            assert logger.level == logging.ERROR

    def test_log_level_mappings(self):
        """Test all supported log level mappings."""
        test_cases = [
            ("DEBUG", logging.DEBUG),
            ("INFO", logging.INFO),
            ("WARNING", logging.WARNING),
            ("WARN", logging.WARNING),  # alias
            ("ERROR", logging.ERROR),
            ("CRITICAL", logging.CRITICAL),
            ("FATAL", logging.CRITICAL),  # alias
        ]

        for log_level_str, expected_level in test_cases:
            with patch.dict(os.environ, {"LOG_LEVEL": log_level_str}, clear=True):
                logger = getLogger("test_module")
                assert (
                    logger.level == expected_level
                ), f"Failed for log level: {log_level_str}"

    def test_log_level_case_insensitive(self):
        """Test that log level is case insensitive."""
        with patch.dict(os.environ, {"LOG_LEVEL": "debug"}, clear=True):
            logger = getLogger("test_module")
            assert logger.level == logging.DEBUG

    def test_invalid_log_level_defaults_to_info(self):
        """Test that invalid log level defaults to INFO."""
        with patch.dict(os.environ, {"LOG_LEVEL": "INVALID_LEVEL"}, clear=True):
            logger = getLogger("test_module")
            assert logger.level == logging.INFO

    def test_different_log_stack_values(self):
        """Test getLogger with different log_stack values."""
        test_stacks = [
            "api",
            "database",
            "auth",
            "user_service",
            "test.module.submodule",
        ]

        for stack in test_stacks:
            logger = getLogger(stack)
            assert logger.name == f"amplify-{stack}"

    def test_logger_is_logging_instance(self):
        """Test that returned logger is a proper logging.Logger instance."""
        logger = getLogger("test_module")
        assert isinstance(logger, logging.Logger)

    def test_logger_name_format(self):
        """Test that logger name follows the expected format."""
        with patch.dict(os.environ, {"SERVICE_NAME": "test_service"}, clear=True):
            logger = getLogger("my_module")
            assert logger.name == "test_service-my_module"

    def test_multiple_loggers_different_stacks(self):
        """Test creating multiple loggers with different stacks."""
        logger1 = getLogger("module1")
        logger2 = getLogger("module2")

        assert logger1.name == "amplify-module1"
        assert logger2.name == "amplify-module2"
        assert logger1 is not logger2

    def test_same_log_stack_returns_same_logger(self):
        """Test that same log_stack returns the same logger instance."""
        logger1 = getLogger("same_module")
        logger2 = getLogger("same_module")

        assert logger1 is logger2

    def test_logger_level_consistency(self):
        """Test that logger level is set consistently."""
        with patch.dict(os.environ, {"LOG_LEVEL": "WARNING"}, clear=True):
            logger = getLogger("test_module")
            assert logger.level == logging.WARNING

            # Create another logger with same environment
            logger2 = getLogger("another_module")
            assert logger2.level == logging.WARNING

    def test_empty_log_stack(self):
        """Test getLogger with empty log_stack."""
        logger = getLogger("")
        assert logger.name == "amplify-"

    def test_none_log_stack(self):
        """Test getLogger with None log_stack (should handle gracefully)."""
        logger = getLogger(None)
        assert logger.name == "amplify-None"

    def test_logger_has_handlers(self):
        """Test that logger has appropriate handlers configured."""
        getLogger("test_module")
        # The logger should inherit from root logger which has basicConfig
        assert len(logging.getLogger().handlers) > 0

    def test_logger_can_log_messages(self):
        """Test that the logger can actually log messages."""
        logger = getLogger("test_module")

        # This should not raise any exceptions
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")
        logger.critical("Critical message")

    def test_environment_variable_override(self):
        """Test that environment variables can be overridden."""
        # Set initial values
        with patch.dict(
            os.environ, {"SERVICE_NAME": "initial", "LOG_LEVEL": "DEBUG"}, clear=True
        ):
            logger1 = getLogger("test")
            assert logger1.name == "initial-test"
            assert logger1.level == logging.DEBUG

        # Override values
        with patch.dict(
            os.environ, {"SERVICE_NAME": "override", "LOG_LEVEL": "ERROR"}, clear=True
        ):
            logger2 = getLogger("test")
            assert logger2.name == "override-test"
            assert logger2.level == logging.ERROR

    def test_log_level_aliases_work(self):
        """Test that log level aliases (WARN, FATAL) work correctly."""
        with patch.dict(os.environ, {"LOG_LEVEL": "WARN"}, clear=True):
            logger = getLogger("test")
            assert logger.level == logging.WARNING

        with patch.dict(os.environ, {"LOG_LEVEL": "FATAL"}, clear=True):
            logger = getLogger("test")
            assert logger.level == logging.CRITICAL

    def test_poll_status_handler_init(self):
        """Test PollStatusHandler initialization."""
        from unittest.mock import patch

        with patch("pycommon.logger.boto3"):
            from pycommon.logger import PollStatusHandler

            handler = PollStatusHandler("test-table", min_interval_seconds=10)
            assert handler.min_interval == 10
            assert handler.last_update_time == {}

    def test_poll_status_handler_emit_no_polling_active(self):
        """Test PollStatusHandler.emit when no polling is active."""
        from unittest.mock import Mock, patch

        with patch("pycommon.logger.boto3") as mock_boto3:
            # Set up mock table before creating handler
            mock_table = Mock()
            mock_boto3.resource.return_value.Table.return_value = mock_table

            from pycommon.logger import PollStatusHandler

            handler = PollStatusHandler("test-table")
            record = logging.LogRecord(
                "test", logging.INFO, "", 0, "Test message", (), None
            )

            # Should not raise and not update DynamoDB
            handler.emit(record)
            assert not mock_table.update_item.called

    def test_poll_status_handler_emit_with_active_polling(self):
        """Test PollStatusHandler.emit with active polling."""
        from unittest.mock import Mock, patch

        with patch("pycommon.logger.boto3") as mock_boto3:
            from pycommon.logger import PollStatusHandler, activate_poll_tracking

            # Set up mock BEFORE creating handler
            mock_table = Mock()
            mock_boto3.resource.return_value.Table.return_value = mock_table

            handler = PollStatusHandler("test-table", min_interval_seconds=0)
            handler.table = mock_table  # Explicitly set the table

            # Activate polling
            activate_poll_tracking("req-123", "user@test.com")

            # Emit a log record
            record = logging.LogRecord(
                "test", logging.INFO, "", 0, "Test message", (), None
            )
            handler.emit(record)

            # Should update DynamoDB
            assert mock_table.update_item.called

    def test_poll_status_handler_emit_with_error_level(self):
        """Test PollStatusHandler.emit with ERROR level sets status to failed."""
        from unittest.mock import Mock, patch

        with patch("pycommon.logger.boto3") as mock_boto3:
            from pycommon.logger import PollStatusHandler, activate_poll_tracking

            # Set up mock BEFORE creating handler
            mock_table = Mock()
            mock_boto3.resource.return_value.Table.return_value = mock_table

            handler = PollStatusHandler("test-table", min_interval_seconds=0)
            handler.table = mock_table  # Explicitly set the table

            # Activate polling
            activate_poll_tracking("req-123", "user@test.com")

            # Emit an error log record
            record = logging.LogRecord(
                "test", logging.ERROR, "", 0, "Error message", (), None
            )
            handler.emit(record)

            # Should update with status 'failed'
            call_args = mock_table.update_item.call_args
            assert call_args[1]["ExpressionAttributeValues"][":status"] == "failed"

    def test_poll_status_handler_rate_limiting(self):
        """Test PollStatusHandler rate limiting."""
        from unittest.mock import Mock, patch

        with patch("pycommon.logger.boto3") as mock_boto3:
            from pycommon.logger import PollStatusHandler, activate_poll_tracking

            # Set up mock BEFORE creating handler
            mock_table = Mock()
            mock_boto3.resource.return_value.Table.return_value = mock_table

            handler = PollStatusHandler("test-table", min_interval_seconds=10)
            handler.table = mock_table  # Explicitly set the table

            # Activate polling
            activate_poll_tracking("req-123", "user@test.com")

            # First emit should work
            record1 = logging.LogRecord(
                "test", logging.INFO, "", 0, "Message 1", (), None
            )
            handler.emit(record1)
            assert mock_table.update_item.call_count == 1

            # Second emit immediately after should be rate limited
            record2 = logging.LogRecord(
                "test", logging.INFO, "", 0, "Message 2", (), None
            )
            handler.emit(record2)
            assert mock_table.update_item.call_count == 1  # Still 1, not 2

    def test_poll_status_handler_error_handling(self):
        """Test PollStatusHandler handles errors gracefully."""
        import sys
        from io import StringIO
        from unittest.mock import Mock, patch

        with patch("pycommon.logger.boto3") as mock_boto3:
            from pycommon.logger import PollStatusHandler, activate_poll_tracking

            # Set up mock BEFORE creating handler
            mock_table = Mock()
            mock_table.update_item.side_effect = Exception("DynamoDB error")
            mock_boto3.resource.return_value.Table.return_value = mock_table

            handler = PollStatusHandler("test-table", min_interval_seconds=0)
            handler.table = mock_table  # Explicitly set the table

            # Activate polling
            activate_poll_tracking("req-123", "user@test.com")

            # Capture stderr to verify error message
            captured_stderr = StringIO()
            with patch.object(sys, "stderr", captured_stderr):
                # Should not raise exception
                record = logging.LogRecord(
                    "test", logging.INFO, "", 0, "Test message", (), None
                )
                handler.emit(record)  # Should not raise

            # Verify error was printed to stderr
            stderr_output = captured_stderr.getvalue()
            assert "Error updating poll status" in stderr_output
            assert "DynamoDB error" in stderr_output

    def test_activate_poll_tracking(self):
        """Test activate_poll_tracking sets request context."""
        from pycommon.logger import (
            activate_poll_tracking,
            deactivate_poll_tracking,
            get_active_poll_request_id,
        )

        activate_poll_tracking("req-456", "user@example.com")
        assert get_active_poll_request_id() == "req-456"

        deactivate_poll_tracking()
        assert get_active_poll_request_id() is None

    def test_deactivate_poll_tracking(self):
        """Test deactivate_poll_tracking clears request context."""
        from pycommon.logger import (
            activate_poll_tracking,
            deactivate_poll_tracking,
            get_active_poll_request_id,
        )

        activate_poll_tracking("req-789", "user@test.com")
        assert get_active_poll_request_id() == "req-789"

        deactivate_poll_tracking()
        assert get_active_poll_request_id() is None

    def test_get_active_poll_request_id_none_when_inactive(self):
        """Test get_active_poll_request_id returns None when inactive."""
        from pycommon.logger import deactivate_poll_tracking, get_active_poll_request_id

        deactivate_poll_tracking()  # Ensure clean state
        assert get_active_poll_request_id() is None

    def test_getLogger_with_poll_status_table(self):
        """Test getLogger adds PollStatusHandler when POLL_STATUS_TABLE is set."""
        from unittest.mock import patch

        with patch.dict(
            os.environ, {"POLL_STATUS_TABLE": "test-poll-table"}, clear=True
        ), patch("pycommon.logger.boto3"):
            from pycommon.logger import PollStatusHandler

            logger = getLogger("poll_test")

            # Check if PollStatusHandler was added
            has_poll_handler = any(
                isinstance(h, PollStatusHandler) for h in logger.handlers
            )
            assert has_poll_handler

    def test_getLogger_without_poll_status_table(self):
        """Test getLogger doesn't add PollStatusHandler when table not configured."""
        from unittest.mock import patch

        with patch.dict(os.environ, {}, clear=True):
            from pycommon.logger import PollStatusHandler

            logger = getLogger("no_poll_test")

            # Check that no PollStatusHandler was added
            has_poll_handler = any(
                isinstance(h, PollStatusHandler) for h in logger.handlers
            )
            assert not has_poll_handler

    def test_getLogger_poll_handler_setup_failure(self):
        """Test getLogger handles PollStatusHandler setup failure gracefully."""
        from unittest.mock import patch

        with patch.dict(
            os.environ, {"POLL_STATUS_TABLE": "test-table"}, clear=True
        ), patch("pycommon.logger.boto3") as mock_boto3:
            mock_boto3.resource.side_effect = Exception("AWS connection failed")

            # Should not raise, just skip adding the handler
            logger = getLogger("fail_test")
            assert isinstance(logger, logging.Logger)
