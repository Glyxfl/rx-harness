"""核心数据结构。

只保留"可观测 + 可评测"所必需的最小集合：工具调用、观察、决策、轨迹四类。
不放 reward、world model、checkpoint —— 那些属于训练框架，不属于一个评测用的运行壳。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class ToolCall:
    name: str
    args: dict[str, Any]


@dataclass
class Observation:
    tool: str
    ok: bool
    content: str
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class Decision:
    """策略（LLM 或规则）在单步中的决策。call 与 answer 二选一。"""

    thought: str
    call: Optional[ToolCall] = None
    answer: Optional[str] = None


@dataclass
class Step:
    index: int
    thought: str
    call: Optional[ToolCall]
    obs: Optional[Observation]


@dataclass
class Trace:
    task_id: str
    steps: list[Step] = field(default_factory=list)
    answer: Optional[str] = None
    tokens: int = 0
    stop_reason: str = "unknown"

    def tool_calls(self) -> list[ToolCall]:
        return [s.call for s in self.steps if s.call is not None]

    def last_obs(self) -> Optional[Observation]:
        for s in reversed(self.steps):
            if s.obs is not None:
                return s.obs
        return None
