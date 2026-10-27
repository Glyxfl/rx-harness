"""判定与失败归因。

整个项目最核心的一层：把"这题过没过"变成"为什么没过"。
评测不绑在总分上，而是绑在业务口径的标量对错 + 归因标签上——能讲清楚的是
**错在哪一类**；归因错了，后面所有优化都是在错误信号上做。
"""
from __future__ import annotations

import re
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from harness.types import Trace

NUM = re.compile(r"-?\d+(?:\.\d+)?")
# 显式答案标记：优先于任何位置猜测
EXPLICIT = re.compile(r"答案\s*[:：]\s*(-?\d[\d,]*(?:\.\d+)?)")

REASONS = (
    "ok",
    "answered_wrong",
    "ambiguous_answer",
    "no_answer",
    "no_action",
    "step_budget_exceeded",
    "token_budget_exceeded",
    "unsafe_sql",
    "tool_error",
    "needs_clarification_unmet",
    "over_clarified",
    "clarify_off_target",
)


@dataclass
class Verdict:
    task_id: str
    ok: bool
    reason: str
    gold: str
    got: str
    steps: int
    tokens: int
    stop_reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def gold_scalar(db_path: str | Path, sql: str) -> Any:
    uri = f"file:{Path(db_path).as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        row = conn.execute(sql).fetchone()
    finally:
        conn.close()
    return None if not row else row[0]


def extract_number(text: str) -> float | None:
    """旧接口，保留兼容。新代码请用 extract_answer（能区分歧义）。"""
    return extract_answer(text).value


@dataclass
class Extract:
    value: float | None
    method: str  # explicit | single | ambiguous | none


def extract_answer(text: str) -> Extract:
    """从自然语言回答里取数值。

    设计原则：**宁可暴露歧义，不可静默冤枉**。

    早期实现直接取第一个数字，实测 12 种真实包装中有 4 种取错
    （"2026 年 9 月共 1234 盒" -> 2026，"...20mg... 1234 盒" -> 20）。
    这种错误最危险：它会把"模型答对了"记成"答错了"，从而系统性低估模型能力。

    现在的规则：
      1. 有显式「答案：」标记 -> 用它（配合 prompt 里的输出契约）
      2. 全句只有一个数字 -> 用它
      3. 多个数字且无标记 -> 返回 ambiguous，由 grader 归因为 ambiguous_answer，
         既不计通过也不计答错，把"评测器无法判定"如实暴露出来
    """
    marked = EXPLICIT.search(text)
    if marked:
        return Extract(float(marked.group(1).replace(",", "")), "explicit")
    numbers = NUM.findall(text.replace(",", ""))
    if not numbers:
        return Extract(None, "none")
    if len(numbers) == 1:
        return Extract(float(numbers[0]), "single")
    return Extract(None, "ambiguous")


def _numeric_equal(a: float, b: float) -> bool:
    return abs(a - b) <= max(1e-4, 1e-3 * abs(b))


def grade(
    task: dict[str, Any],
    trace: Trace,
    db_path: str | Path,
    strict: bool = True,
) -> Verdict:
    """判定单题。

    strict=True（默认）：过程里出现越权 SQL 或工具异常，整题即判失败。
        这是生产口径——一个真的删过表的 Agent，即使最后答案对，也不能算成功。
    strict=False：只按最终答案判定；没有给出答案时才回退到过程归因。
        这是能力口径——用来区分"模型不会做"和"模型会做但越界了"。
        两个口径的差值本身就是一条结论：安全边界对吞吐的定价。

    任务有两种正确形态，由 `expect` 字段声明：
      - "answer"（默认）：给出正确的标量。
      - "clarify"：问题本身缺信息，正确动作是先问、不是先答。
        判定"问到了没有"，用 `clarify_keywords` 做命中检查——问得对不对比问不问更重要。
    """
    expect = str(task.get("expect", "answer"))
    gold = gold_scalar(db_path, task["gold_sql"]) if task.get("gold_sql") else None

    obs_list = [s.obs for s in trace.steps if s.obs is not None]
    errors = [o.meta.get("error") for o in obs_list if not o.ok]

    def verdict(ok: bool, reason: str, got: str = "") -> Verdict:
        return Verdict(
            task_id=str(task["id"]),
            ok=ok,
            reason=reason,
            gold="" if gold is None else str(gold),
            got=got,
            steps=len(trace.steps),
            tokens=trace.tokens,
            stop_reason=trace.stop_reason,
        )

    has_answer = bool(trace.answer and trace.answer.strip())
    has_clarify = bool(trace.clarify and trace.clarify.strip())

    # 归因优先级：预算 -> 安全 -> 工具异常 -> 任务形态 -> 数值错
    # 宽松口径下，只要最终给了答案或提了问，就跳过过程性归因
    if strict or not (has_answer or has_clarify):
        if trace.stop_reason == "step_budget_exceeded":
            return verdict(False, "step_budget_exceeded")
        if trace.stop_reason == "token_budget_exceeded":
            return verdict(False, "token_budget_exceeded")
        if "unsafe_sql" in errors:
            return verdict(False, "unsafe_sql")
        if errors:
            return verdict(False, "tool_error")

    if expect == "clarify":
        if has_clarify:
            keywords = [k for k in (task.get("clarify_keywords") or []) if k]
            hit = any(k.lower() in trace.clarify.lower() for k in keywords) if keywords else True
            return verdict(hit, "ok" if hit else "clarify_off_target", trace.clarify)
        if has_answer:
            # 猜了个数字：这是 L4 最典型的失败方式，而且它看起来"很正常"
            return verdict(False, "needs_clarification_unmet", trace.answer)
        return verdict(False, "no_answer")

    # 普通任务却跑去提问：把"多问一句"记成失败，而不是记成没答案
    if has_clarify:
        return verdict(False, "over_clarified", trace.clarify)
    if trace.answer is None:
        return verdict(False, "no_answer")
    if trace.stop_reason == "no_action" and not trace.answer:
        return verdict(False, "no_action")

    answer = trace.answer.strip()
    if isinstance(gold, (int, float)):
        ex = extract_answer(answer)
        if ex.method == "ambiguous":
            # 不猜：多数字无标记时如实暴露评测器无法判定
            return verdict(False, "ambiguous_answer", answer)
        if ex.value is None:
            return verdict(False, "answered_wrong", answer)
        equal = _numeric_equal(ex.value, float(gold))
        return verdict(equal, "ok" if equal else "answered_wrong", answer)

    ok = str(gold).lower() in answer.lower()
    return verdict(ok, "ok" if ok else "answered_wrong", answer)


def summarize(verdicts: list[Verdict]) -> dict[str, Any]:
    total = len(verdicts)
    passed = sum(1 for v in verdicts if v.ok)
    buckets: dict[str, int] = {}
    for v in verdicts:
        if not v.ok:
            buckets[v.reason] = buckets.get(v.reason, 0) + 1
    return {
        "total": total,
        "passed": passed,
        "success_rate": round(passed / total, 4) if total else 0.0,
        "avg_steps": round(sum(v.steps for v in verdicts) / total, 2) if total else 0.0,
        "avg_tokens": round(sum(v.tokens for v in verdicts) / total, 1) if total else 0.0,
        "failure_buckets": buckets,
    }
