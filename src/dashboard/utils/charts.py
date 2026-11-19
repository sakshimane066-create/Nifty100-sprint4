"""Plotly chart builders shared by dashboard pages."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def bar_line(df: pd.DataFrame, x: str, bars: list[str], title: str) -> go.Figure:
    """Grouped bar chart of several columns over x."""
    fig = go.Figure([go.Bar(x=df[x], y=df[c], name=c.replace("_", " ").title()) for c in bars])
    fig.update_layout(title=title, barmode="group", height=330, margin=dict(t=40, b=10), legend=dict(orientation="h"))
    return fig


def stacked(df: pd.DataFrame, x: str, cols: list[str], title: str) -> go.Figure:
    """Stacked bar chart."""
    fig = go.Figure([go.Bar(x=df[x], y=df[c], name=c.replace("_", " ").title()) for c in cols])
    fig.update_layout(title=title, barmode="stack", height=330, margin=dict(t=40, b=10), legend=dict(orientation="h"))
    return fig


def trend_lines(df: pd.DataFrame, x: str, cols: list[str], title: str) -> go.Figure:
    """Multi-line trend chart."""
    fig = go.Figure([go.Scatter(x=df[x], y=df[c], mode="lines+markers", name=c.replace("_", " ")) for c in cols])
    fig.update_layout(title=title, height=330, margin=dict(t=40, b=10), legend=dict(orientation="h"))
    return fig


def radar(series: dict[str, list[float]], labels: list[str], title: str) -> go.Figure:
    """Radar chart; values are percentile ranks 0-100."""
    fig = go.Figure()
    for name, vals in series.items():
        fig.add_trace(go.Scatterpolar(r=vals + vals[:1], theta=labels + labels[:1], fill="toself", name=name, opacity=0.6))
    fig.update_layout(title=title, polar=dict(radialaxis=dict(range=[0, 100])), height=460, legend=dict(orientation="h"))
    return fig


def donut(df: pd.DataFrame, names: str, values: str, title: str) -> go.Figure:
    """Donut chart."""
    fig = px.pie(df, names=names, values=values, hole=0.5, title=title)
    fig.update_layout(height=380, margin=dict(t=40, b=10))
    return fig
