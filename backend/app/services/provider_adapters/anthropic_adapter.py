"""Anthropic Messages API protocol adapter."""

import json

from .base import BaseAdapter, StreamEvent


class AnthropicAdapter(BaseAdapter):
    """Handles Anthropic Messages API protocol."""

    @property
    def provider_name(self) -> str:
        return "anthropic"

    def build_upstream_url(self, target_url: str) -> str:
        return target_url.rstrip("/") + "/messages"

    def build_headers(self, api_key: str) -> dict:
        return {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

    def build_request_body(
        self, body: dict, target_model: str, defaults: dict
    ) -> dict:
        forward_body = {**body, "model": target_model}
        # max_tokens is required for Anthropic
        if "max_tokens" not in forward_body and defaults.get("max_tokens"):
            forward_body["max_tokens"] = defaults["max_tokens"]
        if defaults.get("temperature") is not None and "temperature" not in body:
            forward_body["temperature"] = defaults["temperature"]
        return forward_body

    def extract_response(self, response: dict) -> tuple[str, int, int]:
        usage = response.get("usage", {})
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)

        content_blocks = response.get("content", [])
        content = ""
        for block in content_blocks:
            if block.get("type") == "text":
                content += block.get("text", "")

        return content, input_tokens, output_tokens

    def parse_stream_event(self, lines: list[str]) -> StreamEvent | None:
        """Parse Anthropic SSE lines.

        Anthropic format uses event: + data: pairs:
            event: content_block_delta
            data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"Hello"}}

            event: message_stop
            data: {"type":"message_stop"}
        """
        event_type = None
        data_json = None

        for line in lines:
            if line.startswith("event:"):
                event_type = line[6:].strip()
            elif line.startswith("data:"):
                data_str = line[5:].strip()
                try:
                    data_json = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

        if data_json is None:
            return None

        msg_type = data_json.get("type", event_type or "")

        if msg_type == "message_stop":
            return StreamEvent(done=True)

        if msg_type == "content_block_delta":
            delta = data_json.get("delta", {})
            text = delta.get("text", "")
            if text:
                return StreamEvent(text=text)

        if msg_type == "message_start":
            message = data_json.get("message", {})
            usage = message.get("usage", {})
            return StreamEvent(
                input_tokens=usage.get("input_tokens", 0),
            )

        if msg_type == "message_delta":
            usage = data_json.get("usage", {})
            return StreamEvent(
                output_tokens=usage.get("output_tokens", 0),
            )

        if msg_type == "error":
            error_info = data_json.get("error", {})
            return StreamEvent(error=error_info.get("message", "Unknown error"))

        return None

    def format_error(self, status: int, body: dict) -> dict:
        return {
            "type": "error",
            "error": {
                "type": body.get("error", {}).get("type", "api_error"),
                "message": body.get("detail", body.get("error", {}).get("message", str(body))),
            },
        }

    def error_sse(self, message: str, error_type: str = "upstream_error") -> str:
        error_data = json.dumps(
            {
                "type": "error",
                "error": {"type": error_type, "message": message},
            }
        )
        return f"event: error\ndata: {error_data}\n\n"

    def to_openai_sse(self, event: StreamEvent) -> str:
        """Convert Anthropic StreamEvent to OpenAI SSE format for Chat page."""
        if event.done:
            return "data: [DONE]\n\n"
        if event.error:
            error_data = json.dumps(
                {"error": {"message": event.error, "type": "upstream_error"}}
            )
            return f"data: {error_data}\n\n"
        if event.text:
            chunk = {
                "choices": [
                    {
                        "delta": {"content": event.text},
                        "index": 0,
                        "finish_reason": None,
                    }
                ]
            }
            return f"data: {json.dumps(chunk)}\n\n"
        return ""
