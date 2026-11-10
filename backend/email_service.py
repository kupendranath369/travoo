"""Transactional email via the app owner's own Resend account (RESEND_API_KEY + RESEND_FROM)."""
import logging
import os
from pathlib import Path

import resend
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")
logger = logging.getLogger("travoo")


class EmailNotConfigured(Exception):
    pass


class EmailSendFailed(Exception):
    pass


def email_configured() -> bool:
    return bool(os.environ.get("RESEND_API_KEY", "").strip() and os.environ.get("RESEND_FROM", "").strip())


async def send_email(*, to: str, subject: str, html: str, text: str = "", idempotency_key: str = "") -> str:
    """Send one email. Returns the provider's email id once Resend has accepted it; raises otherwise."""
    if not email_configured():
        logger.error("Email not configured: set RESEND_API_KEY and RESEND_FROM in backend/.env")
        raise EmailNotConfigured()
    resend.api_key = os.environ["RESEND_API_KEY"].strip()
    params = {"from": os.environ["RESEND_FROM"].strip(), "to": [to], "subject": subject, "html": html}
    if text:
        params["text"] = text
    options = {"idempotency_key": idempotency_key} if idempotency_key else None
    try:
        res = await (resend.Emails.send_async(params, options) if options else resend.Emails.send_async(params))
    except Exception as exc:  # resend raises ResendError subclasses with the provider's message
        logger.error("Resend rejected email to %s: %s", to, exc)
        raise EmailSendFailed(str(exc)) from exc
    email_id = (res or {}).get("id")
    if not email_id:
        logger.error("Resend returned no id for email to %s: %s", to, res)
        raise EmailSendFailed("No id returned by provider")
    logger.info("Email accepted by Resend id=%s to=%s subject=%s", email_id, to, subject)
    return email_id


async def send_email_quietly(**kw) -> bool:
    """Best-effort notification email (status updates). Never raises."""
    try:
        await send_email(**kw)
        return True
    except Exception:
        return False
