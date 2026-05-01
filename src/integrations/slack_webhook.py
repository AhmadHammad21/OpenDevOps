"""Slack Incoming Webhook integration — posts investigation results as rich Block Kit messages."""

from __future__ import annotations

from typing import Any

from loguru import logger


# Sidebar colour per root-cause category
_CATEGORY_COLORS: dict[str, str] = {
    "SYSTEM_CHANGE":     "#e67e22",
    "INPUT_ANOMALY":     "#3498db",
    "RESOURCE_LIMIT":    "#e74c3c",
    "COMPONENT_FAILURE": "#c0392b",
    "DEPENDENCY_ISSUE":  "#9b59b6",
    "UNKNOWN":           "#95a5a6",
}

_CONFIDENCE_EMOJI: dict[str, str] = {
    "HIGH": "🟢", "MEDIUM": "🟡", "LOW": "🔴",
}


def _build_payload(result: dict[str, Any], session_id: str, app_url: str | None = None) -> dict:
    category   = result.get("root_cause_category", "UNKNOWN")
    summary    = result.get("root_cause_summary", "No summary provided.")
    confidence = result.get("confidence", "LOW")
    evidence   = result.get("evidence", [])
    mitigation = result.get("mitigation_steps", [])
    services   = result.get("services_affected", [])
    color      = _CATEGORY_COLORS.get(category, "#95a5a6")
    conf_emoji = _CONFIDENCE_EMOJI.get(confidence, "🔴")

    def _bullets(items: list[str]) -> str:
        return "\n".join(f"• {i}" for i in items) if items else "_None recorded_"

    blocks: list[dict] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "🔍 OpenDevOps Agent — Investigation Complete"},
        },
        {"type": "divider"},
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Root cause*\n`{category}`"},
                {"type": "mrkdwn", "text": f"*Confidence*\n{conf_emoji} {confidence}"},
            ],
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Summary*\n{summary}"},
        },
    ]

    if evidence:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Evidence*\n{_bullets(evidence)}"},
        })

    if mitigation:
        steps = "\n".join(f"{i+1}. {s}" for i, s in enumerate(mitigation))
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Mitigation steps*\n{steps}"},
        })

    if services:
        blocks.append({
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"*Services affected:* {', '.join(f'`{s}`' for s in services)}"}],
        })

    footer_parts = [f"Session `{session_id[:8]}`"]
    if app_url:
        footer_parts.append(f"<{app_url}/chat/{session_id}|Open in app>")
    blocks.append({
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": "  ·  ".join(footer_parts)}],
    })

    return {
        "attachments": [{
            "color": color,
            "blocks": blocks,
        }]
    }


async def post_investigation(
    webhook_url: str,
    result: dict[str, Any],
    session_id: str,
    app_url: str | None = None,
) -> None:
    """Fire-and-forget: post a completed investigation result to Slack."""
    try:
        import httpx
        payload = _build_payload(result, session_id, app_url)
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(webhook_url, json=payload)
            if resp.status_code != 200:
                logger.warning("Slack webhook returned {}: {}", resp.status_code, resp.text)
            else:
                logger.info("Slack notification sent for session {}", session_id[:8])
    except Exception as e:
        logger.error("Slack notification failed: {}", e)
