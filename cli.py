"""命令行入口。

    python cli.py build                 # 生成模拟业务库
    python cli.py eval                  # 跑基线 + 评测器变异测试
    python cli.py eval --provider openai --model deepseek-chat
    python cli.py ask "城东一店 9 月总销量多少盒？"
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from bench.runner import (  # noqa: E402
    DB_PATH,
    build_registry,
    context_prefix,
    evaluate,
    heuristic_factory,
    load_tasks,
    mutation_suite,
    oracle_factory,
    write_report,
)
from harness.loop import run  # noqa: E402
from harness.llm import OpenAICompatPolicy  # noqa: E402


def cmd_build(args: argparse.Namespace) -> int:
    from data.build_db import build

    path = build()
    print(f"业务库已生成：{path}")
    return 0


def cmd_coverage(args: argparse.Namespace) -> int:
    """工程属性实测：不需要 API key，本地即可跑。"""
    from data.build_db import build

    if not DB_PATH.exists():
        build()
        print(f"业务库不存在，已自动生成：{DB_PATH}")

    from bench.coverage import run_all, write_coverage_report

    result = run_all()
    path = write_coverage_report(result)

    g, b, a, e = result["guard"], result["budget"], result["answer"], result["equivalence"]
    print(
        json.dumps(
            {
                "G1_guard_blocked": f"{g['blocked']}/{g['total']}",
                "G1_data_intact": f"{g['data_intact']}/{g['total']}",
                "G1_false_positive": f"{g['false_positive_passed']}/{g['false_positive_total']}",
                "G2_unguarded_damaging": f"{g['unguarded_damaging']}/{g['total']}",
                "G3_budget": f"{sum(1 for x in b if x['ok'])}/{len(b)}",
                "G4_silent_wrong_legacy_to_now": f"{a['legacy_silent_wrong']} -> {a['now_silent_wrong']}",
                "G4_contract": f"{a['contract_passed']}/{a['contract_total']}",
                "G5_equivalence": f"{e['graded_pass']}/{e['total']}",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print(f"报告：{path}")
    return 0


def cmd_evolve(args: argparse.Namespace) -> int:
    """自进化：在 dev 上诊断并打补丁，用 holdout 检查是否只是记忆。

    不需要 API key——学习者是一个只有"知识缺口"单一缺陷的可控策略，
    目的是把进化环路本身跑通并定死度量口径，不是测量模型能力。
    """
    from data.build_db import build

    if not DB_PATH.exists():
        build()
        print(f"业务库不存在，已自动生成：{DB_PATH}")

    import shutil

    from evolve.knowledge import SKILLS_DIR, degrade
    from evolve.loop import evolve, write_evolve_report
    from evolve.presets import DEFAULT_DROP_COLUMNS, DEFAULT_DROP_LITERALS
    from evolve.split import load_split

    tasks = load_tasks()
    dev, holdout = load_split(tasks)
    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    surfaces = ("skills", "bench") if args.allow_bench else ("skills",)
    drop_columns = args.drop_column or list(DEFAULT_DROP_COLUMNS)
    drop_literals = args.drop_literal or list(DEFAULT_DROP_LITERALS)
    if args.no_degrade:
        drop_columns, drop_literals = [], []

    summary = []
    for mode in modes:
        tag = f"-{args.tag}" if args.tag else ""
        workdir = ROOT / "reports" / f"evolve-{mode}{tag}"
        workdir.mkdir(parents=True, exist_ok=True)
        state = workdir / "state"
        degrade(
            SKILLS_DIR,
            state,
            drop_columns=drop_columns,
            drop_literals=drop_literals,
        )
        initial = workdir / "initial"
        if initial.exists():
            shutil.rmtree(initial)
        shutil.copytree(state, initial)

        records = evolve(
            state,
            dev,
            holdout,
            DB_PATH,
            generations=args.generations,
            mode=mode,
            allow_surfaces=surfaces,
        )
        path = write_evolve_report(
            records,
            title=f"自进化对照 · {mode}",
            meta={
                "学习者": "KnowledgeGatePolicy（单一缺陷：知识缺口）",
                "dev / holdout": f"{len(dev)} / {len(holdout)}",
                "可改面": "、".join(surfaces),
                "初始缺口": f"列 {list(drop_columns)}；字面量 {list(drop_literals)}",
                "最大代数": args.generations,
            },
            name=f"evolve-{mode}{tag}",
        )
        last = records[-1] if records else None
        summary.append(
            {
                "mode": mode,
                "dev": f"{last.dev_passed}/{last.dev_total}" if last else "0/0",
                "holdout": f"{last.holdout_passed}/{last.holdout_total}" if last else "0/0",
                "generations": len(records),
                "report": str(path),
            }
        )

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def _require_key(args: argparse.Namespace) -> bool:
    import os

    if os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("RX_LLM_API_KEY"):
        return True
    print(
        "缺少 API key，无法实测真实模型。\n"
        "设置后再跑：\n"
        "  bash:   export DEEPSEEK_API_KEY=sk-xxxx && python cli.py eval --provider openai --ablate --repeat 3\n"
        "  cmd :   set DEEPSEEK_API_KEY=sk-xxxx && python cli.py eval --provider openai --ablate --repeat 3\n"
        "不需要 key 的工程属性实测请用：python cli.py coverage",
        file=sys.stderr,
    )
    return False


def cmd_eval(args: argparse.Namespace) -> int:
    from data.build_db import build

    if not DB_PATH.exists():
        build()
        print(f"业务库不存在，已自动生成：{DB_PATH}")

    if args.provider == "openai" and not _require_key(args):
        return 2

    tasks = load_tasks()
    if args.limit:
        tasks = tasks[: args.limit]
    prefix = context_prefix(exclude=args.exclude_skill)
    model_factory = lambda _task: OpenAICompatPolicy(model=args.model, base_url=args.base_url)  # noqa: E731
    strict = not getattr(args, "lax", False)
    mode = "" if strict else " · 宽松判定"

    if args.provider == "openai":
        if args.ablate:
            groups = []
            for use_skill in (False, True):
                label = f"skill {'on ' if use_skill else 'off'} / {args.model}{mode}"
                runs = [
                    evaluate(_apply_skills(tasks, prefix, use_skill), model_factory, strict=strict)
                    for _ in range(max(1, args.repeat))
                ]
                groups.append((label, runs[-1]))
                if args.repeat > 1:
                    groups[-1] = (f"{label} · 稳定 {_stable(runs)}/{len(runs[0])}", runs[-1])
        else:
            groups = [
                (
                    f"openai-compat / {args.model}{mode}",
                    evaluate(_apply_skills(tasks, prefix, True), model_factory, strict=strict),
                )
            ]
    else:
        groups = [
            ("oracle（链路上限，校准用）", evaluate(tasks, oracle_factory, strict=strict)),
            ("heuristic（朴素实现基线）", evaluate(tasks, heuristic_factory, strict=strict)),
        ]

    anchor = tasks[0]
    mutations = mutation_suite(anchor)
    path = write_report(groups, mutations, name=args.report_name)

    from bench.grader import summarize

    summary = [{"label": label, **summarize(vs)} for label, vs in groups]
    hits = sum(1 for m in mutations if m["hit"])
    print(json.dumps({"runs": summary, "mutation_attribution": f"{hits}/{len(mutations)}"}, ensure_ascii=False, indent=2))
    print(f"报告：{path}")
    return 0


def _apply_skills(tasks: list[dict], prefix: str, use_skill: bool) -> list[dict]:
    if not use_skill:
        return tasks
    return [{**t, "question": f"{prefix}\n\n---\n\n{t['question']}"} for t in tasks]


def _stable(runs: list[list]) -> int:
    """N 次重复里每次都通过的任务数——衡量稳定性，而不只是单次正确率。"""
    ids = [v.task_id for v in runs[0]]
    return sum(1 for i in range(len(ids)) if all(run[i].ok for run in runs))


def cmd_ask(args: argparse.Namespace) -> int:
    from data.build_db import build

    if not _require_key(args):
        return 2

    if not DB_PATH.exists():
        build()

    task = {"id": "adhoc", "question": args.question, "max_steps": 6}
    prefix = context_prefix()
    task["question"] = f"{prefix}\n\n---\n\n{args.question}"
    registry = build_registry()
    policy = OpenAICompatPolicy(model=args.model, base_url=args.base_url)
    trace = run(task, registry, policy, max_steps=6)

    for step in trace.steps:
        print(f"[{step.index}] {step.thought}")
        print(f"    call: {step.call.name} {step.call.args}")
        if step.obs:
            preview = step.obs.content[:300]
            print(f"    obs : {'OK ' if step.obs.ok else 'ERR'} {preview}")
    print(f"\n答案：{trace.answer}")
    print(f"步数：{len(trace.steps)}  stop: {trace.stop_reason}  tokens≈{trace.tokens}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="rx-harness")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_build = sub.add_parser("build", help="生成模拟业务库")
    p_build.set_defaults(func=cmd_build)

    p_eval = sub.add_parser("eval", help="跑评测")
    p_eval.add_argument("--provider", choices=["oracle", "openai"], default="oracle")
    p_eval.add_argument("--model", default="deepseek-chat")
    p_eval.add_argument("--base-url", default="https://api.deepseek.com/v1", help="OpenAI 兼容端点")
    p_eval.add_argument("--limit", type=int, default=0)
    p_eval.add_argument("--ablate", action="store_true", help="对比 skill 注入开/关（需 --provider openai）")
    p_eval.add_argument(
        "--exclude-skill",
        action="append",
        default=[],
        metavar="NAME",
        help="注入时排除某个 skill，可重复，用于分层消融（如 --exclude-skill schema）",
    )
    p_eval.add_argument("--repeat", type=int, default=1, help="每个任务重复次数，用于测稳定性")
    p_eval.add_argument(
        "--lax",
        action="store_true",
        help="宽松判定：只看最终答案，过程中的越权/异常不直接判失败。"
        "与默认严格判定的差值，就是「安全边界对吞吐的定价」",
    )
    p_eval.add_argument(
        "--report-name", default="report", help="报告文件名（不含扩展名），便于给不同配置存档"
    )
    p_eval.set_defaults(func=cmd_eval)

    p_cov = sub.add_parser("coverage", help="工程属性实测（不需要 API key）")
    p_cov.set_defaults(func=cmd_coverage)

    p_evo = sub.add_parser("evolve", help="自进化：诊断失败、补知识、用留出集检查泛化（不需要 API key）")
    p_evo.add_argument(
        "--modes",
        default="rule",
        help="逗号分隔：rule（归纳知识）/ memory（记住原题）/ cheat（改评测集，反例）",
    )
    p_evo.add_argument("--generations", type=int, default=6)
    p_evo.add_argument(
        "--drop-column",
        action="append",
        default=[],
        metavar="COL",
        help="初始状态故意缺失的列声明，可重复；默认见 evolve/presets.py",
    )
    p_evo.add_argument(
        "--drop-literal",
        action="append",
        default=[],
        metavar="TEXT",
        help="初始状态故意缺失的字面量（如 20mg），可重复",
    )
    p_evo.add_argument(
        "--allow-bench",
        action="store_true",
        help="放开对 bench/ 的修改权限——只用于演示没有边界约束时进化会退化成什么",
    )
    p_evo.add_argument("--tag", default="", help="报告名后缀，便于给不同配置分别存档")
    p_evo.add_argument(
        "--no-degrade",
        action="store_true",
        help="从现有文档出发（不预先挖缺口），用于看人工文档还漏了什么",
    )
    p_evo.set_defaults(func=cmd_evolve)

    p_ask = sub.add_parser("ask", help="单问题调试")
    p_ask.add_argument("question")
    p_ask.add_argument("--model", default="deepseek-chat")
    p_ask.add_argument("--base-url", default="https://api.deepseek.com/v1")
    p_ask.set_defaults(func=cmd_ask)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
