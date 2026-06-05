"""Anthropic Messages API protocol adapter."""

import json
import uuid

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

    def build_request_body(self, body: dict, target_model: str, defaults: dict) -> dict:
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
            error_data = json.dumps({"error": {"message": event.error, "type": "upstream_error"}})
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

    # --- Protocol bridge: Anthropic <-> OpenAI format conversion ---

    def to_openai_request(self, body: dict, target_model: str) -> dict:
        """Convert Anthropic request body to OpenAI format.

        Used when client sends Anthropic format but upstream is OpenAI-compatible.
        """
        messages = []
        # Extract system prompt
        system = body.get("system")
        if system:
            messages.append({"role": "system", "content": system})
        # Convert messages (Anthropic uses same role names, just needs content extraction)
        for msg in body.get("messages", []):
            role = msg["role"]
            content = msg.get("content", "")
            # Handle Anthropic content blocks (list of dicts)
            if isinstance(content, list):
                text_parts = [p.get("text", "") for p in content if p.get("type") == "text"]
                content = "\n".join(text_parts)
            messages.append({"role": role, "content": content})

        openai_body = {
            "model": target_model,
            "messages": messages,
        }
        if "max_tokens" in body:
            openai_body["max_tokens"] = body["max_tokens"]
        if "temperature" in body:
            openai_body["temperature"] = body["temperature"]
        if "stream" in body:
            openai_body["stream"] = body["stream"]
        return openai_body

    def from_openai_response(self, response: dict) -> dict:
        """Convert OpenAI response to Anthropic format.

        Used when upstream returns OpenAI format but client expects Anthropic format.
        """
        usage = response.get("usage", {})
        content_text = ""
        choices = response.get("choices", [])
        if choices:
            content_text = choices[0].get("message", {}).get("content", "")

        return {
            "id": f"msg_{uuid.uuid4().hex[:24]}",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": content_text}],
            "model": response.get("model", ""),
            "stop_reason": "end_turn",
            "usage": {
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
            },
        }

    def from_openai_sse_chunk(self, data: dict) -> str:
        """Convert an OpenAI SSE data chunk to Anthropic SSE format.

        Returns the Anthropic SSE string (may be multiple events).
        """
        msg_id = data.get("id", "")
        model = data.get("model", "")
        choices = data.get("choices", [])
        usage = data.get("usage")

        events = ""

        # If this is the first chunk with role, emit message_start
        if choices and choices[0].get("delta", {}).get("role") == "assistant":
            start_data = json.dumps(
                {
                    "type": "message_start",
                    "message": {
                        "id": f"msg_{msg_id}" if msg_id else f"msg_{uuid.uuid4().hex[:24]}",
                        "type": "message",
                        "role": "assistant",
                        "content": [],
                        "model": model,
                        "usage": {"input_tokens": 0, "output_tokens": 0},
                    },
                }
            )
            events += f"event: message_start\ndata: {start_data}\n\n"
            # Emit content_block_start
            block_start = json.dumps(
                {
                    "type": "content_block_start",
                    "index": 0,
                    "content_block": {"type": "text", "text": ""},
                }
            )
            events += f"event: content_block_start\ndata: {block_start}\n\n"

        # Emit content from delta
        if choices:
            delta = choices[0].get("delta", {})
            content = delta.get("content")
            if content:
                delta_data = json.dumps(
                    {
                        "type": "content_block_delta",
                        "index": 0,
                        "delta": {"type": "text_delta", "text": content},
                    }
                )
                events += f"event: content_block_delta\ndata: {delta_data}\n\n"

        # If finish_reason is set, emit stop events
        if choices and choices[0].get("finish_reason"):
            # content_block_stop
            block_stop = json.dumps({"type": "content_block_stop", "index": 0})
            events += f"event: content_block_stop\ndata: {block_stop}\n\n"
            # message_delta with usage
            output_tokens = 0
            if usage:
                output_tokens = usage.get("completion_tokens", 0)
            msg_delta = json.dumps(
                {
                    "type": "message_delta",
                    "delta": {"stop_reason": "end_turn"},
                    "usage": {"output_tokens": output_tokens},
                }
            )
            events += f"event: message_delta\ndata: {msg_delta}\n\n"
            # message_stop
            events += f"event: message_stop\ndata: {json.dumps({'type': 'message_stop'})}\n\n"

        # If usage is in final chunk (no choices), emit token info
        if usage and not choices:
            msg_delta = json.dumps(
                {
                    "type": "message_delta",
                    "delta": {"stop_reason": "end_turn"},
                    "usage": {"output_tokens": usage.get("completion_tokens", 0)},
                }
            )
            events += f"event: message_delta\ndata: {msg_delta}\n\n"
            events += f"event: message_stop\ndata: {json.dumps({'type': 'message_stop'})}\n\n"

        return events
