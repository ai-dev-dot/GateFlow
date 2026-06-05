"""Provider adapter registry.

Usage:
    from app.services.provider_adapters import get_adapter
    adapter = get_adapter("anthropic")
    url = adapter.build_upstream_url("https://api.anthropic.com/v1")
"""

from .anthropic_adapter import AnthropicAdapter
from .base import BaseAdapter, StreamEvent
from .openai_adapter import OpenAIAdapter

_adapters: dict[str, type[BaseAdapter]] = {
    "openai": OpenAIAdapter,
    "anthropic": AnthropicAdapter,
}


def get_adapter(provider: str) -> BaseAdapter:
    """Get an adapter instance for the given provider name.

    Falls back to OpenAIAdapter for unknown providers (backward compatible).
    """
    cls = _adapters.get(provider.lower())
    if cls is None:
        # Default to OpenAI for unknown providers (backward compatible)
        return OpenAIAdapter()
    return cls()


def register_adapter(provider: str, adapter_cls: type[BaseAdapter]) -> None:
    """Register a custom adapter for a provider."""
    _adapters[provider.lower()] = adapter_cls


__all__ = ["get_adapter", "register_adapter", "BaseAdapter", "StreamEvent"]
