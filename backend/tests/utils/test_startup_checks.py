"""Tests for startup config checks (P0-1: JWT_SECRET_KEY)."""

import pytest

from app.config import get_settings
from app.utils.startup_checks import verify_jwt_secret_not_placeholder


def test_jwt_secret_rejects_obvious_placeholder(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", "your-secret-key-change-in-production")
    with pytest.raises(RuntimeError, match="placeholder"):
        verify_jwt_secret_not_placeholder()


def test_jwt_secret_rejects_contains_change(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", "please-change-this-in-production-ok")
    with pytest.raises(RuntimeError, match="placeholder"):
        verify_jwt_secret_not_placeholder()


def test_jwt_secret_rejects_replace_keyword(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", "REPLACE-WITH-YOUR-SECRET-12345")
    with pytest.raises(RuntimeError, match="placeholder"):
        verify_jwt_secret_not_placeholder()


def test_jwt_secret_rejects_xxx_placeholder(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
    with pytest.raises(RuntimeError, match="placeholder"):
        verify_jwt_secret_not_placeholder()


def test_jwt_secret_rejects_too_short(monkeypatch):
    settings = get_settings()
    # 20 chars of opaque alphanumerics, no placeholder keywords, but < 32
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", "8k3m9Xp2qLv7nT4wY6jR")
    with pytest.raises(RuntimeError, match="too short"):
        verify_jwt_secret_not_placeholder()


def test_jwt_secret_accepts_strong_random(monkeypatch):
    settings = get_settings()
    # 48 chars of opaque alphanumerics, no placeholder keywords
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", "8k3m9Xp2qLv7nT4wY6jR1sH5cF0aB9dE2gK4iO6uM8pQ")
    # Should not raise
    verify_jwt_secret_not_placeholder()
