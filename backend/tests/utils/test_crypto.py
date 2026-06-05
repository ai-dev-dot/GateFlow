"""Tests for Fernet-based upstream key encryption (utils.crypto).

Pins down the round-trip and the preview formatter. These run against the
real settings (no monkeypatching the Fernet key) so they double as a
sanity check that .env has a working ENCRYPTION_KEY in the test env.
"""

import pytest
from cryptography.fernet import Fernet

from app.config import get_settings
from app.utils.crypto import (
    decrypt_key,
    encrypt_key,
    key_preview,
    verify_fernet_works,
)


def test_round_trip_preserves_plaintext():
    plaintext = "sk-aB3cD4eF5gH6iJ7kL8mN9oP0qR1sT2uV3wX4yZ5"
    token = encrypt_key(plaintext)
    assert token != plaintext, "Fernet token must not be plaintext"
    assert decrypt_key(token) == plaintext


def test_each_encryption_produces_different_token():
    """Fernet includes a random IV per call — two encryptions of the same
    plaintext must produce different ciphertexts (otherwise the cipher
    leaks structure)."""
    plaintext = "sk-same-key-twice-aaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    t1 = encrypt_key(plaintext)
    t2 = encrypt_key(plaintext)
    assert t1 != t2
    assert decrypt_key(t1) == plaintext
    assert decrypt_key(t2) == plaintext


def test_preview_short_key_returns_stars():
    assert key_preview("") == ""
    assert key_preview("short") == "***"
    assert key_preview("12345678") == "***"


def test_preview_long_key_format():
    plaintext = "sk-aB3cD4eF5gH6iJ7kL8mN"
    # First 4: "sk-a", Last 4: "L8mN" (positions 17-20 of 21-char string)
    assert key_preview(plaintext) == "sk-a...L8mN"


def test_decrypt_rejects_garbage():
    with pytest.raises(Exception):  # InvalidToken or RuntimeError — both are failure
        decrypt_key("not-a-valid-fernet-token")


def test_verify_fernet_works_at_startup():
    """Should not raise with a valid configured key."""
    verify_fernet_works()


def test_encrypt_rejects_empty():
    with pytest.raises(ValueError):
        encrypt_key("")


def test_decrypt_rejects_empty():
    with pytest.raises(ValueError):
        decrypt_key("")


def test_uses_settings_fernet_key():
    """Sanity: encryption token must decrypt with the same configured key.
    If someone swaps ENCRYPTION_KEY without re-encrypting, existing rows
    will fail to decrypt — this test pins the contract.
    """
    settings = get_settings()
    assert settings.ENCRYPTION_KEY, "ENCRYPTION_KEY must be set in test env"
    # Build a Fernet from the same key and confirm the token decodes.
    f = Fernet(settings.ENCRYPTION_KEY.encode())
    plaintext = "sk-compat-check-aaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    token = f.encrypt(plaintext.encode()).decode()
    assert decrypt_key(token) == plaintext
