"""Formatted Excel export helper (no matplotlib / streamlit dependency)."""
from __future__ import annotations

import io

import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter


def to_excel_bytes(df: pd.DataFrame, sheet: str = "Results", pct_cols: tuple[str, ...] = ()) -> bytes:
    """Formatted .xlsx: bold header, freeze panes, widths, 2-decimal numbers, auto-filter."""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        df.to_excel(xw, sheet_name=sheet, index=False)
        ws = xw.sheets[sheet]
        for cell in ws[1]:
            cell.font = Font(bold=True, color="FFFFFF", name="Arial")
            cell.fill = PatternFill("solid", fgColor="1F3864")
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        for i, col in enumerate(df.columns, start=1):
            letter = get_column_letter(i)
            longest = max([len(str(col))] + [len(str(v)) for v in df[col].head(200)])
            ws.column_dimensions[letter].width = min(max(12, longest + 2), 45)
            if pd.api.types.is_numeric_dtype(df[col]):
                for row in ws.iter_rows(min_row=2, min_col=i, max_col=i):
                    row[0].number_format = "#,##0.00"
        ws.freeze_panes = "C2"
        ws.auto_filter.ref = ws.dimensions
        ws.row_dimensions[1].height = 32
    return buf.getvalue()
