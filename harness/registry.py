"""工具注册与调用。

只保留"声明式注册 + 统一错误包装"：评测关心的是**工具调用是否可复现**，
而不是工具生态有多大。每个注册项自带参数说明，直接渲染进 prompt。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .types import Observation

ToolFn = Callable[[dict], Observation]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    params: dict[str, str]
    fn: ToolFn


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}
        self.call_log: list[str] = []

    def register(self, spec: ToolSpec) -> "ToolRegistry":
        if spec.name in self._tools:
            raise ValueError(f"duplicate tool: {spec.name}")
        self._tools[spec.name] = spec
        return self

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return list(self._tools)

    def describe(self) -> str:
        """渲染成给策略用的工具说明，即注入到上下文里的 tool schema。"""
        lines = []
        for spec in self._tools.values():
            params = ", ".join(f"{k}: {v}" for k, v in spec.params.items())
            lines.append(f"- {spec.name}({params}) -> {spec.description}")
        return "\n".join(lines)

    def call(self, name: str, args: dict) -> Observation:
        self.call_log.append(name)
        spec = self._tools.get(name)
        if spec is None:
            return Observation(
                tool=name, ok=False, content=f"unknown tool: {name}", meta={"error": "unknown_tool"}
            )
        try:
            return spec.fn(args)
        except Exception as exc:  # noqa: BLE001 - 工具异常必须转成观测，不能打断 agent
            return Observation(
                tool=name,
                ok=False,
                content=f"tool error: {exc}",
                meta={"error": "tool_exception", "detail": str(exc)},
            )
