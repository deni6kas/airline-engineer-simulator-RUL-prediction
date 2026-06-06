"""Plotly charts: RUL prediction over time + sensor telemetry."""
from __future__ import annotations

import plotly.graph_objects as go

from . import config

_DARK = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color=config.COL["ink_dim"], size=11,
              family="Consolas, monospace"),
    margin=dict(l=44, r=14, t=10, b=34),
)


def _grid(fig: go.Figure) -> None:
    fig.update_xaxes(gridcolor=config.COL["panel_edge"], zeroline=False,
                     linecolor=config.COL["panel_edge"])
    fig.update_yaxes(gridcolor=config.COL["panel_edge"], zeroline=False,
                     linecolor=config.COL["panel_edge"])


def rul_chart(pred_df, reveal_truth: bool, height: int = 230) -> go.Figure:
    """pred_df columns: cycle, predicted_rul, true_rul.

    Predicted line is always shown. The hidden True-RUL line is only revealed
    after maintenance / crash (reveal_truth=True).
    """
    fig = go.Figure()

    # status bands
    xs = pred_df["cycle"]
    if len(xs):
        x0, x1 = int(xs.min()), int(xs.max()) + 1
        fig.add_hrect(y0=config.SAFE_MIN, y1=200, fillcolor=config.COL["safe"],
                      opacity=0.06, line_width=0)
        fig.add_hrect(y0=config.WARNING_MIN, y1=config.SAFE_MIN,
                      fillcolor=config.COL["warning"], opacity=0.07, line_width=0)
        fig.add_hrect(y0=0, y1=config.WARNING_MIN, fillcolor=config.COL["critical"],
                      opacity=0.08, line_width=0)

    fig.add_trace(go.Scatter(
        x=pred_df["cycle"], y=pred_df["predicted_rul"],
        mode="lines+markers", name="ML Model Prediction",
        line=dict(color=config.COL["accent"], width=2.5),
        marker=dict(size=3),
    ))

    if reveal_truth:
        fig.add_trace(go.Scatter(
            x=pred_df["cycle"], y=pred_df["true_rul"],
            mode="lines", name="True RUL",
            line=dict(color=config.COL["ink"], width=2, dash="dash"),
        ))

    fig.update_layout(
        height=height, showlegend=True,
        legend=dict(orientation="h", y=1.12, x=0, bgcolor="rgba(0,0,0,0)"),
        **_DARK,
    )
    fig.update_xaxes(title="Cycles")
    fig.update_yaxes(title="RUL", rangemode="tozero")
    _grid(fig)
    return fig


def sensor_chart(sensor_df, label: str, height: int = 230) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=sensor_df["cycle"], y=sensor_df["sensor_value"],
        mode="lines", line=dict(color=config.COL["accent"], width=2),
        fill="tozeroy", fillcolor="rgba(54,194,246,0.08)",
        name=label,
    ))
    fig.update_layout(height=height, showlegend=False, **_DARK)
    fig.update_xaxes(title="Cycles")
    fig.update_yaxes(title=label, rangemode="normal")
    _grid(fig)
    return fig
