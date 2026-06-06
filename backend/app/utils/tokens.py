"""Token estimation utilities.

Single source of truth for "rough" token counting used to seed the
``AuditLog.request_tokens`` column before the upstream returns its
authoritative usage chunk. The estimate is intentionally conservative
(~3 chars per token for mixed Chinese / English) and is overwritten by
the upstream-reported count whenever the usage chunk arrives.

Three call sites used to roll their own version of this logic (chat
service, gateway service, Anthropic bridge router); the canonical
implementation lives here so all paths agree.
"""


# Conservative heuristic: 1 token ≈ 3 characters across mixed CJK / Latin
# text. Real models use BPE; this is a deliberately rough estimator.
CHARS_PER_TOKEN = 3


def estimate_tokens(messages: list[dict]) -> int:
    """Rough input-token estimate from an OpenAI / Anthropic message list.

    Walks each message's ``content`` field:
      - ``str`` content: counted by length
      - ``list`` content (Anthropic content blocks): sums ``text`` per dict part
      - anything else: skipped (the old inline ``str(content)`` would
        coerce numbers / None to a misleading "1"; skipping is safer)

    Returns at least 1 so a non-empty message list never logs 0 tokens.
    """
    total_chars = 0
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            total_chars += len(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict):
                    total_chars += len(part.get("text", ""))
    return max(1, total_chars // CHARS_PER_TOKEN)
