"""IdM credentials and TOTP secret in the OS keyring (macOS Keychain, Windows Credential Manager, ...)."""

import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import parse_qs, urlparse

import keyring
import pyotp

SERVICE = "studon-sync"


@dataclass
class Credentials:
    username: str
    password: str
    totp_secret: str


def load() -> Optional[Credentials]:
    username = keyring.get_password(SERVICE, "username")
    password = keyring.get_password(SERVICE, "password")
    if not username or not password:
        return None
    return Credentials(username, password, keyring.get_password(SERVICE, "totp_secret") or "")


def stored_username() -> str:
    return keyring.get_password(SERVICE, "username") or ""


def has_password() -> bool:
    return bool(keyring.get_password(SERVICE, "password"))


def has_totp_secret() -> bool:
    return bool(keyring.get_password(SERVICE, "totp_secret"))


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
    if username:
        keyring.set_password(SERVICE, "username", username.strip())
    if password:
        keyring.set_password(SERVICE, "password", password)
    if totp_secret:
        keyring.set_password(SERVICE, "totp_secret", normalize_secret(totp_secret))


def clear() -> None:
    for key in ("username", "password", "totp_secret"):
        try:
            keyring.delete_password(SERVICE, key)
        except keyring.errors.PasswordDeleteError:
            pass


def current_code(secret: Optional[str] = None) -> tuple[str, int]:
    """Returns (current 6-digit code, seconds left) for `secret` or the stored secret."""
    secret = normalize_secret(secret) if secret else keyring.get_password(SERVICE, "totp_secret")
    if not secret:
        raise ValueError("no TOTP secret")
    totp = pyotp.TOTP(secret)
    return totp.now(), totp.interval - int(time.time()) % totp.interval
