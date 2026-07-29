"""Deterministic, dependency-light table and SVG rendering."""

from __future__ import annotations

import csv
import html
import io
import math
from collections.abc import Mapping, Sequence
from typing import Any, cast


def csv_text(rows: Sequence[Mapping[str, Any]]) -> str:
    """Render dictionaries as stable UTF-8 CSV text."""
    fields = list(rows[0]) if rows else ["status"]
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows or [{"status": "no_rows"}])
    return stream.getvalue()


def markdown_text(rows: Sequence[Mapping[str, Any]]) -> str:
    """Render a compact GitHub Markdown table."""
    rendered = list(rows) or [{"status": "no_rows"}]
    fields = list(rendered[0])
    def escape(value: Any) -> str:
        return str(value).replace("|", r"\|").replace("\n", " ")

    lines = [
        "| " + " | ".join(escape(field) for field in fields) + " |",
        "| " + " | ".join("---" for _ in fields) + " |",
    ]
    lines.extend(
        "| " + " | ".join(escape(row.get(field, "")) for field in fields) + " |"
        for row in rendered
    )
    return "\n".join(lines) + "\n"


def html_text(rows: Sequence[Mapping[str, Any]]) -> str:
    """Render a standalone HTML table fragment."""
    rendered = list(rows) or [{"status": "no_rows"}]
    fields = list(rendered[0])
    head = "".join(f"<th>{html.escape(str(field))}</th>" for field in fields)
    body = "".join(
        "<tr>"
        + "".join(
            f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields
        )
        + "</tr>"
        for row in rendered
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>\n"


def latex_text(rows: Sequence[Mapping[str, Any]]) -> str:
    """Render a minimal booktabs-compatible LaTeX table."""
    rendered = list(rows) or [{"status": "no_rows"}]
    fields = list(rendered[0])

    def escape(value: Any) -> str:
        text = str(value)
        for before, after in (
            ("\\", r"\textbackslash{}"),
            ("&", r"\&"),
            ("%", r"\%"),
            ("$", r"\$"),
            ("#", r"\#"),
            ("_", r"\_"),
            ("{", r"\{"),
            ("}", r"\}"),
        ):
            text = text.replace(before, after)
        return text

    lines = [
        r"\begin{tabular}{" + "l" * len(fields) + "}",
        r"\toprule",
        " & ".join(escape(field) for field in fields) + r" \\",
        r"\midrule",
    ]
    lines.extend(
        " & ".join(escape(row.get(field, "")) for field in fields) + r" \\"
        for row in rendered
    )
    lines.extend([r"\bottomrule", r"\end{tabular}", ""])
    return "\n".join(lines)


def svg_chart(
    title: str,
    rows: Sequence[Mapping[str, Any]],
    *,
    label_key: str,
    value_key: str,
    secondary_key: str | None = None,
) -> str:
    """Render a deterministic bar/interval SVG without a plotting dependency."""
    usable: list[tuple[str, float, float | None]] = []
    for row in rows[:30]:
        try:
            value = float(row[value_key])
            secondary = (
                float(row[secondary_key])
                if secondary_key is not None and row.get(secondary_key) not in (None, "")
                else None
            )
        except (KeyError, TypeError, ValueError):
            continue
        if math.isfinite(value) and (secondary is None or math.isfinite(secondary)):
            usable.append((str(row.get(label_key, "")), value, secondary))
    width, height = 1000, max(360, 92 + 28 * max(1, len(usable)))
    values = [abs(value) for _, value, _ in usable]
    values.extend(abs(item) for _, _, item in usable if item is not None)
    scale = 720 / max(values or [1.0])
    zero_x = 180
    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="28" y="38" font-family="sans-serif" font-size="22" '
        f'font-weight="600">{html.escape(title)}</text>',
        f'<line x1="{zero_x}" y1="58" x2="{zero_x}" y2="{height - 30}" '
        'stroke="#64748b" stroke-width="1"/>',
    ]
    for index, (label, value, secondary) in enumerate(usable):
        y = 72 + index * 28
        bar_width = abs(value) * scale
        x = zero_x if value >= 0 else zero_x - bar_width
        elements.extend(
            [
                f'<text x="12" y="{y + 12}" font-family="sans-serif" font-size="11">'
                f"{html.escape(label[:27])}</text>",
                f'<rect x="{x:.3f}" y="{y}" width="{bar_width:.3f}" height="13" '
                'fill="#2563eb" opacity="0.82"/>',
                f'<text x="{max(zero_x + 4, x + bar_width + 5):.3f}" y="{y + 11}" '
                f'font-family="monospace" font-size="10">{value:.6g}</text>',
            ]
        )
        if secondary is not None:
            secondary_width = abs(secondary) * scale
            secondary_x = zero_x if secondary >= 0 else zero_x - secondary_width
            elements.append(
                f'<rect x="{secondary_x:.3f}" y="{y + 14}" '
                f'width="{secondary_width:.3f}" height="5" fill="#dc2626" opacity="0.68"/>'
            )
    if not usable:
        elements.append(
            '<text x="28" y="100" font-family="sans-serif" font-size="14">'
            "No finite source rows.</text>"
        )
    elements.append("</svg>\n")
    return "\n".join(elements)


def svg_line_chart(
    title: str,
    rows: Sequence[Mapping[str, Any]],
    *,
    value_key: str,
    secondary_key: str | None = None,
) -> str:
    """Render one or two ordered numeric series as a deterministic SVG."""
    usable: list[tuple[float, float | None]] = []
    for row in rows:
        try:
            value = float(row[value_key])
            secondary = (
                float(row[secondary_key])
                if secondary_key is not None
                and row.get(secondary_key) not in (None, "")
                else None
            )
        except (KeyError, TypeError, ValueError):
            continue
        if math.isfinite(value) and (secondary is None or math.isfinite(secondary)):
            usable.append((value, secondary))
    if len(usable) > 240:
        step = math.ceil(len(usable) / 240)
        usable = usable[::step]
    width, height = 1000, 440
    plot_left, plot_top, plot_width, plot_height = 76, 70, 884, 310
    primary_values = [value for value, _ in usable]
    secondary_values = [item for _, item in usable if item is not None]
    minimum = min(primary_values or [0.0])
    maximum = max(primary_values or [1.0])
    span = maximum - minimum or 1.0
    secondary_minimum = min(secondary_values or [0.0])
    secondary_maximum = max(secondary_values or [1.0])
    secondary_span = secondary_maximum - secondary_minimum or 1.0

    def points(index: int) -> str:
        selected = [
            float(cast(float, value if index == 0 else secondary))
            for value, secondary in usable
            if index == 0 or secondary is not None
        ]
        count = max(1, len(selected) - 1)
        series_maximum = maximum if index == 0 else secondary_maximum
        series_span = span if index == 0 else secondary_span
        return " ".join(
            f"{plot_left + position * plot_width / count:.2f},"
            f"{plot_top + (series_maximum - value) * plot_height / series_span:.2f}"
            for position, value in enumerate(selected)
        )

    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="28" y="38" font-family="sans-serif" font-size="22" '
        f'font-weight="600">{html.escape(title)}</text>',
        f'<rect x="{plot_left}" y="{plot_top}" width="{plot_width}" '
        f'height="{plot_height}" fill="none" stroke="#94a3b8"/>',
        f'<text x="8" y="{plot_top + 10}" font-family="monospace" '
        f'font-size="10">{maximum:.6g}</text>',
        f'<text x="8" y="{plot_top + plot_height}" font-family="monospace" '
        f'font-size="10">{minimum:.6g}</text>',
    ]
    if usable:
        elements.append(
            f'<polyline points="{points(0)}" fill="none" stroke="#2563eb" '
            'stroke-width="2"/>'
        )
        if secondary_key is not None and any(item is not None for _, item in usable):
            elements.extend(
                [
                    f'<polyline points="{points(1)}" fill="none" stroke="#dc2626" '
                    'stroke-width="1.5"/>',
                    f'<text x="965" y="{plot_top + 10}" font-family="monospace" '
                    f'font-size="10" fill="#dc2626">{secondary_maximum:.6g}</text>',
                    f'<text x="965" y="{plot_top + plot_height}" font-family="monospace" '
                    f'font-size="10" fill="#dc2626">{secondary_minimum:.6g}</text>',
                ]
            )
    else:
        elements.append(
            '<text x="90" y="110" font-family="sans-serif" font-size="14">'
            "No finite source rows.</text>"
        )
    elements.append("</svg>\n")
    return "\n".join(elements)
