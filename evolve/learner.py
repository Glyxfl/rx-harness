"""可控学习者：只有"知识缺口"这一个缺陷的策略。

这里必须先说清它是什么、不是什么。

它**不是**大模型，也**不是**在模拟大模型的推理能力。它是一个"行为完全由注入的
知识文本决定"的确定性策略：能写对 SQL，但只有在文档里明确写过表名、列名、
值域、规格对应关系时，它才写得对；文档里没有的，它就和真实模型一样去猜
（`date` 猜成 `sale_date`、`region='城东'` 猜成 `'城东区'`、两个规格混成一个）。

为什么需要它：进化环路是否成立，取决于"失败信号 → 补丁 → 分数变化"这条链能否闭合。
闭不闭合跟学习者是模型还是规则无关；而学习者如果是 API 模型，"分数变化"里就混进了
采样噪声和网络抖动，反而看不出环路本身的问题。所以先用一个单一缺陷的学习者把
环路跑通、把度量口径定死，再把 policy 工厂换成真模型即可（接口完全一致）。

这不是省事，是把"机制验证"和"效果验证"分开——两者混在一起时，谁也说明不了。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from harness.types import Decision, ToolCall

from .knowledge import COLUMN_GUESS, REGION_VALUES

SEP = "\n\n---\n\n"


def split_context(text: str) -> tuple[str, str]:
    """把注入上下文和用户问题分开。

    声明检查只能看上下文那一段——问题里出现的词是"用户说的"，不是"文档写的"，
    混在一起会让 `城东区` 意外命中 `城东` 的声明，把缺口掩盖掉。
    """
    if SEP in text:
        prefix, _, question = text.partition(SEP)
        return prefix, question
    return "", text


def _scalar(content: str) -> str:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return content.strip()
    rows = payload.get("rows") or []
    if not rows or not rows[0]:
        return ""
    value = rows[0][0]
    return "" if value is None else str(value)


def _replay(prefix: str, question: str) -> str | None:
    """把上下文里的"历史问答示例"当模板复用。

    只在原题一字不差时才命中——这正是"记忆"的行为。真模型会做语义近似，
    因此这个学习者在记忆型补丁上是**高估**的，不是低估；报告里按此口径读。
    """
    for matched in re.finditer(r"问：(.*?)\n答：\s*```sql\s*(.*?)```", prefix, re.S):
        if matched.group(1).strip() == question.strip():
            return matched.group(2).strip()
    return None


@dataclass
class KnowledgeGatePolicy:
    sql: str = ""
    expect: str = "answer"
    keywords: tuple[str, ...] = ()

    def decide(self, ctx: dict) -> Decision:
        prefix, question = split_context(ctx["question"])
        history = ctx["history"]

        if not history:
            if self.expect == "clarify":
                return self._clarify(prefix)
            sql = _replay(prefix, question) or self._gate(self.sql, prefix)
            return Decision(
                thought="按已知结构直接查询",
                call=ToolCall("sql", {"sql": sql}),
            )

        obs = history[-1].obs
        if obs is None or not obs.ok:
            return Decision(thought="查询失败，终止", answer="")
        return Decision(thought="取标量", answer=_scalar(obs.content))

    def _clarify(self, prefix: str) -> Decision:
        """缺规格说明时，它不知道自己缺什么，于是照常给个数。

        这正是 L4 最典型的失败：格式正确、数字真实、但答的不是这个问题。
        会不会问，取决于文档里有没有一条"缺了这个维度就先确认"的规则——
        光提到"门店""规格"这些词不够，得明确写了"该问"。
        """
        has_rule = "先向用户确认" in prefix or "必须先确认" in prefix
        if has_rule and any(k and k in prefix for k in self.keywords):
            gap = self.keywords[0] if self.keywords else "所需信息"
            return Decision(thought="问题未指明关键信息，先确认", clarify=f"请补充{gap}后再查询。")
        return Decision(thought="按品名直接求和", call=ToolCall("sql", {"sql": "SELECT SUM(qty) FROM sales"}))

    @staticmethod
    def _gate(sql: str, prefix: str) -> str:
        if not sql:
            return sql
        # 1) 列名未声明 -> 猜一个常见的近义名
        for column, guess in COLUMN_GUESS.items():
            if f"`{column}`" in prefix:
                continue
            if not re.search(rf"\b{column}\b", sql):
                continue
            sql = re.sub(rf"\b{column}\b", guess, sql)

        # 2) 规格对应关系未声明 -> 把两个规格搞混
        if not ("20mg" in prefix and "40mg" in prefix):
            sql = (
                sql.replace("'P001'", "'__SPEC__'")
                .replace("'P002'", "'P001'")
                .replace("'__SPEC__'", "'P002'")
            )

        # 3) 值域未声明 -> 按问题里的字面写法去猜（"城东" -> "城东区"）
        for region in REGION_VALUES:
            if region in prefix:
                continue
            sql = re.sub(
                rf"region\s*=\s*'{region}'",
                f"region='{region}区'",
                sql,
            )
        return sql
