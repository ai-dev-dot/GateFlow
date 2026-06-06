"""Unit tests for the P1-2 byte-level SSE bridge.

Covers ``AnthropicBridgeTransformer``:
- Single-chunk round-trip (OpenAI SSE in → Anthropic SSE out)
- Chunks split on line boundary (buffer state survives across calls)
- [DONE] short-circuits further output
- Malformed JSON lines are skipped silently
- Multi-event chunk (one chunk contains many `data:` lines)
- ``flush()`` drains trailing content without trailing newline
- ``flush()`` returns empty buffer cleanly
"""

import json
import re

from app.services.provider_adapters.anthropic_adapter import AnthropicBridgeTransformer


def _openai_chunk(
    *,
    msg_id: str = "chatcmpl-x",
    model: str = "deepseek-chat",
    role: str | None = None,
    content: str | None = None,
    finish_reason: str | None = None,
    usage: dict | None = None,
) -> bytes:
    """Build a single OpenAI SSE data chunk (without trailing blank line)."""
    data: dict = {"id": msg_id, "model": model, "choices": [], "object": "chat.completion.chunk"}
    if role is not None or content is not None or finish_reason is not None:
        delta: dict = {}
        if role is not None:
            delta["role"] = role
        if content is not None:
            delta["content"] = content
        data["choices"] = [{"index": 0, "delta": delta, "finish_reason": finish_reason}]
    if usage is not None:
        data["usage"] = usage
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n".encode()


def _text_payload(s: bytes) -> list[str]:
    """Extract all `"text": "..."` values from a transformed SSE blob."""
    return re.findall(r'"text":\s*"([^"]*)"', s.decode("utf-8"))


def test_first_chunk_emits_message_start_and_block_start():
    """First chunk with role=assistant emits Anthropic message_start + content_block_start."""
    t = AnthropicBridgeTransformer()
    out = t(_openai_chunk(role="assistant")).decode("utf-8")

    assert "event: message_start" in out
    assert "event: content_block_start" in out


def test_text_delta_emits_content_block_delta():
    t = AnthropicBridgeTransformer()
    t(_openai_chunk(role="assistant"))  # drain first-chunk events
    out = t(_openai_chunk(content="Hello")).decode("utf-8")

    assert "event: content_block_delta" in out
    assert _text_payload(out.encode("utf-8")) == ["Hello"]


def test_finish_reason_emits_block_stop_and_message_stop():
    t = AnthropicBridgeTransformer()
    t(_openai_chunk(role="assistant"))
    t(_openai_chunk(content="x"))
    out = t(
        _openai_chunk(content="", finish_reason="stop", usage={"completion_tokens": 7})
    ).decode("utf-8")

    assert "event: content_block_stop" in out
    assert "event: message_stop" in out
    # Usage propagates into the message_delta event
    assert '"output_tokens": 7' in out or '"output_tokens":7' in out


def test_done_marker_short_circuits():
    """After [DONE] the transformer returns empty bytes for any further input."""
    t = AnthropicBridgeTransformer()
    t(_openai_chunk(role="assistant"))
    t(b"data: [DONE]\n\n")
    # Any further input is ignored
    assert t(_openai_chunk(content="ignored")) == b""
    assert t(b"more bytes") == b""


def test_malformed_json_lines_skipped():
    """Invalid JSON in a data line is skipped without aborting the transform."""
    t = AnthropicBridgeTransformer()
    t(_openai_chunk(role="assistant"))
    out = t(b"data: {not valid json}\n\n" + _openai_chunk(content="ok")).decode("utf-8")
    assert _text_payload(out.encode("utf-8")) == ["ok"]


def test_empty_data_line_skipped():
    t = AnthropicBridgeTransformer()
    t(_openai_chunk(role="assistant"))
    # bare "data:" with no payload — should not crash
    out = t(b"data: \n\n" + _openai_chunk(content="x")).decode("utf-8")
    assert _text_payload(out.encode("utf-8")) == ["x"]


def test_chunk_split_across_line_boundary():
    """If a chunk ends mid-line, the next call must continue from the buffer."""
    t = AnthropicBridgeTransformer()
    t(_openai_chunk(role="assistant"))
    # Split the content chunk in half at a random byte
    full = _openai_chunk(content="split_here")
    cut = len(full) // 2
    out1 = t(full[:cut]).decode("utf-8")
    out2 = t(full[cut:]).decode("utf-8")
    combined = out1 + out2
    assert _text_payload(combined.encode("utf-8")) == ["split_here"]


def test_multiple_data_lines_in_one_chunk():
    """A single upstream chunk may contain many `data:` lines; all should be processed."""
    t = AnthropicBridgeTransformer()
    t(_openai_chunk(role="assistant"))
    combined_chunk = _openai_chunk(content="a") + _openai_chunk(content="b")
    out = t(combined_chunk).decode("utf-8")
    assert _text_payload(out.encode("utf-8")) == ["a", "b"]


def test_flush_drains_trailing_content_without_newline():
    """When the upstream ends without a final newline, flush() emits the rest."""
    t = AnthropicBridgeTransformer()
    t(_openai_chunk(role="assistant"))
    # Build a data chunk WITHOUT a trailing blank line so it stays in the buffer
    raw = _openai_chunk(content="partial").rstrip(b"\n")
    out_before_flush = t(raw)
    assert out_before_flush == b""  # all buffered (no newline to trigger split)
    flushed = t.flush().decode("utf-8")
    assert _text_payload(flushed.encode("utf-8")) == ["partial"]


def test_flush_on_empty_buffer_returns_empty():
    t = AnthropicBridgeTransformer()
    assert t.flush() == b""
    # Subsequent flush is also empty
    t(_openai_chunk(role="assistant"))
    assert t(b"").decode("utf-8") == ""  # no input
    assert t.flush() == b""  # nothing buffered beyond what was already emitted


def test_flush_after_done_returns_empty():
    t = AnthropicBridgeTransformer()
    t(_openai_chunk(role="assistant"))
    t(b"data: [DONE]\n\n")
    assert t.flush() == b""


def test_stateful_across_calls():
    """A sequence of small chunks must produce the same text payload as a single large chunk."""
    small = AnthropicBridgeTransformer()
    small(_openai_chunk(role="assistant"))
    out_small = b""
    for ch in [_openai_chunk(content="H"), _openai_chunk(content="i"), _openai_chunk(content="!")]:
        out_small += small(ch)

    big = AnthropicBridgeTransformer()
    big(_openai_chunk(role="assistant"))
    out_big = big(_openai_chunk(content="H") + _openai_chunk(content="i") + _openai_chunk(content="!"))

    assert _text_payload(out_small) == _text_payload(out_big) == ["H", "i", "!"]
