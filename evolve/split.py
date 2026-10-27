"""dev / holdout 分层划分。

没有留出集的"自进化"无法被证伪：任何补丁都能把 dev 刷到 100%，
而刷满的可能是记忆，不是能力。所以这里先做一件事——把 60 条题切成两半，
进化只能看 dev，holdout 只用来观测。

分层键是 (level, expect)：L1~L4 四层 + answer/clarify 两种正确形态，
保证两半的难度构成一致，否则"提升"可能只是切分偶然。
划分结果冻结到 bench/splits.json，种子写死，任何人重跑都得到同一份切分。
"""
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SPLIT_PATH = ROOT / "bench" / "splits.json"
SEED = 20261027


def stratified_split(
    tasks: list[dict[str, Any]],
    holdout_ratio: float = 0.5,
    seed: int = SEED,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rng = random.Random(seed)
    buckets: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for task in tasks:
        key = (str(task.get("level", "?")), str(task.get("expect", "answer")))
        buckets.setdefault(key, []).append(task)

    dev: list[dict[str, Any]] = []
    holdout: list[dict[str, Any]] = []
    for key in sorted(buckets):
        group = sorted(buckets[key], key=lambda t: str(t["id"]))
        rng.shuffle(group)
        n_hold = max(1, round(len(group) * holdout_ratio))
        n_hold = min(n_hold, len(group) - 1) if len(group) > 1 else 0
        holdout.extend(group[:n_hold])
        dev.extend(group[n_hold:])

    return sorted(dev, key=lambda t: str(t["id"])), sorted(holdout, key=lambda t: str(t["id"]))


def write_split(dev: list[dict[str, Any]], holdout: list[dict[str, Any]], path: Path = SPLIT_PATH) -> Path:
    payload = {
        "seed": SEED,
        "dev": [t["id"] for t in dev],
        "holdout": [t["id"] for t in holdout],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_split(tasks: list[dict[str, Any]], path: Path = SPLIT_PATH) -> tuple[list, list]:
    """优先读冻结文件；缺失时现切一份并落盘。"""
    if not path.exists():
        dev, holdout = stratified_split(tasks)
        write_split(dev, holdout, path)
        return dev, holdout
    payload = json.loads(path.read_text(encoding="utf-8"))
    index = {str(t["id"]): t for t in tasks}
    dev = [index[i] for i in payload["dev"] if i in index]
    holdout = [index[i] for i in payload["holdout"] if i in index]
    return dev, holdout
