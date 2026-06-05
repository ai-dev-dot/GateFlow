"""OpenAI protocol adapter."""

import json

from .base import BaseAdapter, StreamEvent


class OpenAIAdapter(BaseAdapter):
    """Handles OpenAI-compatible chat completions protocol."""

    @property
    def provider_name(self) -> str:
        return "openai"

    def build_upstream_url(self, target_url: str) -> str:
        return target_url.rstrip("/") + "/chat/completions"

    def build_headers(self, api_key: str) -> dict:
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def build_request_body(self, body: dict, target_model: str, defaults: dict) -> dict:
        forward_body = {**body, "model": target_model}
        if defaults.get("temperature") is not None and "temperature" not in body:
            forward_body["temperature"] = defaults["temperature"]
        if defaults.get("max_tokens") is not None and "max_tokens" not in body:
            forward_body["max_tokens"] = defaults["max_tokens"]
        return forward_body

    def extract_response(self, response: dict) -> tuple[str, int, int]:
        usage = response.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        choices = response.get("choices", [])
        content = ""
        if choices:
            content = choices[0].get("message", {}).get("content", "")

        return content, input_tokens, output_tokens

    def parse_stream_event(self, lines: list[str]) -> StreamEvent | None:
        """Parse OpenAI SSE lines.

        OpenAI format:
            data: {"choices":[{"delta":{"content":"Hello"}}]}
            data: [DONE]
        """
        for line in lines:
            if not line.startswith("data:"):
                continue
            data_str = line[5:].strip()
            if data_str == "[DONE]":
                return StreamEvent(done=True)
            try:
                data = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            event = StreamEvent()
            # Extract usage from the final chunk (when stream_options.include_usage is set)
            usage = data.get("usage")
            if usage:
                event.input_tokens = usage.get("prompt_tokens", 0)
                event.output_tokens = usage.get("completion_tokens", 0)

            # Extract delta content
            choices = data.get("choices", [])
            for choice in choices:
                delta = choice.get("delta", {})
                content = delta.get("content")
                if content:
                    event.text += content

            return event
        return None

    def format_error(self, status: int, body: dict) -> dict:
        return {
            "error": {
                "message": body.get("detail", str(body)),
                "type": "upstream_error",
                "code": status,
            }
        }

    def error_sse(self, message: str, error_type: str = "upstream_error") -> str:
        error_data = json.dumps({"error": {"message": message, "type": error_type}})
        return f"data: {error_data}\n\n"

    def to_openai_sse(self, event: StreamEvent) -> str:
        """OpenAI events pass through unchanged."""
        if event.done:
            return "data: [DONE]\n\n"
        if event.error:
            return self.error_sse(event.error)
        if event.text:
            chunk = {
                "choices": [{"delta": {"content": event.text}, "index": 0, "finish_reason": None}]
            }
            return f"data: {json.dumps(chunk)}\n\n"
        return ""
