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
