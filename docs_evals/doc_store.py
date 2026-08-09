"""Markdown corpus doc store for question eval and task A/B."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


def load_pages_from_dirs(prefixes: Iterable[tuple[str, Path]]) -> Dict[str, str]:
    pages: Dict[str, str] = {}
    for prefix, base in prefixes:
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.md")):
            if path.name.lower() == "readme.md":
                continue
            rel = path.relative_to(base).as_posix()
            key = f"{prefix}/{rel}".replace(".md", "")
            pages[key] = path.read_text(encoding="utf-8", errors="replace")
    return pages


class MarkdownDocStore:
    def __init__(self, pages: Dict[str, str]):
        self.pages = pages

    @classmethod
    def from_roots(cls, *roots: tuple[str, Path]) -> MarkdownDocStore:
        return cls(load_pages_from_dirs(roots))

    def search(self, query: str, *, limit: int = 5) -> List[Dict[str, str]]:
        terms = [t for t in re.split(r"\s+", query.lower()) if len(t) > 2]
        scored: List[Tuple[int, str, str]] = []
        for slug, text in self.pages.items():
            hay = (slug + " " + text).lower()
            score = sum(hay.count(t) for t in terms)
            if score:
                scored.append((score, slug, text[:2000]))
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
        return ""
