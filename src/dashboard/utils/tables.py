"""Display helpers: null-safe heatmap tables and formatted Excel export."""
from __future__ import annotations

import pandas as pd

from src.utils.excel import to_excel_bytes  # noqa: F401  (re-exported for the dashboard pages)

DASH = "—"
# matplotlib's RdYlGn stops, interpolated here so the dashboard needs no matplotlib
_RDYLGN = ["#a50026", "#d73027", "#f46d43", "#fdae61", "#fee08b", "#ffffbf", "#d9ef8b", "#a6d96a", "#66bd63", "#1a9850", "#006837"]


def _rgb(h: str) -> tuple[float, float, float]:
    return tuple(int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))  # type: ignore[return-value]


def rdylgn(x: float) -> tuple[float, float, float]:
    """RGB (0-1) on the red-yellow-green scale for x in [0, 1]."""
    x = min(max(x, 0.0), 1.0) * (len(_RDYLGN) - 1)
    i = min(int(x), len(_RDYLGN) - 2)
    f = x - i
    a, b = _rgb(_RDYLGN[i]), _rgb(_RDYLGN[i + 1])
    return tuple(a[k] + (b[k] - a[k]) * f for k in range(3))  # type: ignore[return-value]


def _hex(rgb: tuple[float, float, float]) -> str:
    return "#" + "".join(f"{round(c * 255):02x}" for c in rgb)


def heatmap_table(values: pd.DataFrame, vmin: float = 0, vmax: float = 100, nd: int = 0):
    """Styler with a colour scale where null cells show a dash on grey.

    Streamlit ignores Styler formats for null cells (it prints 'None' on black), so the cells are
    pre-rendered as strings and coloured with an explicit per-cell style instead.
    """
    text = values.map(lambda v: DASH if pd.isna(v) else f"{v:.{nd}f}")

    def style(_: pd.DataFrame) -> pd.DataFrame:
        out = pd.DataFrame("", index=values.index, columns=values.columns)
        for r in values.index:
            for c in values.columns:
                v = values.at[r, c]
                if pd.isna(v):
                    out.at[r, c] = "background-color:#3a3f4b;color:#9aa0ab"
                    continue
                rgb = rdylgn((v - vmin) / (vmax - vmin))
                lum = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]
                out.at[r, c] = f"background-color:{_hex(rgb)};color:{'#111' if lum > 0.45 else '#fff'}"
        return out

    return text.style.apply(style, axis=None)


def plain_table(values: pd.DataFrame, nd: int = 2) -> pd.DataFrame:
    """Numbers as formatted strings with a dash for nulls (avoids Streamlit's 'None')."""
    return values.map(lambda v: DASH if pd.isna(v) else f"{v:,.{nd}f}")
