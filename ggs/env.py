"""Helpers for reading configuration from environment variables."""

import os
import secrets
from pathlib import Path


def env_str(name, default=""):
    return os.environ.get(name, default).strip()


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    return [item.strip() for item in env_str(name, default).split(",") if item.strip()]


def normalize_base_path(value):
    """Turn "ggs", "/ggs/" or "" into "/ggs" or "" (no trailing slash)."""
    value = (value or "").strip().strip("/")
    return f"/{value}" if value else ""


def load_or_create_secret_key(data_dir: Path):
    """Use GGS_SECRET_KEY, or a key generated once and kept in the data volume."""
    key = env_str("GGS_SECRET_KEY")
    if key:
        return key
    key_file = data_dir / "secret_key"
    if key_file.exists():
        return key_file.read_text().strip()
    key = secrets.token_urlsafe(50)
    key_file.write_text(key)
    key_file.chmod(0o600)
    return key
