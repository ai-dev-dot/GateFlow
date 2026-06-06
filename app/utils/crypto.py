"""Symmetric encryption for upstream API keys at rest.

Uses Fernet (AES-128-CBC + HMAC-SHA256) from the cryptography package.
The encryption key comes from settings.ENCRYPTION_KEY (must be a valid
44-byte base64 Fernet key, generated via `Fernet.generate_key()`).

Why Fernet (not raw AES):
- Authenticated encryption out of the box (detects tampering)
- Built-in key rotation support (Fernet accepts a list of keys)
- No IV/key-size footguns

Storage pattern:
- DB stores `encrypted_key` (Fernet token) + `key_preview` (display-only)
- Decryption happens only at the call site (`build_headers`) via
  `provider_key.get_decrypted_key()` — plaintext is a local variable
  scoped to a single function call.
"""

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


def _fernet() -> Fernet:
    """Build a Fernet instance from the configured key.

    Fails fast with a clear error if the key is missing or malformed.
    """
    key = get_settings().ENCRYPTION_KEY
    if not key:
        raise RuntimeError(
            "ENCRYPTION_KEY is not configured. "
            "Generate one with: python -c 'from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())'"
        )
    try:
        return Fernet(key.encode())
    except Exception as exc:
        raise RuntimeError(
            f"ENCRYPTION_KEY is not a valid Fernet key (44-byte base64). Generate a new one. ({exc})"
        ) from exc


def encrypt_key(plaintext: str) -> str:
    """Encrypt a plaintext API key. Returns the Fernet token as a string."""
    if not plaintext:
        raise ValueError("Cannot encrypt empty key")
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_key(token: str) -> str:
    """Decrypt a Fernet token back to plaintext. Raises on invalid key or token."""
    if not token:
        raise ValueError("Cannot decrypt empty token")
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise RuntimeError(
            "Failed to decrypt key — ENCRYPTION_KEY may have changed since this row was written"
        ) from exc


def key_preview(plaintext: str) -> str:
    """Return a short, display-safe preview of a key.

    Example: "sk-aB3cD4eF5gH6iJ7kL8mN9oP0qR1sT2uV3wX4yZ5" -> "sk-a...2uV"
    For very short keys (e.g. legacy short test keys), return "***" only.
    """
    if not plaintext:
        return ""
    if len(plaintext) <= 8:
        return "***"
    return f"{plaintext[:4]}...{plaintext[-4:]}"


def verify_fernet_works() -> None:
    """Lifespan check: confirm the configured key can encrypt + decrypt.

    Called once at startup. Fails fast so misconfiguration is caught
    before serving any traffic.
    """
    probe = "gateflow-startup-probe-ok"
    token = encrypt_key(probe)
    if decrypt_key(token) != probe:
        raise RuntimeError("ENCRYPTION_KEY round-trip failed at startup")
