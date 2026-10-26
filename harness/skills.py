"""Skill 加载。

只做一件事：把领域约束（口径、枚举值、join 键）以 `SKILL.md` 的声明式形式注入上下文。
这是整个项目投入最小、收益最高的一层——不改代码就能修正口径错误，
而且换业务域时只换 Markdown，不动 runtime。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Skill:
    name: str
    when: str
    body: str
    path: Path


def load_skills(root: str | Path) -> dict[str, Skill]:
    root = Path(root)
    skills: dict[str, Skill] = {}
    for path in sorted(root.glob("*/SKILL.md")):
        meta: dict[str, str] = {}
        lines = path.read_text(encoding="utf-8").splitlines()
        i = 0
        while i < len(lines) and lines[i].strip():
            if ":" in lines[i]:
                key, _, value = lines[i].partition(":")
                meta[key.strip()] = value.strip()
            i += 1
        body = "\n".join(lines[i:]).strip()
        name = meta.get("name", path.parent.name)
        skills[name] = Skill(name=name, when=meta.get("when", ""), body=body, path=path)
    return skills


def render_for_prompt(skills: dict[str, Skill], active: list[str] | None = None) -> str:
    """只注入当前任务相关的 skill，避免上下文里塞满无关业务规则。"""
    if active is None:
        active = list(skills)
    chunks = []
    for name in active:
        skill = skills.get(name)
        if skill is None:
            continue
        chunks.append(f"### {skill.name}\n适用场景：{skill.when}\n{skill.body}")
    return "\n\n".join(chunks)
