"""Tests for audit service: pending log creation + completion recording.

These tests protect:
- Snapshot fields are written at pending time (not JOIN-fetched later)
- record_completion sets status="completed" for 200, "failed" otherwise
- Total tokens = request + response
"""

import pytest
from sqlalchemy import select

from app.models.audit import AuditLog
from app.services.audit_service import AuditService


@pytest.mark.asyncio
async def test_create_pending_log_writes_snapshots(db_session, test_user):
    """Snapshot fields (username, department) are taken at create time."""
    service = AuditService(db_session)
    log = await service.create_pending_log(
        user=test_user,
        model="gpt-4",
        provider="openai",
        path="/v1/chat/completions",
        request_body='{"messages":[]}',
        is_stream=False,
    )
    await db_session.commit()
    await db_session.refresh(log)

    assert log.id is not None
    assert log.status == "pending"
    assert log.username == "alice"
    assert log.department == "工程部"
    assert log.model == "gpt-4"
    assert log.provider == "openai"
    assert log.path == "/v1/chat/completions"
    assert log.is_stream is False


@pytest.mark.asyncio
async def test_record_completion_success(db_session, test_user):
    """200 → status='completed'."""
    service = AuditService(db_session)
    log = await service.create_pending_log(
        user=test_user,
        model="gpt-4",
        provider="openai",
        path="/v1/chat/completions",
        request_body=None,
        is_stream=True,
    )
    await db_session.commit()

    await service.record_completion(
        log, status_code=200, request_tokens=10, response_tokens=20, latency_ms=150
    )
    await db_session.commit()

    assert log.status == "completed"
    assert log.status_code == 200
    assert log.request_tokens == 10
    assert log.response_tokens == 20
    assert log.total_tokens == 30
    assert log.latency_ms == 150
    assert log.completed_at is not None


@pytest.mark.asyncio
async def test_record_completion_failure(db_session, test_user):
    """non-200 → status='failed'."""
    service = AuditService(db_session)
    log = await service.create_pending_log(
        user=test_user,
        model="gpt-4",
        provider="openai",
        path="/v1/chat/completions",
        request_body=None,
        is_stream=False,
    )
    await db_session.commit()

    await service.record_completion(
        log, status_code=503, request_tokens=10, response_tokens=0, latency_ms=5000
    )
    await db_session.commit()

    assert log.status == "failed"
    assert log.status_code == 503


@pytest.mark.asyncio
async def test_snapshot_unchanged_after_user_mutation(db_session, test_user):
    """THE core invariant: rename user/department AFTER audit log created,
    old audit log's snapshot fields stay unchanged.

    This is the architectural principle behind the refactor — stats must not
    change because of post-hoc user/department mutations.
    """
    service = AuditService(db_session)
    log = await service.create_pending_log(
        user=test_user,
        model="gpt-4",
        provider="openai",
        path="/v1/chat/completions",
        request_body=None,
        is_stream=False,
    )
    await db_session.commit()
    original_username = log.username
    original_department = log.department

    # Simulate user/department mutations
    test_user.username = "alice-renamed"
    test_user.department.name = "新部门"
    await db_session.commit()

    # Refresh log from DB
    result = await db_session.execute(select(AuditLog).where(AuditLog.id == log.id))
    refreshed = result.scalar_one()
    assert refreshed.username == original_username, "username snapshot must be frozen"
    assert refreshed.department == original_department, "department snapshot must be frozen"


@pytest.mark.asyncio
async def test_request_body_truncation(db_session, test_user, monkeypatch):
    """Body longer than 100KB gets truncated to MAX_LOG_CONTENT_LENGTH.

    With AUDIT_LOG_FULL_BODY=true, the truncated body is Fernet-encrypted
    before storage. Fernet uses base64 + HMAC overhead, so the persisted
    ciphertext is ~36% larger than plaintext. We assert the semantic
    invariant instead: the decrypted body equals the truncated plaintext.
    """
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "AUDIT_LOG_FULL_BODY", True)

    service = AuditService(db_session)
    big_body = "x" * (200 * 1024)  # 200KB
    log = await service.create_pending_log(
        user=test_user,
        model="gpt-4",
        provider="openai",
        path="/v1/chat/completions",
        request_body=big_body,
        is_stream=False,
    )
    await db_session.commit()
    assert log.request_body != big_body, "encrypted, not plaintext"
    # Round-trip decrypts back to the truncated (not original) body —
    # this is the actual contract we care about.
    decrypted = service.decrypt_request_body(log.request_body)
    assert decrypted == big_body[: service.MAX_LOG_CONTENT_LENGTH]
    assert len(decrypted) == service.MAX_LOG_CONTENT_LENGTH


@pytest.mark.asyncio
async def test_preview_is_first_n_chars(db_session, test_user, monkeypatch):
    """request_body_preview contains the first N characters of the body,
    in plaintext, regardless of FULL_BODY setting."""
    from app.config import get_settings

    settings = get_settings()
    n = settings.AUDIT_LOG_PREVIEW_CHARS

    # FULL_BODY=true
    monkeypatch.setattr(settings, "AUDIT_LOG_FULL_BODY", True)
    body = "A" * (n * 3) + "END"
    service = AuditService(db_session)
    log = await service.create_pending_log(
        user=test_user,
        model="m",
        provider="p",
        path="/x",
        request_body=body,
        is_stream=False,
    )
    await db_session.commit()
    assert log.request_body_preview == "A" * n

    # FULL_BODY=false
    monkeypatch.setattr(settings, "AUDIT_LOG_FULL_BODY", False)
    log2 = await service.create_pending_log(
        user=test_user,
        model="m",
        provider="p",
        path="/x",
        request_body=body,
        is_stream=False,
    )
    await db_session.commit()
    assert log2.request_body_preview == "A" * n
    assert log2.request_body is None, "FULL_BODY=false must drop encrypted body"


@pytest.mark.asyncio
async def test_record_admin_access_writes_meta_audit(db_session, admin_user, monkeypatch):
    """When an admin views a log body, a new AuditLog row is created with
    path='/admin/audit-access' recording the action."""
    from sqlalchemy import select
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "AUDIT_LOG_FULL_BODY", True)

    # First create a target log as a regular user
    from app.models.audit import AuditLog

    target = AuditLog(
        user_id=admin_user.id,  # admin looking at their own log for simplicity
        username=admin_user.username,
        department=admin_user.department.name,
        model="gpt-4",
        provider="openai",
        method="POST",
        path="/v1/chat/completions",
        request_body_preview="some preview",
        is_stream=False,
        status="completed",
    )
    db_session.add(target)
    await db_session.commit()
    await db_session.refresh(target)

    # Now admin views it (meta-audit)
    service = AuditService(db_session)
    meta = await service.record_admin_access(
        admin_user, target, ip_address="10.0.0.1"
    )
    await db_session.commit()

    assert meta.path == "/admin/audit-access"
    assert meta.user_id == admin_user.id
    assert meta.status == "completed"
    assert "target_log_id" in meta.request_body_preview
    assert str(target.id) in meta.request_body_preview
    assert meta.ip_address == "10.0.0.1"


@pytest.mark.asyncio
async def test_decrypt_request_body_round_trip(db_session, test_user, monkeypatch):
    """decrypt_request_body must recover the original plaintext when
    AUDIT_LOG_FULL_BODY=true."""
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "AUDIT_LOG_FULL_BODY", True)
    service = AuditService(db_session)
    body = "the quick brown fox jumps over the lazy dog"
    log = await service.create_pending_log(
        user=test_user,
        model="m",
        provider="p",
        path="/x",
        request_body=body,
        is_stream=False,
    )
    await db_session.commit()
    assert service.decrypt_request_body(log.request_body) == body
