"""DeepAgents-based investigation agent."""

import json
import re
import uuid
from typing import Any

from deepagents import create_deep_agent
from langchain_litellm import ChatLiteLLM
from agent.config import settings
from models.agent import Confidence, Investigation, InvestigationResult, RootCauseCategory
from agent.prompts import SYSTEM_PROMPT
from loguru import logger
from tools.cloudtrail import ALL_CLOUDTRAIL_TOOLS
from tools.cloudwatch import ALL_CLOUDWATCH_TOOLS
from tools.ec2 import ALL_EC2_TOOLS
from tools.ecs import ALL_ECS_TOOLS
from tools.final_answer import ALL_FINAL_ANSWER_TOOLS
from tools.iam import ALL_IAM_TOOLS
from tools.lambda_ import ALL_LAMBDA_TOOLS
from tools.rds import ALL_RDS_TOOLS

ALL_TOOLS = (
    ALL_CLOUDWATCH_TOOLS
    + ALL_CLOUDTRAIL_TOOLS
    + ALL_ECS_TOOLS
    + ALL_LAMBDA_TOOLS
    + ALL_EC2_TOOLS
    + ALL_RDS_TOOLS
    + ALL_IAM_TOOLS
    + ALL_FINAL_ANSWER_TOOLS
)

_agent = None


def init_agent(checkpointer: Any) -> None:
    """Create the agent with the given checkpointer. Called once during app startup."""
    global _agent
    model = ChatLiteLLM(
        model=settings.llm_model,
        api_base=settings.llm_api_base or None,
        api_key=settings.llm_api_key or None,
    )
    _agent = create_deep_agent(
        model=model,
        tools=ALL_TOOLS,
        system_prompt=SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )


def get_agent() -> Any:
    if _agent is None:
        raise RuntimeError("Agent not initialised — call init_agent() first")
    return _agent


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


def _build_result(raw: dict[str, Any]) -> InvestigationResult:
    return InvestigationResult(
        root_cause_category=RootCauseCategory(raw.get("root_cause_category", "UNKNOWN")),
        root_cause_summary=raw.get("root_cause_summary", ""),
        evidence=raw.get("evidence", []),
        mitigation_steps=raw.get("mitigation_steps", []),
        validation_steps=raw.get("validation_steps", []),
        confidence=Confidence(raw.get("confidence", "LOW")),
        services_affected=raw.get("services_affected", []),
        recommended_follow_up=raw.get("recommended_follow_up", ""),
        raw_json=raw,
    )


class InvestigationAgent:
    """Synchronous wrapper for the CLI investigate command."""

    def investigate(self, investigation: Investigation) -> InvestigationResult:
        user_msg = investigation.description
        if investigation.alarm_name:
            user_msg += f"\nAlarm name: {investigation.alarm_name}"
        if investigation.service:
            user_msg += f"\nService: {investigation.service}"
        if investigation.region:
            user_msg += f"\nRegion: {investigation.region}"

        thread_id = str(uuid.uuid4())
        config = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": settings.max_tool_calls * 3 + 15,
        }

        logger.info("investigation_started description={}", investigation.description)

        result = get_agent().invoke(
            {"messages": [{"role": "user", "content": user_msg}]},
            config=config,
        )

        messages = result.get("messages", [])
        last_msg = messages[-1] if messages else None
        content = ""
        if last_msg is not None:
            content = last_msg.content if hasattr(last_msg, "content") else str(last_msg)

        logger.info("investigation_complete")

        raw = _parse_result_json(content)
        if raw:
            return _build_result(raw)
        return InvestigationResult(root_cause_summary=content)
