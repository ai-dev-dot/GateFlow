"""Unit tests for P1-6: chat user_message orphan on LLM failure.

P1-6 ensures that when the LLM call fails, the user message is NOT
left in the database without a corresponding AI response. The user
should not see a stranded question with no answer.

Two paths are covered:
- send_message (non-streaming): user_message + AI message share one
  transaction. If _call_llm raises, the transaction rolls back and
  neither is persisted.
- send_message_stream (streaming): user_message is committed early
  (the on_complete hook runs in a NEW session and needs to see it).
  When the stream fails, the hook deletes the orphan user_message.

Verification uses a FRESH session (via _session_factory) because the
test's own session has its identity map populated with the
(uncommitted) Message objects — re-querying on the same session
would return the cached rows even after a real rollback.
"""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.models.chat import Conversation, Message
from app.models.gateway import ModelConfig
from app.models.provider_key import ProviderAPIKey
from app.services.chat_service import ChatService
from app.utils.crypto import encrypt_key, key_preview


def _session_factory(db_session):
    """Build a session factory bound to the test engine so verification
    can see committed state (the test session's identity map is stale
    after a rollback or a delete in another path).
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker

    engine = db_session.bind
    return async_sessionmaker(engine, expire_on_commit=False)


async def _make_conversation(db, user, *, model="gpt-4"):
    conv = Conversation(user_id=user.id, model=model, title=None)
    db.add(conv)
    # send_message_stream looks up a real ModelConfig by model_alias AND
    # an active ProviderAPIKey before calling the forwarder — stub both.
    db.add(
        ModelConfig(
            model_alias=model,
            provider="openai",
            target_model="gpt-4",
            target_url="https://api.openai.com/v1",
            is_active=True,
        )
    )
    db.add(
        ProviderAPIKey(
            provider="openai",
            encrypted_key=encrypt_key("sk-test"),
            key_preview=key_preview("sk-test"),
            name="test-key",
            is_active=True,
        )
    )
    await db.commit()
    await db.refresh(conv)
    return conv


async def _count_messages(verify_session, conversation_id):
    result = await verify_session.execute(
        select(Message).where(Message.conversation_id == conversation_id)
    )
    return list(result.scalars().all())


# ---------- send_message (non-streaming) ----------


@pytest.mark.asyncio
async def test_send_message_rolls_back_user_message_when_llm_raises(
    db_session, test_user
):
    """If _call_llm raises (currently defensive — it doesn't, but might
    in future), the user_message must NOT be persisted without a
    matching AI response.
    """
    conv = await _make_conversation(db_session, test_user)
    factory = _session_factory(db_session)
    service = ChatService(db_session)
    # Capture the id before any potential rollback expires attributes.
    conv_id = conv.id

    with (
        patch.object(
            service,
            "_call_llm",
            new=AsyncMock(side_effect=RuntimeError("simulated upstream blowup")),
        ),
        pytest.raises(RuntimeError, match="simulated upstream blowup"),
    ):
        await service.send_message(conv_id, test_user, "hello?")

    # The test session is still open and the rolled-back transaction
    # shares the StaticPool connection with the verify session, which
    # would let it see uncommitted data. Explicitly close the test
    # session's transaction so the verify session gets a clean view.
    await db_session.rollback()

    async with factory() as verify:
        msgs = await _count_messages(verify, conv_id)
    assert msgs == [], f"expected no committed messages, found {[m.role for m in msgs]}"


@pytest.mark.asyncio
async def test_send_message_persists_both_on_success(db_session, test_user):
    """Sanity check: with a working _call_llm, both user + AI messages persist."""
    conv = await _make_conversation(db_session, test_user)
    factory = _session_factory(db_session)
    service = ChatService(db_session)

    with patch.object(
        service,
        "_call_llm",
        new=AsyncMock(return_value=("hi back", 5)),
    ):
        result = await service.send_message(conv.id, test_user, "hello")

    assert result is not None
    assert result.role == "assistant"
    async with factory() as verify:
        msgs = (
            await verify.execute(
                select(Message)
                .where(Message.conversation_id == conv.id)
                .order_by(Message.created_at)
            )
        ).scalars().all()
    assert [m.role for m in msgs] == ["user", "assistant"]
    assert [m.content for m in msgs] == ["hello", "hi back"]


# ---------- send_message_stream (streaming) ----------


class _FakeResponse:
    """Stand-in for a StreamingResponse (the test never reads its body)."""

    body_iterator = iter([])


async def _setup_stream_capture(db_session, test_user, conv_id, content):
    """Drive send_message_stream with a mocked StreamForwarder that
    captures the on_complete closure for the test to invoke directly.
    """
    service = ChatService(db_session)
    captured: dict = {}

    async def fake_forward(*, on_complete, **kwargs):
        captured["on_complete"] = on_complete
        return _FakeResponse()

    with patch(
        "app.services.chat_service.StreamForwarder.forward",
        new=AsyncMock(side_effect=fake_forward),
    ):
        result = await service.send_message_stream(conv_id, test_user, content)
    return captured["on_complete"], result


@pytest.mark.asyncio
async def test_send_message_stream_deletes_orphan_on_stream_failure(
    db_session, test_user
):
    """When the upstream stream fails (status_code != 200), the
    on_complete hook must delete the orphan user_message.
    """
    conv = await _make_conversation(db_session, test_user)
    factory = _session_factory(db_session)

    on_complete, _ = await _setup_stream_capture(
        db_session, test_user, conv.id, "hello stream"
    )

    # Sanity: the user_message is committed and visible to a fresh session
    async with factory() as verify:
        pre = await _count_messages(verify, conv.id)
    assert len(pre) == 1 and pre[0].role == "user"

    # Invoke the hook with a FAILED status. In production this runs in a
    # fresh session inside _save_after_stream; for unit-testing the
    # hook's own logic we run it on the test session and commit.
    await on_complete(db_session, full_content="", status_code=500)
    await db_session.commit()

    async with factory() as verify:
        post = await _count_messages(verify, conv.id)
    assert post == [], f"orphan user_message not cleaned up, found {[m.role for m in post]}"


@pytest.mark.asyncio
async def test_send_message_stream_saves_ai_message_on_success(db_session, test_user):
    """Sanity check: on success, the AI message is saved normally."""
    conv = await _make_conversation(db_session, test_user)
    factory = _session_factory(db_session)

    on_complete, _ = await _setup_stream_capture(
        db_session, test_user, conv.id, "stream hi"
    )

    await on_complete(db_session, full_content="streamed response", status_code=200)
    await db_session.commit()

    async with factory() as verify:
        msgs = (
            await verify.execute(
                select(Message)
                .where(Message.conversation_id == conv.id)
                .order_by(Message.created_at)
            )
        ).scalars().all()
    assert [m.role for m in msgs] == ["user", "assistant"]
    assert [m.content for m in msgs] == ["stream hi", "streamed response"]


@pytest.mark.asyncio
async def test_send_message_stream_deletes_orphan_on_empty_content(db_session, test_user):
    """If status_code=200 but no content was streamed (some upstreams
    do this on degenerate input), the on_complete also cleans up the
    orphan so the conversation doesn't show a question with no answer.
    """
    conv = await _make_conversation(db_session, test_user)
    factory = _session_factory(db_session)

    on_complete, _ = await _setup_stream_capture(
        db_session, test_user, conv.id, "stream empty"
    )
    await on_complete(db_session, full_content="", status_code=200)
    await db_session.commit()

    async with factory() as verify:
        msgs = await _count_messages(verify, conv.id)
    assert msgs == []


@pytest.mark.asyncio
async def test_send_message_stream_does_not_touch_other_conversations(
    db_session, test_user
):
    """The orphan cleanup must target the specific user_message by id,
    not by conversation_id (which could match messages from other convos
    in concurrent / interleaved scenarios).
    """
    conv_a = await _make_conversation(db_session, test_user, model="model-a")
    conv_b = await _make_conversation(db_session, test_user, model="model-b")
    factory = _session_factory(db_session)

    # Pre-seed conv_b with a user message that should survive the cleanup
    db_session.add(
        Message(conversation_id=conv_b.id, role="user", content="untouched", tokens=1)
    )
    await db_session.commit()

    on_complete, _ = await _setup_stream_capture(
        db_session, test_user, conv_a.id, "this one fails"
    )
    await on_complete(db_session, full_content="", status_code=504)
    await db_session.commit()

    async with factory() as verify:
        a_msgs = await _count_messages(verify, conv_a.id)
        b_msgs = await _count_messages(verify, conv_b.id)

    assert a_msgs == [], "conv_a orphan should be cleaned up"
    assert len(b_msgs) == 1 and b_msgs[0].content == "untouched", (
        "conv_b message must not be touched"
    )
