"""HMAC-SHA256 hashing for client API key lookup.

Client API keys (`gf_xxx`) are never stored in plaintext. Instead we store
`key_hash = HMAC-SHA256(HMAC_SECRET, key)`. Authentication computes the
same hash on the incoming token and looks it up by indexed column —
O(1) lookup, no brute-forceable bcrypt step on the hot path.

Why HMAC (not bcrypt):
- Lookup needs to be O(1) by indexed column, not O(n) brute force
- HMAC is one-way with a server-side secret: even if `key_hash` leaks
  via SQL injection or DB dump, attacker needs both the hash and the
  HMAC_SECRET to forge a key — same security model as a salted hash
- bcrypt's slow KDF is overkill here since the key is already
  60 chars of cryptographic randomness (`secrets.token_urlsafe`)

Rotation note: rotating HMAC_SECRET invalidates all existing keys
(intentional — they must be re-issued). Document before rotating.
"""

import hashlib
import hmac

from app.config import get_settings


def hash_api_key(plaintext_key: str) -> str:
    """Compute HMAC-SHA256 of a client API key.

    Returns hex-encoded digest (64 chars). Deterministic — same input
    always yields the same hash with the same secret.
    """
    if not plaintext_key:
        raise ValueError("Cannot hash empty API key")
    secret = get_settings().HMAC_SECRET
    if not secret:
        raise RuntimeError(
            "HMAC_SECRET is not configured. "
            "Generate one with: python -c 'import secrets;print(secrets.token_urlsafe(48))'"
        )
    return hmac.new(secret.encode(), plaintext_key.encode(), hashlib.sha256).hexdigest()


def api_key_prefix(plaintext_key: str) -> str:
    """Return a short, display-safe prefix of a client API key.

    Example: "gf_aB3cD4eF5gH6iJ7kL8mN..." -> "gf_aB3cD4eF"
    Length is 11 chars: "gf_" (3) + 8 random chars.
    """
    if not plaintext_key:
        return ""
    return plaintext_key[:11]


def verify_hmac_works() -> None:
    """Lifespan check: confirm HMAC computation is stable and deterministic."""
    probe = "gateflow-startup-probe"
    h1 = hash_api_key(probe)
    h2 = hash_api_key(probe)
    if h1 != h2 or len(h1) != 64:
        raise RuntimeError("HMAC_SECRET round-trip failed at startup")
