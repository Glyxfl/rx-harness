"""诊断与补丁：进化循环里"看失败 → 提修改"的那一段。

三种补丁代表三种真实存在的"进化"：

  rule    —— 从失败证据归纳出缺失的知识，补进文档（提升抽象层级）
  memory  —— 把失败那道题的标准查询原样写进上下文（记忆，不是学习）
  cheat   —— 直接改判分依据（让标准答案等于自己答的数）

后两种都能立刻让 dev 涨分，这正是自进化最危险的地方：**分数涨了不代表系统变好了**。
所以循环里必须同时满足两个约束——只看 dev 决定接受与否，改动面必须限定在知识层。
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from typing import Any

from harness.types import Trace

from .knowledge import REGION_VALUES, real_schema, schema_rebuild_text, spec_rule_text, value_domain_text

COLUMN_ERROR = re.compile(r"no such column:\s*([A-Za-z_][A-Za-z0-9_.]*)")
REGION_WORDS = ("片区", "城东", "城西", "城南")


@dataclass
class Evidence:
    task_id: str
    kind: str  # column | value_domain | spec
    detail: str
    item: str = ""


@dataclass
class Patch:
    pid: str
    kind: str  # rule | memory | cheat
    surface: str  # skills | bench
    rationale: str
    skill: str = "schema"
    text: str = ""
    covers: list[str] = field(default_factory=list)


def _nearest_column(guessed: str, columns: list[str]) -> str | None:
    """从报错里那个错的列名，反推它本来想写哪个列。

    只用报错文本 + 真实结构，不读学习者的猜测表——否则诊断就等于抄答案。
    相似度不够时返回 None 而不是硬猜：报告里写一个错的"实际列名"，
    比不写更糟。反正列的补丁是按库结构整体重建，不依赖这一条判断。
    """
    tail = guessed.split(".")[-1]
    if tail in columns:
        return tail
    match = difflib.get_close_matches(tail, columns, n=1, cutoff=0.6)
    return match[0] if match else None


def diagnose(verdicts: list, traces: dict[str, Trace], db_path: Any, task_index: dict[str, dict]) -> list[Evidence]:
    schema = real_schema(db_path)
    all_columns = sorted({c for cols in schema.values() for c, _ in cols})

    out: list[Evidence] = []
    for v in verdicts:
        if v.ok:
            continue
        trace = traces.get(v.task_id)
        task = task_index.get(v.task_id, {})
        question = str(task.get("question", ""))

        if v.reason == "tool_error" and trace is not None:
            for step in trace.steps:
                if step.obs is None or step.obs.ok:
                    continue
                detail = str(step.obs.meta.get("detail") or step.obs.content)
                match = COLUMN_ERROR.search(detail)
                if match:
                    guessed = match.group(1).split(".")[-1]
                    real = _nearest_column(guessed, all_columns)
                    clue = f"库中实际列名应为 {real}" if real else "库中不存在此列"
                    out.append(
                        Evidence(
                            task_id=v.task_id,
                            kind="column",
                            detail=f"报错 no such column: {guessed}；{clue}",
                            item=real or guessed,
                        )
                    )
                    break

        elif v.reason == "needs_clarification_unmet":
            # 该问没问。这里刻意**不读** task["clarify_keywords"]——那是判定器用的关键词，
            # 拿它去写补丁等于抄答案。只看失败形态：没做任何过滤就全表求和。
            out.append(
                Evidence(
                    task_id=v.task_id,
                    kind="clarify",
                    detail=f"问题条件明显不全（got={v.got}，与全表求和一致），却直接给了数而没有确认",
                    item="",
                )
            )

        elif v.reason == "answered_wrong":
            if any(w in question for w in REGION_WORDS) and (v.got == "" or v.got in ("0", "0.0")):
                out.append(
                    Evidence(
                        task_id=v.task_id,
                        kind="value_domain",
                        detail=f"过滤片区后返回空（got={v.got or 'NULL'}），说明片区取值写法与库中不一致",
                        item="region",
                    )
                )
            elif "降压片" in question and v.got != v.gold:
                out.append(
                    Evidence(
                        task_id=v.task_id,
                        kind="spec",
                        detail=f"答案 {v.got} 与标准值 {v.gold} 不符，且该品名有 20mg/40mg 两个规格",
                        item="spec",
                    )
                )
    return out


def propose(
    evidence: list[Evidence],
    mode: str,
    db_path: Any,
    tasks: dict[str, dict],
    failing: list[str] | None = None,
) -> list[Patch]:
    """按归因聚合出候选补丁。一次一代只提交一个，好让每条补丁的收益可归因。"""
    by_kind: dict[str, list[Evidence]] = {}
    for item in evidence:
        by_kind.setdefault(item.kind, []).append(item)

    if mode == "cheat":
        # 反例：不修知识，改评测集本身——把失败题标记为跳过，分母立刻变小。
        covers = sorted(set(failing or [e.task_id for e in evidence]))
        return [
            Patch(
                pid="cheat-0",
                kind="cheat",
                surface="bench",
                rationale=f"跳过 dev 上 {len(covers)} 道失败题（改评测集，不改系统）",
                covers=covers,
            )
        ]

    if mode == "memory":
        # 反例：把失败题的原题与标准查询原样记进上下文。对见过的题有效，对没见过的题无效。
        blocks, covers = [], []
        for task_id in sorted({e.task_id for e in evidence}):
            task = tasks.get(task_id, {})
            if not task.get("gold_sql"):
                continue
            blocks.append(f"问：{task['question']}\n答：\n```sql\n{task['gold_sql']}\n```")
            covers.append(task_id)
        if not blocks:
            return []
        return [
            Patch(
                pid="memory-batch",
                kind="memory",
                surface="skills",
                skill="schema",
                rationale=f"把 {len(covers)} 道失败题的原题与标准 SQL 追加为示例（记住题目，不是学会规则）",
                text="## 历史问答示例\n\n" + "\n\n".join(blocks),
                covers=covers,
            )
        ]

    if not by_kind:
        return []

    order = ["column", "value_domain", "spec", "clarify"]
    kind = min(by_kind, key=lambda k: order.index(k) if k in order else 99)
    targets = by_kind[kind]

    if kind == "column":
        return [
            Patch(
                pid="rule-schema",
                kind="rule",
                surface="skills",
                skill="schema",
                rationale=f"{len(targets)} 题因列名猜错失败（{sorted({t.item for t in targets})}），按库结构重建字段清单",
                text=schema_rebuild_text(real_schema(db_path)),
                covers=[t.task_id for t in targets],
            )
        ]
    if kind == "value_domain":
        return [
            Patch(
                pid="rule-value-domain",
                kind="rule",
                surface="skills",
                skill="schema",
                rationale=f"{len(targets)} 题因片区取值写法不符返回空，补值域映射",
                text=value_domain_text(),
                covers=[t.task_id for t in targets],
            )
        ]
    if kind == "spec":
        return [
            Patch(
                pid="rule-spec",
                kind="rule",
                surface="skills",
                skill="sales_query",
                rationale=f"{len(targets)} 题在双规格产品上答错，补规格必须显式指定的规则",
                text=spec_rule_text(),
                covers=[t.task_id for t in targets],
            )
        ]

    # clarify：把"条件不全却直接作答"的失败归纳成一条通用规则。
    # 规则文本只枚举业务维度，不读判定器用的关键词——否则就是把评分标准抄进文档。
    text = (
        "## 缺信息时必须先确认\n\n"
        "- 问题若缺少时间范围（哪个月份、哪一周、哪一天）、门店或片区、具体产品与规格、\n"
        "  指标口径（销量还是销售额、怎么算）、阈值或定义中的任一项，说明按现有信息无法唯一确定答案：\n"
        "  不要猜，先向用户确认缺的那一项。\n"
        "- 一次只问最关键的那个缺口，不要罗列一堆问题。\n"
        "- 信息齐全时必须直接作答，不得反问。"
    )
    return [
        Patch(
            pid="rule-clarify",
            kind="rule",
            surface="skills",
            skill="sales_query",
            rationale=f"{len(targets)} 题在条件不全时直接给了数，归纳出「缺失维度要先确认」的通用规则",
            text=text,
            covers=[t.task_id for t in targets],
        )
    ]
