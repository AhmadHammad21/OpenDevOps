"""Telegram Bot API integration — posts investigation results as formatted messages."""

from __future__ import annotations

from typing import Any

from loguru import logger

_CONFIDENCE_EMOJI: dict[str, str] = {
    "HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢",
}


def _build_message(
    result: dict[str, Any],
    session_id: str,
    is_test: bool = False,
) -> str:
    category   = result.get("root_cause_category", "UNKNOWN")
    summary    = result.get("root_cause_summary", "No summary provided.")
    confidence = result.get("confidence", "LOW")
    evidence   = result.get("evidence", [])
    mitigation = result.get("mitigation_steps", [])
    services   = result.get("services_affected", [])
    conf_emoji = _CONFIDENCE_EMOJI.get(confidence, "🟢")

    header = "🧪 <b>[TEST] OpenDevOps — Investigation Complete</b>" if is_test else \
             "🔍 <b>OpenDevOps — Investigation Complete</b>"

    lines = [header, ""]
    lines += [f"{conf_emoji} <b>{confidence} confidence</b>  ·  <code>{category}</code>", ""]
    lines += [f"<b>Root Cause</b>\n{summary}", ""]

    if services:
        lines += [f"<b>Services affected:</b> {', '.join(f'<code>{s}</code>' for s in services)}", ""]

    if evidence:
        ev_text = "\n".join(f"• {e}" for e in evidence[:5])
        lines += [f"<b>Evidence</b>\n{ev_text}", ""]

    if mitigation:
        mt_text = "\n".join(f"{i+1}. {s}" for i, s in enumerate(mitigation))
        lines += [f"<b>Mitigation Steps</b>\n{mt_text}", ""]

    lines.append(f"<i>Session <code>{session_id[:8]}</code></i>")
    return "\n".join(lines)


async def _post(bot_token: str, chat_id: str, text: str) -> tuple[bool, str]:
    """Return (success, error_detail). error_detail is empty on success."""
    try:
        import httpx
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            })
            if resp.status_code != 200:
                detail = resp.text
                logger.warning("Telegram API returned {}: {}", resp.status_code, detail)
                return False, detail
            return True, ""
    except Exception as e:
        logger.error("Telegram notification failed: {}", e)
        return False, str(e)


async def post_investigation(
    bot_token: str,
    chat_id: str,
    result: dict[str, Any],
    session_id: str,
    is_test: bool = False,
) -> bool:
    """Post a completed investigation result to Telegram. Returns True on success."""
    text = _build_message(result, session_id, is_test=is_test)
    ok, _ = await _post(bot_token, chat_id, text)
    if ok:
        logger.info("Telegram notification sent for session {}", session_id[:8])
    return ok


async def post_failed_investigation(
    bot_token: str,
    chat_id: str,
    service: str,
    error: str,
    session_id: str,
    is_test: bool = False,
) -> bool:
    """Post a failed investigation alert to Telegram. Returns True on success."""
    header = "🧪 <b>[TEST] OpenDevOps — Investigation Failed</b>" if is_test else \
             "⚠️ <b>OpenDevOps — Investigation Failed</b>"
    text = (
        f"{header}\n\n"
        f"<b>Service:</b> <code>{service}</code>\n"
        f"<b>Error:</b> {error}\n\n"
        f"<i>Session <code>{session_id[:8]}</code></i>"
    )
    ok, _ = await _post(bot_token, chat_id, text)
    if ok:
        logger.info("Telegram failure notification sent for session {}", session_id[:8])
    return ok
