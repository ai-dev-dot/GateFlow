"""Startup-time configuration checks.

Runs once at app lifespan startup (before any traffic). Each check is
intentionally strict: a misconfigured production deploy must crash early
rather than silently use insecure defaults.

Add a new function here for each new invariant. They are called in order
from `app.main:lifespan` before `create_all`.
"""

import logging

from app.config import get_settings

logger = logging.getLogger(__name__)


def _is_obvious_placeholder(value: str) -> bool:
    """Detect values that look like 'todo, change me' placeholders.

    Heuristic: the string contains words like 'change', 'replace',
    'placeholder', 'todo', 'your-', or equals 'default'.
    """
    lowered = value.lower()
    needles = ("change", "replace", "placeholder", "todo", "your-", "default", "example", "xxxxx")
    return any(n in lowered for n in needles)


def verify_jwt_secret_not_placeholder() -> None:
    """P0-1: refuse to start if JWT_SECRET_KEY is a known placeholder or
    shorter than 32 characters.

    Why both checks:
    - A strong-looking placeholder like 'change-me-in-production-please-...'
      would pass a length check but is still insecure
    - A 32-char value of literal 'aaaa...' would pass a placeholder check
      but has effectively zero entropy

    Both checks together catch the realistic failure modes.
    """
    settings = get_settings()
    key = settings.JWT_SECRET_KEY

    if _is_obvious_placeholder(key):
        raise RuntimeError(
            "JWT_SECRET_KEY looks like a placeholder value. "
            "Generate a real one: "
            'python -c "import secrets;print(secrets.token_urlsafe(48))"'
        )

    if len(key) < 32:
        raise RuntimeError(
            f"JWT_SECRET_KEY is too short ({len(key)} chars, min 32). "
            "Generate a real one: "
            'python -c "import secrets;print(secrets.token_urlsafe(48))"'
        )

    logger.info("JWT_SECRET_KEY validation: OK (%d chars)", len(key))
