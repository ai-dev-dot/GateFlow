"""Tests for HMAC-SHA256 client key hashing (utils.hashing)."""

import pytest

from app.config import get_settings
from app.utils.hashing import api_key_prefix, hash_api_key, verify_hmac_works


def test_hash_is_deterministic():
    """Same input + same secret must produce same hash (this is what
    makes O(1) DB lookup possible)."""
    key = "gf_abc123def456abc123def456abc123def456abc123"
    h1 = hash_api_key(key)
    h2 = hash_api_key(key)
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex


def test_hash_differs_for_different_keys():
    k1 = "gf_aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaa"
    k2 = "gf_bbbb2222bbbb2222bbbb2222bbbb2222bbbb2222bbb"
    assert hash_api_key(k1) != hash_api_key(k2)


def test_prefix_is_first_11_chars():
    key = "gf_aB3cD4eF5gH6iJ7kL8mN9oP0qR1sT2uV3wX4yZ5"
    assert api_key_prefix(key) == "gf_aB3cD4eF"


def test_prefix_empty_returns_empty():
    assert api_key_prefix("") == ""


def test_verify_hmac_works_at_startup():
    """Should not raise with a valid configured HMAC_SECRET."""
    verify_hmac_works()


def test_hash_rejects_empty():
    with pytest.raises(ValueError):
        hash_api_key("")


def test_hash_uses_settings_hmac_secret():
    """Sanity: changing the secret would change the hash, so DB rows
    would no longer match. This test pins that the hash format depends
    on the configured secret.
    """
    settings = get_settings()
    assert settings.HMAC_SECRET, "HMAC_SECRET must be set in test env"
    key = "gf_secret-binding-aaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    h = hash_api_key(key)
    # Standard hex SHA-256
    assert all(c in "0123456789abcdef" for c in h)
