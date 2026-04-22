"""ReAct-style investigation agent loop."""

import json
import logging
import re
from typing import Any

import structlog
from openai import OpenAI

from agent.config import settings
from agent.memory import InvestigationState
from agent.models import Confidence, Investigation, InvestigationResult, RootCauseCategory
from agent.prompts import SYSTEM_PROMPT
from tools.base import BaseTool
from tools.cloudtrail import ALL_CLOUDTRAIL_TOOLS
from tools.cloudwatch import ALL_CLOUDWATCH_TOOLS
from tools.ec2 import ALL_EC2_TOOLS
from tools.ecs import ALL_ECS_TOOLS
from tools.iam import ALL_IAM_TOOLS
from tools.lambda_ import ALL_LAMBDA_TOOLS
from tools.rds import ALL_RDS_TOOLS

logger = structlog.get_logger(__name__)

ALL_TOOLS: list[BaseTool] = (
    ALL_CLOUDWATCH_TOOLS
    + ALL_CLOUDTRAIL_TOOLS
    + ALL_ECS_TOOLS
    + ALL_LAMBDA_TOOLS
    + ALL_EC2_TOOLS
    + ALL_RDS_TOOLS
    + ALL_IAM_TOOLS
)

_TOOL_MAP: dict[str, BaseTool] = {t.name: t for t in ALL_TOOLS}


def _openai_client() -> OpenAI:
    return OpenAI(api_key=settings.openrouter_api_key, base_url=settings.openrouter_base_url)


def _parse_result_json(text: str) -> dict[str, Any] | None:
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    try:
        start = text.rfind("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            return json.loads(text[start:end])
    except json.JSONDecodeError:
        pass
    return None


def _build_result(raw: dict[str, Any], state: InvestigationState) -> InvestigationResult:
    return InvestigationResult(
        root_cause_category=RootCauseCategory(raw.get("root_cause_category", "UNKNOWN")),
        root_cause_summary=raw.get("root_cause_summary", ""),
        evidence=raw.get("evidence", []),
        mitigation_steps=raw.get("mitigation_steps", []),
        validation_steps=raw.get("validation_steps", []),
        confidence=Confidence(raw.get("confidence", "LOW")),
        services_affected=raw.get("services_affected", []),
        recommended_follow_up=raw.get("recommended_follow_up", ""),
        tool_calls_made=state.tool_call_count(),
        raw_json=raw,
    )


class InvestigationAgent:
    def __init__(self) -> None:
        self._client = _openai_client()
        self._tools_schema = [t.as_openai_tool() for t in ALL_TOOLS]

    def investigate(self, investigation: Investigation) -> InvestigationResult:
        state = InvestigationState(description=investigation.description)

        user_msg = investigation.description
        if investigation.alarm_name:
            user_msg += f"\nAlarm name: {investigation.alarm_name}"
        if investigation.service:
            user_msg += f"\nService: {investigation.service}"
        if investigation.region:
            user_msg += f"\nRegion: {investigation.region}"

        state.messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]

        log = logger.bind(description=investigation.description)
        log.info("investigation_started")

        for _ in range(settings.max_tool_calls + 1):
            response = self._client.chat.completions.create(
                model=settings.openrouter_model,
                messages=state.messages,
                tools=self._tools_schema,
                tool_choice="auto",
            )

            choice = response.choices[0]
            msg = choice.message
            state.messages.append(msg.model_dump(exclude_none=True))

            if choice.finish_reason == "stop" or not msg.tool_calls:
                content = msg.content or ""
                log.info("investigation_complete", tool_calls=state.tool_call_count())
                raw = _parse_result_json(content)
                if raw:
                    return _build_result(raw, state)
                return InvestigationResult(
                    root_cause_summary=content,
                    tool_calls_made=state.tool_call_count(),
                )

            if state.tool_call_count() >= settings.max_tool_calls:
                log.warning("max_tool_calls_reached", limit=settings.max_tool_calls)
                break

            tool_results = []
            for tool_call in msg.tool_calls:
                fn_name = tool_call.function.name
                try:
                    fn_args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    fn_args = {}

                tool = _TOOL_MAP.get(fn_name)
                if tool:
                    log.info("tool_call", tool=fn_name, args=fn_args)
                    result = tool.run(**fn_args)
                    log.info("tool_result", tool=fn_name, keys=list(result.keys()))
                else:
                    result = {"error": f"Unknown tool: {fn_name}"}

                state.add_tool_call(fn_name, fn_args, result)
                tool_results.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result),
                    }
                )

            state.messages.extend(tool_results)

        log.warning("investigation_ended_without_result")
        return InvestigationResult(
            root_cause_summary="Investigation ended without a conclusive result.",
            tool_calls_made=state.tool_call_count(),
            confidence=Confidence.LOW,
        )
