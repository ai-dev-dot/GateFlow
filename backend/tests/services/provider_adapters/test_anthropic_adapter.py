"""Tests for AnthropicAdapter."""

import json
import pytest
from app.services.provider_adapters.anthropic_adapter import AnthropicAdapter


@pytest.fixture
def adapter():
    return AnthropicAdapter()


class TestBuildUpstreamUrl:
    def test_appends_messages(self, adapter):
        assert adapter.build_upstream_url("https://api.anthropic.com/v1") == "https://api.anthropic.com/v1/messages"

    def test_strips_trailing_slash(self, adapter):
        assert adapter.build_upstream_url("https://api.anthropic.com/v1/") == "https://api.anthropic.com/v1/messages"


class TestBuildHeaders:
    def test_x_api_key(self, adapter):
        headers = adapter.build_headers("sk-ant-test-key")
        assert headers["x-api-key"] == "sk-ant-test-key"
        assert headers["anthropic-version"] == "2023-06-01"
        assert headers["content-type"] == "application/json"


class TestBuildRequestBody:
    def test_replaces_model(self, adapter):
        body = adapter.build_request_body(
            {"model": "claude-sonnet", "messages": [], "max_tokens": 1024},
            "claude-sonnet-4-20250514",
            {},
        )
        assert body["model"] == "claude-sonnet-4-20250514"

    def test_injects_default_max_tokens(self, adapter):
        body = adapter.build_request_body(
            {"model": "claude-sonnet", "messages": []},
            "claude-sonnet-4-20250514",
            {"temperature": None, "max_tokens": 4096},
        )
        assert body["max_tokens"] == 4096

    def test_does_not_override_explicit_max_tokens(self, adapter):
        body = adapter.build_request_body(
            {"model": "claude-sonnet", "messages": [], "max_tokens": 1024},
            "claude-sonnet-4-20250514",
            {"temperature": None, "max_tokens": 4096},
        )
        assert body["max_tokens"] == 1024

    def test_applies_default_temperature(self, adapter):
        body = adapter.build_request_body(
            {"model": "claude-sonnet", "messages": [], "max_tokens": 1024},
            "claude-sonnet-4-20250514",
            {"temperature": 0.5, "max_tokens": None},
        )
        assert body["temperature"] == 0.5


class TestExtractResponse:
    def test_extracts_content_and_tokens(self, adapter):
        response = {
            "content": [{"type": "text", "text": "Hello world"}],
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }
        content, input_tokens, output_tokens = adapter.extract_response(response)
        assert content == "Hello world"
        assert input_tokens == 10
        assert output_tokens == 5

    def test_multiple_content_blocks(self, adapter):
        response = {
            "content": [
                {"type": "text", "text": "Hello "},
                {"type": "text", "text": "world"},
            ],
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }
        content, _, _ = adapter.extract_response(response)
        assert content == "Hello world"

    def test_empty_content(self, adapter):
        response = {"content": [], "usage": {"input_tokens": 10, "output_tokens": 0}}
        content, _, _ = adapter.extract_response(response)
        assert content == ""


class TestParseStreamEvent:
    def test_content_block_delta(self, adapter):
        lines = [
            "event: content_block_delta",
            'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Hello"}}',
        ]
        event = adapter.parse_stream_event(lines)
        assert event is not None
        assert event.text == "Hello"
        assert event.done is False

    def test_message_start(self, adapter):
        lines = [
            "event: message_start",
            'data: {"type":"message_start","message":{"usage":{"input_tokens":25}}}',
        ]
        event = adapter.parse_stream_event(lines)
        assert event is not None
        assert event.input_tokens == 25

    def test_message_delta_output_tokens(self, adapter):
        lines = [
            "event: message_delta",
            'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":15}}',
        ]
        event = adapter.parse_stream_event(lines)
        assert event is not None
        assert event.output_tokens == 15

    def test_message_stop(self, adapter):
        lines = [
            "event: message_stop",
            'data: {"type":"message_stop"}',
        ]
        event = adapter.parse_stream_event(lines)
        assert event is not None
        assert event.done is True

    def test_error_event(self, adapter):
        lines = [
            "event: error",
            'data: {"type":"error","error":{"type":"overloaded_error","message":"Overloaded"}}',
        ]
        event = adapter.parse_stream_event(lines)
        assert event is not None
        assert event.error == "Overloaded"

    def test_unknown_event_type(self, adapter):
        lines = [
            "event: ping",
            'data: {"type":"ping"}',
        ]
        event = adapter.parse_stream_event(lines)
        assert event is None

    def test_no_data_line(self, adapter):
        lines = ["event: content_block_delta"]
        event = adapter.parse_stream_event(lines)
        assert event is None

    def test_invalid_json(self, adapter):
        lines = ["event: content_block_delta", "data: not-json"]
        event = adapter.parse_stream_event(lines)
        assert event is None


class TestToOpenaiSse:
    def test_text_event(self, adapter):
        from app.services.provider_adapters.base import StreamEvent
        event = StreamEvent(text="Hi")
        result = adapter.to_openai_sse(event)
        assert result.startswith("data: ")
        data = json.loads(result.replace("data: ", "").strip())
        assert data["choices"][0]["delta"]["content"] == "Hi"

    def test_done_event(self, adapter):
        from app.services.provider_adapters.base import StreamEvent
        event = StreamEvent(done=True)
        result = adapter.to_openai_sse(event)
        assert "data: [DONE]" in result

    def test_error_event(self, adapter):
        from app.services.provider_adapters.base import StreamEvent
        event = StreamEvent(error="Something failed")
        result = adapter.to_openai_sse(event)
        assert result.startswith("data: ")
        data = json.loads(result.replace("data: ", "").strip())
        assert data["error"]["message"] == "Something failed"

    def test_empty_event(self, adapter):
        from app.services.provider_adapters.base import StreamEvent
        event = StreamEvent()
        result = adapter.to_openai_sse(event)
        assert result == ""


class TestFormatError:
    def test_format(self, adapter):
        result = adapter.format_error(500, {"detail": "Internal error"})
        assert result["type"] == "error"
        assert result["error"]["message"] == "Internal error"


class TestErrorSse:
    def test_format(self, adapter):
        result = adapter.error_sse("timeout", "timeout")
        assert "event: error" in result
        assert "data:" in result
        # Parse the data line
        for line in result.split("\n"):
            if line.startswith("data:"):
                data = json.loads(line[5:].strip())
                assert data["error"]["message"] == "timeout"
                break
