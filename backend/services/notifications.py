"""Notification services — email, WhatsApp, SMS."""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

from backend.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


def send_email(to: str, subject: str, body_html: str, body_text: Optional[str] = None) -> bool:
    """Send email via SMTP. Returns True on success."""
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        logger.warning(f"SMTP not configured. Would send to {to}: {subject}")
        return False

    msg = MIMEMultipart("alternative")
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to
    msg["Subject"] = subject

    if body_text:
        msg.attach(MIMEText(body_text, "plain"))
    msg.attach(MIMEText(body_html, "html"))

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_FROM, [to], msg.as_string())
        logger.info(f"Email sent to {to}: {subject}")
        return True
    except Exception as e:
        logger.error(f"Email failed to {to}: {e}")
        return False


def send_whatsapp(phone: str, message: str) -> bool:
    """Send WhatsApp message. Placeholder — configure webhook URL in settings."""
    logger.info(f"[WhatsApp Placeholder] To: {phone} | Message: {message[:100]}")
    # TODO: Integrate with WhatsApp Business API / webhook
    # import httpx
    # httpx.post(settings.WHATSAPP_WEBHOOK_URL, json={"phone": phone, "message": message})
    return False


def send_sms(phone: str, message: str) -> bool:
    """Send SMS. Placeholder — configure SMS gateway in settings."""
    logger.info(f"[SMS Placeholder] To: {phone} | Message: {message[:100]}")
    # TODO: Integrate with SMS gateway (MSG91, Twilio, etc.)
    return False


def build_tender_alert_html(tenders: list, search_name: str) -> str:
    """Build HTML email body for tender alerts."""
    rows = ""
    for t in tenders[:20]:
        title = t.get("title", "")[:80]
        source = t.get("source", "").upper()
        state = t.get("state", "")
        close = t.get("bid_close_date", "")
        value = t.get("tender_value_estimated", "")
        value_str = f"₹{float(value):,.0f}" if value else "—"
        rows += f"""
        <tr>
            <td style="padding:8px;border-bottom:1px solid #eee;">{title}</td>
            <td style="padding:8px;border-bottom:1px solid #eee;">{source}</td>
            <td style="padding:8px;border-bottom:1px solid #eee;">{state}</td>
            <td style="padding:8px;border-bottom:1px solid #eee;">{value_str}</td>
            <td style="padding:8px;border-bottom:1px solid #eee;">{str(close)[:10] if close else '—'}</td>
        </tr>"""

    return f"""
    <html><body style="font-family:Arial,sans-serif;max-width:700px;margin:auto;">
    <h2 style="color:#1e40af;">🔔 TenderWatch Alert: {search_name}</h2>
    <p>{len(tenders)} new tender(s) matched your saved search.</p>
    <table style="width:100%;border-collapse:collapse;font-size:13px;">
        <thead><tr style="background:#f1f5f9;">
            <th style="padding:8px;text-align:left;">Title</th>
            <th style="padding:8px;">Source</th>
            <th style="padding:8px;">State</th>
            <th style="padding:8px;">Value</th>
            <th style="padding:8px;">Closes</th>
        </tr></thead>
        <tbody>{rows}</tbody>
    </table>
    <p style="color:#6b7280;font-size:12px;margin-top:20px;">
        — TenderWatch Portal | <a href="http://localhost:5173">Open Dashboard</a>
    </p>
    </body></html>"""
