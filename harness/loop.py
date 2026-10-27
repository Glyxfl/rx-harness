"""Agent 主循环（ReAct 的极简版）。

单 agent 的 think -> act -> observe 步进，加三个硬预算：步数、token、
以及"只能调注册过的工具"。不做到多 agent 编排和断点恢复——那是框架的活，
这里要的是一个能被完整观测、完整度量的最小闭环。
"""
from __future__ import annotations

from typing import Any, Protocol

from .registry import ToolRegistry
from .types import Decision, Step, Trace


class Policy(Protocol):
    def decide(self, ctx: dict[str, Any]) -> Decision: ...


def estimate_tokens(text: str) -> int:
    """粗估，中文按 1 字 ≈ 0.6 token 计。仅用于预算控制，不做计费依据。"""
    return max(1, int(len(text) * 0.6))


def run(
    task: dict[str, Any],
    registry: ToolRegistry,
    policy: Policy,
    max_steps: int = 6,
    token_budget: int = 6000,
) -> Trace:
    trace = Trace(task_id=str(task["id"]))
    history: list[Step] = []

    for i in range(max_steps):
        decision = policy.decide(
            {"question": task["question"], "history": history, "registry": registry}
        )
        trace.tokens += estimate_tokens(decision.thought) + 80

        # 反问澄清：问题本身缺信息时，正确的收尾是一次提问，不是一次查询。
        # 排在 answer 之前，因为"我先问清楚"比"我猜一个"优先级更高。
        if decision.clarify is not None:
            trace.clarify = decision.clarify
            trace.stop_reason = "clarified"
            return trace

        if decision.answer is not None:
            trace.answer = decision.answer
            trace.stop_reason = "answered"
            return trace

        if decision.call is None:
            trace.stop_reason = "no_action"
            return trace

        obs = registry.call(decision.call.name, decision.call.args)
        step = Step(index=i, thought=decision.thought, call=decision.call, obs=obs)
        trace.steps.append(step)
        history.append(step)

        if trace.tokens > token_budget:
            trace.stop_reason = "token_budget_exceeded"
            return trace

    trace.stop_reason = "step_budget_exceeded"
    return trace


def run_with_policy(ctx_policy: Policy, **kwargs: Any) -> Trace:
    return run(policy=ctx_policy, **kwargs)
