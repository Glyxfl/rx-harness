"""最小单测：护栏必须挡住写操作，评测器必须能归因。

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bench.runner import build_registry, load_tasks, mutation_suite  # noqa: E402
from harness.loop import run  # noqa: E402
from harness.llm import OraclePolicy  # noqa: E402
from harness.types import Observation, Step, ToolCall, Trace  # noqa: E402
from tools.sql import UnsafeSQL, check_sql  # noqa: E402


class TestSQLGuard(unittest.TestCase):
    def test_allows_select(self) -> None:
        sql = "SELECT SUM(qty) FROM sales WHERE store_id='S001'"
        self.assertEqual(check_sql(sql + ";"), sql)

    def test_blocks_write(self) -> None:
        for bad in (
            "DELETE FROM sales",
            "SELECT 1; DROP TABLE sales",
            "UPDATE sales SET qty=0",
            "SELECT * FROM sqlite_master",
            "SELECT * FROM sales -- comment",
        ):
            with self.subTest(sql=bad):
                with self.assertRaises(UnsafeSQL):
                    check_sql(bad)


class TestEvaluator(unittest.TestCase):
    def test_oracle_hits_all_tasks(self) -> None:
        from bench.grader import grade

        tasks = load_tasks()
        for task in tasks:
            registry = build_registry()
            trace = run(task, registry, OraclePolicy(sql=task["gold_sql"]), max_steps=3)
            verdict = grade(task, trace, ROOT / "data" / "rx.db")
            with self.subTest(task=task["id"]):
                self.assertTrue(verdict.ok, f"{task['id']} 失败：{verdict.reason}")

    def test_mutation_attribution(self) -> None:
        cases = mutation_suite(load_tasks()[0])
        misses = [c for c in cases if not c["hit"]]
        self.assertEqual(misses, [], f"归因失败：{misses}")

    def test_strict_and_lax_grading_differ_only_on_process(self) -> None:
        """同一份轨迹：严格判定失败，宽松判定通过。差值就是越界的代价。"""
        from bench.grader import grade, gold_scalar

        task = load_tasks()[0]
        db = ROOT / "data" / "rx.db"
        gold = gold_scalar(db, task["gold_sql"])
        trace = Trace(
            task_id=task["id"],
            steps=[
                Step(
                    0,
                    "先看有哪些表",
                    ToolCall("sql", {"sql": "SELECT name FROM sqlite_master"}),
                    Observation("sql", False, "blocked", {"error": "unsafe_sql"}),
                ),
                Step(
                    1,
                    "正常查询",
                    ToolCall("sql", {"sql": task["gold_sql"]}),
                    Observation("sql", True, f'{{"columns":["v"],"rows":[[{gold}]]}}'),
                ),
            ],
            answer=f"答案：{gold}",
            stop_reason="answered",
        )

        strict = grade(task, trace, db, strict=True)
        lax = grade(task, trace, db, strict=False)
        self.assertFalse(strict.ok)
        self.assertEqual(strict.reason, "unsafe_sql")
        self.assertTrue(lax.ok, f"宽松判定应当只看最终答案，实际：{lax.reason}")


class TestAnswerExtraction(unittest.TestCase):
    """评测器最容易被忽略的缺陷：把答对记成答错。"""

    def test_explicit_marker_wins(self) -> None:
        from bench.grader import extract_answer

        for text in ("答案：1234", "答案: 1,234 盒", "先查了 sales 表，答案：1234"):
            with self.subTest(text=text):
                ex = extract_answer(text)
                self.assertEqual(ex.method, "explicit")
                self.assertEqual(ex.value, 1234.0)

    def test_never_silently_wrong(self) -> None:
        """多个数字且无标记时，必须暴露歧义，不能猜错。"""
        from bench.grader import extract_answer

        for text in (
            "2026 年 9 月共 1234 盒",
            "降压片 20mg 在 2026 年 9 月销量 1234 盒",
            "P001（20mg 规格）9 月销量 1234 盒",
        ):
            with self.subTest(text=text):
                ex = extract_answer(text)
                self.assertEqual(ex.method, "ambiguous")
                self.assertIsNone(ex.value)


class TestCoverageSuites(unittest.TestCase):
    """工程属性实测组本身也要有回归保护，否则它会悄悄失效。"""

    def test_guard_blocks_everything_and_keeps_data_intact(self) -> None:
        from bench.coverage import guard_suite

        result = guard_suite()
        self.assertEqual(result["blocked"], result["total"], "有越权 SQL 未被拒绝")
        self.assertEqual(result["data_intact"], result["total"], "护栏执行后数据被改动")

    def test_guard_does_not_block_legit_queries(self) -> None:
        from bench.coverage import guard_suite

        result = guard_suite()
        self.assertEqual(
            result["false_positive_passed"],
            result["false_positive_total"],
            "合法查询被护栏误杀",
        )

    def test_budget_controls(self) -> None:
        from bench.coverage import budget_suite

        for case in budget_suite():
            with self.subTest(case=case["case"]):
                self.assertTrue(case["ok"], f"{case['case']} 未按预期：{case['got']}")

    def test_evaluator_not_fooled_by_equivalent_sql(self) -> None:
        from bench.coverage import equivalence_suite

        result = equivalence_suite()
        self.assertEqual(
            result["graded_pass"], result["total"], "等价写法被评测器判错"
        )


if __name__ == "__main__":
    unittest.main()
