"""Registry of CLI-based LLM backend detectors, consulted in priority order.

To add a provider: implement the LlmDetector protocol in a new module here and
append an instance to ALL_DETECTORS.
"""

from agent.llm.detectors.base import LlmDetector
from agent.llm.detectors.claude_code import ClaudeCodeDetector

ALL_DETECTORS: list[LlmDetector] = [
    ClaudeCodeDetector(),
]

__all__ = ["LlmDetector", "ALL_DETECTORS", "ClaudeCodeDetector"]
