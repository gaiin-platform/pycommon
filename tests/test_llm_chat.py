import json
from unittest.mock import Mock, patch

import pytest

from pycommon.llm.chat import chat, chat_streaming


class TestChat:
    """Test cases for the chat function."""

    def test_chat_successful_response(self):
        """Test chat function with successful response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            b'data: {"d": "Hello", "s": "content"}',
            b'data: {"d": " world", "s": "content"}',
            b'data: {"s": "meta", "type": "usage", "tokens": 10}',
        ]

        with patch("pycommon.llm.chat.requests.post", return_value=mock_response):
            result, meta_events = chat(
                "https://api.example.com/chat",
                "test_token",
                {"messages": [{"role": "user", "content": "Hello"}]},
            )

        assert result == "Hello world"
        assert len(meta_events) == 1
        assert meta_events[0]["type"] == "usage"
        assert meta_events[0]["tokens"] == 10

    def test_chat_with_exception_in_streaming(self):
        """Test chat function when chat_streaming raises an exception."""
        with patch(
            "pycommon.llm.chat.chat_streaming", side_effect=Exception("Network error")
        ):
            with patch("builtins.print") as mock_print:
                result, meta_events = chat(
                    "https://api.example.com/chat", "test_token", {"messages": []}
                )

        assert result == "Error: Network error"
        assert meta_events == []
        mock_print.assert_called_once_with("Error in chat function: Network error")

    def test_chat_empty_response(self):
        """Test chat function with empty response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = []

        with patch("pycommon.llm.chat.requests.post", return_value=mock_response):
            result, meta_events = chat(
                "https://api.example.com/chat", "test_token", {"messages": []}
            )

        assert result == ""
        assert meta_events == []

    def test_chat_only_meta_events(self):
        """Test chat function with only meta events."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            b'data: {"s": "meta", "type": "start"}',
            b'data: {"s": "meta", "type": "end"}',
        ]

        with patch("pycommon.llm.chat.requests.post", return_value=mock_response):
            result, meta_events = chat(
                "https://api.example.com/chat", "test_token", {"messages": []}
            )

        assert result == ""
        assert len(meta_events) == 2
        assert meta_events[0]["type"] == "start"
        assert meta_events[1]["type"] == "end"


class TestChatStreaming:
    """Test cases for the chat_streaming function."""

    def test_chat_streaming_successful_response(self):
        """Test chat_streaming function with successful response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            b'data: {"d": "Hello", "s": "content"}',
            b'data: {"d": " world", "s": "content"}',
            b'data: {"s": "meta", "type": "usage"}',
        ]

        content_events = []
        meta_events = []

        def content_handler(data):
            content_events.append(data)

        def meta_handler(data):
            meta_events.append(data)

        with patch("pycommon.llm.chat.requests.post", return_value=mock_response):
            chat_streaming(
                "https://api.example.com/chat",
                "test_token",
                {"messages": []},
                content_handler,
                meta_handler,
            )

        assert len(content_events) == 2
        assert content_events[0]["d"] == "Hello"
        assert content_events[1]["d"] == " world"
        assert len(meta_events) == 1
        assert meta_events[0]["type"] == "usage"

    def test_chat_streaming_http_error_with_json_error_message(self):
        """Test chat_streaming with HTTP error containing JSON error message."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"error": "Invalid request format"}

        with patch("pycommon.llm.chat.requests.post", return_value=mock_response):
            with patch("builtins.print") as mock_print:
                with pytest.raises(Exception) as exc_info:
                    chat_streaming(
                        "https://api.example.com/chat",
                        "test_token",
                        {"messages": []},
                        lambda x: None,
                    )

        assert "Request failed with status 400: Invalid request format" in str(
            exc_info.value
        )
        mock_print.assert_called_once_with(
            "Request failed with status 400: Invalid request format"
        )

    def test_chat_streaming_http_error_without_error_message(self):
        """Test chat_streaming with HTTP error without error message in JSON."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"status": "error"}
        mock_response.raise_for_status.side_effect = Exception(
            "500 Internal Server Error"
        )

        with patch("pycommon.llm.chat.requests.post", return_value=mock_response):
            with pytest.raises(Exception) as exc_info:
                chat_streaming(
                    "https://api.example.com/chat",
                    "test_token",
                    {"messages": []},
                    lambda x: None,
                )

        assert "500 Internal Server Error" in str(exc_info.value)

    def test_chat_streaming_http_error_with_json_decode_error(self):
        """Test chat_streaming with HTTP error and JSON decode error."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_response.raise_for_status.side_effect = Exception("400 Bad Request")

        with patch("pycommon.llm.chat.requests.post", return_value=mock_response):
            with pytest.raises(Exception) as exc_info:
                chat_streaming(
                    "https://api.example.com/chat",
                    "test_token",
                    {"messages": []},
                    lambda x: None,
                )

        assert "400 Bad Request" in str(exc_info.value)

    def test_chat_streaming_with_error_in_response_stream(self):
        """Test chat_streaming when error is detected in response stream."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            b'data: {"d": "Hello", "s": "content"}',
            b'data: {"error": "Service temporarily unavailable"}',
        ]

        with patch("pycommon.llm.chat.requests.post", return_value=mock_response):
            with patch("builtins.print") as mock_print:
                with pytest.raises(Exception) as exc_info:
                    chat_streaming(
                        "https://api.example.com/chat",
                        "test_token",
                        {"messages": []},
                        lambda x: None,
                    )

        assert "Service temporarily unavailable" in str(exc_info.value)
        mock_print.assert_called_once_with(
            "Error detected from chat service: Service temporarily unavailable"
        )

    def test_chat_streaming_with_json_decode_error_in_stream(self):
        """Test chat_streaming with JSON decode error in response stream."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            b'data: {"d": "Hello", "s": "content"}',
            b"data: invalid json",
            b'data: {"d": " world", "s": "content"}',
        ]

        content_events = []

        def content_handler(data):
            content_events.append(data)

        with patch("pycommon.llm.chat.requests.post", return_value=mock_response):
            with patch("builtins.print") as mock_print:
                chat_streaming(
                    "https://api.example.com/chat",
                    "test_token",
                    {"messages": []},
                    content_handler,
                )

        # Should have processed valid JSON lines and skipped invalid ones
        assert len(content_events) == 2
        assert content_events[0]["d"] == "Hello"
        assert content_events[1]["d"] == " world"

        # Should have printed JSON decode error
        mock_print.assert_called_once()
        assert "JSON decode error" in mock_print.call_args[0][0]

    def test_chat_streaming_with_empty_lines(self):
        """Test chat_streaming with empty lines in response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            b"",
            b'data: {"d": "Hello", "s": "content"}',
            b"",
            b"data: ",
            b'data: {"d": " world", "s": "content"}',
        ]

        content_events = []

        def content_handler(data):
            content_events.append(data)

        with patch("pycommon.llm.chat.requests.post", return_value=mock_response):
            chat_streaming(
                "https://api.example.com/chat",
                "test_token",
                {"messages": []},
                content_handler,
            )

        assert len(content_events) == 2
        assert content_events[0]["d"] == "Hello"
        assert content_events[1]["d"] == " world"

    def test_chat_streaming_with_data_prefix_stripping(self):
        """Test chat_streaming properly strips 'data: ' prefix."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            b'data: {"d": "Test", "s": "content"}',
            b'{"d": "NoPrefix", "s": "content"}',  # No data: prefix
        ]

        content_events = []

        def content_handler(data):
            content_events.append(data)

        with patch("pycommon.llm.chat.requests.post", return_value=mock_response):
            chat_streaming(
                "https://api.example.com/chat",
                "test_token",
                {"messages": []},
                content_handler,
            )

        assert len(content_events) == 2
        assert content_events[0]["d"] == "Test"
        assert content_events[1]["d"] == "NoPrefix"

    def test_chat_streaming_default_meta_handler(self):
        """Test chat_streaming with default meta_handler (lambda x: None)."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            b'data: {"d": "Hello", "s": "content"}',
            b'data: {"s": "meta", "type": "usage"}',
        ]

        content_events = []

        def content_handler(data):
            content_events.append(data)

        with patch("pycommon.llm.chat.requests.post", return_value=mock_response):
            # Test with default meta_handler parameter
            chat_streaming(
                "https://api.example.com/chat",
                "test_token",
                {"messages": []},
                content_handler,
            )

        assert len(content_events) == 1
        assert content_events[0]["d"] == "Hello"

    def test_chat_streaming_request_headers(self):
        """Test that chat_streaming sends correct headers."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = []

        with patch(
            "pycommon.llm.chat.requests.post", return_value=mock_response
        ) as mock_post:
            chat_streaming(
                "https://api.example.com/chat",
                "test_access_token",
                {"messages": []},
                lambda x: None,
            )

        mock_post.assert_called_once_with(
            "https://api.example.com/chat",
            headers={
                "Authorization": "Bearer test_access_token",
                "Content-Type": "application/json",
            },
            json={"messages": []},
            stream=True,
        )

    def test_chat_streaming_with_missing_d_key(self):
        """Test chat_streaming with content events missing 'd' key."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            b'data: {"s": "content", "other": "value"}',  # Missing 'd' key
            b'data: {"d": "Hello", "s": "content"}',
        ]

        content_events = []

        def content_handler(data):
            content_events.append(data)

        with patch("pycommon.llm.chat.requests.post", return_value=mock_response):
            chat_streaming(
                "https://api.example.com/chat",
                "test_token",
                {"messages": []},
                content_handler,
            )

        assert len(content_events) == 2
        assert content_events[0].get("d", "") == ""  # Should handle missing 'd' key
        assert content_events[1]["d"] == "Hello"


class TestChatIntegration:
    """Integration tests for chat function using chat_streaming."""

    def test_chat_content_and_meta_accumulation(self):
        """Test that chat function properly accumulates content and meta events."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            b'data: {"d": "First", "s": "content"}',
            b'data: {"s": "meta", "type": "start", "id": 1}',
            b'data: {"d": " second", "s": "content"}',
            b'data: {"s": "meta", "type": "end", "id": 2}',
            b'data: {"d": " third", "s": "content"}',
        ]

        with patch("pycommon.llm.chat.requests.post", return_value=mock_response):
            result, meta_events = chat(
                "https://api.example.com/chat", "test_token", {"messages": []}
            )

        assert result == "First second third"
        assert len(meta_events) == 2
        assert meta_events[0]["type"] == "start"
        assert meta_events[0]["id"] == 1
        assert meta_events[1]["type"] == "end"
        assert meta_events[1]["id"] == 2

    def test_chat_with_content_handler_missing_d_key(self):
        """Test chat function when content events are missing 'd' key."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            b'data: {"s": "content", "other": "data"}',  # Missing 'd' key
            b'data: {"d": "Hello", "s": "content"}',
            b'data: {"s": "content"}',  # Missing 'd' key
        ]

        with patch("pycommon.llm.chat.requests.post", return_value=mock_response):
            result, meta_events = chat(
                "https://api.example.com/chat", "test_token", {"messages": []}
            )

        # Should concatenate empty string for missing 'd' keys and "Hello"
        # for present one
        assert result == "Hello"
        assert meta_events == []
