"""评测执行器：基线 + 评测器的变异测试。

核心思路：一个从没被验证过的评测器，本身就是不可信的。
所以除了跑基线，还额外做一层"对评测器做变异测试"——
对同一道题注入 6 类已知故障，看评测器能不能准确归因到对应标签。
归因准确率 = 评测器可信度的下限证明。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from harness.llm import (
    MUTATORS,
    ClarifyPolicy,
    MutatedPolicy,
    OraclePolicy,
    RepeatingPolicy,
    SilentPolicy,
)
from harness.loop import run
from harness.registry import ToolRegistry, ToolSpec
from harness.skills import load_skills, render_for_prompt
from tools.sql import make_sql_tool

from .grader import Verdict, grade, summarize

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "rx.db"
TASK_PATH = ROOT / "bench" / "tasks.jsonl"
SKILLS_DIR = ROOT / "skills"
REPORT_DIR = ROOT / "reports"


def load_tasks(path: Path = TASK_PATH) -> list[dict[str, Any]]:
    tasks = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            tasks.append(json.loads(line))
    return tasks


def build_registry(db_path: Path = DB_PATH) -> ToolRegistry:
    return ToolRegistry().register(
        ToolSpec(
            name="sql",
            description="在只读业务库上执行 SELECT 查询，返回 JSON（columns + rows）",
            params={"sql": "string，单条 SELECT 语句"},
            fn=make_sql_tool(db_path),
        )
    )


def context_prefix(skills_dir: Path = SKILLS_DIR, exclude: list[str] | None = None) -> str:
    """渲染注入上下文。exclude 用于做"去掉某一层"的消融，比如只看口径不看 schema。"""
    skills = load_skills(skills_dir)
    active = [n for n in skills if not exclude or n not in exclude]
    return render_for_prompt(skills, active)


def evaluate(
    tasks: list[dict[str, Any]],
    policy_factory: Callable[[dict[str, Any]], Any],
    db_path: Path = DB_PATH,
    strict: bool = True,
) -> list[Verdict]:
    verdicts = []
    for task in tasks:
        registry = build_registry(db_path)
        trace = run(task, registry, policy_factory(task), max_steps=task.get("max_steps", 6))
        verdicts.append(grade(task, trace, db_path, strict=strict))
    return verdicts


def oracle_factory(task: dict[str, Any]):
    """链路上限校准。

    对"该提问"的任务，正确形态不是一个数值，所以 oracle 直接给出带关键缺口的问句。
    注意这只校准判定器能否识别提问形态，不代表模型能力。
    """
    if str(task.get("expect", "answer")) == "clarify":
        return ClarifyPolicy(keywords=list(task.get("clarify_keywords") or []))
    return OraclePolicy(sql=task["gold_sql"])


def heuristic_factory(task: dict[str, Any]):
    from harness.llm import HeuristicPolicy

    return HeuristicPolicy()


MUTATION_CASES = [
    ("wrong_filter", "wrong_filter", "answered_wrong"),
    ("wrong_aggregation", "wrong_aggregation", "answered_wrong"),
    ("wrong_table", "wrong_table", "answered_wrong"),
    ("unsafe_sql", "unsafe_sql", "unsafe_sql"),
    ("no_answer", "no_answer", "no_answer"),
    ("step_budget", "step_budget", "step_budget_exceeded"),
]


def mutation_suite(task: dict[str, Any], db_path: Path = DB_PATH) -> list[dict[str, Any]]:
    if not task.get("gold_sql"):
        return []
    results = []
    for name, kind, expected in MUTATION_CASES:
        registry = build_registry(db_path)
        if kind == "no_answer":
            policy = SilentPolicy(sql=task["gold_sql"])
        elif kind == "step_budget":
            policy = RepeatingPolicy(sql=task["gold_sql"])
        else:
            policy = MutatedPolicy(base=OraclePolicy(sql=task["gold_sql"]), mutate=MUTATORS[kind], label=kind)
        trace = run(task, registry, policy, max_steps=4)
        verdict = grade(task, trace, db_path)
        results.append(
            {
                "mutation": name,
                "expected": expected,
                "got": verdict.reason,
                "hit": verdict.reason == expected,
            }
        )
    return results


def write_report(
    groups: list[tuple[str, list[Verdict]]],
    mutations: list[dict[str, Any]],
    out_dir: Path = REPORT_DIR,
    name: str = "report",
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    hits = sum(1 for m in mutations if m["hit"])

    payload = {
        "summaries": [{"label": label, **summarize(vs)} for label, vs in groups],
        "verdicts": {label: [v.to_dict() for v in vs] for label, vs in groups},
        "mutation_suite": {
            "hit": hits,
            "total": len(mutations),
            "accuracy": round(hits / len(mutations), 4) if mutations else 0.0,
            "cases": mutations,
        },
    }
    (out_dir / f"{name}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = ["# 评测报告", ""]
    lines += ["## 汇总对比", "", "| 配置 | 通过/总数 | 成功率 | 平均工具步数 | 平均 token |", "| --- | --- | --- | --- | --- |"]
    for label, vs in groups:
        s = summarize(vs)
        lines.append(
            f"| {label} | {s['passed']}/{s['total']} | {s['success_rate']:.2%} | {s['avg_steps']} | {s['avg_tokens']} |"
        )

    for label, vs in groups:
        s = summarize(vs)
        lines += ["", f"## 明细 · {label}", ""]
        if s["failure_buckets"]:
            lines += ["失败归因分布：", "", "| 归因 | 数量 |", "| --- | --- |"]
            lines += [f"| {k} | {v} |" for k, v in s["failure_buckets"].items()]
            lines.append("")
        else:
            lines += ["无失败任务。", ""]
        lines += ["| 任务 | 结果 | 归因 | gold | got | 步数 |", "| --- | --- | --- | --- | --- | --- |"]
        for v in vs:
            lines.append(
                f"| {v.task_id} | {'PASS' if v.ok else 'FAIL'} | {v.reason} | {v.gold} | {v.got} | {v.steps} |"
            )

    lines += [
        "",
        "## 评测器变异测试",
        "",
        "对同一道题注入 6 类已知故障，检查评测器能否归因到对应标签。",
        f"归因准确率：**{hits}/{len(mutations)}**",
        "",
        "| 注入故障 | 期望归因 | 实际归因 | 命中 |",
        "| --- | --- | --- | --- |",
    ]
    for m in mutations:
        lines.append(f"| {m['mutation']} | {m['expected']} | {m['got']} | {'Y' if m['hit'] else 'N'} |")

    md_path = out_dir / f"{name}.md"
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_path
