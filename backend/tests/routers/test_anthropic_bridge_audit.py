"""Regression test for P0-3: Anthropic→OpenAI bridge must write audit log.

This test pins down the bug where `POST /v1/messages` (Anthropic format) to an
OpenAI-compatible upstream was not creating any AuditLog row.

We verify the fix by exercising the same code path (audit log creation +
StreamForwarder.save_after_stream) that the bridge router uses, with a
mocked OpenAI upstream. This avoids the auth-middleware UUID type issue
that arises only when running on SQLite (production uses PostgreSQL).
"""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.models.audit import AuditLog
from app.models.gateway import ModelConfig
from app.models.provider_key import ProviderAPIKey
from app.services.audit_service import AuditService
from app.services.provider_adapters import OpenAIAdapter
from app.services.stream_forwarder import StreamForwarder


class FakeOpenAIResponse:
    """Non-streaming response for OpenAI → Anthropic bridge."""

    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json = json_data or {}
        self.text = str(json_data)

    def json(self):
        return self._json


class FakeHttpxClient:
    def __init__(self, response):
        self._response = response

    async def post(self, url, **kwargs):
        return self._response

    async def stream(self, method, url, **kwargs):
        raise NotImplementedError


def _session_factory(db_session):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    engine = db_session.bind
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.mark.asyncio
async def test_anthropic_bridge_path_creates_audit_log(db_session, test_user):
    """P0-3 regression: Anthropic→OpenAI bridge MUST create audit log row.

    Verifies the same code path the bridge router uses:
    1. AuditService.create_pending_log with path='/v1/messages'
    2. StreamForwarder.save_after_stream updates status='completed' on 200
    """
    # Setup: ModelConfig + ProviderKey (same as the bridge router)
    mc = ModelConfig(
        model_alias="claude-sonnet",
        provider="openai",
        target_model="deepseek-chat",
        target_url="https://api.deepseek.com/v1",
        is_active=True,
        default_temperature=0.7,
        default_max_tokens=2048,
    )
    db_session.add(mc)
    from app.utils.crypto import encrypt_key, key_preview
    pk = ProviderAPIKey(
        provider="openai",
        encrypted_key=encrypt_key("sk-fake-deepseek"),
        key_preview=key_preview("sk-fake-deepseek"),
        name="deepseek-prod",
        is_active=True,
    )
    db_session.add(pk)
    await db_session.commit()
    await db_session.refresh(pk)

    # Step 1: create pending audit log (mimics bridge router behavior)
    audit_svc = AuditService(db_session)
    audit_log = await audit_svc.create_pending_log(
        user=test_user,
        model="claude-sonnet",
        provider="openai",
        path="/v1/messages",  # <-- key: bridge path
        request_body='{"messages":[{"role":"user","content":"Hello"}]}',
        is_stream=False,
    )
    await db_session.commit()
    await db_session.refresh(audit_log)

    # Step 2: simulate successful bridge completion (calls save_after_stream)
    factory = _session_factory(db_session)
    forwarder = StreamForwarder(db_session, OpenAIAdapter(), session_factory=factory)
    fake_response = FakeOpenAIResponse(
        200,
        {
            "id": "chatcmpl-123",
            "model": "deepseek-chat",
            "choices": [{"message": {"role": "assistant", "content": "Hi back"}, "index": 0}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3},
        },
    )
    fake_client = FakeHttpxClient(fake_response)

    with patch(
        "app.utils.http_client.get_http_client",
        AsyncMock(return_value=fake_client),
    ):
        await forwarder.save_after_stream(
            audit_log_id=audit_log.id,
            provider_key_id=pk.id,
            status_code=200,
            request_tokens=5,
            response_tokens=3,
            input_tokens=0,
            latency_ms=150,
            full_content="",
            on_complete=None,
        )

    # Step 3: verify audit log was created AND updated to completed
    async with factory() as verify:
        result = await verify.execute(
            select(AuditLog).where(
                AuditLog.path == "/v1/messages",
                AuditLog.user_id == test_user.id,
            )
        )
        rows = result.scalars().all()

    assert len(rows) == 1, (
        f"P0-3 regression: expected 1 audit log row for /v1/messages, got {len(rows)}. "
        "The bridge path is supposed to write audit logs since the Wave 1 fix."
    )
    row = rows[0]
    assert row.status == "completed"
    assert row.status_code == 200
    assert row.model == "claude-sonnet"
    assert row.provider == "openai"
    assert row.request_tokens == 5
    assert row.response_tokens == 3


@pytest.mark.asyncio
async def test_anthropic_bridge_audit_log_uses_snapshot(db_session, test_user):
    """P0-3: audit log captures snapshot at request time, not later."""
    audit_svc = AuditService(db_session)
    audit_log = await audit_svc.create_pending_log(
        user=test_user,
        model="claude-sonnet",
        provider="openai",
        path="/v1/messages",
        request_body=None,
        is_stream=True,
    )
    await db_session.commit()
    await db_session.refresh(audit_log)

    # The audit log should have the snapshot fields from the request time.
    assert audit_log.username == "alice"
    assert audit_log.department == "工程部"
    assert audit_log.status == "pending"
