"""自进化层的单元测试。

重点不是"进化能不能涨分"，而是三件事有没有被守住：
  1. 划分是否互斥且覆盖全部任务
  2. 知识完整时学习者应贴近满分（否则后面的提升无法归因）
  3. 越界补丁是否被白名单挡住
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bench.grader import summarize  # noqa: E402
from bench.runner import DB_PATH, load_tasks  # noqa: E402
from evolve.knowledge import degrade, skill_texts  # noqa: E402
from evolve.learner import split_context  # noqa: E402
from evolve.loop import evaluate_with, evolve  # noqa: E402
from evolve.operators import Evidence, Patch, propose  # noqa: E402
from evolve.presets import DEFAULT_DROP_COLUMNS, DEFAULT_DROP_LITERALS  # noqa: E402
from evolve.split import stratified_split  # noqa: E402


class TestSplit(unittest.TestCase):
    def test_disjoint_and_covering(self) -> None:
        tasks = load_tasks()
        dev, holdout = stratified_split(tasks)
        dev_ids = {t["id"] for t in dev}
        hold_ids = {t["id"] for t in holdout}
        self.assertEqual(len(dev) + len(holdout), len(tasks))
        self.assertFalse(dev_ids & hold_ids)

    def test_stratification_preserves_levels(self) -> None:
        tasks = load_tasks()
        dev, holdout = stratified_split(tasks)
        for side in (dev, holdout):
            levels = {t["level"] for t in side}
            self.assertEqual(levels, {"L1", "L2", "L3", "L4"})


class TestKnowledgeGateLearner(unittest.TestCase):
    def test_split_context_isolates_question(self) -> None:
        prefix, question = split_context("### schema\n`date`\n\n---\n\n城东区门店销量？")
        self.assertIn("`date`", prefix)
        self.assertEqual(question, "城东区门店销量？")

    def test_full_knowledge_has_no_column_guessing(self) -> None:
        """文档完整时，失败只应来自"文档从没写过的事实"，不该出现猜列名。

        实测存在两类真实缺口：片区取值从未写进文档（4 题）、
        "缺信息要先确认"这条规则从未写进文档（13 题）。
        这两类正是自进化要补的东西——如果这里出现 tool_error，说明链路坏了。
        """
        tasks = load_tasks()
        verdicts, _ = evaluate_with(ROOT / "skills", tasks, DB_PATH)
        summary = summarize(verdicts)
        self.assertNotIn("tool_error", summary["failure_buckets"])
        self.assertNotIn("unsafe_sql", summary["failure_buckets"])
        self.assertEqual(set(summary["failure_buckets"]), {"answered_wrong", "needs_clarification_unmet"})
        self.assertGreaterEqual(summary["passed"], 40)

    def test_degrade_creates_gap(self) -> None:
        tmp = ROOT / "reports" / "_test_state"
        degrade(ROOT / "skills", tmp, drop_columns=DEFAULT_DROP_COLUMNS, drop_literals=DEFAULT_DROP_LITERALS)
        text = "\n".join(skill_texts(tmp).values())
        self.assertNotIn("`target_qty`", text)
        self.assertNotIn("20mg", text)

    def test_degraded_scores_lower(self) -> None:
        tasks = load_tasks()
        tmp = ROOT / "reports" / "_test_state2"
        degrade(ROOT / "skills", tmp, drop_columns=DEFAULT_DROP_COLUMNS, drop_literals=DEFAULT_DROP_LITERALS)
        full, _ = evaluate_with(ROOT / "skills", tasks, DB_PATH)
        bad, _ = evaluate_with(tmp, tasks, DB_PATH)
        self.assertLess(summarize(bad)["passed"], summarize(full)["passed"])


class TestEvolutionLoop(unittest.TestCase):
    def test_rule_mode_converges_and_generalizes(self) -> None:
        tasks = load_tasks()
        dev, holdout = stratified_split(tasks)
        state = ROOT / "reports" / "_test_evolve"
        degrade(ROOT / "skills", state, drop_columns=DEFAULT_DROP_COLUMNS, drop_literals=DEFAULT_DROP_LITERALS)
        records = evolve(state, dev, holdout, DB_PATH, generations=6, mode="rule")
        last = records[-1]
        self.assertEqual(last.dev_passed, last.dev_total)
        self.assertEqual(last.holdout_passed, last.holdout_total)

    def test_cheat_patch_is_rejected(self) -> None:
        tasks = load_tasks()
        dev, holdout = stratified_split(tasks)
        state = ROOT / "reports" / "_test_cheat"
        degrade(ROOT / "skills", state, drop_columns=DEFAULT_DROP_COLUMNS, drop_literals=DEFAULT_DROP_LITERALS)
        records = evolve(state, dev, holdout, DB_PATH, generations=2, mode="cheat")
        self.assertFalse(records[0].accepted)
        self.assertIn("不在允许范围", records[0].note)

    def test_memory_patch_does_not_help_holdout(self) -> None:
        tasks = load_tasks()
        dev, holdout = stratified_split(tasks)
        state = ROOT / "reports" / "_test_memory"
        degrade(ROOT / "skills", state, drop_columns=DEFAULT_DROP_COLUMNS, drop_literals=DEFAULT_DROP_LITERALS)
        records = evolve(state, dev, holdout, DB_PATH, generations=2, mode="memory")
        self.assertLess(records[-1].holdout_passed, records[-1].dev_passed)


class TestProposeSurface(unittest.TestCase):
    def test_cheat_patch_surface_is_bench(self) -> None:
        patch = propose([Evidence("q01", "column", "x", "date")], "cheat", DB_PATH, {}, failing=["q01"])[0]
        self.assertEqual(patch.surface, "bench")
        self.assertEqual(patch.kind, "cheat")

    def test_rule_patch_surface_is_skills(self) -> None:
        patch = propose([Evidence("q01", "column", "x", "date")], "rule", DB_PATH, {})[0]
        self.assertEqual(patch.surface, "skills")


if __name__ == "__main__":
    unittest.main()
