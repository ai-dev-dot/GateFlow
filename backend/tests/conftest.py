"""Shared fixtures for GateFlow tests."""

import pytest
from app.services.provider_adapters import get_adapter, OpenAIAdapter, AnthropicAdapter


@pytest.fixture
def openai_adapter():
    return OpenAIAdapter()


@pytest.fixture
def anthropic_adapter():
    return AnthropicAdapter()
