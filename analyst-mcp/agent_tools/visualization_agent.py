from __future__ import annotations

import base64
import io
import uuid
from pathlib import Path
from typing import Any, Callable

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from config import settings
from direct_tools.artifacts import load_dataframe

matplotlib.use("Agg")

_CHART_TYPES = {"histogram", "scatter", "bar", "line", "heatmap", "boxplot", "pie"}


def _plots_dir() -> Path:
    d = Path(settings.plots_dir)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _save_fig(fig: "plt.Figure", name: str) -> tuple[str, str]:
    """Сохранить фигуру в PNG, вернуть (path, base64)."""
    p = _plots_dir() / f"{name}_{uuid.uuid4().hex[:8]}.png"
    fig.savefig(p, dpi=100, bbox_inches="tight")
    plt.close(fig)
    b64 = base64.b64encode(p.read_bytes()).decode()
    return str(p), b64


def register(mcp: Any, audited: Callable) -> None:
    @mcp.tool()
    @audited
    def visualization_agent(
        artifact_id: str,
        chart_type: str,
        params: dict | None = None,
    ) -> dict[str, Any]:
        """Построить график по данным из артефакта и сохранить в PNG.

        Args:
            artifact_id: ID артефакта с данными.
            chart_type: Тип графика: 'histogram', 'scatter', 'bar', 'line',
                        'heatmap', 'boxplot', 'pie'.
            params: Параметры графика:
                    - x (str): колонка для оси X
                    - y (str): колонка для оси Y (или список для bar/line)
                    - title (str): заголовок
                    - bins (int): для histogram
                    - top_n (int): для bar/pie — топ N значений

        Returns:
            {
                "status": "ok" | "error",
                "chart_type": str,
                "plot_path": str,
                "base64": str,
                "description": str
            }
        """
        if chart_type not in _CHART_TYPES:
            return {"status": "error", "error": f"Unknown chart_type. Choose from: {_CHART_TYPES}"}

        params = params or {}
        try:
            df = load_dataframe(artifact_id)
        except FileNotFoundError:
            return {"status": "error", "error": f"Artifact not found: {artifact_id}"}

        try:
            fig, description = _plot(df, chart_type, params)
            path, b64 = _save_fig(fig, chart_type)
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

        return {
            "status": "ok",
            "chart_type": chart_type,
            "plot_path": path,
            "base64": b64,
            "description": description,
        }


def _plot(df: pd.DataFrame, chart_type: str, params: dict) -> tuple["plt.Figure", str]:
    x = params.get("x", "")
    y = params.get("y", "")
    title = params.get("title", chart_type)

    if chart_type == "histogram":
        col = x or (df.select_dtypes(include="number").columns[0] if len(df.select_dtypes(include="number").columns) > 0 else df.columns[0])
        bins = params.get("bins", 30)
        fig, ax = plt.subplots()
        df[col].dropna().hist(bins=bins, ax=ax, edgecolor="white")
        ax.set_title(title or f"Гистограмма: {col}")
        ax.set_xlabel(col)
        ax.set_ylabel("Количество")
        return fig, f"Гистограмма колонки '{col}', {bins} бинов"

    if chart_type == "scatter":
        if not x or not y:
            num_cols = list(df.select_dtypes(include="number").columns)
            x = x or (num_cols[0] if num_cols else df.columns[0])
            y = y or (num_cols[1] if len(num_cols) > 1 else num_cols[0])
        fig, ax = plt.subplots()
        ax.scatter(df[x], df[y], alpha=0.5, s=15)
        ax.set_title(title or f"{x} vs {y}")
        ax.set_xlabel(x)
        ax.set_ylabel(y)
        return fig, f"Диаграмма рассеяния: {x} vs {y}"

    if chart_type == "bar":
        if not x or not y:
            raise ValueError("'x' and 'y' params required for bar chart")
        top_n = params.get("top_n")
        plot_df = df[[x, y]].dropna()
        if top_n:
            plot_df = plot_df.nlargest(int(top_n), y)
        fig, ax = plt.subplots()
        ax.bar(plot_df[x].astype(str), plot_df[y])
        ax.set_title(title or f"{y} по {x}")
        ax.set_xlabel(x)
        ax.set_ylabel(y)
        plt.xticks(rotation=45, ha="right")
        return fig, f"Столбчатая диаграмма: {y} по {x}"

    if chart_type == "line":
        if not x or not y:
            raise ValueError("'x' and 'y' params required for line chart")
        fig, ax = plt.subplots()
        plot_df = df[[x, y]].dropna().sort_values(x)
        ax.plot(plot_df[x].astype(str), plot_df[y], marker="o", markersize=3)
        ax.set_title(title or f"{y} по {x}")
        ax.set_xlabel(x)
        ax.set_ylabel(y)
        plt.xticks(rotation=45, ha="right")
        return fig, f"Линейный график: {y} по {x}"

    if chart_type == "heatmap":
        num_df = df.select_dtypes(include="number")
        corr = num_df.corr()
        fig, ax = plt.subplots(figsize=(max(6, len(corr.columns)), max(5, len(corr.columns) - 1)))
        sns.heatmap(corr, annot=True, fmt=".2f", cmap="coolwarm", ax=ax, linewidths=0.5)
        ax.set_title(title or "Корреляционная матрица")
        return fig, "Тепловая карта корреляций числовых колонок"

    if chart_type == "boxplot":
        col = y or x or (df.select_dtypes(include="number").columns[0] if len(df.select_dtypes(include="number").columns) > 0 else df.columns[0])
        group = x if x and x != col else None
        fig, ax = plt.subplots()
        if group and group in df.columns:
            groups = [g[col].dropna().values for _, g in df.groupby(group)]
            labels = [str(name) for name, _ in df.groupby(group)]
            ax.boxplot(groups, labels=labels)
            plt.xticks(rotation=45, ha="right")
        else:
            ax.boxplot(df[col].dropna().values)
        ax.set_title(title or f"Boxplot: {col}")
        ax.set_ylabel(col)
        return fig, f"Boxplot колонки '{col}'"

    if chart_type == "pie":
        if not x or not y:
            raise ValueError("'x' (labels) and 'y' (values) params required for pie chart")
        top_n = params.get("top_n", 10)
        plot_df = df[[x, y]].dropna().nlargest(int(top_n), y)
        fig, ax = plt.subplots()
        ax.pie(plot_df[y], labels=plot_df[x].astype(str), autopct="%1.1f%%", startangle=90)
        ax.set_title(title or f"Круговая: {y} по {x}")
        return fig, f"Круговая диаграмма: {y} по {x}, топ {top_n}"

    raise ValueError(f"Unhandled chart_type: {chart_type}")
