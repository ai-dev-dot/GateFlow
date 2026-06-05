"""Tests for audit service: pending log creation + completion recording.

These tests protect:
- Snapshot fields are written at pending time (not JOIN-fetched later)
- record_completion sets status="completed" for 200, "failed" otherwise
- Total tokens = request + response
"""

import uuid
from datetime import datetime

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
        user=test_user, model="gpt-4", provider="openai",
        path="/v1/chat/completions", request_body=None, is_stream=True,
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
        user=test_user, model="gpt-4", provider="openai",
        path="/v1/chat/completions", request_body=None, is_stream=False,
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
        user=test_user, model="gpt-4", provider="openai",
        path="/v1/chat/completions", request_body=None, is_stream=False,
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
async def test_request_body_truncation(db_session, test_user):
    """Body longer than 100KB gets truncated."""
    service = AuditService(db_session)
    big_body = "x" * (200 * 1024)  # 200KB
    log = await service.create_pending_log(
        user=test_user, model="gpt-4", provider="openai",
        path="/v1/chat/completions", request_body=big_body, is_stream=False,
    )
    await db_session.commit()
    assert len(log.request_body) == service.MAX_LOG_CONTENT_LENGTH
