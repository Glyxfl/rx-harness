"""生成评测用的合成业务库（全部为随机生成的演示数据，不含任何真实企业信息）。

刻意保留零售业务里最常见的三个坑：
  1. 同产品多规格（降压片 20mg / 40mg），天然产生"规格歧义"
  2. 销量表与库存表口径不同（按天 vs 快照）
  3. 目标表按月聚合，需要跨表 join 才能算完成率，且库里有两个月
"""
from __future__ import annotations

import random
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "rx.db"

# 门店与产品均为虚构名称，region 故意用两字枚举值（与口语的"XX 区"不相等），
# 保留"枚举值猜测"这个真实坑
STORES = [
    ("S001", "城东一店", "城东"),
    ("S002", "城西二店", "城西"),
    ("S003", "城南三店", "城南"),
]

PRODUCTS = [
    ("P001", "降压片", "20mg"),
    ("P002", "降压片", "40mg"),
    ("P003", "止咳糖浆", "10ml"),
    ("P004", "感冒颗粒", "12袋"),
]

PRICE = {"P001": 38.5, "P002": 62.0, "P003": 21.0, "P004": 15.8}
DATES = [f"2026-09-{d:02d}" for d in range(1, 11)]
AUG_DATES = [f"2026-08-{d:02d}" for d in range(20, 32)]
MONTHS = ("2026-08", "2026-09")

SCHEMA = """
CREATE TABLE stores(store_id TEXT PRIMARY KEY, name TEXT NOT NULL, region TEXT NOT NULL);
CREATE TABLE products(product_id TEXT PRIMARY KEY, name TEXT NOT NULL, spec TEXT NOT NULL);
CREATE TABLE sales(date TEXT NOT NULL, store_id TEXT NOT NULL,
                   product_id TEXT NOT NULL, qty INTEGER NOT NULL, amount REAL NOT NULL);
CREATE TABLE inventory(date TEXT NOT NULL, store_id TEXT NOT NULL,
                       product_id TEXT NOT NULL, qty INTEGER NOT NULL);
CREATE TABLE targets(month TEXT NOT NULL, store_id TEXT NOT NULL,
                     product_id TEXT NOT NULL, target_qty INTEGER NOT NULL);
"""

COMMENTS = {
    "stores": "门店维度表，region 为片区枚举值",
    "products": "产品维度表，同一 name 可能有多个 spec",
    "sales": "日粒度销量流水，qty 为盒数，amount 为金额",
    "inventory": "日末库存快照，仅 2026-09-10 有值",
    "targets": "月度目标，粒度为 月 × 门店 × 产品",
}


def build(path: Path = DB_PATH, seed: int = 42) -> Path:
    if path.exists():
        path.unlink()
    rng = random.Random(seed)
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)

    conn.executemany("INSERT INTO stores VALUES (?,?,?)", STORES)
    conn.executemany("INSERT INTO products VALUES (?,?,?)", PRODUCTS)

    rows = []
    for date in AUG_DATES + DATES:
        for store_id, _, _ in STORES:
            for product_id, _, _ in PRODUCTS:
                qty = rng.randint(8, 90)
                rows.append((date, store_id, product_id, qty, round(qty * PRICE[product_id], 2)))
    conn.executemany("INSERT INTO sales VALUES (?,?,?,?,?)", rows)

    conn.executemany(
        "INSERT INTO inventory VALUES ('2026-09-10',?,?,?)",
        [(s, p, rng.randint(15, 260)) for s, _, _ in STORES for p, _, _ in PRODUCTS],
    )
    # 两个月份的目标：故意留下"忘记过滤月份就重复计数"的坑
    conn.executemany(
        "INSERT INTO targets VALUES (?,?,?,?)",
        [
            (month, s, p, rng.randint(120, 620))
            for month in MONTHS
            for s, _, _ in STORES
            for p, _, _ in PRODUCTS
        ],
    )

    for table, comment in COMMENTS.items():
        conn.executescript(
            f"CREATE TABLE IF NOT EXISTS _meta_{table}(note TEXT); "
            f"INSERT INTO _meta_{table} VALUES ('{comment}');"
        )
    conn.commit()
    conn.close()
    return path


if __name__ == "__main__":
    out = build()
    print(f"built {out}")
