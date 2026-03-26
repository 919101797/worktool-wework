"""
AXUIElement Core for macOS Accessibility
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any

import ApplicationServices as AppSvc  # type: ignore[import-untyped]
from ApplicationServices import (  # type: ignore[import-untyped]
    AXIsProcessTrusted,
    kAXErrorSuccess,
)

logger = logging.getLogger(__name__)


def check_accessibility_permission() -> bool:
    return bool(AXIsProcessTrusted())


@dataclass
class Rect:
    x: int
    y: int
    w: int
    h: int


def ax_attr(element: Any, name: str, default: Any = None) -> Any:
    try:
        err, value = AppSvc.AXUIElementCopyAttributeValue(element, name, None)
        if err == kAXErrorSuccess and value is not None:
            return value
    except Exception:
        pass
    return default


def ax_rect(element: Any) -> Rect | None:
    pos_val = ax_attr(element, "AXPosition")
    size_val = ax_attr(element, "AXSize")
    if pos_val is None or size_val is None:
        return None

    pos_ok, pos = AppSvc.AXValueGetValue(pos_val, AppSvc.kAXValueCGPointType, None)
    size_ok, size = AppSvc.AXValueGetValue(size_val, AppSvc.kAXValueCGSizeType, None)

    if not pos_ok or not size_ok:
        return None

    return Rect(
        x=math.floor(pos.x),
        y=math.floor(pos.y),
        w=math.floor(size.width),
        h=math.floor(size.height),
    )


def walk(
    element: Any,
    depth: int,
    fn: Any,
    visited: set | None = None,
    max_depth: int = 10,
    max_children: int = 160,
) -> Any | None:
    if visited is None:
        visited = set()
    if element is None or depth > max_depth:
        return None

    element_id = id(element)
    if element_id in visited:
        return None
    visited.add(element_id)

    result = fn(element, depth)
    if result is not None:
        return result

    children = ax_attr(element, "AXChildren", [])
    if not children:
        return None

    for i in range(min(len(children), max_children)):
        found = walk(children[i], depth + 1, fn, visited, max_depth, max_children)
        if found is not None:
            return found

    return None


def collect(element: Any, fn: Any) -> list:
    out: list = []

    def collector(el: Any, depth: int) -> None:
        item = fn(el, depth)
        if item is not None:
            out.append(item)
        return None

    walk(element, 0, collector)
    return out


def find_left_table(win: Any) -> Any | None:
    win_rect = ax_rect(win)
    if win_rect is None:
        return None

    def matcher(el: Any, _depth: int) -> Any | None:
        role = ax_attr(el, "AXRole", "")
        rect = ax_rect(el)
        if rect is None or role != "AXTable":
            return None
        dx = rect.x - win_rect.x
        if 350 <= rect.w <= 500 and 0 <= dx <= 80:
            return el
        return None

    return walk(win, 0, matcher)


def find_bottom_input(win: Any) -> Any | None:
    win_rect = ax_rect(win)
    if win_rect is None:
        return None

    candidates = collect(win, lambda el, _: _match_bottom_input(el, win_rect))
    candidates.sort(key=lambda c: (-c["rect"].y, -c["area"]))
    return candidates[0]["el"] if candidates else None


def _match_bottom_input(el: Any, win_rect: Rect) -> dict | None:
    role = ax_attr(el, "AXRole", "")
    rect = ax_rect(el)
    if rect is None:
        return None
    dy = rect.y - win_rect.y
    if (
        role in ("AXTextField", "AXTextArea")
        and rect.w >= 450
        and rect.h >= 120
        and dy >= math.floor(win_rect.h * 0.55)
    ):
        return {"el": el, "rect": rect, "area": rect.w * rect.h}
    return None


def current_conversation(win: Any) -> str | None:
    win_rect = ax_rect(win)
    if win_rect is None:
        return None

    titles = collect(win, lambda el, _: _match_title(el, win_rect))
    titles.sort(key=lambda t: (t["rect"].y, t["rect"].x))
    return titles[0]["value"] if titles else None


def _match_title(el: Any, win_rect: Rect) -> dict | None:
    role = ax_attr(el, "AXRole", "")
    value = str(ax_attr(el, "AXValue", "") or "")
    rect = ax_rect(el)
    if rect is None or not value:
        return None
    dy = rect.y - win_rect.y
    dx = rect.x - win_rect.x
    if (
        role in ("AXStaticText", "AXTextField")
        and 0 <= dy <= 80
        and 380 <= dx <= win_rect.w - 200
        and 40 <= rect.w <= 260
        and 18 <= rect.h <= 40
    ):
        return {"value": value, "rect": rect}
    return None


def collect_row_texts(row: Any) -> list[str]:
    texts: list[str] = []

    def extractor(el: Any, _depth: int) -> None:
        role = ax_attr(el, "AXRole", "")
        if role not in ("AXStaticText", "AXTextField", "AXTextArea", "AXButton"):
            return None
        title = str(ax_attr(el, "AXTitle", "") or "")
        value = str(ax_attr(el, "AXValue", "") or "")
        if title:
            texts.append(title)
        if value:
            texts.append(value)
        return None

    walk(row, 0, extractor)
    return texts


def get_rows(win: Any) -> list | None:
    table_el = find_left_table(win)
    if table_el is None:
        return None
    return ax_attr(table_el, "AXRows", [])


def find_row_by_title(win: Any, title: str) -> tuple[Any, int | None, list[str]]:
    rows = get_rows(win)
    if not rows:
        return None, None, []

    for i, row in enumerate(rows):
        texts = collect_row_texts(row)
        if texts and texts[0] == title:
            return row, i + 1, texts

    return None, None, []
