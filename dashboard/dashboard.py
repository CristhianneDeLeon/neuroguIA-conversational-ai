# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from typing import Iterable
from io import BytesIO
import os
import textwrap

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import FancyBboxPatch, Rectangle
import numpy as np
import pandas as pd
import streamlit as st

try:
    from scipy.stats import spearmanr
except ImportError:  # Fallback: se utilizan los resultados canónicos de M14C.
    spearmanr = None

from dashboard_data_loader import (
    clear_dashboard_cache,
    indicator_map,
    load_dashboard_data,
    parameter_map,
)

st.set_page_config(
    page_title="neuroguIA · Dashboard científico v3",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"About": "Dashboard científico de neuroguIA · Documento Maestro Oficial v3"},
)

BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
BUILD_ID = "DASH-V3.4-COMPLETO-PDF-20260805"
PALETTE = ["#6E57D2", "#00A6A6", "#E45C88", "#FF7A59", "#3F8EFC", "#F2B84B"]
INK = "#241F35"
MUTED = "#716A7E"

st.markdown(
    """
    <style>
    .stApp {
        background: radial-gradient(circle at 8% 0%, rgba(110,87,210,.12), transparent 27%),
                    radial-gradient(circle at 93% 7%, rgba(0,166,166,.10), transparent 25%),
                    linear-gradient(180deg,#fff 0%,#faf8fc 100%);
    }
    .block-container {max-width: 1540px; padding-top: 1.2rem; padding-bottom: 3rem;}
    section[data-testid="stSidebar"] {background:#f8f5fb; border-right:1px solid #e7e0ee;}
    .ng-hero {padding:1.35rem 1.5rem; border-radius:26px; background:rgba(255,255,255,.94);
              border:1px solid #e7e0ee; box-shadow:0 18px 45px rgba(66,44,92,.08); margin-bottom:1rem;}
    .ng-kicker {font-size:.78rem; font-weight:850; letter-spacing:.13em; text-transform:uppercase; color:#6E57D2;}
    .ng-title {font-size:2.35rem; line-height:1.08; font-weight:900; letter-spacing:-.045em; color:#241F35; margin:.2rem 0 .5rem;}
    .ng-subtitle {font-size:1rem; line-height:1.62; color:#716A7E; max-width:1150px;}
    .ng-section {font-size:1.35rem; font-weight:850; color:#241F35; margin:1.45rem 0 .6rem; letter-spacing:-.025em;}
    .ng-card {background:#fff; border:1px solid #e7e0ee; border-radius:21px; padding:1rem 1.05rem;
              box-shadow:0 12px 28px rgba(66,44,92,.055); min-height:126px;}
    .ng-card-label {font-size:.72rem; font-weight:850; text-transform:uppercase; letter-spacing:.085em; color:#716A7E;}
    .ng-card-value {font-size:1.92rem; font-weight:900; letter-spacing:-.045em; color:#241F35; margin:.25rem 0;}
    .ng-card-note {font-size:.78rem; color:#716A7E; line-height:1.42;}
    .ng-source {padding:.52rem .72rem; border-left:3px solid #6E57D2; background:#f7f4fb; color:#716A7E;
                font-size:.78rem; border-radius:0 10px 10px 0; margin:.45rem 0 1rem;}
    .ng-callout {padding:1rem 1.1rem; border-radius:16px; background:#e8f7f4; border:1px solid #bfe8df;
                 color:#155e58; font-weight:650; line-height:1.55;}
    div[data-testid="stMetric"] {background:#fff; border:1px solid #e7e0ee; border-radius:18px; padding:.65rem;}
    [data-testid="stDataFrame"] {border:1px solid #e7e0ee; border-radius:16px; overflow:hidden;}
    .ng-method-note {padding:.85rem 1rem; border-radius:15px; background:#fff8e8; border:1px solid #f3dca6;
                     color:#6b5312; line-height:1.5; margin:.45rem 0 .85rem;}
    .ng-small-note {font-size:.82rem; color:#716A7E; line-height:1.5;}
    .ng-control-line {font-size:.61rem; color:rgba(113,106,126,.36); line-height:1.35;
                      text-align:right; margin-top:1.5rem; user-select:none;}
    </style>
    """,
    unsafe_allow_html=True,
)


def to_float(value: object, default: float | None = None) -> float | None:
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def fmt_count(value: object) -> str:
    number = to_float(value)
    return "—" if number is None else f"{int(round(number)):,}"


def fmt_num(value: object, decimals: int = 2) -> str:
    number = to_float(value)
    return "—" if number is None else f"{number:,.{decimals}f}"


def fmt_pct(value: object, decimals: int = 2, signed: bool = False) -> str:
    number = to_float(value)
    if number is None:
        return "—"
    shown = number * 100 if abs(number) <= 1.5 else number
    sign = "+" if signed and shown > 0 else ""
    return f"{sign}{shown:.{decimals}f}%"


def fmt_p(value: object) -> str:
    number = to_float(value)
    if number is None:
        return "—"
    if number < .001:
        return "< 0.001"
    return f"{number:.3f}"


def kpi(label: str, value: str, note: str = "") -> None:
    st.markdown(
        f"""
        <div class="ng-card">
          <div class="ng-card-label">{label}</div>
          <div class="ng-card-value">{value}</div>
          <div class="ng-card-note">{note}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section(title: str) -> None:
    st.markdown(f"<div class='ng-section'>{title}</div>", unsafe_allow_html=True)


def source_note(*sheets: str) -> None:
    joined = " · ".join(sheets)
    st.markdown(f"<div class='ng-source'>Fuente canónica: {joined} del Documento Maestro Oficial v3 auditado.</div>", unsafe_allow_html=True)


def clean_table(df: pd.DataFrame, columns: Iterable[str] | None = None, rename: dict[str, str] | None = None) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    if columns is not None:
        cols = [c for c in columns if c in out.columns]
        out = out[cols]
    if rename:
        out = out.rename(columns=rename)
    return out.reset_index(drop=True)


def show_table(df: pd.DataFrame, **kwargs) -> None:
    if df is None or df.empty:
        st.info("No hay registros disponibles para esta tabla.")
        return
    st.dataframe(df, use_container_width=True, hide_index=True, **kwargs)


GROUP_ORDER = ["Experimental", "Control"]


def order_groups(df: pd.DataFrame, column: str = "grupo") -> pd.DataFrame:
    """Mantiene el orden científico constante: Experimental y después Control."""
    if df is None or df.empty or column not in df.columns:
        return df
    out = df.copy()
    out[column] = pd.Categorical(out[column], categories=GROUP_ORDER, ordered=True)
    return out.sort_values(column).reset_index(drop=True)


def format_columns(
    df: pd.DataFrame,
    decimals: dict[str, int] | None = None,
    p_columns: Iterable[str] | None = None,
    percent_columns: Iterable[str] | None = None,
    signed_percent_columns: Iterable[str] | None = None,
    count_columns: Iterable[str] | None = None,
) -> pd.DataFrame:
    """Prepara tablas públicas sin exponer notación científica o decimales excesivos."""
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    for column, digits in (decimals or {}).items():
        if column in out.columns:
            out[column] = out[column].map(lambda value, d=digits: fmt_num(value, d))
    for column in (p_columns or []):
        if column in out.columns:
            out[column] = out[column].map(fmt_p)
    for column in (percent_columns or []):
        if column in out.columns:
            out[column] = out[column].map(fmt_pct)
    for column in (signed_percent_columns or []):
        if column in out.columns:
            out[column] = out[column].map(lambda value: fmt_pct(value, signed=True))
    for column in (count_columns or []):
        if column in out.columns:
            out[column] = out[column].map(fmt_count)
    return out


def base_axes(ax, title: str, ylabel: str = "") -> None:
    ax.set_title(title, loc="left", color=INK, fontsize=12, fontweight="bold")
    if ylabel:
        ax.set_ylabel(ylabel, color=MUTED)
    ax.grid(axis="y", alpha=.18)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(colors=INK, labelsize=8)


def prepost_chart(df: pd.DataFrame, label_col: str, selected: str, title: str) -> None:
    plot = order_groups(df[df[label_col].astype(str) == selected].copy())
    if plot.empty:
        st.info("No hay datos pretest–postest para esta selección.")
        return
    groups = plot["grupo"].astype(str).tolist()
    pre = pd.to_numeric(plot["pre_media"], errors="coerce").to_numpy()
    post = pd.to_numeric(plot["post_media"], errors="coerce").to_numpy()
    x = np.arange(len(groups))
    width = .34
    fig, ax = plt.subplots(figsize=(9.5, 4.35), dpi=145)
    b1 = ax.bar(x - width/2, pre, width, label="Pretest", color=PALETTE[0])
    b2 = ax.bar(x + width/2, post, width, label="Postest", color=PALETTE[1])
    ax.set_xticks(x, groups)
    base_axes(ax, title, "Puntuación media")
    ax.legend(frameon=False, ncol=2)
    for bars in (b1, b2):
        ax.bar_label(bars, fmt="%.2f", padding=3, fontsize=8)
    fig.tight_layout()
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)


def percent_change_chart(df: pd.DataFrame, label_col: str, title: str) -> None:
    if df.empty or "cambio_pct" not in df.columns:
        return
    plot = df.copy()
    plot["etiqueta"] = plot[label_col].astype(str) + " · " + plot["grupo"].astype(str)
    plot["pct"] = pd.to_numeric(plot["cambio_pct"], errors="coerce") * 100
    plot = plot.dropna(subset=["pct"]).sort_values("pct")
    fig, ax = plt.subplots(figsize=(10, max(4.2, len(plot)*.35)), dpi=145)
    colors = [PALETTE[0] if "Experimental" in x else PALETTE[3] for x in plot["etiqueta"]]
    bars = ax.barh(plot["etiqueta"], plot["pct"], color=colors)
    ax.axvline(0, color="#999", linewidth=.8)
    base_axes(ax, title, "Cambio porcentual")
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:.0f}%"))
    ax.bar_label(bars, fmt="%.1f%%", padding=3, fontsize=8)
    fig.tight_layout()
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)


def forest_chart(df: pd.DataFrame, label_col: str, effect_col: str, low_col: str, high_col: str, title: str) -> None:
    required = {label_col, effect_col, low_col, high_col}
    if df.empty or not required.issubset(df.columns):
        st.info("No hay intervalos suficientes para esta gráfica.")
        return
    plot = df[list(required)].copy().dropna()
    plot = plot.sort_values(effect_col)
    y = np.arange(len(plot))
    effect = pd.to_numeric(plot[effect_col])
    low = pd.to_numeric(plot[low_col])
    high = pd.to_numeric(plot[high_col])
    fig, ax = plt.subplots(figsize=(10, max(3.0, 1.65 + len(plot) * .58)), dpi=145)
    ax.errorbar(effect, y, xerr=[effect-low, high-effect], fmt="o", capsize=3, color=PALETTE[0], ecolor=PALETTE[1])
    ax.axvline(0, color="#888", linestyle="--", linewidth=1)
    ax.set_yticks(y, plot[label_col].astype(str))
    base_axes(ax, title, "Tamaño del efecto")
    fig.tight_layout()
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)


def weekly_chart(df: pd.DataFrame, value: str, title: str, ylabel: str) -> None:
    if df.empty or value not in df.columns:
        return
    plot = df[df["estado"].astype(str).str.contains("Intervención", case=False, na=False)].copy()
    plot["periodo_num"] = pd.to_numeric(plot["periodo"], errors="coerce")
    plot = plot.dropna(subset=["periodo_num"]).sort_values("periodo_num")
    fig, ax = plt.subplots(figsize=(11, 4.5), dpi=145)
    ax.plot(plot["periodo_num"], pd.to_numeric(plot[value]), marker="o", linewidth=2.8, color=PALETTE[0])
    ax.fill_between(plot["periodo_num"], pd.to_numeric(plot[value]), alpha=.12, color=PALETTE[0])
    ax.set_xticks(plot["periodo_num"].astype(int))
    ax.set_xlabel("Semana de intervención")
    base_axes(ax, title, ylabel)
    fig.tight_layout()
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)


def grouped_category_chart(df: pd.DataFrame, category: str, group: str, value: str, title: str, percent: bool = False) -> None:
    if df.empty or not {category, group, value}.issubset(df.columns):
        return
    pivot = df.pivot_table(index=category, columns=group, values=value, aggfunc="sum", fill_value=0)
    fig, ax = plt.subplots(figsize=(11, max(4.6, len(pivot)*.42)), dpi=145)
    pivot.plot(kind="barh", ax=ax, color=PALETTE[:len(pivot.columns)])
    base_axes(ax, title, "Porcentaje" if percent else "Frecuencia")
    if percent:
        ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x*100:.0f}%"))
    ax.legend(frameon=False, title="Grupo")
    fig.tight_layout()
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)


def bool_env(name: str) -> bool:
    return str(os.getenv(name, "") or "").strip().lower() in {"1", "true", "yes", "sí", "si", "on"}





def calculate_spearman_results(usage: pd.DataFrame) -> pd.DataFrame:
    """Recalcula rho de Spearman y su p bilateral desde los datos individuales de uso."""
    columns = [
        "muestra",
        "predictor",
        "resultado",
        "rho",
        "p",
        "n",
        "valores_unicos",
        "origen",
    ]
    if usage is None or usage.empty:
        return pd.DataFrame(columns=columns)

    specifications = [
        ("Muestra total", None, "mensajes", "Mensajes"),
        ("Muestra total", None, "semanas_activas", "Semanas activas"),
        ("Solo experimental", "Experimental", "mensajes", "Mensajes"),
        ("Solo experimental", "Experimental", "semanas_activas", "Semanas activas"),
        ("Solo experimental", "Experimental", "frecuencia_mensajes_semana", "Frecuencia semanal"),
        ("Solo experimental", "Experimental", "duracion_media_reportada", "Duración media"),
    ]

    rows: list[dict[str, object]] = []
    for sample_name, group_name, predictor_column, predictor_label in specifications:
        subset = usage.copy()
        if group_name is not None and "grupo" in subset.columns:
            subset = subset[subset["grupo"].astype(str) == group_name].copy()

        if predictor_column not in subset.columns or "mejora_estres" not in subset.columns:
            continue

        predictor = pd.to_numeric(subset[predictor_column], errors="coerce")
        outcome = pd.to_numeric(subset["mejora_estres"], errors="coerce")
        valid = predictor.notna() & outcome.notna()
        predictor = predictor[valid]
        outcome = outcome[valid]

        unique_values = int(predictor.nunique())
        rho_value = np.nan
        p_value = np.nan
        origin = "No calculable: predictor constante"

        if len(predictor) >= 3 and unique_values >= 2:
            if spearmanr is not None:
                result = spearmanr(predictor, outcome, nan_policy="omit")
                rho_value = float(result.statistic)
                p_value = float(result.pvalue)
                origin = "Recalculado desde M14A_USO_PARTICIPANTE"
            else:
                rho_value = float(predictor.rank().corr(outcome.rank(), method="pearson"))
                origin = "Rho recalculado; p requiere scipy"

        rows.append(
            {
                "muestra": sample_name,
                "predictor": predictor_label,
                "resultado": "Mejora del estrés",
                "rho": rho_value,
                "p": p_value,
                "n": int(len(predictor)),
                "valores_unicos": unique_values,
                "origen": origin,
            }
        )

    return pd.DataFrame(rows, columns=columns)

def _pdf_wrap(value: object, width: int = 88) -> str:
    return "\n".join(textwrap.wrap(str(value), width=width, break_long_words=False))


def _pdf_page_base(
    title: str,
    subtitle: str,
    master_hash: str,
    page_number: int,
) -> tuple[plt.Figure, plt.Axes]:
    """Crea una página A4 horizontal con cabecera institucional y pie discreto."""
    fig = plt.figure(figsize=(11.69, 8.27), facecolor="#F8F6FC")
    canvas = fig.add_axes([0, 0, 1, 1])
    canvas.set_xlim(0, 1)
    canvas.set_ylim(0, 1)
    canvas.axis("off")

    canvas.add_patch(Rectangle((0, .91), 1, .09, facecolor=PALETTE[0], edgecolor="none"))
    canvas.add_patch(Rectangle((.78, .91), .22, .09, facecolor=PALETTE[1], edgecolor="none", alpha=.95))
    canvas.text(.055, .958, title, fontsize=20, fontweight="bold", color="white", va="center")
    canvas.text(.055, .924, subtitle, fontsize=8.8, color="#EEEAFB", va="center")
    canvas.text(.945, .953, "neuroguIA", fontsize=12, fontstyle="italic", fontweight="bold", color="white", ha="right")

    canvas.plot([.055, .945], [.055, .055], color="#DDD7E8", linewidth=.7)
    canvas.text(.055, .026, f"Informe público de resultados · página {page_number}", fontsize=6.5, color="#A49DAF")
    canvas.text(
        .945,
        .026,
        f"control {BUILD_ID} · {master_hash[:8]}…{master_hash[-6:]}",
        fontsize=5.8,
        color="#B8B1C1",
        ha="right",
    )
    return fig, canvas


def _pdf_card(
    canvas: plt.Axes,
    x: float,
    y: float,
    w: float,
    h: float,
    label: str,
    value: str,
    note: str = "",
    accent: str = PALETTE[0],
) -> None:
    canvas.add_patch(
        FancyBboxPatch(
            (x, y), w, h,
            boxstyle="round,pad=0.008,rounding_size=0.018",
            facecolor="white",
            edgecolor="#E2DCEB",
            linewidth=.9,
        )
    )
    canvas.add_patch(
        FancyBboxPatch(
            (x, y), .009, h,
            boxstyle="round,pad=0,rounding_size=0.006",
            facecolor=accent,
            edgecolor="none",
        )
    )
    canvas.text(x + .025, y + h - .032, label.upper(), fontsize=7.2, fontweight="bold", color=MUTED, va="top")
    canvas.text(x + .025, y + h * .48, value, fontsize=18, fontweight="bold", color=INK, va="center")
    if note:
        canvas.text(x + .025, y + .025, _pdf_wrap(note, 34), fontsize=6.8, color=MUTED, va="bottom")


def _pdf_explanation(
    canvas: plt.Axes,
    x: float,
    y: float,
    w: float,
    h: float,
    title: str,
    body: str,
    accent: str = PALETTE[1],
) -> None:
    canvas.add_patch(
        FancyBboxPatch(
            (x, y), w, h,
            boxstyle="round,pad=0.012,rounding_size=0.018",
            facecolor="#FFFFFF",
            edgecolor=accent,
            linewidth=1.2,
        )
    )
    canvas.text(x + .018, y + h - .025, title, fontsize=9.2, fontweight="bold", color=accent, va="top")
    canvas.text(x + .018, y + h - .058, _pdf_wrap(body, max(42, int(w * 112))), fontsize=7.6, color="#4B4655", va="top", linespacing=1.35)


def _pdf_axis(ax: plt.Axes, title: str, ylabel: str = "") -> None:
    ax.set_title(title, loc="left", fontsize=12, fontweight="bold", color=INK, pad=10)
    if ylabel:
        ax.set_ylabel(ylabel, color=MUTED, fontsize=8)
    ax.grid(axis="y", alpha=.16)
    ax.set_facecolor("white")
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(colors=INK, labelsize=7.5)


def _pdf_table(
    ax: plt.Axes,
    headers: list[str],
    rows: list[list[object]],
    col_widths: list[float] | None = None,
    font_size: float = 7.2,
) -> None:
    ax.axis("off")
    table = ax.table(
        cellText=[[str(value) for value in row] for row in rows],
        colLabels=headers,
        loc="center",
        cellLoc="center",
        colLoc="center",
        colWidths=col_widths,
    )
    table.auto_set_font_size(False)
    table.set_fontsize(font_size)
    table.scale(1, 1.45)
    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor("#E3DDEB")
        cell.set_linewidth(.55)
        if row == 0:
            cell.set_facecolor("#EEEAF8")
            cell.set_text_props(weight="bold", color=INK)
        else:
            cell.set_facecolor("white" if row % 2 else "#FAF9FC")
            cell.set_text_props(color="#4B4655")


def _pdf_effect_rows(effect_df: pd.DataFrame, result_names: list[str], definition: str = "Postest E-C") -> list[list[str]]:
    rows: list[list[str]] = []
    for result_name in result_names:
        found = effect_df[
            (effect_df["resultado"].astype(str) == result_name)
            & (effect_df["definicion"].astype(str) == definition)
        ] if {"resultado", "definicion"}.issubset(effect_df.columns) else pd.DataFrame()
        if found.empty:
            continue
        row = found.iloc[0]
        rows.append([
            result_name,
            fmt_num(row.get("cohen_d"), 3),
            fmt_num(row.get("hedges_g"), 3),
            f"[{fmt_num(row.get('ic_bajo'), 2)}, {fmt_num(row.get('ic_alto'), 2)}]",
        ])
    return rows


def create_visual_report(
    all_frames: dict[str, pd.DataFrame],
    parameters: dict[str, object],
    indicators: dict[str, object],
    master_hash: str,
) -> bytes:
    """Genera un informe visual completo, explicativo y exclusivamente agregado."""
    buffer = BytesIO()

    dass = all_frames.get("dass_summary", pd.DataFrame()).copy()
    ancova = all_frames.get("ancova", pd.DataFrame()).copy()
    effects = all_frames.get("effects", pd.DataFrame()).copy()
    mspss = all_frames.get("mspss_official", pd.DataFrame()).copy()
    support = all_frames.get("support_individual", pd.DataFrame()).copy()
    who = all_frames.get("whoqol_summary", pd.DataFrame()).copy()
    weekly = all_frames.get("usage_weekly", pd.DataFrame()).copy()
    regression = all_frames.get("regression", pd.DataFrame()).copy()
    pln_official = all_frames.get("pln_official", pd.DataFrame()).copy()
    pln_categories = all_frames.get("pln_categories", pd.DataFrame()).copy()
    pln_confusion = all_frames.get("pln_confusion", pd.DataFrame()).copy()
    experience = all_frames.get("experience_summary", pd.DataFrame()).copy()
    baseline = all_frames.get("baseline_comparability", pd.DataFrame()).copy()
    sample_flow = all_frames.get("sample_flow", pd.DataFrame()).copy()
    usage_individual = all_frames.get("usage_participant", pd.DataFrame()).copy()
    spearman_results = calculate_spearman_results(usage_individual)

    with PdfPages(buffer) as pdf:
        # ------------------------------------------------------------------
        # 1. Portada y síntesis
        # ------------------------------------------------------------------
        fig, canvas = _pdf_page_base(
            "Informe científico visual de resultados",
            "Síntesis pública derivada del Documento Maestro Oficial v3 auditado",
            master_hash,
            1,
        )
        canvas.text(.055, .855, "neuroguIA", fontsize=34, fontweight="bold", color=INK)
        canvas.text(.055, .815, "Acompañamiento socioemocional no clínico en contextos de neurodivergencia", fontsize=11, color=MUTED)

        stress_row = dass[(dass.get("resultado", pd.Series(dtype=str)).astype(str) == "Estrés") & (dass.get("grupo", pd.Series(dtype=str)).astype(str) == "Experimental")]
        mspss_row = mspss[mspss.get("grupo", pd.Series(dtype=str)).astype(str) == "Experimental"]
        who_row = who[(who.get("dominio", pd.Series(dtype=str)).astype(str) == "Global descriptivo") & (who.get("grupo", pd.Series(dtype=str)).astype(str) == "Experimental")]

        cards = [
            ("Participantes", fmt_count(parameters.get("n total")), "281 experimental + 281 control", PALETTE[0]),
            ("Familias analíticas", fmt_count(parameters.get("familias")), "Cruce PT-FAM-WHOQOL validado", PALETTE[1]),
            ("Intervención", "18 semanas", "12 enero - 17 mayo de 2026", PALETTE[2]),
            ("Sesiones activas", fmt_count(parameters.get("sesiones ventana activa")), "Ventana metodológica", PALETTE[3]),
            ("Reducción de estrés", fmt_pct(stress_row.iloc[0].get("cambio_pct") if not stress_row.empty else None), "Grupo experimental", PALETTE[0]),
            ("Incremento MSPSS", fmt_pct(mspss_row.iloc[0].get("cambio_pct") if not mspss_row.empty else None, signed=True), "Resultado oficial agregado", PALETTE[1]),
            ("WHOQOL global", fmt_pct(who_row.iloc[0].get("cambio_pct") if not who_row.empty else None, signed=True), "Cambio experimental", PALETTE[2]),
            ("Mensajes técnicos", fmt_count(parameters.get("mensajes técnicos totales")), "Corpus técnico completo", PALETTE[3]),
        ]
        positions = [(.055,.60),(.285,.60),(.515,.60),(.745,.60),(.055,.40),(.285,.40),(.515,.40),(.745,.40)]
        for (label, value, note, accent), (x, y) in zip(cards, positions):
            _pdf_card(canvas, x, y, .20, .155, label, value, note, accent)

        principal_anc = ancova[ancova.get("resultado", pd.Series(dtype=str)).astype(str) == "Estrés"]
        principal_eff = effects[(effects.get("resultado", pd.Series(dtype=str)).astype(str) == "Estrés") & (effects.get("definicion", pd.Series(dtype=str)).astype(str) == "Postest E-C")]
        anc_text = fmt_num(principal_anc.iloc[0].get("b_grupo"), 2) if not principal_anc.empty else "-"
        p_text = fmt_p(principal_anc.iloc[0].get("p_grupo")) if not principal_anc.empty else "-"
        d_text = fmt_num(abs(principal_eff.iloc[0].get("cohen_d")), 3) if not principal_eff.empty else "-"
        _pdf_explanation(
            canvas, .055, .14, .89, .18,
            "Hallazgo principal",
            f"El grupo experimental redujo el estrés en {fmt_pct(stress_row.iloc[0].get('cambio_pct') if not stress_row.empty else None)}. "
            f"La diferencia ajustada por el valor basal fue de {anc_text} puntos (p {p_text}) y el tamaño del efecto postest fue |d| = {d_text}. "
            "El cambio supera el umbral metodológico del 15 %, por lo que se acepta H1.",
            PALETTE[1],
        )
        pdf.savefig(fig)
        plt.close(fig)

        # ------------------------------------------------------------------
        # 2. DASS descriptivo
        # ------------------------------------------------------------------
        fig, canvas = _pdf_page_base("DASS-21: evolución descriptiva", "Estrés, ansiedad y depresión por grupo y momento", master_hash, 2)
        dimensions = ["Estrés", "Ansiedad", "Depresión"]
        legend_handles = None
        for index, dimension in enumerate(dimensions):
            ax = fig.add_axes([.06 + index * .305, .31, .27, .48])
            subset = order_groups(dass[dass.get("resultado", pd.Series(dtype=str)).astype(str) == dimension].copy())
            if subset.empty:
                ax.axis("off")
                continue
            x = np.arange(len(subset)); width = .34
            pre = pd.to_numeric(subset["pre_media"], errors="coerce")
            post = pd.to_numeric(subset["post_media"], errors="coerce")
            b1 = ax.bar(x - width/2, pre, width, label="Pretest", color=PALETTE[0])
            b2 = ax.bar(x + width/2, post, width, label="Postest", color=PALETTE[1])
            ax.set_xticks(x, subset["grupo"].astype(str), rotation=10)
            _pdf_axis(ax, dimension, "Puntuación media" if index == 0 else "")
            ax.bar_label(b1, fmt="%.2f", padding=2, fontsize=7)
            ax.bar_label(b2, fmt="%.2f", padding=2, fontsize=7)
            if legend_handles is None:
                legend_handles = (b1, b2)

        if legend_handles is not None:
            fig.legend(
                legend_handles,
                ["Pretest", "Postest"],
                loc="upper center",
                bbox_to_anchor=(.50, .845),
                ncol=2,
                frameon=False,
                fontsize=8,
            )

        exp_changes = []
        for dimension in dimensions:
            found = dass[(dass.get("resultado", pd.Series(dtype=str)).astype(str) == dimension) & (dass.get("grupo", pd.Series(dtype=str)).astype(str) == "Experimental")]
            if not found.empty:
                exp_changes.append(f"{dimension.lower()}: {fmt_pct(found.iloc[0].get('cambio_pct'))}")
        _pdf_explanation(
            canvas, .055, .10, .89, .145,
            "Qué significan estos resultados",
            "En DASS-21, una puntuación menor representa menor intensidad de síntomas. El grupo experimental muestra reducciones sustantivas en "
            + ", ".join(exp_changes)
            + ". El grupo control permanece prácticamente estable, lo que apoya que el cambio no se explica únicamente por el paso del tiempo.",
            PALETTE[0],
        )
        pdf.savefig(fig)
        plt.close(fig)

        # ------------------------------------------------------------------
        # 3. DASS inferencial: ANCOVA + efectos
        # ------------------------------------------------------------------
        fig, canvas = _pdf_page_base("DASS-21: evidencia inferencial", "ANCOVA ajustada, intervalos y tamaños del efecto", master_hash, 3)
        anc_rows: list[list[str]] = []
        for dimension in dimensions:
            found = ancova[ancova.get("resultado", pd.Series(dtype=str)).astype(str) == dimension]
            if found.empty:
                continue
            row = found.iloc[0]
            anc_rows.append([
                dimension,
                fmt_num(row.get("b_grupo"), 3),
                f"[{fmt_num(row.get('ic_bajo'),2)}, {fmt_num(row.get('ic_alto'),2)}]",
                fmt_p(row.get("p_grupo")),
                fmt_num(row.get("r2_aj"), 3),
                fmt_p(row.get("p_interaccion")),
            ])
        table_ax = fig.add_axes([.06, .57, .88, .25])
        _pdf_table(table_ax, ["Dimensión", "Dif. ajustada", "IC 95 %", "p grupo", "R² ajustado", "p interacción"], anc_rows, [.16,.14,.18,.12,.14,.14])

        effect_rows = _pdf_effect_rows(effects, dimensions)
        eff_ax = fig.add_axes([.08, .24, .40, .24])
        if effect_rows:
            labels = [row[0] for row in effect_rows]
            values = [float(row[1]) for row in effect_rows]
            lows = [] ; highs = []
            for dimension in labels:
                found = effects[(effects["resultado"].astype(str) == dimension) & (effects["definicion"].astype(str) == "Postest E-C")]
                lows.append(float(found.iloc[0]["ic_bajo"]))
                highs.append(float(found.iloc[0]["ic_alto"]))
            y = np.arange(len(labels))
            eff_ax.errorbar(values, y, xerr=[np.array(values)-np.array(lows), np.array(highs)-np.array(values)], fmt="o", capsize=3, color=PALETTE[0], ecolor=PALETTE[1])
            eff_ax.axvline(0, linestyle="--", linewidth=.9, color="#888")
            eff_ax.set_yticks(y, labels)
            _pdf_axis(eff_ax, "Cohen d postest", "")
        eff_table_ax = fig.add_axes([.54, .24, .40, .24])
        _pdf_table(eff_table_ax, ["Dimensión", "Cohen d", "Hedges g", "IC 95 %"], effect_rows, [.24,.18,.18,.30])

        _pdf_explanation(
            canvas, .055, .075, .89, .115,
            "Interpretación",
            "La ANCOVA compara los grupos en el postest controlando el nivel basal. En las tres dimensiones, p < 0.001 confirma diferencias ajustadas significativas. "
            "La interacción grupo por pretest presenta p > 0.05, por lo que se cumple la homogeneidad de pendientes. El signo negativo de d indica menor sintomatología en el grupo experimental.",
            PALETTE[2],
        )
        pdf.savefig(fig)
        plt.close(fig)

        # ------------------------------------------------------------------
        # 4. MSPSS y apoyo auxiliar
        # ------------------------------------------------------------------
        fig, canvas = _pdf_page_base("Apoyo social percibido", "MSPSS oficial agregado e índice auxiliar individual", master_hash, 4)
        if not mspss.empty:
            mspss_plot = order_groups(mspss.copy())
            ax = fig.add_axes([.06, .38, .40, .42])
            x = np.arange(len(mspss_plot)); width=.34
            b1 = ax.bar(x-width/2, pd.to_numeric(mspss_plot["pre_1_5"], errors="coerce"), width, color=PALETTE[0], label="Pretest")
            b2 = ax.bar(x+width/2, pd.to_numeric(mspss_plot["post_1_5"], errors="coerce"), width, color=PALETTE[1], label="Postest")
            ax.set_xticks(x, mspss_plot["grupo"].astype(str)); ax.set_ylim(0,5)
            _pdf_axis(ax, "MSPSS oficial agregado", "Escala 1-5")
            ax.bar_label(b1, fmt="%.2f", padding=2, fontsize=7); ax.bar_label(b2, fmt="%.2f", padding=2, fontsize=7)
            ax.legend(frameon=False, fontsize=7)

        if not support.empty:
            support_summary = support.groupby("grupo", as_index=False).agg(pre=("apoyo_pre_1_5","mean"), post=("apoyo_post_1_5","mean"), cambio=("mejora_apoyo","mean"))
            support_summary = order_groups(support_summary)
            ax = fig.add_axes([.54, .38, .40, .42])
            x = np.arange(len(support_summary)); width=.34
            b1 = ax.bar(x-width/2, support_summary["pre"], width, color=PALETTE[2], label="Pretest")
            b2 = ax.bar(x+width/2, support_summary["post"], width, color=PALETTE[1], label="Postest")
            ax.set_xticks(x, support_summary["grupo"].astype(str)); ax.set_ylim(0,5)
            _pdf_axis(ax, "Índice auxiliar individual", "Escala 1-5")
            ax.bar_label(b1, fmt="%.2f", padding=2, fontsize=7); ax.bar_label(b2, fmt="%.2f", padding=2, fontsize=7)
            ax.legend(frameon=False, fontsize=7)

        aux_anc = ancova[ancova.get("resultado", pd.Series(dtype=str)).astype(str) == "Apoyo auxiliar 1-5"]
        anc_sentence = ""
        if not aux_anc.empty:
            row = aux_anc.iloc[0]
            anc_sentence = f" Para el índice auxiliar, la diferencia ajustada fue {fmt_num(row.get('b_grupo'),3)} puntos, IC 95 % [{fmt_num(row.get('ic_bajo'),2)}, {fmt_num(row.get('ic_alto'),2)}], p {fmt_p(row.get('p_grupo'))}."
        _pdf_explanation(
            canvas, .055, .13, .89, .17,
            "Qué debe interpretarse -y qué no",
            "La MSPSS oficial aumentó de 2.69 a 4.48 en el grupo experimental, mientras el control cambió mínimamente. "
            "El índice auxiliar permite análisis individuales, pero no equivale a la administración original de los 12 reactivos MSPSS; por ello se presenta como evidencia complementaria y no como una segunda puntuación del mismo instrumento."
            + anc_sentence,
            PALETTE[1],
        )
        pdf.savefig(fig)
        plt.close(fig)

        # ------------------------------------------------------------------
        # 5. WHOQOL-BREF + ANCOVA
        # ------------------------------------------------------------------
        fig, canvas = _pdf_page_base("WHOQOL-BREF: calidad de vida", "Cambios por dominio, ANCOVA y tamaño del efecto", master_hash, 5)
        if not who.empty:
            plot = who.copy()
            group_short = plot["grupo"].astype(str).map({"Experimental":"Exp.", "Control":"Ctrl."}).fillna(plot["grupo"].astype(str))
            domain_short = plot["dominio"].astype(str).replace({"Global descriptivo":"Global"})
            plot["etiqueta"] = domain_short + " - " + group_short
            plot["pct"] = pd.to_numeric(plot["cambio_pct"], errors="coerce") * 100
            plot = plot.dropna(subset=["pct"]).sort_values("pct")
            ax = fig.add_axes([.11, .39, .46, .42])
            colors = [PALETTE[0] if "Exp." in value else PALETTE[3] for value in plot["etiqueta"]]
            bars = ax.barh(plot["etiqueta"], plot["pct"], color=colors)
            ax.axvline(0, color="#888", linewidth=.7)
            ax.xaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:.0f}%"))
            _pdf_axis(ax, "Cambio porcentual por dominio", "")
            ax.bar_label(bars, fmt="%.1f%%", padding=2, fontsize=6.8)

        who_anc = ancova[ancova.get("resultado", pd.Series(dtype=str)).astype(str).str.startswith("WHOQOL")].copy()
        who_rows: list[list[str]] = []
        for _, row in who_anc.iterrows():
            result_name = str(row.get("resultado", ""))
            effect_match = effects[
                (effects.get("resultado", pd.Series(dtype=str)).astype(str) == result_name)
                & (effects.get("definicion", pd.Series(dtype=str)).astype(str) == "Postest E-C")
            ]
            d_value = fmt_num(effect_match.iloc[0].get("cohen_d"), 2) if not effect_match.empty else "-"
            who_rows.append([
                result_name.replace("WHOQOL ", ""),
                fmt_num(row.get("b_grupo"), 2),
                f"[{fmt_num(row.get('ic_bajo'),1)}, {fmt_num(row.get('ic_alto'),1)}]",
                fmt_p(row.get("p_grupo")),
                fmt_num(row.get("r2_aj"), 3),
                d_value,
            ])
        table_ax = fig.add_axes([.61, .40, .34, .39])
        _pdf_table(table_ax, ["Dominio", "Dif.", "IC 95 %", "p", "R²", "d"], who_rows, [.28,.13,.25,.11,.11,.10], 6.2)

        _pdf_explanation(
            canvas, .055, .105, .89, .19,
            "Interpretación",
            "Las mejoras más amplias del grupo experimental se observan en relaciones sociales y bienestar psicológico. "
            "Las ANCOVA por dominio controlan el valor basal y muestran diferencias ajustadas significativas. "
            "El índice global es una síntesis descriptiva del proyecto y no constituye un quinto dominio oficial del WHOQOL-BREF. "
            "Un cambio positivo representa una mejor percepción de calidad de vida.",
            PALETTE[0],
        )
        pdf.savefig(fig)
        plt.close(fig)

        # ------------------------------------------------------------------
        # 6. Uso y adherencia
        # ------------------------------------------------------------------
        fig, canvas = _pdf_page_base("Uso y adherencia", "Evolución durante las 18 semanas de intervención", master_hash, 6)
        active = weekly[weekly.get("estado", pd.Series(dtype=str)).astype(str).str.contains("Intervención", case=False, na=False)].copy() if not weekly.empty else pd.DataFrame()
        if not active.empty:
            active["semana"] = pd.to_numeric(active["periodo"], errors="coerce")
            active = active.dropna(subset=["semana"]).sort_values("semana")
            for idx, (column, title, color) in enumerate([("sesiones","Sesiones por semana",PALETTE[0]),("mensajes","Mensajes por semana",PALETTE[1])]):
                ax = fig.add_axes([.07, .52 - idx*.29, .60, .23])
                values = pd.to_numeric(active[column], errors="coerce")
                ax.plot(active["semana"], values, marker="o", linewidth=2.3, color=color)
                ax.fill_between(active["semana"], values, alpha=.12, color=color)
                ax.set_xticks(active["semana"].astype(int))
                _pdf_axis(ax, title, column.capitalize())

        _pdf_card(canvas, .72, .64, .22, .12, "Sesiones activas", fmt_count(parameters.get("sesiones ventana activa")), "Dentro de la intervención", PALETTE[0])
        _pdf_card(canvas, .72, .48, .22, .12, "Sesiones técnicas", fmt_count(parameters.get("sesiones técnicas totales")), "Incluye registros fuera de ventana", PALETTE[1])
        _pdf_card(canvas, .72, .32, .22, .12, "Mensajes técnicos", fmt_count(parameters.get("mensajes técnicos totales")), "Corpus completo", PALETTE[2])
        _pdf_card(canvas, .72, .16, .22, .12, "Continuidad histórica", fmt_num(indicators.get("continuidad histórica"),2), "Indicador agregado 0-100", PALETTE[3])

        _pdf_explanation(
            canvas, .055, .075, .61, .11,
            "Interpretación",
            "La actividad crece progresivamente hacia las últimas semanas, lo que refleja una adopción acumulativa del sistema. "
            "Las 1,325 sesiones corresponden a la ventana experimental; las 6,463 sesiones técnicas incluyen registros anteriores y posteriores, por lo que no deben confundirse.",
            PALETTE[1],
        )
        pdf.savefig(fig)
        plt.close(fig)

        # ------------------------------------------------------------------
        # 7. Spearman y regresión
        # ------------------------------------------------------------------
        fig, canvas = _pdf_page_base("Relación entre uso y resultados", "Spearman bilateral y regresión ajustada", master_hash, 7)
        experimental_usage = usage_individual[usage_individual.get("grupo", pd.Series(dtype=str)).astype(str) == "Experimental"].copy() if not usage_individual.empty else pd.DataFrame()
        ax = fig.add_axes([.07, .38, .45, .42])
        if not experimental_usage.empty:
            ax.scatter(pd.to_numeric(experimental_usage["mensajes"], errors="coerce"), pd.to_numeric(experimental_usage["mejora_estres"], errors="coerce"), alpha=.58, color=PALETTE[0], edgecolor="none")
            _pdf_axis(ax, "Mensajes y mejora del estrés", "Mejora del estrés")
            ax.set_xlabel("Mensajes por participante", fontsize=8)

        message_result = spearman_results[(spearman_results.get("muestra", pd.Series(dtype=str)).astype(str) == "Solo experimental") & (spearman_results.get("predictor", pd.Series(dtype=str)).astype(str) == "Mensajes")]
        if not message_result.empty:
            result = message_result.iloc[0]
            _pdf_card(canvas, .57, .66, .17, .12, "rho Spearman", fmt_num(result.get("rho"),4), "Mensajes vs. mejora", PALETTE[0])
            _pdf_card(canvas, .77, .66, .17, .12, "p bilateral", fmt_p(result.get("p")), f"N = {fmt_count(result.get('n'))}", PALETTE[1])

        coef = regression[pd.to_numeric(regression.get("coef", pd.Series(dtype=float)), errors="coerce").notna()].copy().head(5) if not regression.empty else pd.DataFrame()
        reg_ax = fig.add_axes([.57, .32, .37, .27])
        if not coef.empty and {"predictor","coef","ic_bajo","ic_alto"}.issubset(coef.columns):
            values = pd.to_numeric(coef["coef"], errors="coerce")
            lows = pd.to_numeric(coef["ic_bajo"], errors="coerce")
            highs = pd.to_numeric(coef["ic_alto"], errors="coerce")
            y = np.arange(len(coef))
            reg_ax.errorbar(values, y, xerr=[values-lows, highs-values], fmt="o", capsize=3, color=PALETTE[2], ecolor=PALETTE[1])
            reg_ax.axvline(0, linestyle="--", linewidth=.8, color="#888")
            reg_ax.set_yticks(y, coef["predictor"].astype(str))
            _pdf_axis(reg_ax, "Coeficientes de la regresión", "")

        _pdf_explanation(
            canvas, .055, .085, .89, .14,
            "Interpretación",
            "Dentro del grupo experimental, la asociación monotónica entre mensajes y mejora del estrés es cercana a cero y no significativa cuando p > 0.05. "
            "Esto significa que un mayor número de mensajes, por sí solo, no garantiza una mejoría mayor. La regresión incorpora simultáneamente frecuencia, continuidad, estrés basal y edad para distinguir sus aportaciones independientes.",
            PALETTE[2],
        )
        pdf.savefig(fig)
        plt.close(fig)

        # ------------------------------------------------------------------
        # 8. PLN: panorama y categorías
        # ------------------------------------------------------------------
        fig, canvas = _pdf_page_base("Analítica conversacional y PLN", "Resultados históricos y corpus operativo", master_hash, 8)
        hist = pln_official[pln_official.get("módulo", pd.Series(dtype=str)).astype(str) == "Histórico de tesis"] if not pln_official.empty else pd.DataFrame()
        oper = pln_official[pln_official.get("módulo", pd.Series(dtype=str)).astype(str) == "Operativo técnico"] if not pln_official.empty else pd.DataFrame()
        _pdf_card(canvas, .055, .72, .20, .12, "Corpus histórico", fmt_count(hist.iloc[0].get("registros") if not hist.empty else None), "9 categorías", PALETTE[0])
        _pdf_card(canvas, .275, .72, .20, .12, "Accuracy histórico", fmt_pct(hist.iloc[0].get("accuracy") if not hist.empty else None), "Evaluación de tesis", PALETTE[1])
        _pdf_card(canvas, .495, .72, .20, .12, "Corpus operativo", fmt_count(oper.iloc[0].get("registros") if not oper.empty else None), "7 categorías", PALETTE[2])
        _pdf_card(canvas, .715, .72, .20, .12, "Accuracy técnico", fmt_pct(oper.iloc[0].get("accuracy") if not oper.empty else None), "Control interno", PALETTE[3])

        frequency = pln_categories[pd.to_numeric(pln_categories.get("soporte", pd.Series(dtype=float)), errors="coerce") > 300].copy() if not pln_categories.empty else pd.DataFrame()
        ax = fig.add_axes([.08, .26, .52, .38])
        if not frequency.empty:
            frequency = frequency.sort_values("soporte")
            bars = ax.barh(frequency["categoria"].astype(str).str.replace("_"," "), pd.to_numeric(frequency["soporte"], errors="coerce"), color=PALETTE[1])
            _pdf_axis(ax, "Frecuencia operativa por categoría", "")
            ax.bar_label(bars, padding=2, fontsize=7)

        perf = pln_categories[(pd.to_numeric(pln_categories.get("soporte", pd.Series(dtype=float)), errors="coerce") <= 300) & pd.to_numeric(pln_categories.get("f1", pd.Series(dtype=float)), errors="coerce").notna()].copy() if not pln_categories.empty else pd.DataFrame()
        perf_rows = []
        for _, row in perf.iterrows():
            perf_rows.append([str(row.get("categoria","")).replace("_"," "), fmt_count(row.get("soporte")), fmt_num(row.get("precision"),3), fmt_num(row.get("recall"),3), fmt_num(row.get("f1"),3)])
        table_ax = fig.add_axes([.65, .27, .29, .36])
        _pdf_table(table_ax, ["Categoría", "N", "Prec.", "Recall", "F1"], perf_rows, [.36,.12,.16,.16,.14], 6.1)

        _pdf_explanation(
            canvas, .055, .085, .89, .115,
            "Interpretación",
            "La evaluación histórica de 1,020 casos y el corpus operativo de 6,463 registros son capas distintas. El accuracy histórico representa la evaluación científica reportada; el accuracy técnico describe un control interno del corpus operativo y no sustituye una validación externa independiente.",
            PALETTE[1],
        )
        pdf.savefig(fig)
        plt.close(fig)

        # ------------------------------------------------------------------
        # 9. Matriz de confusión
        # ------------------------------------------------------------------
        fig, canvas = _pdf_page_base("PLN: matriz de confusión", "Correspondencia entre etiqueta y predicción en el módulo operativo", master_hash, 9)
        if not pln_confusion.empty:
            label_col = pln_confusion.columns[0]
            numeric = pln_confusion.drop(columns=[label_col]).apply(pd.to_numeric, errors="coerce")
            ax = fig.add_axes([.08, .22, .58, .58])
            im = ax.imshow(numeric.to_numpy(), cmap="Purples")
            ax.set_xticks(range(len(numeric.columns)), [str(c).replace("_"," ") for c in numeric.columns], rotation=38, ha="right", fontsize=7)
            ax.set_yticks(range(len(pln_confusion)), pln_confusion[label_col].astype(str).str.replace("_"," "), fontsize=7)
            ax.set_xlabel("Predicción", fontsize=8); ax.set_ylabel("Etiqueta de referencia", fontsize=8)
            for i in range(numeric.shape[0]):
                for j in range(numeric.shape[1]):
                    value = numeric.iloc[i,j]
                    if not pd.isna(value):
                        ax.text(j, i, f"{int(value)}", ha="center", va="center", fontsize=6.8, color="white" if value > np.nanmax(numeric.to_numpy())*.5 else INK)
            fig.colorbar(im, ax=ax, fraction=.046, pad=.04)

        _pdf_explanation(
            canvas, .70, .46, .24, .28,
            "Cómo leerla",
            "Cada fila representa la categoría de referencia y cada columna la predicción del sistema. Los valores de la diagonal corresponden a clasificaciones coincidentes; los valores fuera de la diagonal muestran confusiones entre categorías.",
            PALETTE[0],
        )
        _pdf_explanation(
            canvas, .70, .19, .24, .20,
            "Alcance",
            "Esta matriz pertenece al módulo operativo reproducible. Debe leerse como control técnico y no como sustituto de la evaluación histórica con nueve categorías.",
            PALETTE[3],
        )
        pdf.savefig(fig)
        plt.close(fig)

        # ------------------------------------------------------------------
        # 10. Experiencia y usabilidad
        # ------------------------------------------------------------------
        fig, canvas = _pdf_page_base("Experiencia y usabilidad", "Indicadores agregados disponibles al cierre", master_hash, 10)
        exp_rows = []
        for _, row in experience.iterrows():
            exp_rows.append([
                str(row.get("variable", row.get("indicador", ""))),
                fmt_count(row.get("n")),
                fmt_num(row.get("media"),2),
                fmt_num(row.get("de"),2),
                fmt_num(row.get("mínimo", row.get("minimo")),2),
                fmt_num(row.get("máximo", row.get("maximo")),2),
            ])
        table_ax = fig.add_axes([.08, .42, .84, .34])
        _pdf_table(table_ax, ["Indicador", "N", "Media", "DE", "Mín.", "Máx."], exp_rows, [.38,.10,.12,.12,.12,.12])
        _pdf_explanation(
            canvas, .055, .15, .89, .18,
            "Interpretación y límite",
            "Los indicadores agregados permiten describir saturación inicial, expectativas, satisfacción, intención de continuidad y UTIL10. "
            "No se informa alfa de Cronbach ni análisis por reactivo de UTIL10, APOYO10 o EAPC12 porque las respuestas individuales por reactivo no se localizaron en la fuente primaria. Esta ausencia se conserva explícita para evitar estimaciones artificiales.",
            PALETTE[2],
        )
        pdf.savefig(fig)
        plt.close(fig)

        # ------------------------------------------------------------------
        # 11. Diseño, muestra y comparabilidad
        # ------------------------------------------------------------------
        fig, canvas = _pdf_page_base("Diseño y calidad metodológica", "Muestra, comparabilidad basal y criterios de análisis", master_hash, 11)
        flow_rows = []
        for _, row in sample_flow.head(8).iterrows():
            values = row.tolist()
            flow_rows.append([str(v) if not pd.isna(v) else "" for v in values[:4]])
        flow_ax = fig.add_axes([.06, .48, .42, .31])
        if flow_rows:
            _pdf_table(flow_ax, [str(c) for c in sample_flow.columns[:4]], flow_rows, None, 6.2)

        base_rows = []
        for _, row in baseline.head(10).iterrows():
            base_rows.append([
                str(row.get("variable","")),
                str(row.get("prueba","")),
                fmt_num(row.get("estadistico"),3),
                fmt_p(row.get("p")),
                fmt_num(row.get("efecto"),3),
            ])
        base_ax = fig.add_axes([.52, .42, .42, .37])
        if base_rows:
            _pdf_table(base_ax, ["Variable", "Prueba", "Estad.", "p", "Efecto"], base_rows, [.30,.26,.14,.13,.14], 6.0)

        _pdf_explanation(
            canvas, .055, .13, .89, .18,
            "Interpretación",
            "El diseño cuasi-experimental compara 281 participantes experimentales y 281 controles. La comparabilidad basal ayuda a verificar que los grupos no partían de diferencias relevantes. "
            "Las distribuciones sociodemográficas especialmente regulares se preservan como aparecen en la fuente y permanecen señaladas en el control de calidad; no fueron alteradas ni aleatorizadas.",
            PALETTE[0],
        )
        pdf.savefig(fig)
        plt.close(fig)

        # ------------------------------------------------------------------
        # 12. Cierre metodológico
        # ------------------------------------------------------------------
        fig, canvas = _pdf_page_base("Claves para la lectura del informe", "Alcances, restricciones y reproducibilidad", master_hash, 12)
        notes = [
            ("DASS-21", "Una reducción indica menor intensidad de estrés, ansiedad o depresión."),
            ("ANCOVA", "Compara los grupos en el postest controlando el nivel basal. El valor p informa significancia y R² ajustado la capacidad explicativa."),
            ("MSPSS", "Se conserva el resultado oficial agregado. El índice auxiliar individual es complementario y no equivale a los 12 reactivos MSPSS."),
            ("WHOQOL-BREF", "Los dominios oficiales son físico, psicológico, relaciones sociales y entorno. El global es descriptivo."),
            ("Spearman", "Rho mide asociación monotónica; p evalúa si la asociación observada es compatible con ausencia de relación."),
            ("PLN", "La evaluación histórica y el módulo operativo se mantienen separados para preservar trazabilidad."),
            ("Privacidad", "El PDF contiene únicamente resultados agregados y no permite reconstruir registros individuales."),
            ("Reproducibilidad", "La versión y el hash abreviado permanecen discretamente en el pie para control técnico."),
        ]
        for idx, (label, body) in enumerate(notes):
            col = idx % 2; row = idx // 2
            _pdf_explanation(canvas, .055 + col*.455, .72 - row*.155, .42, .12, label, body, PALETTE[idx % len(PALETTE)])
        pdf.savefig(fig)
        plt.close(fig)

    buffer.seek(0)
    return buffer.getvalue()


payload = load_dashboard_data()
frames: dict[str, pd.DataFrame] = payload["frames"]
params = parameter_map(frames.get("parameters", pd.DataFrame()))
usage_map = indicator_map(frames.get("usage_official", pd.DataFrame()))
ALLOW_AUDIT = bool_env("DASHBOARD_AUDIT_MODE")

if payload["errors"]:
    st.error("El dashboard no puede garantizar consistencia porque faltan datos del maestro.")
    for error in payload["errors"]:
        st.code(error)
    st.stop()

with st.sidebar:
    logo = ASSETS_DIR / "logo_full.png"
    if logo.exists():
        st.image(str(logo), use_container_width=True)
    st.caption("Panel científico · Documento Maestro Oficial v3")
    st.caption(f"Versión activa: {BUILD_ID}")
    st.success("Fuente canónica cargada")
    page = st.radio(
        "Navegación",
        [
            "Resumen ejecutivo",
            "DASS-21",
            "MSPSS y apoyo",
            "WHOQOL-BREF",
            "Uso y adherencia",
            "Correlaciones y regresión",
            "Analítica conversacional y PLN",
            "Experiencia y usabilidad",
            "Sociodemografía",
            "Metodología y calidad",
            "Informe PDF",
        ],
    )
    audit_mode = st.toggle("Auditoría interna", value=False, disabled=not ALLOW_AUDIT)
    if not ALLOW_AUDIT:
        st.caption("La vista individual está deshabilitada en el despliegue público.")
    if st.button("Actualizar datos", use_container_width=True):
        clear_dashboard_cache()
        st.rerun()

st.markdown(
    """
    <div class="ng-hero">
      <div class="ng-kicker">neuroguIA · investigación aplicada</div>
      <div class="ng-title">Dashboard científico de resultados</div>
      <div class="ng-subtitle">Todas las tarjetas, tablas y gráficas se derivan del Documento Maestro Oficial v3 auditado. Los resultados históricos, los datos verificables y los módulos pendientes se presentan por separado.</div>
    </div>
    """,
    unsafe_allow_html=True,
)

if payload["warnings"]:
    with st.expander("Advertencias de consistencia detectadas"):
        for warning in payload["warnings"]:
            st.warning(warning)

# --------------------------- RESUMEN ---------------------------
if page == "Resumen ejecutivo":
    dass = frames["dass_summary"]
    stress = dass[(dass["resultado"] == "Estrés") & (dass["grupo"] == "Experimental")].iloc[0]
    mspss = frames["mspss_official"]
    mspss_exp = mspss[mspss["grupo"] == "Experimental"].iloc[0]
    who = frames["whoqol_summary"]
    who_global = who[(who["dominio"] == "Global descriptivo") & (who["grupo"] == "Experimental")].iloc[0]
    pln = frames["pln_official"]
    pln_hist = pln[pln["módulo"] == "Histórico de tesis"].iloc[0]

    cards = [
        ("Participantes", fmt_count(params.get("n total")), "281 experimental + 281 control"),
        ("Familias analíticas", fmt_count(params.get("familias")), "crosswalk WHOQOL–PT–FAM validado"),
        ("Intervención", "18 semanas", "12 ene–17 may 2026"),
        ("Sesiones en intervención", fmt_count(params.get("sesiones ventana activa")), "ventana metodológica activa"),
        ("Sesiones técnicas", fmt_count(params.get("sesiones técnicas totales")), "corpus completo; incluye fuera de ventana"),
        ("Mensajes técnicos", fmt_count(params.get("mensajes técnicos totales")), "corpus completo"),
        ("Reducción de estrés", fmt_pct(stress["cambio_pct"]), "grupo experimental; H1 aceptada"),
        ("Incremento MSPSS", fmt_pct(mspss_exp["cambio_pct"], signed=True), "resultado oficial agregado"),
        ("WHOQOL global", fmt_pct(who_global["cambio_pct"], signed=True), "cambio experimental"),
        ("Accuracy histórico PLN", fmt_pct(pln_hist["accuracy"]), "1,020 registros; 9 categorías"),
        ("Engagement histórico", fmt_num(usage_map.get("engagement histórico"), 2), "indicador agregado 0–100"),
        ("Continuidad histórica", fmt_num(usage_map.get("continuidad histórica"), 2), "indicador agregado 0–100"),
    ]
    cols = st.columns(4)
    for i, card in enumerate(cards):
        with cols[i % 4]:
            kpi(*card)

    section("Hallazgo principal")
    anc = frames["ancova"]
    stress_anc = anc[anc["resultado"] == "Estrés"].iloc[0]
    effect = frames["effects"]
    stress_effect = effect[(effect["resultado"] == "Estrés") & (effect["definicion"] == "Postest E-C")].iloc[0]
    st.markdown(
        f"<div class='ng-callout'>El grupo experimental redujo el estrés en <strong>{fmt_pct(stress['cambio_pct'])}</strong>. "
        f"La diferencia ajustada por el nivel basal fue de <strong>{fmt_num(stress_anc['b_grupo'], 2)} puntos</strong> "
        f"(p {fmt_p(stress_anc['p_grupo'])}) y el tamaño del efecto postest fue <strong>|d| = {fmt_num(abs(stress_effect['cohen_d']), 3)}</strong>. "
        f"El cambio superó el umbral de 15%; por tanto, <strong>se acepta H1</strong>.</div>",
        unsafe_allow_html=True,
    )
    source_note("M06_DASS_RESUMEN", "M07_ANCOVA", "M08_EFECTOS")

    c1, c2 = st.columns(2)
    with c1:
        section("Cambios DASS-21")
        percent_change_chart(dass, "resultado", "Cambio porcentual por dimensión y grupo")
    with c2:
        section("Cambios WHOQOL-BREF")
        percent_change_chart(who, "dominio", "Cambio porcentual por dominio y grupo")

    st.info("El total técnico de 6,463 sesiones no equivale a las sesiones ocurridas dentro de las 18 semanas. El dashboard conserva ambas cifras con su definición correspondiente.")

# --------------------------- DASS ---------------------------
elif page == "DASS-21":
    dass = frames["dass_summary"]
    variable = st.selectbox("Dimensión", dass["resultado"].dropna().unique().tolist())
    prepost_chart(dass, "resultado", variable, f"{variable}: pretest y postest por grupo")
    selected = dass[dass["resultado"] == variable].copy()
    selected = order_groups(selected)
    show = clean_table(selected, ["grupo","n","pre_media","pre_de","post_media","post_de","cambio_favorable","cambio_pct","estado"], {
        "grupo":"Grupo","n":"N","pre_media":"Pre media","pre_de":"Pre DE","post_media":"Post media","post_de":"Post DE",
        "cambio_favorable":"Cambio favorable","cambio_pct":"Cambio %","estado":"Origen del cálculo"
    })
    show = format_columns(
        show,
        decimals={"Pre media":2, "Pre DE":2, "Post media":2, "Post DE":2, "Cambio favorable":2},
        signed_percent_columns=["Cambio %"],
        count_columns=["N"],
    )
    show_table(show)

    section("ANCOVA ajustada")
    anc = frames["ancova"]
    anc_row = anc[anc["resultado"] == variable]
    if not anc_row.empty:
        row = anc_row.iloc[0]
        cols = st.columns(5)
        values = [
            ("Diferencia ajustada", fmt_num(row["b_grupo"], 3), "experimental − control"),
            ("IC 95 %", f"{fmt_num(row['ic_bajo'],2)} a {fmt_num(row['ic_alto'],2)}", "coeficiente de grupo"),
            ("p de grupo", fmt_p(row["p_grupo"]), "errores robustos HC3"),
            ("R² ajustado", fmt_num(row["r2_aj"], 3), "capacidad explicativa"),
            ("Interacción grupo×pre", fmt_p(row["p_interaccion"]), "homogeneidad de pendientes"),
        ]
        for i, item in enumerate(values):
            with cols[i]: kpi(*item)

    section("Tamaños del efecto")
    eff = frames["effects"]
    eff_var = eff[eff["resultado"] == variable].copy()
    eff_var["etiqueta"] = eff_var["definicion"]
    forest_chart(eff_var, "etiqueta", "cohen_d", "ic_bajo", "ic_alto", f"{variable}: Cohen’s d e IC 95%")
    st.markdown(
        "<div class='ng-small-note'>En el contraste postest, un valor negativo indica puntuaciones menores en el grupo experimental. "
        "En el cambio favorable, un valor positivo indica una mejoría mayor en el grupo experimental.</div>",
        unsafe_allow_html=True,
    )
    effect_table = clean_table(eff_var, ["definicion","cohen_d","hedges_g","ic_bajo","ic_alto"], {
        "definicion":"Definición","cohen_d":"Cohen’s d","hedges_g":"Hedges g","ic_bajo":"IC 95 % inferior","ic_alto":"IC 95 % superior"
    })
    effect_table = format_columns(
        effect_table,
        decimals={"Cohen’s d":3, "Hedges g":3, "IC 95 % inferior":3, "IC 95 % superior":3},
    )
    show_table(effect_table)

    with st.expander("Supuestos, normalidad y pruebas no paramétricas"):
        assumptions = clean_table(
            frames["ancova_assumptions"][frames["ancova_assumptions"]["resultado"] == variable],
            rename={
                "resultado":"Resultado", "n":"N", "b_grupo":"Diferencia ajustada", "se_hc3":"EE robusto HC3",
                "ic_bajo":"IC 95 % inferior", "ic_alto":"IC 95 % superior", "p_grupo":"p del grupo",
                "b_pre":"Coeficiente basal", "r2":"R²", "r2_aj":"R² ajustado",
                "b_interaccion":"Interacción grupo × pretest", "p_interaccion":"p interacción",
                "shapiro_w":"Shapiro W", "shapiro_p":"p Shapiro", "levene":"Levene", "levene_p":"p Levene",
            },
        )
        assumptions = format_columns(
            assumptions,
            decimals={
                "Diferencia ajustada":3, "EE robusto HC3":3, "IC 95 % inferior":3, "IC 95 % superior":3,
                "Coeficiente basal":3, "R²":3, "R² ajustado":3, "Interacción grupo × pretest":3,
                "Shapiro W":3, "Levene":3,
            },
            p_columns=["p del grupo", "p interacción", "p Shapiro", "p Levene"],
            count_columns=["N"],
        )
        show_table(assumptions)

        normal = frames["normality"]
        mask = normal.astype(str).apply(lambda c: c.str.contains(variable, case=False, na=False)).any(axis=1)
        normal_show = clean_table(normal[mask], rename={
            "resultado":"Resultado", "grupo":"Grupo", "momento":"Momento", "shapiro_w":"Shapiro W", "p":"p"
        })
        normal_show = format_columns(normal_show, decimals={"Shapiro W":4}, p_columns=["p"])
        show_table(normal_show)

        nonp = frames["nonparametric"]
        mask = nonp.astype(str).apply(lambda c: c.str.contains(variable, case=False, na=False)).any(axis=1)
        nonp_show = clean_table(nonp[mask], rename={
            "resultado":"Resultado", "comparacion":"Comparación", "prueba":"Prueba",
            "estadistico":"Estadístico", "p":"p", "r":"Tamaño del efecto r",
        })
        nonp_show = format_columns(
            nonp_show,
            decimals={"Estadístico":3, "Tamaño del efecto r":3},
            p_columns=["p"],
        )
        show_table(nonp_show)
        st.caption("Interpretación: la homogeneidad de pendientes se considera cumplida cuando p de la interacción > 0.05. Los errores robustos HC3 reducen el impacto de la heterocedasticidad.")
    source_note("M05_DASS_PREPOST", "M06_DASS_RESUMEN", "M07_ANCOVA", "M31_NO_PARAMETRICAS")

# --------------------------- MSPSS / APOYO ---------------------------
elif page == "MSPSS y apoyo":
    st.markdown(
        "<div class='ng-method-note'><strong>MSPSS oficial agregado.</strong> Corresponde al instrumento principal de apoyo social percibido. "
        "La fuente recuperada conserva los resultados por grupo, pero no la matriz individual de los 12 reactivos.</div>",
        unsafe_allow_html=True,
    )
    mspss = order_groups(frames["mspss_official"].copy())
    fig, ax = plt.subplots(figsize=(9.4, 4.35), dpi=145)
    x = np.arange(len(mspss)); width=.34
    b1=ax.bar(x-width/2, pd.to_numeric(mspss["pre_1_5"]), width, label="Pretest", color=PALETTE[0])
    b2=ax.bar(x+width/2, pd.to_numeric(mspss["post_1_5"]), width, label="Postest", color=PALETTE[1])
    ax.set_xticks(x, mspss["grupo"]); ax.set_ylim(0,5)
    base_axes(ax, "MSPSS oficial agregado", "Escala 1–5"); ax.legend(frameon=False)
    ax.bar_label(b1,fmt="%.2f",padding=3); ax.bar_label(b2,fmt="%.2f",padding=3)
    fig.tight_layout(); st.pyplot(fig,use_container_width=True); plt.close(fig)
    show = clean_table(mspss, rename={
        "grupo":"Grupo", "n":"N", "pre_1_5":"Pretest", "post_1_5":"Postest",
        "cambio":"Cambio", "cambio_pct":"Cambio %", "estatus":"Estatus",
    })
    show = format_columns(
        show,
        decimals={"Pretest":2, "Postest":2, "Cambio":2},
        signed_percent_columns=["Cambio %"],
        count_columns=["N"],
    )
    show_table(show)

    section("Índice auxiliar de apoyo individual")
    st.markdown(
        "<div class='ng-method-note'><strong>Indicador auxiliar individual.</strong> Esta variable complementaria permite análisis por participante, "
        "pero no equivale a la administración original de la MSPSS ni debe interpretarse como una segunda puntuación del mismo instrumento.</div>",
        unsafe_allow_html=True,
    )
    support = frames["support_individual"].copy()
    summary = support.groupby("grupo", as_index=False).agg(
        n=("participant_id","count"), pre=("apoyo_pre_1_5","mean"), post=("apoyo_post_1_5","mean"), cambio=("mejora_apoyo","mean")
    )
    summary["cambio_pct"] = np.where(summary["pre"] != 0, summary["cambio"] / summary["pre"], np.nan)
    summary = order_groups(summary)
    fig, ax = plt.subplots(figsize=(9.4,4.35),dpi=145)
    x=np.arange(len(summary)); width=.34
    b1=ax.bar(x-width/2,summary["pre"],width,label="Pretest",color=PALETTE[2]); b2=ax.bar(x+width/2,summary["post"],width,label="Postest",color=PALETTE[1])
    ax.set_xticks(x,summary["grupo"]); ax.set_ylim(0,5); base_axes(ax,"Apoyo auxiliar: pretest y postest","Escala 1–5"); ax.legend(frameon=False)
    ax.bar_label(b1,fmt="%.2f",padding=3); ax.bar_label(b2,fmt="%.2f",padding=3); fig.tight_layout(); st.pyplot(fig,use_container_width=True); plt.close(fig)
    show = clean_table(summary, rename={
        "grupo":"Grupo", "n":"N", "pre":"Pretest", "post":"Postest", "cambio":"Cambio", "cambio_pct":"Cambio %",
    })
    show = format_columns(
        show,
        decimals={"Pretest":2, "Postest":2, "Cambio":2},
        signed_percent_columns=["Cambio %"],
        count_columns=["N"],
    )
    show_table(show)

    anc = frames["ancova"]
    row = anc[anc["resultado"] == "Apoyo auxiliar 1-5"].iloc[0]
    cols=st.columns(4)
    for i,item in enumerate([
        ("Diferencia ajustada",fmt_num(row["b_grupo"],3),"experimental − control"),
        ("IC 95 %",f"{fmt_num(row['ic_bajo'],2)} a {fmt_num(row['ic_alto'],2)}","coeficiente"),
        ("p",fmt_p(row["p_grupo"]),"ANCOVA HC3"),
        ("R² ajustado",fmt_num(row["r2_aj"],3),"modelo"),
    ]):
        with cols[i]: kpi(*item)
    source_note("M09_MSPSS_OFICIAL", "M10_APOYO_AUXILIAR", "M07_ANCOVA")

# --------------------------- WHOQOL ---------------------------
elif page == "WHOQOL-BREF":
    who = frames["whoqol_summary"]
    domain = st.selectbox("Dominio", who["dominio"].dropna().unique().tolist())
    prepost_chart(who, "dominio", domain, f"WHOQOL-BREF · {domain}")
    section("Cambios por dominio")
    percent_change_chart(who, "dominio", "WHOQOL-BREF: cambio porcentual por grupo")

    section("ANCOVA por dominio")
    anc = frames["ancova"]
    who_anc = anc[anc["resultado"].astype(str).str.startswith("WHOQOL")].copy()
    who_anc["IC 95 %"] = who_anc.apply(
        lambda row: f"[{fmt_num(row.get('ic_bajo'), 2)}, {fmt_num(row.get('ic_alto'), 2)}]",
        axis=1,
    )
    who_table = clean_table(
        who_anc,
        ["resultado","b_grupo","IC 95 %","p_grupo","r2_aj","p_interaccion","levene_p"],
        {
            "resultado":"Dominio",
            "b_grupo":"Diferencia ajustada",
            "p_grupo":"p del grupo",
            "r2_aj":"R² ajustado",
            "p_interaccion":"p interacción",
            "levene_p":"p Levene",
        },
    )
    who_table = format_columns(
        who_table,
        decimals={"Diferencia ajustada":3, "R² ajustado":3},
        p_columns=["p del grupo", "p interacción", "p Levene"],
    )
    show_table(who_table)
    section("Tamaños del efecto WHOQOL")
    eff = frames["effects"]
    who_eff = eff[eff["resultado"].astype(str).str.startswith("WHOQOL") & (eff["definicion"] == "Postest E-C")].copy()
    forest_chart(who_eff, "resultado", "cohen_d", "ic_bajo", "ic_alto", "WHOQOL-BREF: Cohen’s d postest")
    who_eff_table = clean_table(
        who_eff,
        ["resultado","cohen_d","hedges_g","ic_bajo","ic_alto"],
        {
            "resultado":"Dominio", "cohen_d":"Cohen’s d", "hedges_g":"Hedges g",
            "ic_bajo":"IC 95 % inferior", "ic_alto":"IC 95 % superior",
        },
    )
    who_eff_table = format_columns(
        who_eff_table,
        decimals={"Cohen’s d":3, "Hedges g":3, "IC 95 % inferior":3, "IC 95 % superior":3},
    )
    show_table(who_eff_table)

    if audit_mode:
        with st.expander("Puntuaciones anonimizadas por participante"):
            show_table(frames["whoqol_scores"].head(562))
        with st.expander("Crosswalk WHOQOL ↔ PT ↔ FAM"):
            show_table(frames["id_crosswalk"])
    source_note("M11_WHOQOL_ITEMS", "M12A_WHOQOL_PUNTAJES", "M12_WHOQOL_RESUMEN", "M24_ID_CROSSWALK")

# --------------------------- USO ---------------------------
elif page == "Uso y adherencia":
    cards = [
        ("Participantes con uso",fmt_count(usage_map.get("participantes con uso vinculado")),"grupo experimental"),
        ("Sesiones en 18 semanas",fmt_count(usage_map.get("sesiones en 18 semanas")),"12 ene–17 may"),
        ("Sesiones de cierre",fmt_count(usage_map.get("sesiones postest/cierre")),"18–21 may"),
        ("Sesiones técnicas",fmt_count(usage_map.get("sesiones técnicas totales")),"corpus completo"),
        ("Mensajes técnicos",fmt_count(usage_map.get("mensajes técnicos totales")),"corpus completo"),
        ("Duración técnica",f"{fmt_num(usage_map.get('duración técnica media'),2)} min","promedio por sesión"),
        ("Engagement",fmt_num(usage_map.get("engagement histórico"),2),"histórico agregado"),
        ("Continuidad",fmt_num(usage_map.get("continuidad histórica"),2),"histórico agregado"),
    ]
    cols=st.columns(4)
    for i,item in enumerate(cards):
        with cols[i%4]: kpi(*item)

    weekly=frames["usage_weekly"]
    c1,c2=st.columns(2)
    with c1: weekly_chart(weekly,"sesiones","Sesiones por semana","Sesiones")
    with c2: weekly_chart(weekly,"mensajes","Mensajes por semana","Mensajes")
    weekly_active = weekly[weekly["estado"].astype(str).str.contains("Intervención",case=False,na=False)].copy()
    weekly_show = clean_table(
        weekly_active,
        ["periodo","inicio","fin","sesiones","mensajes","duracion_total","familias_uuid","estado"],
        {
            "periodo":"Semana", "inicio":"Inicio", "fin":"Fin", "sesiones":"Sesiones", "mensajes":"Mensajes",
            "duracion_total":"Duración total", "familias_uuid":"Familias activas", "estado":"Periodo",
        },
    )
    weekly_show = format_columns(
        weekly_show,
        decimals={"Duración total":1},
        count_columns=["Semana","Sesiones","Mensajes","Familias activas"],
    )
    show_table(weekly_show)

    section("Distribución horaria técnica")
    bands=frames["time_bands"].copy()
    fig,ax=plt.subplots(figsize=(10,4.6),dpi=145)
    bars=ax.bar(bands["franja"],pd.to_numeric(bands["sesiones_técnicas"]),color=PALETTE[:4])
    base_axes(ax,"Sesiones por franja horaria","Sesiones técnicas"); ax.bar_label(bars,fmt="%d",padding=3); fig.tight_layout(); st.pyplot(fig,use_container_width=True); plt.close(fig)
    show = clean_table(
        bands,
        ["franja","sesiones_técnicas","proporción","estatus"],
        {"franja":"Franja horaria","sesiones_técnicas":"Sesiones técnicas","proporción":"Proporción","estatus":"Origen"},
    )
    show = format_columns(show, percent_columns=["Proporción"], count_columns=["Sesiones técnicas"])
    show_table(show)

    section("Adherencia individual")
    usage=frames["usage_participant"]
    exp=usage[usage["grupo"]=="Experimental"].copy()
    c1,c2=st.columns(2)
    with c1:
        counts=exp["adherencia"].value_counts().reindex(["Baja","Media-baja","Media-alta","Alta"]).dropna()
        fig,ax=plt.subplots(figsize=(7,4.4),dpi=145); bars=ax.bar(counts.index,counts.values,color=PALETTE[:len(counts)])
        base_axes(ax,"Participantes por nivel de adherencia","Participantes"); ax.bar_label(bars,padding=3); fig.tight_layout(); st.pyplot(fig,use_container_width=True); plt.close(fig)
    with c2:
        fig,ax=plt.subplots(figsize=(7,4.4),dpi=145); ax.hist(pd.to_numeric(exp["mensajes"],errors="coerce").dropna(),bins=12,color=PALETTE[0],alpha=.85)
        base_axes(ax,"Distribución de mensajes por participante","Participantes"); ax.set_xlabel("Mensajes"); fig.tight_layout(); st.pyplot(fig,use_container_width=True); plt.close(fig)
    if audit_mode:
        with st.expander("Datos individuales de uso"):
            show_table(exp)
    source_note("M14_USO_OFICIAL", "M14A_USO_PARTICIPANTE", "M14B_USO_SEMANAL", "M16_FRANJAS_HORARIAS")

# --------------------------- CORRELACIÓN / REGRESIÓN ---------------------------
elif page == "Correlaciones y regresión":
    st.info("Spearman se añade como análisis complementario; no sustituye ANCOVA, tamaños del efecto, regresión ni métricas del clasificador.")
    usage = frames["usage_participant"].copy()
    corr_calculated = calculate_spearman_results(usage)
    corr_canonical = frames["correlations"].copy()
    corr = corr_calculated if not corr_calculated.empty else corr_canonical

    section("Correlación de Spearman: coeficiente ρ y significancia p")

    key_rows = corr[
        corr["predictor"].astype(str).isin(["Mensajes", "messages"])
    ].copy()
    total_row = key_rows[key_rows["muestra"].astype(str) == "Muestra total"]
    exp_row = key_rows[key_rows["muestra"].astype(str) == "Solo experimental"]

    c1, c2, c3, c4 = st.columns(4)
    if not total_row.empty:
        value = total_row.iloc[0]
        with c1:
            kpi("ρ Spearman · muestra total", fmt_num(value["rho"], 4), "mensajes vs. mejora del estrés")
        with c2:
            kpi("p Spearman · muestra total", fmt_p(value["p"]), f"N = {fmt_count(value['n'])}")
    if not exp_row.empty:
        value = exp_row.iloc[0]
        with c3:
            kpi("ρ Spearman · experimental", fmt_num(value["rho"], 4), "mensajes vs. mejora del estrés")
        with c4:
            kpi("p Spearman · experimental", fmt_p(value["p"]), f"N = {fmt_count(value['n'])}")

    show = clean_table(
        corr,
        ["muestra","predictor","resultado","rho","p","n","valores_unicos","origen"],
        {
            "muestra":"Muestra", "predictor":"Predictor", "resultado":"Resultado",
            "rho":"ρ de Spearman", "p":"p bilateral", "n":"N",
            "valores_unicos":"Valores únicos", "origen":"Origen del cálculo",
        },
    )
    show = format_columns(
        show,
        decimals={"ρ de Spearman":4},
        p_columns=["p bilateral"],
        count_columns=["N","Valores únicos"],
    )
    show_table(show)
    st.warning(
        "La correlación de la muestra total está influida por la exposición cero del grupo control. "
        "Para evaluar una posible relación dosis–respuesta debe priorizarse el grupo experimental. "
        "En este grupo, mensajes y mejora del estrés muestran ρ = 0.0208 y p = 0.728, "
        "por lo que no se observa una asociación monotónica estadísticamente significativa."
    )

    exp=usage[usage["grupo"]=="Experimental"].copy()
    fig,ax=plt.subplots(figsize=(9.6,5),dpi=145)
    ax.scatter(pd.to_numeric(exp["mensajes"]),pd.to_numeric(exp["mejora_estres"]),alpha=.62,color=PALETTE[0],edgecolor="none")
    base_axes(ax,"Mensajes y mejora del estrés · grupo experimental","Mejora del estrés")
    ax.set_xlabel("Mensajes por participante")
    row_match = corr[
        (corr["muestra"].astype(str) == "Solo experimental")
        & (corr["predictor"].astype(str).isin(["Mensajes", "messages"]))
    ]
    if not row_match.empty:
        row = row_match.iloc[0]
        ax.text(
            .02, .96,
            f"ρ de Spearman = {fmt_num(row['rho'],4)} · p = {fmt_p(row['p'])}",
            transform=ax.transAxes, va="top", fontsize=10, color=INK,
        )
    fig.tight_layout(); st.pyplot(fig,use_container_width=True); plt.close(fig)

    section("Regresión ajustada")
    reg=frames["regression"].copy()
    coef=reg[pd.to_numeric(reg["coef"],errors="coerce").notna()].copy().head(5)
    coef["coef"] = pd.to_numeric(coef["coef"]); coef["ic_bajo"] = pd.to_numeric(coef["ic_bajo"]); coef["ic_alto"] = pd.to_numeric(coef["ic_alto"])
    forest_chart(coef,"predictor","coef","ic_bajo","ic_alto","Predictores de la mejora del estrés")
    reg_table = clean_table(coef,["predictor","coef","se_hc3","ic_bajo","ic_alto","p"],{
        "predictor":"Predictor","coef":"Coeficiente","se_hc3":"EE robusto HC3",
        "ic_bajo":"IC 95 % inferior","ic_alto":"IC 95 % superior","p":"p"
    })
    reg_table = format_columns(
        reg_table,
        decimals={
            "Coeficiente":4, "EE robusto HC3":4,
            "IC 95 % inferior":4, "IC 95 % superior":4,
        },
        p_columns=["p"],
    )
    show_table(reg_table)
    r2row=reg[reg["predictor"].astype(str)=="R²"]
    adjrow=reg[reg["predictor"].astype(str)=="R² ajustado"]
    c1,c2=st.columns(2)
    with c1: kpi("R²",fmt_num(r2row.iloc[0]["coef"],4) if not r2row.empty else "—","modelo experimental")
    with c2: kpi("R² ajustado",fmt_num(adjrow.iloc[0]["coef"],4) if not adjrow.empty else "—","modelo experimental")
    source_note("M14C_CORRELACIONES", "M14D_REGRESION_USO", "M14A_USO_PARTICIPANTE")

# --------------------------- PLN ---------------------------
elif page == "Analítica conversacional y PLN":
    official=frames["pln_official"]
    hist=official[official["módulo"]=="Histórico de tesis"].iloc[0]
    oper=official[official["módulo"]=="Operativo técnico"].iloc[0]
    cols=st.columns(4)
    for i,item in enumerate([
        ("Corpus histórico",fmt_count(hist["registros"]),"9 categorías"),
        ("Accuracy histórico",fmt_pct(hist["accuracy"]),"evaluación de tesis"),
        ("Corpus operativo",fmt_count(oper["registros"]),"7 categorías"),
        ("Accuracy técnico",fmt_pct(oper["accuracy"]),"control interno; no validación externa"),
    ]):
        with cols[i]: kpi(*item)
    st.info("El módulo histórico de 1,020 casos y el corpus operativo de 6,463 registros corresponden a capas distintas. No se combinan en una sola métrica.")

    cat=frames["pln_categories"].copy()
    perf=cat[(pd.to_numeric(cat["soporte"],errors="coerce")<=300) & pd.to_numeric(cat["f1"],errors="coerce").notna()].copy()
    freq=cat[pd.to_numeric(cat["soporte"],errors="coerce")>300].copy()
    if not freq.empty:
        freq= freq.rename(columns={"soporte":"frecuencia","precision":"proporción"})
        fig,ax=plt.subplots(figsize=(10,5),dpi=145); freq=freq.sort_values("frecuencia")
        bars=ax.barh(freq["categoria"],pd.to_numeric(freq["frecuencia"]),color=PALETTE[1])
        base_axes(ax,"Frecuencia observada por categoría","Registros"); ax.bar_label(bars,padding=3); fig.tight_layout(); st.pyplot(fig,use_container_width=True); plt.close(fig)
        show=freq[["categoria","frecuencia","proporción"]].copy(); show["proporción"]=show["proporción"].map(fmt_pct); show_table(show)

    section("Rendimiento técnico por categoría")
    perf_show = clean_table(
        perf,
        ["categoria","soporte","precision","recall","f1"],
        {
            "categoria":"Categoría", "soporte":"Soporte", "precision":"Precisión",
            "recall":"Sensibilidad", "f1":"F1",
        },
    )
    perf_show = format_columns(
        perf_show,
        decimals={"Precisión":3, "Sensibilidad":3, "F1":3},
        count_columns=["Soporte"],
    )
    show_table(perf_show)
    section("Matriz de confusión")
    conf=frames["pln_confusion"].copy()
    if not conf.empty:
        label_col=conf.columns[0]; numeric=conf.drop(columns=[label_col]).apply(pd.to_numeric,errors="coerce")
        fig,ax=plt.subplots(figsize=(8,6.4),dpi=145); im=ax.imshow(numeric.to_numpy(),cmap="Purples")
        ax.set_xticks(range(len(numeric.columns)),numeric.columns,rotation=45,ha="right",fontsize=8)
        ax.set_yticks(range(len(conf)),conf[label_col].astype(str),fontsize=8)
        ax.set_xlabel("Predicción"); ax.set_ylabel("Etiqueta"); ax.set_title("Matriz de confusión operativa",loc="left",fontweight="bold",color=INK)
        for i in range(numeric.shape[0]):
            for j in range(numeric.shape[1]):
                value=numeric.iloc[i,j]
                if not pd.isna(value): ax.text(j,i,f"{int(value)}",ha="center",va="center",fontsize=7)
        fig.colorbar(im,ax=ax,fraction=.046,pad=.04); fig.tight_layout(); st.pyplot(fig,use_container_width=True); plt.close(fig)
    source_note("M17_PLN_OFICIAL", "M17A_PLN_CORPUS", "M17C_PLN_CONFUSION", "M17D_PLN_CATEGORIAS")

# --------------------------- EXPERIENCIA ---------------------------
elif page == "Experiencia y usabilidad":
    summary=frames["experience_summary"].copy()
    summary_show = clean_table(
        summary,
        rename={
            "variable":"Indicador", "n":"N", "media":"Media", "de":"DE",
            "mínimo":"Mínimo", "minimo":"Mínimo", "máximo":"Máximo", "maximo":"Máximo",
            "alfa":"Alfa de Cronbach", "estado":"Estado",
        },
    )
    summary_show = format_columns(
        summary_show,
        decimals={"Media":2, "DE":2, "Mínimo":2, "Máximo":2},
        count_columns=["N"],
    )
    show_table(summary_show)
    scores=frames["experience_scores"].copy()
    variables=[c for c in ["saturacion_pre","expectativas_pre","satisfaccion_post","intencion_continuidad","util10_agregado"] if c in scores.columns]
    selected=st.selectbox("Indicador",variables,format_func=lambda x:x.replace("_"," ").title())
    fig,ax=plt.subplots(figsize=(9.5,4.8),dpi=145)
    ax.hist(pd.to_numeric(scores[selected],errors="coerce").dropna(),bins=12,color=PALETTE[2],alpha=.86)
    base_axes(ax,f"Distribución de {selected.replace('_',' ')}","Participantes"); ax.set_xlabel("Puntuación"); fig.tight_layout(); st.pyplot(fig,use_container_width=True); plt.close(fig)
    st.warning("No se muestra alfa de Cronbach ni análisis por reactivo para UTIL10, APOYO10 o EAPC12 porque las respuestas individuales por reactivo no se localizaron en las fuentes recuperadas.")
    if audit_mode:
        with st.expander("Puntajes agregados por participante"):
            show_table(scores)
    source_note("M13_EXPERIENCIA_POST", "M13A_EXPERIENCIA_PUNTAJES", "M34_DATOS_FALTANTES")

# --------------------------- SOCIO ---------------------------
elif page == "Sociodemografía":
    socio=frames["socio_descriptives"].copy()
    variables=socio["variable"].dropna().unique().tolist()
    selected=st.selectbox("Variable sociodemográfica",variables)
    selected_df=socio[socio["variable"]==selected]
    grouped_category_chart(selected_df,"categoria","grupo","porcentaje",f"{selected}: distribución por grupo",percent=True)
    show = clean_table(
        selected_df,
        ["variable","categoria","grupo","n","porcentaje"],
        {"variable":"Variable","categoria":"Categoría","grupo":"Grupo","n":"N","porcentaje":"Porcentaje"},
    )
    show = format_columns(show, percent_columns=["Porcentaje"], count_columns=["N"])
    show_table(show)

    section("Comparabilidad basal")
    comp=frames["baseline_comparability"].copy()
    display=clean_table(comp,["variable","prueba","estadistico","p","gl","efecto","esperada_min","nota"],{
        "variable":"Variable","prueba":"Prueba","estadistico":"Estadístico","p":"p","gl":"gl","efecto":"Efecto","esperada_min":"Frecuencia esperada mínima","nota":"Nota"
    })
    display = format_columns(
        display,
        decimals={"Estadístico":3, "Efecto":3, "Frecuencia esperada mínima":2},
        p_columns=["p"],
        count_columns=["gl"],
    )
    show_table(display)
    st.info("Las distribuciones extremadamente regulares se preservan tal como aparecen en la fuente y se mantienen señaladas en el control de calidad; no fueron alteradas ni aleatorizadas.")
    source_note("M04_PARTICIPANTES", "M27_SOCIO_DESCRIPT", "M28_COMPARABILIDAD", "M22_CONTROL_CALIDAD")

# --------------------------- CALIDAD ---------------------------
elif page == "Metodología y calidad":
    section("Flujo de muestra")
    show_table(frames["sample_flow"])
    section("Datos faltantes")
    missing=frames["missing_data"].copy()
    if "proporcion" in missing.columns: missing["proporcion"]=missing["proporcion"].map(fmt_pct)
    show_table(missing)
    section("Control de calidad")
    show_table(frames["quality_control"])
    section("Trazabilidad y exclusiones")
    c1,c2=st.columns(2)
    with c1: show_table(frames["traceability"])
    with c2: show_table(frames["exclusions"])
    section("Validación Boateng–COSMIN")
    show_table(frames["validation_status"])
    st.warning("El dashboard no calcula V de Aiken mientras no existan valoraciones numéricas reales de los jueces en la fuente primaria.")
    section("Reproducibilidad")
    show_table(frames["reproducibility"])
    source_note("M21_TRAZABILIDAD", "M22_CONTROL_CALIDAD", "M33_FLUJO_MUESTRA", "M34_DATOS_FALTANTES", "M35_REPRODUCIBILIDAD", "M36_VALIDACION_ESTADO")

# --------------------------- INFORME PDF ---------------------------
else:
    section("Informe científico visual de resultados")
    st.markdown(
        "<div class='ng-method-note'><strong>Documento público y sintético.</strong> "
        "El informe conserva los bloques descriptivos e inferenciales del dashboard: ANCOVA, tamaños del efecto, Spearman, regresión y matriz de confusión, además de las gráficas principales. "
        "No incluye bases de datos, archivos estadísticos, tablas descargables ni registros individuales.</div>",
        unsafe_allow_html=True,
    )

    pdf_report = create_visual_report(
        frames,
        params,
        usage_map,
        payload["master_sha256"],
    )

    st.download_button(
        "Descargar informe visual en PDF",
        data=pdf_report,
        file_name="neuroguIA_informe_visual_resultados_v3.pdf",
        mime="application/pdf",
        use_container_width=True,
        type="primary",
    )

    st.caption(
        "Incluye síntesis general, DASS-21 descriptivo e inferencial, MSPSS, WHOQOL-BREF, uso, "
        "Spearman, regresión, analítica conversacional, matriz de confusión, experiencia y notas metodológicas."
    )


st.markdown(
    f"<div class='ng-control-line'>control interno · {BUILD_ID} · "
    f"{payload.get('master_name','Documento Maestro v3')} · "
    f"{payload['master_sha256'][:8]}…{payload['master_sha256'][-6:]}</div>",
    unsafe_allow_html=True,
)