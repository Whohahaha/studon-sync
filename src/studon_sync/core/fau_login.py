"""
FAU SSO (SimpleSAMLphp, www.sso.uni-erlangen.de) login for StudOn, incl. TOTP.

PFERD's built-in Shibboleth login targets KIT's IdP (j_username/j_password, fudis_otp_input)
and does not work with FAU. This module walks the FAU login forms generically:
username/password and OTP pages are filled in whatever order they appear, until the
IdP returns the SAMLResponse form, which is then posted back to StudOn.

Credentials and the TOTP secret come from the OS keyring (see credentials.py)
and are never logged.
"""

import asyncio
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

import aiohttp
import pyotp
from bs4 import BeautifulSoup, Tag

from ..i18n import t
from . import credentials, paths
from .courses import STUDON_URL

_OTP_NAME = re.compile(r"otp|totp|token|code|mfa|2fa|tfa|response|pin", re.I)
_MAX_STEPS = 8


class LoginError(Exception):
    pass


class _Totp:
    """Generates TOTP codes and never hands out the same code twice."""

    def __init__(self, secret: str) -> None:
        self._totp = pyotp.TOTP(secret) if secret else None
        self._last_step: Optional[int] = None

    async def code(self) -> str:
        if self._totp is None:
            raise LoginError(t("err.no_totp"))
        step = int(time.time()) // self._totp.interval
        if step == self._last_step:
            # Same 30 s window as the last (possibly rejected) code: wait for a fresh one.
            await asyncio.sleep(self._totp.interval - time.time() % self._totp.interval + 1)
            step = int(time.time()) // self._totp.interval
        self._last_step = step
        return self._totp.now()


def _dump_debug(html: str, reason: str) -> Path:
    path = paths.log_dir() / f"login-debug-{datetime.now():%Y%m%d-%H%M%S}.html"
    # Pages are as received from the server; we never echo credentials into them.
    path.write_text(f"<!-- {reason} -->\n{html}", encoding="utf-8")
    return path


def _saml_form(soup: BeautifulSoup) -> Optional[Tag]:
    field = soup.find("input", {"name": "SAMLResponse"})
    return field.find_parent("form") if field else None


def _form_fields(form: Tag) -> dict[str, str]:
    data: dict[str, str] = {}
    for inp in form.find_all("input"):
        name = inp.get("name")
        if not name or inp.get("type", "text").lower() in {"submit", "button", "image", "checkbox", "radio"}:
            continue
        data[name] = inp.get("value", "")
    for inp in form.find_all("input", {"type": re.compile("checkbox|radio", re.I)}):
        if inp.get("name") and inp.has_attr("checked"):
            data[inp["name"]] = inp.get("value", "on")
    for sel in form.find_all("select"):
        opt = sel.find("option", selected=True) or sel.find("option")
        if sel.get("name") and opt is not None:
            data[sel["name"]] = opt.get("value", opt.get_text(strip=True))
    button = form.find("button", {"name": True}) or form.find("input", {"type": "submit", "name": True})
    if button is not None:
        data[button["name"]] = button.get("value", "")
    return data


def _otp_input(form: Tag) -> Optional[str]:
    for inp in form.find_all("input"):
        name = inp.get("name") or ""
        typ = inp.get("type", "text").lower()
        if name in {"username", "password"} or typ not in {"text", "number", "tel", "password"}:
            continue
        if _OTP_NAME.search(name) or _OTP_NAME.search(inp.get("id") or "") or inp.get("autocomplete") == "one-time-code":
            return name
    return None


def _login_form(soup: BeautifulSoup) -> Optional[Tag]:
    for form in soup.find_all("form"):
        if form.get("id") == "language-form":
            continue
        if form.find("input", {"name": "password"}) or _otp_input(form):
            return form
    return None


async def login(sess: aiohttp.ClientSession) -> None:
    """Logs `sess` into StudOn via FAU SSO. Raises LoginError on failure."""
    creds = credentials.load()
    if creds is None:
        raise LoginError(t("err.no_credentials"))
    username, password = creds.username, creds.password
    totp = _Totp(creds.totp_secret)
    sent_password = sent_otp = 0

    async with sess.get(f"{STUDON_URL}/saml.php") as resp:
        url = str(resp.url)
        html = await resp.text()
    if url.startswith("https://www.studon.fau.de/"):
        return  # IdP session still valid, StudOn logged us in directly

    for _ in range(_MAX_STEPS):
        soup = BeautifulSoup(html, "html.parser")

        if (saml := _saml_form(soup)) is not None:
            action = urljoin(url, saml.get("action", ""))
            async with sess.post(action, data=_form_fields(saml)) as resp:
                await resp.read()
            return

        form = _login_form(soup)
        if form is None:
            path = _dump_debug(html, f"unknown page at {url}")
            raise LoginError(t("err.unknown_page", path=path))

        data = _form_fields(form)
        if "password" in data or form.find("input", {"name": "password"}):
            if sent_password >= 1:
                path = _dump_debug(html, "credentials form shown again")
                raise LoginError(t("err.bad_credentials", path=path))
            if form.find("input", {"name": "username"}):
                data["username"] = username
            data["password"] = password
            sent_password += 1
        if otp_name := _otp_input(form):
            if sent_otp >= 1:
                path = _dump_debug(html, "otp form shown again")
                raise LoginError(t("err.bad_otp", path=path))
            data[otp_name] = await totp.code()
            sent_otp += 1

        action = urljoin(url, form.get("action") or url)
        async with sess.post(action, data=data) as resp:
            url = str(resp.url)
            html = await resp.text()

    path = _dump_debug(html, "too many login steps")
    raise LoginError(t("err.too_many_steps", path=path))
