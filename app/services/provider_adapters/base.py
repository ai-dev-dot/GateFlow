"""Base adapter for upstream LLM provider protocol differences."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class StreamEvent:
    """Parsed result from a single SSE message."""

    text: str = ""  # Incremental text content
    input_tokens: int = 0  # Input token count (0 if not reported this event)
    output_tokens: int = 0  # Output token count (0 if not reported this event)
    done: bool = False  # Whether the stream has ended
    error: str = ""  # Error message if any


class BaseAdapter(ABC):
    """Abstract base for provider-specific protocol handling.

    Each adapter knows how to:
    - Build the upstream URL, headers, and request body
    - Parse streaming SSE events and non-streaming responses
    - Format errors in the provider's native format
    - Convert StreamEvent to OpenAI SSE format (for Chat page)
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provider identifier, e.g. 'openai', 'anthropic'."""

    @abstractmethod
    def build_upstream_url(self, target_url: str) -> str:
        """Build the full upstream endpoint URL.

        Args:
            target_url: Base URL from ModelConfig, e.g. "https://api.openai.com/v1"
        """

    @abstractmethod
    def build_headers(self, api_key: str) -> dict:
        """Build request headers including authentication."""

    @abstractmethod
    def build_request_body(self, body: dict, target_model: str, defaults: dict) -> dict:
        """Build the upstream request body.

        Injects target_model and applies default temperature/max_tokens
        from ModelConfig when not present in the original body.

        Args:
            body: Original request body from client
            target_model: Actual model name from ModelConfig
            defaults: {"temperature": float|None, "max_tokens": int|None}
        """

    @abstractmethod
    def extract_response(self, response: dict) -> tuple[str, int, int]:
        """Extract content and token counts from a non-streaming response.

        Returns:
            (content, input_tokens, output_tokens)
        """

    @abstractmethod
    def parse_stream_event(self, lines: list[str]) -> StreamEvent | None:
        """Parse a group of SSE lines into a StreamEvent.

        Args:
            lines: A group of consecutive non-empty lines from the SSE stream,
                   e.g. ["event: content_block_delta", "data: {...}"].
                   An empty line signals the end of a group.

        Returns:
            StreamEvent if the lines represent a parseable event, None to skip.
        """

    @abstractmethod
    def format_error(self, status: int, body: dict) -> dict:
        """Format an error response body for the client."""

    @abstractmethod
    def error_sse(self, message: str, error_type: str = "upstream_error") -> str:
        """Generate an SSE-formatted error message string (including data: prefix)."""

    @abstractmethod
    def to_openai_sse(self, event: StreamEvent) -> str:
        """Convert a StreamEvent to OpenAI-compatible SSE format.

        Used by ChatService to normalize responses for the frontend,
        which always expects choices[].delta.content format.
        """
