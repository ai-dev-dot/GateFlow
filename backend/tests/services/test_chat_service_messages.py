"""Unit tests for ``ChatService.get_messages`` (P1-4).

Locks down the new contract: ``None`` for missing/unauthorized
conversation, ``[]`` for empty but owned conversation. Replaces the
old "return [], then router queries all conversations" pattern that
was an O(N) N+1 on every 404.
"""

from uuid import uuid4

import pytest

from app.models.chat import Conversation, Message
from app.services.chat_service import ChatService


async def _make_conversation(db, user, *, model="gpt-4", title=None):
    conv = Conversation(user_id=user.id, model=model, title=title)
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


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
async def test_get_messages_returns_empty_list_for_owned_empty_conversation(
    db_session, test_user
):
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
