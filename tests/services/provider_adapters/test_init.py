"""Tests for adapter factory (get_adapter, register_adapter)."""

from app.services.provider_adapters import get_adapter, register_adapter
from app.services.provider_adapters.anthropic_adapter import AnthropicAdapter
from app.services.provider_adapters.base import BaseAdapter
from app.services.provider_adapters.openai_adapter import OpenAIAdapter


class TestGetAdapter:
    def test_openai(self):
        adapter = get_adapter("openai")
        assert isinstance(adapter, OpenAIAdapter)

    def test_anthropic(self):
        adapter = get_adapter("anthropic")
        assert isinstance(adapter, AnthropicAdapter)

    def test_case_insensitive(self):
        assert isinstance(get_adapter("OpenAI"), OpenAIAdapter)
        assert isinstance(get_adapter("ANTHROPIC"), AnthropicAdapter)

    def test_unknown_falls_back_to_openai(self):
        adapter = get_adapter("some-new-provider")
        assert isinstance(adapter, OpenAIAdapter)


class TestRegisterAdapter:
    def test_custom_adapter(self):
        class CustomAdapter(BaseAdapter):
            @property
            def provider_name(self):
                return "custom"

            def build_upstream_url(self, target_url):
                return target_url

            def build_headers(self, api_key):
                return {}

            def build_request_body(self, body, target_model, defaults):
                return body

            def extract_response(self, response):
                return "", 0, 0

            def parse_stream_event(self, lines):
                return None

            def format_error(self, status, body):
                return {}

            def error_sse(self, message, error_type="error"):
                return ""

            def to_openai_sse(self, event):
                return ""

        register_adapter("custom", CustomAdapter)
        adapter = get_adapter("custom")
        assert isinstance(adapter, CustomAdapter)
        assert adapter.provider_name == "custom"

    def teardown_method(self):
        # Clean up: re-register to avoid polluting other tests
        from app.services.provider_adapters import _adapters

        _adapters.pop("custom", None)
