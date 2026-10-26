"""入库前的密钥自检：仓库里不允许出现任何真实凭证。

这条测试存在的理由很具体——本项目的评测需要接真实模型，很容易顺手把 key
写进 `cli.py`、报告或 `.env` 再提交。检查成本极低，漏一次代价极高。

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", ".mypy_cache"}

# 真实凭证的特征形态。注意 `sk-xxx` 这类占位符长度不足，不会误报。
SECRET_PATTERNS = {
    "OpenAI/DeepSeek 风格 key": re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    "GitHub token": re.compile(r"\b(ghp|gho|ghu|ghs)_[A-Za-z0-9]{20,}\b"),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "私钥块": re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}

TEXT_SUFFIXES = {".py", ".md", ".json", ".jsonl", ".toml", ".cfg", ".ini", ".txt", ".yml", ".yaml", ""}


def _iter_text_files() -> list[Path]:
    files = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in TEXT_SUFFIXES:
            files.append(path)
    return files


class TestNoSecrets(unittest.TestCase):
    def test_no_credential_shaped_strings(self) -> None:
        hits = []
        for path in _iter_text_files():
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for label, pattern in SECRET_PATTERNS.items():
                for match in pattern.finditer(text):
                    snippet = match.group(0)
                    masked = snippet[:6] + "…" if len(snippet) > 6 else snippet
                    hits.append(f"{path.relative_to(ROOT)}: {label} ({masked})")
        self.assertEqual(hits, [], "发现疑似真实凭证，请改为环境变量：\n" + "\n".join(hits))

    def test_no_dotenv_committed(self) -> None:
        leaking = [
            str(p.relative_to(ROOT))
            for p in ROOT.rglob(".env*")
            if p.is_file() and not any(part in SKIP_DIRS for part in p.parts)
        ]
        self.assertEqual(leaking, [], f".env 不应入库：{leaking}")


if __name__ == "__main__":
    unittest.main()
