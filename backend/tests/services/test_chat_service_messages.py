"""Unit tests for ``ChatService.get_messages`` (P1-4) and
``ChatService._get_capped_history`` (P1-5).

P1-4: ``None`` for missing/unauthorized conversation, ``[]`` for empty
but owned conversation. Replaces the old "return [], then router
queries all conversations" pattern that was an O(N) N+1 on every 404.

P1-5: the history pull is capped at MAX_HISTORY_MESSAGES (system
messages are always included regardless of the cap) so a long
conversation doesn't blow the LLM context window.
"""

from uuid import uuid4

import pytest

from app.models.chat import Conversation, Message
from app.services.chat_service import MAX_HISTORY_MESSAGES, ChatService


async def _make_conversation(db, user, *, model="gpt-4", title=None):
    conv = Conversation(user_id=user.id, model=model, title=title)
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


async def _add_messages(db, conv_id, contents, *, role="user", tokens=1):
    for content in contents:
        db.add(Message(conversation_id=conv_id, role=role, content=content, tokens=tokens))
    await db.commit()


# ---------- P1-4: get_messages ----------


@pytest.mark.asyncio
async def test_get_messages_returns_none_for_nonexistent_conversation(db_session, test_user):
    """Unknown conversation id → None (router maps to 404)."""
    result = await ChatService(db_session).get_messages(uuid4(), test_user)
    assert result is None


@pytest.mark.asyncio
async def test_get_messages_returns_none_for_other_users_conversation(db_session, test_user):
    """A conversation owned by someone else must not leak (None, not []).

    [] would be ambiguous between 'no messages' and 'no permission',
    and the previous N+1 workaround would have fetched ALL of
    test_user's conversations to disambiguate — itself a leak vector.
    """
    other_id = uuid4()
    other_conv = Conversation(user_id=other_id, model="gpt-4", title="private")
    db_session.add(other_conv)
    await db_session.commit()
    await db_session.refresh(other_conv)

    result = await ChatService(db_session).get_messages(other_conv.id, test_user)
    assert result is None


@pytest.mark.asyncio
async def test_get_messages_returns_empty_list_for_owned_empty_conversation(db_session, test_user):
    """A real conversation with no messages must return [] (not None)."""
    conv = await _make_conversation(db_session, test_user)
    result = await ChatService(db_session).get_messages(conv.id, test_user)
    assert result == []


@pytest.mark.asyncio
async def test_get_messages_returns_messages_in_order(db_session, test_user):
    """Messages are returned in created_at order."""
    conv = await _make_conversation(db_session, test_user)
    db_session.add_all(
        [
            Message(conversation_id=conv.id, role="user", content="hi", tokens=1),
            Message(conversation_id=conv.id, role="assistant", content="hello", tokens=1),
            Message(conversation_id=conv.id, role="user", content="how are you", tokens=2),
        ]
    )
    await db_session.commit()

    result = await ChatService(db_session).get_messages(conv.id, test_user)
    assert result is not None
    assert [m.content for m in result] == ["hi", "hello", "how are you"]


# ---------- P1-5: _get_capped_history ----------


@pytest.mark.asyncio
async def test_capped_history_returns_empty_for_no_messages(db_session, test_user):
    conv = await _make_conversation(db_session, test_user)
    result = await ChatService(db_session)._get_capped_history(conv.id)
    assert result == []


@pytest.mark.asyncio
async def test_capped_history_returns_all_when_under_cap(db_session, test_user):
    conv = await _make_conversation(db_session, test_user)
    await _add_messages(db_session, conv.id, ["hi", "hello", "how are you"], role="user")
    await _add_messages(db_session, conv.id, ["I'm good"], role="assistant")

    history = await ChatService(db_session)._get_capped_history(conv.id)
    assert [m.content for m in history] == ["hi", "hello", "how are you", "I'm good"]


@pytest.mark.asyncio
async def test_capped_history_caps_to_max_history_messages(db_session, test_user):
    """Long conversation → only the most recent MAX_HISTORY_MESSAGES non-system messages."""
    conv = await _make_conversation(db_session, test_user)
    n_extra = MAX_HISTORY_MESSAGES + 20
    contents = [f"msg-{i}" for i in range(n_extra)]
    await _add_messages(db_session, conv.id, contents, role="user")

    history = await ChatService(db_session)._get_capped_history(conv.id)
    assert len(history) == MAX_HISTORY_MESSAGES
    # The most recent MAX_HISTORY_MESSAGES messages, in chronological order.
    expected = contents[-MAX_HISTORY_MESSAGES:]
    assert [m.content for m in history] == expected


@pytest.mark.asyncio
async def test_capped_history_always_includes_system_messages(db_session, test_user):
    """System messages are kept even if they exceed the cap.

    A long-running persona-defining system message must survive the
    cap so the assistant doesn't lose its identity on long convos.
    """
    conv = await _make_conversation(db_session, test_user)
    db_session.add(
        Message(
            conversation_id=conv.id,
            role="system",
            content="You are a helpful assistant.",
            tokens=5,
        )
    )
    n_extra = MAX_HISTORY_MESSAGES + 10
    await _add_messages(db_session, conv.id, [f"u-{i}" for i in range(n_extra)], role="user")
    await _add_messages(db_session, conv.id, [f"a-{i}" for i in range(n_extra)], role="assistant")
    await db_session.commit()

    history = await ChatService(db_session)._get_capped_history(conv.id)
    roles = [m.role for m in history]
    # Exactly one system message at the start
    assert roles[0] == "system"
    assert roles.count("system") == 1
    # Total length = 1 system + MAX_HISTORY_MESSAGES recent
    assert len(history) == 1 + MAX_HISTORY_MESSAGES
    # System message content is preserved verbatim
    assert history[0].content == "You are a helpful assistant."


@pytest.mark.asyncio
async def test_capped_history_orders_system_before_recent(db_session, test_user):
    """System messages come first, then recent messages in chronological order."""
    conv = await _make_conversation(db_session, test_user)
    db_session.add(
        Message(
            conversation_id=conv.id,
            role="system",
            content="be concise",
            tokens=2,
        )
    )
    await _add_messages(db_session, conv.id, ["a", "b", "c"], role="user")
    await db_session.commit()

    history = await ChatService(db_session)._get_capped_history(conv.id)
    assert [m.content for m in history] == ["be concise", "a", "b", "c"]


@pytest.mark.asyncio
async def test_capped_history_isolates_by_conversation(db_session, test_user):
    """Messages from other conversations must not leak in."""
    conv_a = await _make_conversation(db_session, test_user, title="A")
    conv_b = await _make_conversation(db_session, test_user, title="B")
    await _add_messages(db_session, conv_a.id, ["a1", "a2"], role="user")
    await _add_messages(db_session, conv_b.id, ["b1", "b2"], role="user")

    history_a = await ChatService(db_session)._get_capped_history(conv_a.id)
    history_b = await ChatService(db_session)._get_capped_history(conv_b.id)
    assert [m.content for m in history_a] == ["a1", "a2"]
    assert [m.content for m in history_b] == ["b1", "b2"]
