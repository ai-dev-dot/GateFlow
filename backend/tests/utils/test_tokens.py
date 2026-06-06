"""Unit tests for ``app.utils.tokens.estimate_tokens`` (P2-4).

Locks down the canonical token estimator used by chat / gateway / bridge
paths so all three call sites share one behaviour.
"""


from app.utils.tokens import CHARS_PER_TOKEN, estimate_tokens


def test_string_content_counted_by_length():
    assert estimate_tokens([{"role": "user", "content": "abcdef"}]) == 2  # 6 // 3


def test_default_chars_per_token():
    # Default heuristic: 3 chars per token. 9 chars = 3 tokens.
    assert estimate_tokens([{"role": "user", "content": "a" * 9}]) == 3


def test_empty_message_list_returns_one():
    # At least 1 even for an empty list, so audit rows never log 0.
    assert estimate_tokens([]) == 1


def test_missing_content_defaults_to_empty_string():
    # A message with no `content` key should be treated as if content=""
    assert estimate_tokens([{"role": "user"}]) == 1  # 0 chars, floor to 1


def test_anthropic_content_block_list():
    """Anthropic content is a list of blocks; sum the text parts."""
    messages = [
        {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Hello "},  # 6 chars
                {"type": "tool_use", "id": "x", "name": "y"},  # ignored
                {"type": "text", "text": "world"},  # 5 chars
            ],
        }
    ]
    assert estimate_tokens(messages) == max(1, 11 // CHARS_PER_TOKEN)  # 11 // 3 = 3


def test_multiple_messages_summed():
    messages = [
        {"role": "system", "content": "a" * 30},  # 10
        {"role": "user", "content": "b" * 30},  # 10
    ]
    assert estimate_tokens(messages) == 20


def test_non_string_non_list_content_skipped():
    """A weird content type (e.g. int, None) is skipped, not coerced.

    The old inline implementation used ``str(content)`` which would turn
    ``None`` into ``"None"`` (4 chars) and inflate the estimate. The new
    estimator skips such values to avoid garbage.
    """
    messages = [
        {"role": "user", "content": None},
        {"role": "user", "content": 12345},
    ]
    assert estimate_tokens(messages) == 1


def test_part_dict_without_text_field_treated_as_empty():
    messages = [
        {
            "role": "assistant",
            "content": [
                {"type": "image", "source": "..."},  # no 'text' key
            ],
        }
    ]
    # 0 chars from this message, but other content present in other msgs is fine.
    assert estimate_tokens(messages) == 1


def test_call_sites_agree_on_typical_message():
    """The three legacy implementations should all give the same answer
    as the canonical one for a typical input.
    """
    messages = [{"role": "user", "content": "Tell me a joke"}]

    # Canonical
    canonical = estimate_tokens(messages)

    # Old chat_service implementation
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            total += len(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict):
                    total += len(part.get("text", ""))
    old_chat = max(1, total // 3)

    # Old anthropic_forward inline (used str() coercion)
    old_anthropic = max(1, sum(len(str(m.get("content", ""))) for m in messages) // 3)

    assert canonical == old_chat == old_anthropic
