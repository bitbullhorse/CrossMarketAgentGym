"""Dependency-free deterministic SVG figures for CPU quickstarts."""

from __future__ import annotations

import math
from pathlib import Path
from xml.sax.saxutils import escape


def write_bar_chart(
    path: Path,
    *,
    title: str,
    y_label: str,
    values: list[tuple[str, float | None]],
    color: str = "#2563eb",
) -> None:
    """Write an accessible SVG bar chart, preserving missing values explicitly."""
    width = 900
    height = 460
    left = 90
    top = 65
    bottom = 105
    chart_width = width - left - 35
    chart_height = height - top - bottom
    finite = [value for _, value in values if value is not None and math.isfinite(value)]
    lower = min(0.0, min(finite, default=0.0))
    upper = max(0.0, max(finite, default=0.0))
    if upper - lower <= 1e-12:
        upper = 1.0
        lower = 0.0
    span = upper - lower

    def y_coordinate(value: float) -> float:
        return top + (upper - value) / span * chart_height

    zero_y = y_coordinate(0.0)
    count = max(1, len(values))
    slot = chart_width / count
    bar_width = slot * 0.58
    elements = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">'
        ),
        f'<title id="title">{escape(title)}</title>',
        f'<desc id="desc">{escape(y_label)} by run; missing values are marked N/A.</desc>',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        (
            f'<text x="{width / 2:.1f}" y="32" text-anchor="middle" '
            f'font-family="sans-serif" font-size="20" font-weight="600">{escape(title)}</text>'
        ),
        (
            f'<line x1="{left}" y1="{zero_y:.2f}" x2="{left + chart_width}" '
            f'y2="{zero_y:.2f}" stroke="#334155" stroke-width="1.5"/>'
        ),
        (
            f'<text x="18" y="{top + chart_height / 2:.1f}" '
            'transform="rotate(-90 18 210)" font-family="sans-serif" font-size="13" '
            f'text-anchor="middle">{escape(y_label)}</text>'
        ),
    ]
    for index in range(5):
        tick_value = lower + span * index / 4
        y = y_coordinate(tick_value)
        elements.extend(
            (
                (
                    f'<line x1="{left}" y1="{y:.2f}" x2="{left + chart_width}" y2="{y:.2f}" '
                    'stroke="#e2e8f0" stroke-width="1"/>'
                ),
                (
                    f'<text x="{left - 8}" y="{y + 4:.2f}" text-anchor="end" '
                    f'font-family="monospace" font-size="11">{tick_value:.4g}</text>'
                ),
            )
        )
    for index, (label, value) in enumerate(values):
        x = left + slot * index + (slot - bar_width) / 2
        if value is None or not math.isfinite(value):
            bar_height = 0.0
            y = zero_y
            display = "N/A"
        else:
            value_y = y_coordinate(value)
            y = min(zero_y, value_y)
            bar_height = abs(value_y - zero_y)
            display = f"{value:.5g}"
        elements.extend(
            (
                (
                    f'<rect x="{x:.2f}" y="{y:.2f}" width="{bar_width:.2f}" '
                    f'height="{bar_height:.2f}" fill="{color}" rx="2"/>'
                ),
                (
                    f'<text x="{x + bar_width / 2:.2f}" y="{max(top + 12, y - 7):.2f}" '
                    f'text-anchor="middle" font-family="monospace" font-size="11">{display}</text>'
                ),
                (
                    f'<text x="{x + bar_width / 2:.2f}" y="{top + chart_height + 24}" '
                    f'text-anchor="end" transform="rotate(-30 {x + bar_width / 2:.2f} '
                    f'{top + chart_height + 24})" font-family="sans-serif" font-size="11">'
                    f"{escape(label)}</text>"
                ),
            )
        )
    elements.append("</svg>")
    path.write_text("\n".join(elements) + "\n", encoding="utf-8")
