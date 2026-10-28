"""Shared bounding-box geometry. Used by ai_perception's tracker/matcher and
available to any other layer that needs to reason about (x, y, w, h) boxes
without pulling in a full CV dependency."""
from __future__ import annotations


def iou(a, b) -> float:
    """Intersection-over-union of two (x, y, w, h) boxes."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    x1, y1 = max(ax, bx), max(ay, by)
    x2, y2 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    union = aw * ah + bw * bh - inter
    return inter / union if union else 0.0


def center(box):
    x, y, w, h = box
    return x + w / 2.0, y + h / 2.0
