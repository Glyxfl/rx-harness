"""进化主循环：evaluate -> diagnose -> patch -> 只在 dev 上决定接受与否。

三条硬约束，缺一条这个循环就会退化成"刷分"：

1. **接受只看 dev**。holdout 每代都跑，但只记录、不参与选择。
   用它来决定接受与否，等于把留出集也变成了训练集。
2. **可改面只有知识层**。题目和判定器不开放——否则最优策略必然是改标准答案。
3. **改动可回滚、可审计**。每代前后各存一份快照，报告里逐条列出补丁来源的证据。
   没有审计的进化，最后没人说得清分数是怎么来的。
"""
from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Sequence

from bench.grader import grade, summarize
from bench.runner import build_registry, context_prefix
from evolve.knowledge import append_text, degrade
from evolve.learner import SEP, KnowledgeGatePolicy
from evolve.operators import Patch, diagnose, propose
from harness.loop import run

ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / "skills"
REPORT_DIR = ROOT / "reports"


@dataclass
class GenRecord:
    gen: int
    dev_passed: int
    dev_total: int
    holdout_passed: int
    holdout_total: int
    patch: str
    accepted: bool
    note: str
    evidence: list[dict[str, str]] = field(default_factory=list)


def evaluate_with(
    skills_dir: str | Path,
    tasks: Sequence[dict[str, Any]],
    db_path: str | Path,
) -> tuple[list, dict[str, Any]]:
    prefix = context_prefix(Path(skills_dir))
    verdicts, traces = [], {}
    for task in tasks:
        if task.get("_skipped"):
            continue
        augmented = {**task, "question": f"{prefix}{SEP}{task['question']}"} if prefix else dict(task)
        registry = build_registry(Path(db_path))
        policy = KnowledgeGatePolicy(
            sql=str(task.get("gold_sql") or ""),
            expect=str(task.get("expect", "answer")),
            keywords=tuple(task.get("clarify_keywords") or ()),
        )
        trace = run(augmented, registry, policy, max_steps=int(task.get("max_steps", 6)))
        verdicts.append(grade(task, trace, db_path))
        traces[str(task["id"])] = trace
    return verdicts, traces


def prepare_state(workdir: Path, drop_columns: Sequence[str], drop_literals: Sequence[str]) -> Path:
    state = Path(workdir) / "state"
    degrade(SKILLS_DIR, state, drop_columns=drop_columns, drop_literals=drop_literals)
    return state


def _apply(state: Path, patch: Patch, task_index: dict[str, dict]) -> None:
    if patch.kind == "cheat":
        # 最省力的"进化"不是让系统变好，而是让分母变小：把失败的题标记为跳过。
        # 分数立刻满分，系统一点没变——这就是为什么修改面必须是白名单。
        for task_id in patch.covers:
            task = task_index.get(task_id)
            if task is not None:
                task["_skipped"] = True
        return
    append_text(state, patch.skill, patch.text)
    append_text(state, patch.skill, patch.text)


def evolve(
    state: Path,
    dev: list[dict[str, Any]],
    holdout: list[dict[str, Any]],
    db_path: Path,
    generations: int = 6,
    mode: str = "rule",
    allow_surfaces: Sequence[str] = ("skills",),
) -> list[GenRecord]:
    task_index = {str(t["id"]): t for t in dev}
    records: list[GenRecord] = []
    snapshot = Path(state).parent / ".snapshot"

    for gen in range(generations):
        dev_v, dev_traces = evaluate_with(state, dev, db_path)
        hold_v, _ = evaluate_with(state, holdout, db_path)
        dev_s, hold_s = summarize(dev_v), summarize(hold_v)
        record = GenRecord(
            gen=gen,
            dev_passed=dev_s["passed"],
            dev_total=dev_s["total"],
            holdout_passed=hold_s["passed"],
            holdout_total=hold_s["total"],
            patch="-",
            accepted=False,
            note="",
        )

        if dev_s["passed"] == dev_s["total"]:
            record.note = "dev 已全通过，停止"
            records.append(record)
            break

        evidence = diagnose(dev_v, dev_traces, db_path, task_index)
        record.evidence = [asdict(e) for e in evidence]
        failing = [v.task_id for v in dev_v if not v.ok]
        candidates = propose(evidence, mode, db_path, task_index, failing=failing)

        chosen = None
        for patch in candidates:
            if patch.surface in allow_surfaces:
                chosen = patch
                break
            record.note = f"拒绝补丁 {patch.pid}：修改面 `{patch.surface}` 不在允许范围 {list(allow_surfaces)}"

        if chosen is None:
            if not record.note:
                record.note = "无可执行补丁，停止"
            records.append(record)
            break

        if snapshot.exists():
            shutil.rmtree(snapshot)
        shutil.copytree(state, snapshot)
        _apply(state, chosen, task_index)
        after_v, _ = evaluate_with(state, dev, db_path)
        after_s = summarize(after_v)
        record.patch = f"{chosen.pid} · {chosen.rationale}"

        # 接受准则按准确率，这是业界最常见的做法。
        # 代价是它对"分母变小"没有免疫力——删掉难题同样能让准确率上涨。
        # 真正挡住这件事的不是准则，而是下面的修改面白名单。
        if after_s["success_rate"] > dev_s["success_rate"] + 1e-9:
            record.accepted = True
            record.note = (
                f"接受：dev {dev_s['passed']}/{dev_s['total']} → {after_s['passed']}/{after_s['total']}"
            )
        else:
            shutil.rmtree(state)
            shutil.copytree(snapshot, state)
            for task in task_index.values():
                task.pop("_skipped", None)
            record.accepted = False
            record.note = (
                f"回滚：dev 未提升（{dev_s['passed']}/{dev_s['total']} → "
                f"{after_s['passed']}/{after_s['total']}）"
            )
            records.append(record)
            break

        records.append(record)

    return records


def write_evolve_report(
    records: list[GenRecord],
    title: str,
    meta: dict[str, Any],
    out_dir: Path = REPORT_DIR,
    name: str = "evolve",
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{name}.json").write_text(
        json.dumps({"title": title, "meta": meta, "generations": [asdict(r) for r in records]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = [f"# {title}", ""]
    if meta:
        lines += [f"- {k}：{v}" for k, v in meta.items()]
        lines.append("")
    lines += [
        "| 代 | dev | holdout | 补丁 | 结果 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for r in records:
        lines.append(
            f"| {r.gen} | {r.dev_passed}/{r.dev_total} | {r.holdout_passed}/{r.holdout_total} "
            f"| {r.patch} | {'接受' if r.accepted else '未接受'}{(' · ' + r.note) if r.note else ''} |"
        )

    if records and records[-1].evidence:
        lines += ["", "## 最后一轮诊断到的失败证据", "", "| 任务 | 类型 | 证据 |", "| --- | --- | --- |"]
        for e in records[-1].evidence[:20]:
            lines.append(f"| {e['task_id']} | {e['kind']} | {e['detail']} |")

    dev_rate = records[-1].dev_passed / records[-1].dev_total if records else 0.0
    hold_rate = records[-1].holdout_passed / records[-1].holdout_total if records else 0.0
    lines += [
        "",
        "## 泛化差距",
        "",
        f"- dev：{records[-1].dev_passed}/{records[-1].dev_total} = {dev_rate:.1%}",
        f"- holdout：{records[-1].holdout_passed}/{records[-1].holdout_total} = {hold_rate:.1%}",
        f"- 差距：{(dev_rate - hold_rate) * 100:.1f} 个百分点",
        "",
        "差距为正说明补丁含有只在 dev 上成立的部分；差距接近 0 才说明改的是规则而不是记忆。",
    ]

    path = out_dir / f"{name}.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
