"""进化主循环：evaluate -> diagnose -> patch -> 只在 dev 上决定接受与否。

三条硬约束，缺一条这个循环就会退化成"刷分"：

1. **接受只看 dev**。holdout 每代都跑，但只记录、不参与选择。
   用它来决定接受与否，等于把留出集也变成了训练集。
2. **可改面只有知识层**。题目和判定器不开放——否则最优策略必然是改标准答案。
3. **改动可回滚、可审计**。每代前后各存一份快照，报告里逐条列出补丁来源的证据。
   没有审计的进化，最后没人说得清分数是怎么来的。
"""
from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

from bench.grader import grade
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
    # 同一补丁的多次重复结果。真模型在 temperature>0 下同一题会时对时错，
    # 单次比较分不清"补丁有效"和"这次抽得好"，所以把分布原样记下来供审计。
    dev_runs_before: list[int] = field(default_factory=list)
    dev_runs_after: list[int] = field(default_factory=list)
    single_run_would_accept: bool = False
    margin: float = 0.0
    failures: dict[str, str] = field(default_factory=dict)


def _median(values: Sequence[int]) -> int:
    ordered = sorted(values)
    if not ordered:
        return 0
    mid = len(ordered) // 2
    return ordered[mid] if len(ordered) % 2 else round((ordered[mid - 1] + ordered[mid]) / 2)


def _state_key(skills_dir: str | Path) -> str:
    """知识状态的指纹：全部 SKILL.md 的内容哈希。

    用于跨代缓存。第 g 代的"补丁后"和第 g+1 代的"补丁前"是同一个状态，
    重跑一遍只会得到同一份 prompt 的另一次采样，不会带来新信息，却要付一倍的钱。
    """
    digest = hashlib.sha256()
    for path in sorted(Path(skills_dir).rglob("*.md")):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _score(counts: Sequence[int], total: int, metric: str) -> float:
    """接受度量。

    count：通过题数的中位数。分母变了它看得见——删题不会加分。
    rate ：准确率。这是业界更常见的做法，但分母一变，删掉难题同样算"进步"。
    默认用 count，不是因为它更先进，而是因为它不让"分母变小"混进来。
    """
    med = _median(counts)
    return float(med) if metric == "count" else (med / total if total else 0.0)


def _fmt_margin(value: float, metric: str) -> str:
    return f"+{value:.0f} 题" if metric == "count" else f"+{value * 100:.1f} pp"


def evaluate_runs(
    skills_dir: str | Path,
    tasks: Sequence[dict[str, Any]],
    db_path: str | Path,
    policy_factory: Callable[[dict[str, Any]], Any] | None = None,
    repeats: int = 1,
) -> tuple[list[list[Any]], dict[str, Any]]:
    """在给定知识状态下跑 repeats 轮，返回每轮的判定与最后一轮的 trace。

    同一题的多次重复共用同一份 prompt，模型在 temperature>0 时的抖动就是噪声本身。
    不重复就无法把"补丁的收益"和"采样的波动"分开。
    trace 只保留最后一轮——诊断只需要一例失败现场，没必要为它多跑一遍。
    """
    prefix = context_prefix(Path(skills_dir))
    all_runs: list[list[Any]] = []
    traces: dict[str, Any] = {}
    for _ in range(max(1, repeats)):
        verdicts: list[Any] = []
        traces = {}
        for task in tasks:
            if task.get("_skipped"):
                continue
            augmented = {**task, "question": f"{prefix}{SEP}{task['question']}"} if prefix else dict(task)
            registry = build_registry(Path(db_path))
            if policy_factory is None:
                policy = KnowledgeGatePolicy(
                    sql=str(task.get("gold_sql") or ""),
                    expect=str(task.get("expect", "answer")),
                    keywords=tuple(task.get("clarify_keywords") or ()),
                )
            else:
                policy = policy_factory(task)
            trace = run(augmented, registry, policy, max_steps=int(task.get("max_steps", 6)))
            verdicts.append(grade(task, trace, db_path))
            traces[str(task["id"])] = trace
        all_runs.append(verdicts)
    return all_runs, traces


def evaluate_with(
    skills_dir: str | Path,
    tasks: Sequence[dict[str, Any]],
    db_path: str | Path,
    policy_factory: Callable[[dict[str, Any]], Any] | None = None,
) -> tuple[list, dict[str, Any]]:
    """单轮评测，返回判定与 trace（诊断需要 trace 才能定位失败发生在哪一步）。"""
    runs, traces = evaluate_runs(skills_dir, tasks, db_path, policy_factory, repeats=1)
    return runs[0], traces


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


def evolve(
    state: Path,
    dev: list[dict[str, Any]],
    holdout: list[dict[str, Any]],
    db_path: Path,
    generations: int = 6,
    mode: str = "rule",
    allow_surfaces: Sequence[str] = ("skills",),
    policy_factory: Callable[[dict[str, Any]], Any] | None = None,
    repeats: int = 1,
    metric: str = "count",
) -> list[GenRecord]:
    task_index = {str(t["id"]): t for t in dev}
    records: list[GenRecord] = []
    snapshot = Path(state).parent / ".snapshot"
    cache: dict[Any, tuple[list[list[Any]], dict[str, Any]]] = {}

    def runs_of(skills_dir: Path, tasks: Sequence[dict[str, Any]], n: int | None = None):
        # 键必须含题号：dev 和 holdout 都是 30 条、共用同一份知识状态，
        # 只按状态和长度做键会让 holdout 直接读到 dev 的结果（曾经踩过）。
        ids = tuple(sorted(str(t["id"]) for t in tasks))
        key = (
            _state_key(skills_dir),
            ids,
            tuple(sorted(str(t["id"]) for t in tasks if t.get("_skipped"))),
            n if n is not None else repeats,
        )
        if key not in cache:
            cache[key] = evaluate_runs(
                skills_dir, tasks, db_path, policy_factory, n if n is not None else repeats
            )
        return cache[key]

    for gen in range(generations):
        before_runs, dev_traces = runs_of(state, dev)
        # holdout 只用于观测，不参与接受判断，因此不需要重复——重复是为决策服务的
        hold_runs, _ = runs_of(state, holdout, 1)
        dev_v = before_runs[-1]
        before_counts = [sum(1 for v in run if v.ok) for run in before_runs]
        hold_counts = [sum(1 for v in run if v.ok) for run in hold_runs]
        record = GenRecord(
            gen=gen,
            dev_passed=_median(before_counts),
            dev_total=len(before_runs[0]),
            holdout_passed=_median(hold_counts),
            holdout_total=len(hold_runs[0]),
            patch="-",
            accepted=False,
            note="",
            dev_runs_before=before_counts,
            dev_runs_after=[],
            failures={v.task_id: v.reason for v in dev_v if not v.ok},
        )

        if record.dev_passed == record.dev_total:
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
        after_runs, _ = runs_of(state, dev)
        after_counts = [sum(1 for v in run if v.ok) for run in after_runs]
        record.patch = f"{chosen.pid} · {chosen.rationale}"
        record.dev_runs_after = after_counts
        # rate 度量的分母是"本轮实际参与评测的题数"，删题后分母会变小——这正是
        # 准确率口径对作弊没有免疫力的机制所在。count 度量不看分母，所以不受影响。
        margin = _score(after_counts, len(after_runs[0]), metric) - _score(
            before_counts, len(before_runs[0]), metric
        )
        record.margin = round(margin, 4)
        # 单次口径会怎么判——留这个字段纯粹为了事后统计两者分歧了多少次。
        record.single_run_would_accept = after_counts[0] > before_counts[0]

        # 接受准则：中位数严格提升。
        # 单次比较在 temperature>0 下会被采样的抖动骗过；重复取中位数把抖动压掉，
        # 代价是每题要跑多次。这个代价换来的是"补丁有效"和"这次抽得好"可以分开。
        if margin > 1e-9:
            record.accepted = True
            record.note = (
                f"接受：dev {_fmt(before_counts)} → {_fmt(after_counts)}（中位数 {_fmt_margin(margin, metric)}）"
            )
        else:
            shutil.rmtree(state)
            shutil.copytree(snapshot, state)
            for task in task_index.values():
                task.pop("_skipped", None)
            record.accepted = False
            record.note = (
                f"回滚：中位数未提升（{_fmt(before_counts)} → {_fmt(after_counts)}，"
                f"差 {_fmt_margin(margin, metric)}）"
            )
            records.append(record)
            break

        records.append(record)

    return records


def _fmt(counts: Sequence[int]) -> str:
    return "/".join(str(c) for c in counts) if len(counts) > 1 else str(counts[0])


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
        "| 代 | dev（中位数） | dev 逐轮 | holdout | 补丁 | 结果 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for r in records:
        runs = f"{'/'.join(map(str, r.dev_runs_before))} → {'/'.join(map(str, r.dev_runs_after))}" if r.dev_runs_after else "/".join(map(str, r.dev_runs_before))
        lines.append(
            f"| {r.gen} | {r.dev_passed}/{r.dev_total} | {runs} | {r.holdout_passed}/{r.holdout_total} "
            f"| {r.patch} | {'接受' if r.accepted else '未接受'}{(' · ' + r.note) if r.note else ''} |"
        )

    if records and records[-1].failures:
        lines += ["", "## 本轮未通过的题目", "", "| 任务 | 归因 |", "| --- | --- |"]
        for task_id, reason in sorted(records[-1].failures.items()):
            lines.append(f"| {task_id} | `{reason}` |")

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
    body = "\n".join(lines) + "\n"
    if any(len(r.dev_runs_before) > 1 for r in records):
        multi = [r for r in records if r.dev_runs_after]
        disagree = [r for r in multi if r.single_run_would_accept != r.accepted]
        body += (
            "\n## 单次口径与重复口径的分歧\n\n"
            f"- 有补丁可判的代次：{len(multi)}\n"
            f"- 其中单次口径会做出相反判断：{len(disagree)}\n"
        )
        if disagree:
            body += "\n| 代 | 单次会接受 | 实际判定 | dev 逐轮（前→后） |\n| --- | --- | --- | --- |\n"
            for r in disagree:
                body += (
                    f"| {r.gen} | {'是' if r.single_run_would_accept else '否'} "
                    f"| {'接受' if r.accepted else '回滚'} "
                    f"| {'/'.join(map(str, r.dev_runs_before))} → {'/'.join(map(str, r.dev_runs_after))} |\n"
                )
        body += "\n分歧全部来自采样抖动：同一份 prompt、同一个模型，逐轮结果本身就在浮动。\n"
    path.write_text(body, encoding="utf-8")
    return path
