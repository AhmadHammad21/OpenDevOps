"""Base class for all AWS read-only tools."""

from abc import ABC, abstractmethod
from typing import Any


class BaseTool(ABC):
    name: str
    description: str

    @property
    @abstractmethod
    def schema(self) -> dict[str, Any]:
        """OpenAI-compatible function schema for this tool."""
        ...

    @abstractmethod
    def run(self, **kwargs: Any) -> dict[str, Any]:
        """Execute the tool and return a structured result dict."""
        ...

    def as_openai_tool(self) -> dict[str, Any]:
        return {"type": "function", "function": self.schema}
