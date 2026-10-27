"""只读 SQL 工具 + 护栏。

业务数据场景下真正需要守的是"不可写 + 限定表白名单 + 禁止多语句"，
用 SQL 静态校验就够了，不必上容器沙箱——这是本项目最主要的工程取舍。
`reports/coverage.md` 里有一组对照实验，量化了它挡得住什么、又误杀了什么。
"""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from harness.types import Observation

ALLOWED_TABLES = {"stores", "products", "sales", "inventory", "targets"}
BLOCKED = re.compile(
    r"\b(insert|update|delete|drop|alter|attach|detach|pragma|vacuum|create|replace)\b", re.I
)
TABLE_REF = re.compile(r"\b(?:from|join)\s+([A-Za-z_][A-Za-z0-9_]*)", re.I)
MAX_ROWS = 200


class UnsafeSQL(ValueError):
    pass


def check_sql(sql: str) -> str:
    stripped = sql.strip().rstrip(";").strip()
    if not stripped:
        raise UnsafeSQL("空语句")
    if not re.match(r"^(select|with)\b", stripped, re.I):
        raise UnsafeSQL("只允许 SELECT / WITH 查询")
    if ";" in stripped:
        raise UnsafeSQL("禁止多语句")
    if "--" in stripped or "/*" in stripped:
        raise UnsafeSQL("禁止注释符")
    if BLOCKED.search(stripped):
        raise UnsafeSQL("包含写操作关键字")
    for table in TABLE_REF.findall(stripped):
        if table.lower() not in ALLOWED_TABLES:
            raise UnsafeSQL(f"表 {table} 不在允许清单内")
    return stripped


def make_sql_tool(db_path: str | Path):
    db_uri = f"file:{Path(db_path).as_posix()}?mode=ro"

    def _run(args: dict) -> Observation:
        sql = str(args.get("sql", ""))
        try:
            safe = check_sql(sql)
        except UnsafeSQL as exc:
            return Observation(
                tool="sql", ok=False, content=f"SQL 被拒绝：{exc}", meta={"error": "unsafe_sql"}
            )
        conn = sqlite3.connect(db_uri, uri=True)
        try:
            cur = conn.execute(safe)
            rows = cur.fetchmany(MAX_ROWS)
            columns = [d[0] for d in (cur.description or [])]
        except sqlite3.Error as exc:
            # 猜错列名是最常见的模型失败方式。早期实现让它直接抛出，
            # 结果是整轮评测中断、grader 里的 tool_error 永远归因为 0。
            # 把它收敛成一条 Observation，失败才可被归因、进而可被进化修复。
            return Observation(
                tool="sql",
                ok=False,
                content=f"SQL 执行失败：{exc}",
                meta={"error": "tool_error", "detail": str(exc), "sql": safe},
            )
        finally:
            conn.close()
        return Observation(
            tool="sql",
            ok=True,
            content=json.dumps({"columns": columns, "rows": rows}, ensure_ascii=False, default=str),
            meta={"rows": len(rows), "sql": safe},
        )

    return _run
