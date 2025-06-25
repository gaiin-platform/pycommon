# =============================================================================
# Tests for api/ses_email.py
# =============================================================================

import os
from unittest.mock import MagicMock, patch

from pycommon.api.ses_email import send_email


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.ses_email.requests.post")
def test_send_email_success(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True}
    mock_post.return_value = mock_response

    result = send_email("test_token", "test@example.com", "Subject", "Body")

    assert result is True


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.ses_email.requests.post")
def test_send_email_success_elif_branch(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True}
    mock_post.return_value = mock_response

    result = send_email("test_token", "user@example.com", "Test Subject", "Test Body")

    assert result is True


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.ses_email.requests.post")
def test_send_email_failure(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.json.return_value = {"success": False}
    mock_post.return_value = mock_response

    result = send_email("test_token", "test@example.com", "Subject", "Body")

    assert result is False


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.ses_email.requests.post")
def test_send_email_exception(mock_post):
    mock_post.side_effect = Exception("Network error")

    result = send_email("test_token", "test@example.com", "Subject", "Body")

    assert result is False
