"""IdM credentials and TOTP secret in the OS keyring (macOS Keychain, Windows Credential Manager, ...).

Everything is stored as ONE keyring item (service "studon-sync", account "credentials", JSON value),
so macOS asks at most once per app for access, and read only once per process (cached).
Older versions stored three separate items; they are migrated on first read.
"""

import json
import time
from dataclasses import asdict, dataclass
from typing import Optional
from urllib.parse import parse_qs, urlparse

import keyring
import keyring.errors
import pyotp

SERVICE = "studon-sync"
ACCOUNT = "credentials"
_LEGACY_ACCOUNTS = ("username", "password", "totp_secret")


@dataclass
class Credentials:
    username: str = ""
    password: str = ""
    totp_secret: str = ""


_cache: Optional[Credentials] = None


def _read() -> Credentials:
    global _cache
    if _cache is None:
        raw = keyring.get_password(SERVICE, ACCOUNT)
        if raw:
            _cache = Credentials(**json.loads(raw))
        else:
            _cache = _migrate_legacy()
    return _cache


def _write(creds: Credentials) -> None:
    global _cache
    keyring.set_password(SERVICE, ACCOUNT, json.dumps(asdict(creds)))
    _cache = creds


def _migrate_legacy() -> Credentials:
    values = {key: keyring.get_password(SERVICE, key) or "" for key in _LEGACY_ACCOUNTS}
    creds = Credentials(**values)
    if any(values.values()):
        _write(creds)
        for key in _LEGACY_ACCOUNTS:
            try:
                keyring.delete_password(SERVICE, key)
            except keyring.errors.PasswordDeleteError:
                pass
    return creds


def load() -> Optional[Credentials]:
    creds = _read()
    return creds if creds.username and creds.password else None


def stored_username() -> str:
    return _read().username


def has_password() -> bool:
    return bool(_read().password)


def has_totp_secret() -> bool:
    return bool(_read().totp_secret)


def normalize_secret(secret: str) -> str:
    """Accepts a Base32 secret or an otpauth:// URI. Raises ValueError if it is not usable."""
    secret = secret.strip()
    if secret.startswith("otpauth://"):
        secret = parse_qs(urlparse(secret).query).get("secret", [""])[0]
    secret = secret.replace(" ", "").upper()
    if not secret:
        raise ValueError("empty secret")
    try:
        pyotp.TOTP(secret).now()
    except Exception as e:
        raise ValueError("not a Base32 secret") from e
    return secret


def save(username: Optional[str] = None, password: Optional[str] = None, totp_secret: Optional[str] = None) -> None:
    """Saves only the values that are given (None or "" keeps the stored value)."""
    current = _read()
    _write(
        Credentials(
            username=username.strip() if username else current.username,
            password=password or current.password,
            totp_secret=normalize_secret(totp_secret) if totp_secret else current.totp_secret,
        )
    )


def clear() -> None:
    global _cache
    for key in (ACCOUNT, *_LEGACY_ACCOUNTS):
        try:
            keyring.delete_password(SERVICE, key)
        except keyring.errors.PasswordDeleteError:
            pass
    _cache = None


def current_code(secret: Optional[str] = None) -> tuple[str, int]:
    """Returns (current 6-digit code, seconds left) for `secret` or the stored secret."""
    secret = normalize_secret(secret) if secret else _read().totp_secret
    if not secret:
        raise ValueError("no TOTP secret")
    totp = pyotp.TOTP(secret)
    return totp.now(), totp.interval - int(time.time()) % totp.interval
