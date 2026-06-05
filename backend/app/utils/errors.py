"""Sanitize internal exception details for API responses.

P0-4: never leak `str(exception)` to clients. Internal errors get logged
with full stack trace (keyed by request_id) and clients see a fixed
message + the request_id for support correlation.

Use these helpers in catch-blocks that would otherwise build responses
from exception text.
"""

import logging
from typing import Any

from app.utils.request_id import get_request_id

logger = logging.getLogger(__name__)


def get_request_id_safe() -> str:
    """Read the current request id; return '-' when called outside a
    request scope (e.g. background task, startup)."""
    try:
        return get_request_id()
    except LookupError:
        return "-"


def safe_error_detail(message: str = "Internal server error") -> dict[str, Any]:
    """Build a client-facing error body that does NOT include the
    exception text. Includes the request_id so users can quote it when
    reporting issues, and we can grep server logs.
    """
    return {
        "detail": message,
        "request_id": get_request_id_safe(),
    }


def log_and_safe_error(
    exception: BaseException,
    *,
    log_prefix: str = "Unhandled error",
    client_message: str = "Internal server error",
) -> dict[str, Any]:
    """Log the full exception (with stack) and return a sanitized
    client body. One-shot helper for the common pattern.
    """
    rid = get_request_id_safe()
    logger.error(f"[{rid}] {log_prefix}: {exception!r}", exc_info=True)
    return safe_error_detail(client_message)

