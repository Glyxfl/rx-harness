"""策略实现：可插拔的"大脑"（决策层）。
这里把决策抽象成一个 decide() 协议，于是同一套 harness 可以跑：
  1. OraclePolicy    —— 已知正确路径，用于校准 harness 与评测器本身
  2. MutatedPolicy   —— 在正确路径上注入已知故障，用于验证评测器的归因能力
  3. OpenAICompatPolicy —— 真实大模型，任何 OpenAI 兼容接口
零依赖：真实调用只用标准库 urllib。
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

from .types import Decision, ToolCall


def _scalar_from_obs(content: str) -> str | None:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return content.strip() or None
    rows = payload.get("rows") or []
    if not rows or not rows[0]:
        return None
    return str(rows[0][0])


@dataclass
class OraclePolicy:
    """按给定 SQL 走一遍，然后把工具返回的标量当作答案。"""

    sql: str

    def decide(self, ctx: dict[str, Any]) -> Decision:
        history = ctx["history"]
        if not history:
            return Decision(thought="直接查询指标库", call=ToolCall("sql", {"sql": self.sql}))
        obs = history[-1].obs
        if obs is None or not obs.ok:
            return Decision(thought="查询失败，终止", answer="")
        value = _scalar_from_obs(obs.content)
        return Decision(thought="从结果中取出标量", answer=value or "")


@dataclass
class ClarifyPolicy:
    """已知该题的信息缺口，直接给出澄清问句。

    它只用来校准"判定器能否识别提问这一形态"，不代表模型能力——它拿到的就是答案。
    这是本项目一贯的做法：先把尺子校好，再拿尺子量人。
    """

    keywords: list[str]

    def decide(self, ctx: dict[str, Any]) -> Decision:
        gap = self.keywords[0] if self.keywords else "所需信息"
        return Decision(
            thought="问题缺少必要信息，先行确认",
            clarify=f"请补充{gap}相关信息后再查询。",
        )


@dataclass
class MutatedPolicy:
    """在 Oracle 路径上施加单一故障，模拟真实的 agent 失败方式。"""

    base: OraclePolicy
    mutate: Callable[[ToolCall], ToolCall]
    label: str

    def decide(self, ctx: dict[str, Any]) -> Decision:
        decision = self.base.decide(ctx)
        if decision.call is not None:
            decision.call = self.mutate(decision.call)
        return decision


@dataclass
class RepeatingPolicy:
    """反复调用同一工具，用于触发步数预算。"""

    sql: str

    def decide(self, ctx: dict[str, Any]) -> Decision:
        return Decision(thought="再查一次", call=ToolCall("sql", {"sql": self.sql}))


@dataclass
class SilentPolicy:
    """从不给答案，用于触发 no_answer。"""

    sql: str

    def decide(self, ctx: dict[str, Any]) -> Decision:
        history = ctx["history"]
        if not history:
            return Decision(thought="先查一次", call=ToolCall("sql", {"sql": self.sql}))
        return Decision(thought="想不出来了")


MUTATORS: dict[str, Callable[[ToolCall], ToolCall]] = {
    "wrong_filter": lambda c: ToolCall(c.name, {"sql": c.args["sql"].replace("S001", "S002")}),
    "wrong_aggregation": lambda c: ToolCall(c.name, {"sql": c.args["sql"].replace("SUM(", "MAX(")}),
    "wrong_table": lambda c: ToolCall(c.name, {"sql": c.args["sql"].replace("FROM sales", "FROM inventory")}),
    "unsafe_sql": lambda c: ToolCall(c.name, {"sql": c.args["sql"] + "; DROP TABLE sales"}),
    "no_answer": lambda c: c,
}

STORE_HINTS = {"城东一店": "S001", "城西二店": "S002", "城南三店": "S003"}
# 只按品名匹配，故意不看规格——这是最常见的真实 bug
PRODUCT_HINTS = [("降压片", "P001"), ("止咳糖浆", "P003"), ("感冒颗粒", "P004")]


@dataclass
class HeuristicPolicy:
    """朴素实现基线：按关键词拼 SQL，不做任何口径约束。

    刻意保留 5 类团队一开始都会犯的真错，用来证明评测集有区分度：
      1. 同品名多规格只取第一个（规格歧义）
      2. join 目标表不加月份条件 -> 重复计数
      3. 排行榜不加 GROUP BY，直接 ORDER BY 行级字段
      4. 库存判断忽略阈值条件
      5. 区间对比题当成全量求和
    """

    def decide(self, ctx: dict[str, Any]) -> Decision:
        history = ctx["history"]
        if history:
            obs = history[-1].obs
            if obs is None or not obs.ok:
                return Decision(thought="查询失败，终止", answer="")
            return Decision(thought="取标量", answer=_scalar_from_obs(obs.content) or "")
        return Decision(thought="按关键词拼查询", call=ToolCall("sql", {"sql": self._guess(ctx["question"])}))

    @staticmethod
    def _guess(question: str) -> str:
        q = question.split("---")[-1]
        store = next((v for k, v in STORE_HINTS.items() if k in q), None)
        product = next((v for k, v in PRODUCT_HINTS if k in q), None)
        month = "2026-09" if ("9 月" in q or "9月" in q) else None
        date_filter = f" AND date LIKE '{month}-%'" if month else ""

        if "库存" in q:
            conds = [c for c in (f"store_id='{store}'" if store else "", f"product_id='{product}'" if product else "") if c]
            where = (" WHERE " + " AND ".join(conds)) if conds else ""
            return f"SELECT SUM(qty) FROM inventory{where}"

        if "完成率" in q:
            join = "JOIN targets t ON t.store_id=s.store_id AND t.product_id=s.product_id"
            window = f" WHERE s.date LIKE '{month}-%'" if month else ""
            if "多少个" in q or "组合" in q:
                return (
                    "SELECT COUNT(*) FROM (SELECT s.store_id, s.product_id, "
                    f"SUM(s.qty)*1.0/MAX(t.target_qty) AS r FROM sales s {join}{window} "
                    "GROUP BY s.store_id, s.product_id) WHERE r >= 1.0"
                )
            conds = []
            if store:
                conds.append(f"s.store_id='{store}'")
            if product:
                conds.append(f"s.product_id='{product}'")
            if month:
                conds.append(f"s.date LIKE '{month}-%'")
            where = (" WHERE " + " AND ".join(conds)) if conds else ""
            return f"SELECT ROUND(SUM(s.qty)*1.0/MAX(t.target_qty),4) FROM sales s {join}{where}"

        if "哪一天" in q:
            return "SELECT date FROM sales ORDER BY qty DESC LIMIT 1"

        if "最高" in q or "最低" in q:
            order = "DESC" if "最高" in q else "ASC"
            metric = "amount" if "销售额" in q else "qty"
            dim = "store_id" if "门店" in q else "product_id"
            return (
                f"SELECT {dim} FROM sales WHERE 1=1{date_filter} "
                f"GROUP BY {dim} ORDER BY SUM({metric}) {order} LIMIT 1"
            )

        conds = []
        if store:
            conds.append(f"store_id='{store}'")
        if product and "两个规格" not in q:
            conds.append(f"product_id='{product}'")
        where = (" WHERE " + " AND ".join(conds)) if conds else " WHERE 1=1"
        return f"SELECT SUM(qty) FROM sales{where}{date_filter}"



SYSTEM_PROMPT = """你是零售业务数据助手。规则：
1. 只能通过 sql 工具查库，禁止臆造数字。
2. 每步只输出一个 JSON，不要输出解释性文字。
3. 需要查询时输出：{"thought":"...","tool":"sql","args":{"sql":"SELECT ..."}}
4. 有足够信息时输出：{"thought":"...","answer":"<最终答案>"}
5. 只允许 SELECT，禁止写操作。
6. answer 里最后必须单独一行以「答案：」开头，后面只跟结果值本身，
   不要把年份、规格、门店编号写进这一行。例如 "答案：1234" 或 "答案：S001"。
7. 若问题缺少必要信息（时间范围、门店、产品规格、指标口径等），且无法从表结构或历史上文推断，
   不要猜测，也不要先查一遍再猜，直接输出：{"thought":"...","clarify":"<向用户确认的一句话>"}
   一次问清最关键的那个缺口，不要罗列一堆问题。宁可问一次，也不要给一个猜出来的数字。
"""


@dataclass
class OpenAICompatPolicy:
    """任何 OpenAI 兼容接口（DeepSeek / 通义 / vLLM / Ollama）。"""

    model: str = "deepseek-chat"
    base_url: str = "https://api.deepseek.com/v1"
    api_key: str = ""
    temperature: float = 0.0

    def decide(self, ctx: dict[str, Any]) -> Decision:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.append({"role": "user", "content": self._render_context(ctx)})
        raw = self._chat(messages)
        return self._parse(raw)

    def _render_context(self, ctx: dict[str, Any]) -> str:
        parts = [f"问题：{ctx['question']}", f"可用工具：\n{ctx['registry'].describe()}"]
        for step in ctx["history"]:
            parts.append(f"第{step.index + 1}步 调用 {step.call.name}: {step.call.args}")
            if step.obs is not None:
                parts.append(f"结果：{step.obs.content[:800]}")
        return "\n\n".join(parts)

    def _resolve_key(self) -> str:
        return (
            self.api_key
            or os.getenv("DEEPSEEK_API_KEY", "")
            or os.getenv("OPENAI_API_KEY", "")
            or os.getenv("RX_LLM_API_KEY", "")
        )

    def _chat(self, messages: list[dict[str, str]]) -> str:
        key = self._resolve_key()
        if not key:
            raise RuntimeError(
                "缺少 API key。请先设置环境变量，例如：\n"
                "  set DEEPSEEK_API_KEY=sk-xxxx   (Windows cmd)\n"
                "  export DEEPSEEK_API_KEY=sk-xxxx (bash)"
            )
        payload = json.dumps(
            {"model": self.model, "messages": messages, "temperature": self.temperature}
        ).encode()
        req = urllib.request.Request(
            f"{self.base_url.rstrip('/')}/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
            },
        )
        data = self._post_with_retry(req)
        msg = data["choices"][0]["message"]
        # 记录真实计费 token。注意与 loop.estimate_tokens 的区别：后者只统计可见输出，
        # 不含推理模型的 reasoning_content，两者的数值不能混用。
        usage = data.get("usage") or {}
        self._last_usage = {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "reasoning_chars": len(msg.get("reasoning_content") or ""),
        }
        return msg["content"]

    def _post_with_retry(self, req: urllib.request.Request, attempts: int = 4) -> dict[str, Any]:
        """限流与瞬时故障重试。

        单次评测里一次 429 只废掉一道题，可以重跑；但自进化一轮要发上千次请求、
        跑几十分钟，中途任何一个未捕获的异常都会让整轮作废。所以这里必须重试。
        只重试可恢复的错误（429 / 5xx / 连接超时），4xx 里的鉴权与参数错误直接抛。
        """
        delay = 2.0
        last: Exception | None = None
        for attempt in range(attempts):
            try:
                with urllib.request.urlopen(req, timeout=90) as resp:
                    return json.loads(resp.read().decode())
            except urllib.error.HTTPError as exc:
                last = exc
                if exc.code not in (408, 409, 429) and exc.code < 500:
                    raise
            except (urllib.error.URLError, TimeoutError) as exc:
                last = exc
            if attempt < attempts - 1:
                time.sleep(delay)
                delay *= 2
        raise RuntimeError(f"调用模型失败（重试 {attempts} 次）：{last}") from last

    @staticmethod
    def _parse(raw: str) -> Decision:
        match = re.search(r"\{.*\}", raw, re.S)
        if not match:
            return Decision(thought="模型未按格式输出", answer=raw.strip())
        try:
            obj = json.loads(match.group(0))
        except json.JSONDecodeError:
            return Decision(thought="JSON 解析失败", answer=raw.strip())
        if obj.get("answer") is not None:
            return Decision(thought=obj.get("thought", ""), answer=str(obj["answer"]))
        if obj.get("clarify") is not None:
            return Decision(thought=obj.get("thought", ""), clarify=str(obj["clarify"]))
        tool = obj.get("tool") or obj.get("name")
        if tool:
            return Decision(thought=obj.get("thought", ""), call=ToolCall(tool, obj.get("args") or {}))
        return Decision(thought="无有效动作")
