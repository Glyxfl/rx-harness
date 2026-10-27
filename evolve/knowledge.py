"""知识层：SKILL.md 的读取、退化与修补。

进化只被允许改这一层。理由是评测层一旦可改，任何分数都不再可信——
`operators.py` 里的 `cheat` 分支会用一次改动把这件事演示出来：
改 gold SQL 能让 dev 立刻满分，但那条"进化"没有任何意义。

本模块只做四件事：读、判声明、造缺口、追加补丁。不做任何模型调用。
"""
from __future__ import annotations

import re
import shutil
import sqlite3
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / "skills"

# 缺声明时学习者的"猜测"，取真实世界里最常见的误写形式。
COLUMN_GUESS = {
    "date": "sale_date",
    "qty": "quantity",
    "amount": "sales_amount",
    "store_id": "store_code",
    "product_id": "sku_id",
    "month": "ym",
    "region": "area",
    "spec": "spec_name",
    "target_qty": "target",
    "name": "label",
}

# 门店名与片区值：中文名与编号的映射，文档里从来没写过。
STORE_NAME_TO_ID = {"城东一店": "S001", "城西二店": "S002", "城南三店": "S003"}
REGION_VALUES = ["城东", "城西", "城南"]
SPEC_MAP = {"P001": "20mg", "P002": "40mg"}


def skill_texts(skills_dir: str | Path = SKILLS_DIR) -> dict[str, str]:
    root = Path(skills_dir)
    return {
        p.parent.name: p.read_text(encoding="utf-8")
        for p in sorted(root.glob("*/SKILL.md"))
    }


def declared_text(skills_dir: str | Path = SKILLS_DIR) -> str:
    return "\n".join(skill_texts(skills_dir).values())


def column_declared(text: str, column: str) -> bool:
    return f"`{column}`" in text


def literal_declared(text: str, literal: str) -> bool:
    return literal in text


def real_schema(db_path: str | Path) -> dict[str, list[tuple[str, str]]]:
    """真实表结构。补丁的来源是库本身，不是模型猜测——这点在报告里要写明。"""
    uri = f"file:{Path(db_path).as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        tables = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        ]
        return {
            t: [(r[1], r[2] or "TEXT") for r in conn.execute(f"PRAGMA table_info({t})")]
            for t in sorted(tables)
        }
    finally:
        conn.close()


def degrade(
    src: str | Path,
    dst: str | Path,
    drop_columns: Iterable[str] = (),
    drop_literals: Iterable[str] = (),
    drop_tables: Iterable[str] = (),
) -> Path:
    """造一个"文档不全"的初始状态。

    这是自进化实验的起点：先把知识挖掉一块，再看进化能不能自己补回来。
    挖法只有两种——删掉声明某个列的行、删掉提到某个值的行——都很贴近真实情况
    （交接来的数据字典往往就是这么缺的）。
    """
    src, dst = Path(src), Path(dst)
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)

    col_res = [re.compile(rf"^\s*-\s*`{re.escape(c)}`") for c in drop_columns]
    table_res = [re.compile(rf"^##\s+{re.escape(t)}(\s|$)") for t in drop_tables]

    for path in dst.glob("*/SKILL.md"):
        kept = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if any(r.match(line) for r in col_res):
                continue
            if any(r.match(line) for r in table_res):
                continue
            if any(lit in line for lit in drop_literals):
                continue
            kept.append(line)
        path.write_text("\n".join(kept) + "\n", encoding="utf-8")
    return dst


def append_text(skills_dir: str | Path, skill: str, text: str) -> Path:
    path = Path(skills_dir) / skill / "SKILL.md"
    body = path.read_text(encoding="utf-8").rstrip("\n")
    path.write_text(f"{body}\n\n{text.strip()}\n", encoding="utf-8")
    return path


def schema_rebuild_text(schema: dict[str, list[tuple[str, str]]]) -> str:
    """按真实库结构重建整段字段清单。

    这是"类别级"补丁：一次补齐全部声明，而不是只补失败那一题用到的列。
    """
    lines = ["## 字段清单（由库结构自动重建）", ""]
    for table, cols in schema.items():
        lines.append(f"### {table}")
        for name, kind in cols:
            lines.append(f"- `{name}` {kind}")
        lines.append("")
    lines.append("以上为库中实际存在的全部列；清单外的列名一律不存在，不要臆造。")
    return "\n".join(lines)


def value_domain_text() -> str:
    """值域补丁：中文名与编号的映射。这类事实无法从库结构推出，只能查数据。"""
    lines = ["## 值域（中文名与编号的对应）", ""]
    for name, sid in STORE_NAME_TO_ID.items():
        lines.append(f"- `{name}` 对应 `store_id='{sid}'`")
    lines.append("- `stores.region` 的取值为：" + " / ".join(f"`{r}`" for r in REGION_VALUES))
    lines.append("  **不含「区」字后缀**，`region='城东'` 不是 `region='城东区'`")
    return "\n".join(lines)


def spec_rule_text() -> str:
    return (
        "## 规格必须显式指定\n\n"
        "- 降压片有 `20mg`（`P001`）和 `40mg`（`P002`）两个规格，是两个独立产品\n"
        "- 问题只写品名、没写规格时，不得自行合并两个规格求和，也不得默认取其中一个\n"
        "- 问题写了规格时，必须按 `product_id` 精确过滤到对应规格"
    )


def spec_rule_text() -> str:
    return (
        "## 规格必须显式指定\n\n"
        "- 降压片有 `20mg`（`P001`）和 `40mg`（`P002`）两个规格，是两个独立产品\n"
        "- 问题只写品名、没写规格时，不得自行合并两个规格求和，也不得默认取其中一个\n"
        "- 问题写了规格时，必须按 `product_id` 精确过滤到对应规格"
    )
