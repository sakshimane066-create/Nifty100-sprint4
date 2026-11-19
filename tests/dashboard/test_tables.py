import io

import numpy as np
import pandas as pd
from openpyxl import load_workbook

from src.dashboard.utils.tables import DASH, heatmap_table, plain_table, to_excel_bytes


def test_heatmap_shows_dash_not_none_for_nulls():
    df = pd.DataFrame({"a": [50.0, np.nan], "b": [100.0, 0.0]}, index=["X", "Y"])
    st = heatmap_table(df)
    body = st._translate(False, False)["body"]
    shown = [c["display_value"] for row in body for c in row if c["type"] == "td"]
    assert shown == ["50", "100", DASH, "0"]
    css = st.to_html()
    assert "#3a3f4b" in css  # grey fill for the null cell


def test_plain_table_dash():
    out = plain_table(pd.DataFrame({"a": [1234.5, np.nan]}))
    assert out["a"].tolist() == ["1,234.50", DASH]


def test_excel_export_is_formatted_and_has_all_rows():
    df = pd.DataFrame({"company_id": ["TCS", "INFY"], "roe": [50.944, 29.79]})
    wb = load_workbook(io.BytesIO(to_excel_bytes(df, "Screener")))
    ws = wb["Screener"]
    assert ws["A1"].font.bold and ws.freeze_panes == "C2" and ws.max_row == 3
    assert ws["B2"].number_format == "#,##0.00" and ws.auto_filter.ref is not None
