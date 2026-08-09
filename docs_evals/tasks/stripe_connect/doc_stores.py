"""Arm-scoped doc stores for Stripe Connect task A/B."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Tuple

TARGET_PATH = "/v1/accounts"
CONNECT_ARM_A_SLUGS = (
    "connect-quickstart.md",
    "control-guide.md",
)


def load_arm_pages(arm_root: Path, *, include: Tuple[str, ...] | None = None) -> Dict[str, str]:
    pages: Dict[str, str] = {}
    if not arm_root.is_dir():
        return pages
    for path in sorted(arm_root.rglob("*.md")):
        rel = path.relative_to(arm_root).as_posix()
        if include and rel not in include and path.name not in include:
            continue
        slug = rel.replace(".md", "")
        pages[slug] = path.read_text(encoding="utf-8", errors="replace")
    return pages


class ArmDocStore:
    def __init__(self, arm: str, control_root: Path, treatment_root: Path):
        self.arm = arm
        if arm == "A":
            self.pages = load_arm_pages(control_root, include=CONNECT_ARM_A_SLUGS)
            if not any("/v1/accounts" in t for t in self.pages.values()):
                qs = treatment_root / "connect-quickstart.md"
                if qs.is_file():
                    self.pages["connect-quickstart"] = qs.read_text(encoding="utf-8")
        else:
            self.pages = {
                p.stem: p.read_text(encoding="utf-8", errors="replace")
                for p in sorted(treatment_root.glob("connect-*.md"))
            }

    def list_pages(self) -> List[str]:
        return sorted(self.pages)

    def search(self, query: str, *, limit: int = 5) -> List[Dict[str, str]]:
        terms = [t for t in re.split(r"\s+", query.lower()) if len(t) > 2]
        scored: List[Tuple[int, str, str]] = []
        for slug, text in self.pages.items():
            hay = (slug + " " + text).lower()
            score = sum(hay.count(t) for t in terms)
            if "/v1/accounts" in hay:
                score += 50
            if "controller" in hay:
                score += 20
            if score:
                scored.append((score, slug, text[:2500]))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {"id": slug, "score": str(score), "snippet": snippet}
            for score, slug, snippet in scored[:limit]
        ]

    def get(self, page_id: str) -> str:
        pid = page_id.replace(".md", "").lstrip("/")
        if pid in self.pages:
            return self.pages[pid][:12000]
        for slug, text in self.pages.items():
            if slug.endswith(pid) or pid.endswith(slug):
                return text[:12000]
        return f"NOT FOUND in arm {self.arm}: {page_id}"
