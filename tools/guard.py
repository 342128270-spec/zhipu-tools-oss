"""guard —— 自建内容安全，替代 /paas/v4/moderations
规则 + 可选模型。默认规则表可在 rules.json 覆盖。
"""
import json, os, re
from pathlib import Path

DEFAULT = {
    "politics": ["敏感政治词示例"],
    "violence": ["杀人", "爆炸物制作", "恐怖袭击"],
    "porn": ["色情", "裸照"],
    "illegal": ["毒品交易", "枪支买卖"],
}
_rules_path = Path(os.environ.get("ZT_DATA", Path.home() / ".zhipu-tools")).expanduser() / "rules.json"


def _rules():
    if _rules_path.exists():
        try:
            return json.loads(_rules_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return DEFAULT


def moderate(text):
    hits = []
    for cat, words in _rules().items():
        for w in words:
            if w and w in text:
                hits.append({"category": cat, "keyword": w})
    return {
        "flagged": bool(hits),
        "categories": sorted({h["category"] for h in hits}),
        "hits": hits,
    }
