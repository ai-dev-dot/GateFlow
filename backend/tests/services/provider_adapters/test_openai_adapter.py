"""Tests for OpenAIAdapter."""

import json
import pytest
from app.services.provider_adapters.openai_adapter import OpenAIAdapter


@pytest.fixture
def adapter():
    return OpenAIAdapter()


class TestBuildUpstreamUrl:
    def test_appends_chat_completions(self, adapter):
        assert adapter.build_upstream_url("https://api.openai.com/v1") == "https://api.openai.com/v1/chat/completions"

    def test_strips_trailing_slash(self, adapter):
        assert adapter.build_upstream_url("https://api.openai.com/v1/") == "https://api.openai.com/v1/chat/completions"


class TestBuildHeaders:
    def test_bearer_token(self, adapter):
        headers = adapter.build_headers("sk-test-key")
        assert headers["Authorization"] == "Bearer sk-test-key"
        assert headers["Content-Type"] == "application/json"


class TestBuildRequestBody:
    def test_replaces_model(self, adapter):
        body = adapter.build_request_body(
            {"model": "gpt-4", "messages": [{"role": "user", "content": "hi"}]},
            "gpt-4-0613",
            {},
        )
        assert body["model"] == "gpt-4-0613"

    def test_applies_default_temperature(self, adapter):
        body = adapter.build_request_body(
            {"model": "gpt-4", "messages": []},
            "gpt-4-0613",
            {"temperature": 0.7, "max_tokens": None},
        )
        assert body["temperature"] == 0.7

    def test_does_not_override_explicit_temperature(self, adapter):
        body = adapter.build_request_body(
            {"model": "gpt-4", "messages": [], "temperature": 1.0},
            "gpt-4-0613",
            {"temperature": 0.7, "max_tokens": None},
        )
        assert body["temperature"] == 1.0

    def test_applies_default_max_tokens(self, adapter):
        body = adapter.build_request_body(
            {"model": "gpt-4", "messages": []},
            "gpt-4-0613",
            {"temperature": None, "max_tokens": 4096},
        )
        assert body["max_tokens"] == 4096

    def test_preserves_existing_fields(self, adapter):
        body = adapter.build_request_body(
            {"model": "gpt-4", "messages": [], "stream": True, "top_p": 0.9},
            "gpt-4-0613",
            {},
        )
        assert body["stream"] is True
        assert body["top_p"] == 0.9


class TestExtractResponse:
    def test_extracts_content_and_tokens(self, adapter):
        response = {
            "choices": [{"message": {"content": "Hello world"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        content, input_tokens, output_tokens = adapter.extract_response(response)
        assert content == "Hello world"
        assert input_tokens == 10
        assert output_tokens == 5

    def test_empty_choices(self, adapter):
        response = {"choices": [], "usage": {"prompt_tokens": 10, "completion_tokens": 0}}
        content, _, _ = adapter.extract_response(response)
        assert content == ""

    def test_missing_usage(self, adapter):
        response = {"choices": [{"message": {"content": "Hi"}}]}
        content, input_tokens, output_tokens = adapter.extract_response(response)
        assert content == "Hi"
        assert input_tokens == 0
        assert output_tokens == 0


class TestParseStreamEvent:
    def test_delta_content(self, adapter):
        lines = ['data: {"choices":[{"delta":{"content":"Hello"}}]}']
        event = adapter.parse_stream_event(lines)
        assert event is not None
        assert event.text == "Hello"
        assert event.done is False

    def test_done_marker(self, adapter):
        lines = ["data: [DONE]"]
        event = adapter.parse_stream_event(lines)
        assert event is not None
        assert event.done is True

    def test_usage_in_final_chunk(self, adapter):
        lines = ['data: {"choices":[],"usage":{"prompt_tokens":10,"completion_tokens":20}}']
        event = adapter.parse_stream_event(lines)
        assert event is not None
        assert event.input_tokens == 10
        assert event.output_tokens == 20

    def test_invalid_json_skipped(self, adapter):
        lines = ["data: not-valid-json"]
        event = adapter.parse_stream_event(lines)
        assert event is None

    def test_no_data_line(self, adapter):
        lines = ["event: ping"]
        event = adapter.parse_stream_event(lines)
        assert event is None

    def test_empty_lines(self, adapter):
        event = adapter.parse_stream_event([])
        assert event is None


class TestErrorSse:
    def test_format(self, adapter):
        result = adapter.error_sse("timeout", "timeout")
        assert result.startswith("data: ")
        assert "[DONE]" not in result
        data = json.loads(result.replace("data: ", "").strip())
        assert data["error"]["message"] == "timeout"
        assert data["error"]["type"] == "timeout"


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

    def test_empty_event(self, adapter):
        from app.services.provider_adapters.base import StreamEvent
        event = StreamEvent()
        result = adapter.to_openai_sse(event)
        assert result == ""
