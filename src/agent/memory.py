from typing import Any

from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    tool_name: str
    arguments: dict[str, Any]
    result: dict[str, Any]


class InvestigationState(BaseModel):
    description: str
    tool_calls: list[ToolCall] = Field(default_factory=list)
    hypotheses: list[str] = Field(default_factory=list)
    messages: list[dict[str, Any]] = Field(default_factory=list)

    def add_tool_call(self, tool_name: str, arguments: dict[str, Any], result: dict[str, Any]) -> None:
        self.tool_calls.append(ToolCall(tool_name=tool_name, arguments=arguments, result=result))

    def tool_call_count(self) -> int:
        return len(self.tool_calls)

    def summary(self) -> str:
        lines = [f"Investigation: {self.description}", f"Tool calls: {self.tool_call_count()}"]
        for tc in self.tool_calls:
            lines.append(f"  - {tc.tool_name}({tc.arguments})")
        return "\n".join(lines)
