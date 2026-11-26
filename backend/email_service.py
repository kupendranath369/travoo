"""Transactional email via Emergent's managed email integration (EMERGENT_EMAIL_KEY + EMAIL_FROM_NAME)."""
import ipaddress
import logging
import os
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")
logger = logging.getLogger("travoo")

EMAIL_BASE_URL = "https://integrations.emergentagent.com"


class EmailNotConfigured(Exception):
    pass


class EmailSendFailed(Exception):
    pass


def email_configured() -> bool:
    return bool(os.environ.get("EMERGENT_EMAIL_KEY", "").strip() and os.environ.get("EMAIL_FROM_NAME", "").strip())


_SHORTENERS = ("bit.ly", "tinyurl.com", "t.co", "is.gd", "cutt.ly", "goo.gl", "rebrand.ly")
_CRED_ASK = ("reply with your password", "reply with the code", "send your password", "cvv",
             "send us your password", "enter your password below", "confirm your card number",
             "your full card number", "seed phrase", "recovery phrase", "verify your card",
             "social security number", "confirm your bank details")
_HOSTISH = re.compile(r"\b(?:https?://)?((?:[a-z0-9-]+\.)+[a-z]{2,})", re.I)


def _host_ok(host: str) -> bool:
    if not host or "xn--" in host:
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        pass
    return not any(host == s or host.endswith("." + s) for s in _SHORTENERS)


def _same_site(shown: str, real: str) -> bool:
    return shown == real or real.endswith("." + shown) or shown.endswith("." + real)


class _EmailScan(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.urls, self.anchors = set(), [], []
        self._href, self._text = None, []

    def handle_starttag(self, tag, attrs):
        self.tags.add(tag.lower())
        self.urls += [v for k, v in attrs if k.lower() in ("href", "src") and v]
        if tag.lower() == "a":
            self._href = dict((k.lower(), v) for k, v in attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href is not None:
            self.anchors.append((self._href, "".join(self._text)))
            self._href, self._text = None, []


def _assert_safe_email(subject: str, html: str) -> None:
    scan = _EmailScan()
    scan.feed(html)
    if scan.tags & {"form", "input", "textarea", "select"}:
        raise ValueError("No forms or input fields in email (G2)")
    body = f"{subject}\n{html}".lower()
    for p in _CRED_ASK:
        if p in body:
            raise ValueError(f"Email asks the recipient for credentials: {p!r} (G2)")
    for url in scan.urls:
        low = url.strip().lower()
        if low.startswith(("mailto:", "tel:", "cid:", "#")):
            continue
        if not low.startswith("https://"):
            raise ValueError(f"Email links/assets must be absolute https: {url!r} (G3)")
        host = urlparse(low).hostname or ""
        if not _host_ok(host) or urlparse(low).username is not None:
            raise ValueError(f"Shortened, numeric-host or credential-bearing URL: {url!r} (G3)")
    for href, text in scan.anchors:
        real = urlparse(href.strip().lower()).hostname or ""
        if not real:
            continue
        for m in _HOSTISH.finditer(text):
            if not _same_site(m.group(1).lower(), real):
                raise ValueError(f"Anchor text {m.group(1)!r} ≠ real link host {real!r} (G3)")


async def send_email(*, to: str, subject: str, html: str, text: str = "", idempotency_key: str = "") -> str:
    """Send one email. Returns the provider's email id once accepted; raises otherwise."""
    if not email_configured():
        logger.error("Email not configured: set EMERGENT_EMAIL_KEY and EMAIL_FROM_NAME in backend/.env")
        raise EmailNotConfigured()
    try:
        _assert_safe_email(subject, html)
    except ValueError as exc:
        logger.error("Email blocked by safety check: %s", exc)
        raise EmailSendFailed(str(exc)) from exc
    payload = {"to": [to], "subject": subject, "html": html, "from_name": os.environ["EMAIL_FROM_NAME"].strip()}
    reply_to = os.environ.get("EMAIL_REPLY_TO", "").strip()
    if reply_to:
        payload["contact_email"] = reply_to
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{EMAIL_BASE_URL}/api/v1/email/send",
                                     headers={"X-Email-Key": os.environ["EMERGENT_EMAIL_KEY"].strip()}, json=payload)
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        try:
            body = exc.response.json()
        except ValueError:
            body = {}
        if body.get("code") in ("insufficient_credits", "integration_disabled", "daily_limit_reached"):
            logger.warning("Email paused: %s (%s): %s", body.get("code"), exc.response.status_code, body.get("message", ""))
        else:
            logger.error("Email send failed to %s: %s %s", to, exc.response.status_code, exc.response.text[:300])
        raise EmailSendFailed(str(exc)) from exc
    except Exception as exc:
        logger.error("Email send error to %s: %s", to, exc)
        raise EmailSendFailed(str(exc)) from exc
    email_id = (resp.json() or {}).get("id")
    if not email_id:
        logger.error("Email provider returned no id for %s", to)
        raise EmailSendFailed("No id returned by provider")
    logger.info("Email accepted id=%s to=%s subject=%s", email_id, to, subject)
    return email_id


async def send_email_quietly(**kw) -> bool:
    """Best-effort notification email (status updates). Never raises."""
    try:
        await send_email(**kw)
        return True
    except Exception:
        return False
