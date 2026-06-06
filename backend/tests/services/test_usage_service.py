"""Unit tests for ``UsageService.get_summary`` (P2-3).

Exercises the shared ``_build_summary_query`` helper for all four
dimensions (user / department / model / api_key) to lock down:
- column shape is identical across dimensions (6 fields)
- user dimension groups by (user_id, username) so snapshots align
- non-user dimensions emit null username
- pending logs (status_code IS NULL) are excluded
- date range filter and user_id filter both work
- invalid dimension raises ValueError
"""

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest

from app.models.audit import AuditLog
from app.services.usage_service import UsageService

# ---------- helpers ----------


def _audit(
    *,
    user_id,
    username="alice",
    department="工程部",
    model="gpt-4",
    api_key_name="k1",
    request_tokens=10,
    response_tokens=20,
    status_code=200,
    timestamp=None,
    path="/v1/chat/completions",
):
    """Build an AuditLog row dict (callers add() + commit)."""
    return AuditLog(
        user_id=user_id,
        username=username,
        department=department,
        model=model,
        provider="openai",
        method="POST",
        path=path,
        request_body_preview=None,
        is_stream=False,
        status="completed" if status_code == 200 else "failed",
        status_code=status_code,
        request_tokens=request_tokens,
        response_tokens=response_tokens,
        total_tokens=request_tokens + response_tokens,
        api_key_name=api_key_name,
        timestamp=timestamp or datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_user_dimension_groups_by_user_and_username(db_session, test_user):
    db_session.add(_audit(user_id=test_user.id, username="alice", request_tokens=5, response_tokens=7))
    db_session.add(_audit(user_id=test_user.id, username="alice", request_tokens=3, response_tokens=2))
    await db_session.commit()

    rows = await UsageService(db_session).get_summary(dimension="user")
    assert len(rows) == 1
    r = rows[0]
    assert r["dimension"] == str(test_user.id)
    assert r["username"] == "alice"
    assert r["request_count"] == 2
    assert r["input_tokens"] == 8
    assert r["output_tokens"] == 9
    assert r["total_tokens"] == 17


@pytest.mark.asyncio
async def test_non_user_dimensions_emit_null_username(db_session, test_user):
    db_session.add(_audit(user_id=test_user.id, department="工程部", model="gpt-4", api_key_name="k1"))
    db_session.add(
        _audit(user_id=test_user.id, department="销售部", model="claude-3", api_key_name="k2")
    )
    await db_session.commit()

    svc = UsageService(db_session)

    dept_rows = await svc.get_summary(dimension="department")
    assert {r["dimension"] for r in dept_rows} == {"工程部", "销售部"}
    assert all(r["username"] is None for r in dept_rows)

    model_rows = await svc.get_summary(dimension="model")
    assert {r["dimension"] for r in model_rows} == {"gpt-4", "claude-3"}
    assert all(r["username"] is None for r in model_rows)

    key_rows = await svc.get_summary(dimension="api_key")
    assert {r["dimension"] for r in key_rows} == {"k1", "k2"}
    assert all(r["username"] is None for r in key_rows)


@pytest.mark.asyncio
async def test_pending_logs_are_excluded(db_session, test_user):
    """Rows with status_code=NULL (pending) must be filtered out."""
    db_session.add(_audit(user_id=test_user.id, request_tokens=10, status_code=200))
    pending = _audit(user_id=test_user.id, request_tokens=999, status_code=None)
    pending.status = "pending"
    db_session.add(pending)
    await db_session.commit()

    rows = await UsageService(db_session).get_summary(dimension="user")
    assert len(rows) == 1
    assert rows[0]["request_count"] == 1
    assert rows[0]["input_tokens"] == 10


@pytest.mark.asyncio
async def test_user_id_filter_narrows_results(db_session, test_user):
    other_id = uuid4()
    db_session.add(_audit(user_id=test_user.id, request_tokens=10))
    db_session.add(_audit(user_id=other_id, request_tokens=20))
    await db_session.commit()

    rows = await UsageService(db_session).get_summary(
        dimension="user", user_id=test_user.id
    )
    assert len(rows) == 1
    assert rows[0]["dimension"] == str(test_user.id)
    assert rows[0]["input_tokens"] == 10


@pytest.mark.asyncio
async def test_date_range_filter(db_session, test_user):
    old = datetime.now(UTC) - timedelta(days=10)
    new = datetime.now(UTC)
    db_session.add(_audit(user_id=test_user.id, request_tokens=10, timestamp=old))
    db_session.add(_audit(user_id=test_user.id, request_tokens=20, timestamp=new))
    await db_session.commit()

    rows = await UsageService(db_session).get_summary(
        dimension="user",
        start_date=date.today() - timedelta(days=1),
    )
    assert len(rows) == 1
    assert rows[0]["input_tokens"] == 20


@pytest.mark.asyncio
async def test_invalid_dimension_raises(db_session):
    with pytest.raises(ValueError, match="不支持的聚合维度"):
        await UsageService(db_session).get_summary(dimension="bogus")


@pytest.mark.asyncio
async def test_result_shape_is_stable_across_dimensions(db_session, test_user):
    """All 4 dimensions must return the same 6-key shape so the frontend
    doesn't need per-dimension adapters.
    """
    db_session.add(_audit(user_id=test_user.id))
    await db_session.commit()

    svc = UsageService(db_session)
    expected_keys = {
        "dimension",
        "username",
        "request_count",
        "input_tokens",
        "output_tokens",
        "total_tokens",
    }
    for dim in ("user", "department", "model", "api_key"):
        rows = await svc.get_summary(dimension=dim)
        assert rows, f"no rows for dimension={dim}"
        for r in rows:
            assert set(r.keys()) == expected_keys, f"shape mismatch in {dim}: {set(r.keys())}"
