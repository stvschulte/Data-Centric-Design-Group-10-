from __future__ import annotations

from math import erfc, sqrt

import numpy as np
import pandas as pd
import plotly.graph_objects as go


def _clean_pair(x, y) -> pd.DataFrame:
    return pd.DataFrame({"x": x, "y": y}).apply(pd.to_numeric, errors="coerce").dropna()


def _approx_p_value_from_r(r: float, n: int) -> float:
    if n <= 3 or not np.isfinite(r) or abs(r) >= 1:
        return float("nan")
    z_score = np.arctanh(r) * sqrt(n - 3)
    return float(erfc(abs(z_score) / sqrt(2)))


def pearsonr(x, y) -> tuple[float, float]:
    paired = _clean_pair(x, y)
    if len(paired) < 3 or paired["x"].nunique() < 2 or paired["y"].nunique() < 2:
        return float("nan"), float("nan")
    r = float(paired["x"].corr(paired["y"]))
    return r, _approx_p_value_from_r(r, len(paired))


def spearmanr(x, y) -> tuple[float, float]:
    paired = _clean_pair(x, y)
    if len(paired) < 3 or paired["x"].nunique() < 2 or paired["y"].nunique() < 2:
        return float("nan"), float("nan")
    ranked_x = paired["x"].rank(method="average")
    ranked_y = paired["y"].rank(method="average")
    return pearsonr(ranked_x, ranked_y)


def add_ols_line(fig, df: pd.DataFrame, x_column: str, y_column: str, color: str, name: str = "OLS trendline") -> None:
    paired = df[[x_column, y_column]].apply(pd.to_numeric, errors="coerce").dropna().sort_values(x_column)
    if len(paired) < 3 or paired[x_column].nunique() < 2 or paired[y_column].nunique() < 2:
        return

    slope, intercept = np.polyfit(paired[x_column], paired[y_column], 1)
    x_values = np.array([paired[x_column].min(), paired[x_column].max()])
    y_values = slope * x_values + intercept
    fig.add_trace(
        go.Scatter(
            x=x_values,
            y=y_values,
            mode="lines",
            name=name,
            line=dict(color=color, width=3),
            hoverinfo="skip",
        )
    )
