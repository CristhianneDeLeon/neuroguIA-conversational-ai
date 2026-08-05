# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from typing import Iterable
import os

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import numpy as np
import pandas as pd
import streamlit as st

from dashboard_data_loader import (
    clear_dashboard_cache,
    frames_to_zip,
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
BUILD_ID = "DASH-V3.0-AUDITADO-20260804"
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


def base_axes(ax, title: str, ylabel: str = "") -> None:
    ax.set_title(title, loc="left", color=INK, fontsize=12, fontweight="bold")
    if ylabel:
        ax.set_ylabel(ylabel, color=MUTED)
    ax.grid(axis="y", alpha=.18)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(colors=INK, labelsize=8)


def prepost_chart(df: pd.DataFrame, label_col: str, selected: str, title: str) -> None:
    plot = df[df[label_col].astype(str) == selected].copy()
    if plot.empty:
        st.info("No hay datos pretest–postest para esta selección.")
        return
    groups = plot["grupo"].astype(str).tolist()
    pre = pd.to_numeric(plot["pre_media"], errors="coerce").to_numpy()
    post = pd.to_numeric(plot["post_media"], errors="coerce").to_numpy()
    x = np.arange(len(groups))
    width = .34
    fig, ax = plt.subplots(figsize=(9.5, 4.8), dpi=145)
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
    fig, ax = plt.subplots(figsize=(10, max(4.4, len(plot)*.43)), dpi=145)
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
            "Descargas",
        ],
    )
    audit_mode = st.toggle("Auditoría interna", value=False, disabled=not ALLOW_AUDIT)
    if not ALLOW_AUDIT:
        st.caption("La vista individual está deshabilitada en el despliegue público.")
    if st.button("Actualizar datos", use_container_width=True):
        clear_dashboard_cache()
        st.rerun()
    st.caption(f"SHA-256: {payload['master_sha256'][:16]}…")

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
    show = clean_table(selected, ["grupo","n","pre_media","pre_de","post_media","post_de","cambio_favorable","cambio_pct","estado"], {
        "grupo":"Grupo","n":"N","pre_media":"Pre media","pre_de":"Pre DE","post_media":"Post media","post_de":"Post DE",
        "cambio_favorable":"Cambio favorable","cambio_pct":"Cambio %","estado":"Estado"
    })
    if "Cambio %" in show.columns:
        show["Cambio %"] = show["Cambio %"].map(lambda x: fmt_pct(x, signed=True))
    show_table(show)

    section("ANCOVA ajustada")
    anc = frames["ancova"]
    anc_row = anc[anc["resultado"] == variable]
    if not anc_row.empty:
        row = anc_row.iloc[0]
        cols = st.columns(5)
        values = [
            ("Diferencia ajustada", fmt_num(row["b_grupo"], 3), "experimental − control"),
            ("IC 95%", f"{fmt_num(row['ic_bajo'],2)} a {fmt_num(row['ic_alto'],2)}", "coeficiente de grupo"),
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
    show_table(clean_table(eff_var, ["definicion","cohen_d","hedges_g","ic_bajo","ic_alto"], {
        "definicion":"Definición","cohen_d":"Cohen’s d","hedges_g":"Hedges g","ic_bajo":"IC bajo","ic_alto":"IC alto"
    }))

    with st.expander("Supuestos, normalidad y pruebas no paramétricas"):
        show_table(frames["ancova_assumptions"][frames["ancova_assumptions"]["resultado"] == variable])
        normal = frames["normality"]
        mask = normal.astype(str).apply(lambda c: c.str.contains(variable, case=False, na=False)).any(axis=1)
        show_table(normal[mask])
        nonp = frames["nonparametric"]
        mask = nonp.astype(str).apply(lambda c: c.str.contains(variable, case=False, na=False)).any(axis=1)
        show_table(nonp[mask])
    source_note("M05_DASS_PREPOST", "M06_DASS_RESUMEN", "M07_ANCOVA", "M31_NO_PARAMETRICAS")

# --------------------------- MSPSS / APOYO ---------------------------
elif page == "MSPSS y apoyo":
    st.warning("La MSPSS se presenta como resultado oficial agregado. El índice individual disponible es un indicador auxiliar de apoyo y no sustituye los 12 reactivos originales de la MSPSS.")
    mspss = frames["mspss_official"].copy()
    fig, ax = plt.subplots(figsize=(9.4, 4.7), dpi=145)
    x = np.arange(len(mspss)); width=.34
    b1=ax.bar(x-width/2, pd.to_numeric(mspss["pre_1_5"]), width, label="Pretest", color=PALETTE[0])
    b2=ax.bar(x+width/2, pd.to_numeric(mspss["post_1_5"]), width, label="Postest", color=PALETTE[1])
    ax.set_xticks(x, mspss["grupo"]); ax.set_ylim(0,5)
    base_axes(ax, "MSPSS oficial agregado", "Escala 1–5"); ax.legend(frameon=False)
    ax.bar_label(b1,fmt="%.2f",padding=3); ax.bar_label(b2,fmt="%.2f",padding=3)
    fig.tight_layout(); st.pyplot(fig,use_container_width=True); plt.close(fig)
    show = mspss.copy(); show["cambio_pct"] = show["cambio_pct"].map(lambda x: fmt_pct(x, signed=True))
    show_table(show)

    section("Índice auxiliar de apoyo individual")
    support = frames["support_individual"].copy()
    summary = support.groupby("grupo", as_index=False).agg(
        n=("participant_id","count"), pre=("apoyo_pre_1_5","mean"), post=("apoyo_post_1_5","mean"), cambio=("mejora_apoyo","mean")
    )
    summary["cambio_pct"] = np.where(summary["pre"] != 0, summary["cambio"] / summary["pre"], np.nan)
    fig, ax = plt.subplots(figsize=(9.4,4.7),dpi=145)
    x=np.arange(len(summary)); width=.34
    b1=ax.bar(x-width/2,summary["pre"],width,label="Pretest",color=PALETTE[2]); b2=ax.bar(x+width/2,summary["post"],width,label="Postest",color=PALETTE[1])
    ax.set_xticks(x,summary["grupo"]); ax.set_ylim(0,5); base_axes(ax,"Apoyo auxiliar: pretest y postest","Escala 1–5"); ax.legend(frameon=False)
    ax.bar_label(b1,fmt="%.2f",padding=3); ax.bar_label(b2,fmt="%.2f",padding=3); fig.tight_layout(); st.pyplot(fig,use_container_width=True); plt.close(fig)
    show = summary.copy(); show["cambio_pct"] = show["cambio_pct"].map(lambda x: fmt_pct(x, signed=True)); show_table(show)

    anc = frames["ancova"]
    row = anc[anc["resultado"] == "Apoyo auxiliar 1-5"].iloc[0]
    cols=st.columns(4)
    for i,item in enumerate([
        ("Diferencia ajustada",fmt_num(row["b_grupo"],3),"experimental − control"),
        ("IC 95%",f"{fmt_num(row['ic_bajo'],2)} a {fmt_num(row['ic_alto'],2)}","coeficiente"),
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
    show_table(clean_table(who_anc, ["resultado","b_grupo","ic_bajo","ic_alto","p_grupo","r2_aj","p_interaccion","levene_p"], {
        "resultado":"Dominio","b_grupo":"Diferencia ajustada","ic_bajo":"IC bajo","ic_alto":"IC alto","p_grupo":"p grupo",
        "r2_aj":"R² ajustado","p_interaccion":"p interacción","levene_p":"p Levene"
    }))
    section("Tamaños del efecto WHOQOL")
    eff = frames["effects"]
    who_eff = eff[eff["resultado"].astype(str).str.startswith("WHOQOL") & (eff["definicion"] == "Postest E-C")].copy()
    forest_chart(who_eff, "resultado", "cohen_d", "ic_bajo", "ic_alto", "WHOQOL-BREF: Cohen’s d postest")

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
    show_table(weekly_active)

    section("Distribución horaria técnica")
    bands=frames["time_bands"].copy()
    fig,ax=plt.subplots(figsize=(10,4.6),dpi=145)
    bars=ax.bar(bands["franja"],pd.to_numeric(bands["sesiones_técnicas"]),color=PALETTE[:4])
    base_axes(ax,"Sesiones por franja horaria","Sesiones técnicas"); ax.bar_label(bars,fmt="%d",padding=3); fig.tight_layout(); st.pyplot(fig,use_container_width=True); plt.close(fig)
    show=bands.copy(); show["proporción"] = show["proporción"].map(fmt_pct); show_table(show)

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
    corr=frames["correlations"].copy()
    section("Correlaciones reproducidas")
    show=corr.copy(); show["rho"] = show["rho"].map(lambda x: fmt_num(x,4)); show["p"] = show["p"].map(fmt_p); show_table(show)
    st.warning("Las asociaciones altas de la muestra total reflejan, en parte, que el grupo control tiene exposición cero. La relación dosis–respuesta debe interpretarse dentro del grupo experimental, donde los coeficientes reproducidos son cercanos a cero.")

    usage=frames["usage_participant"]
    exp=usage[usage["grupo"]=="Experimental"].copy()
    fig,ax=plt.subplots(figsize=(9.6,5),dpi=145)
    ax.scatter(pd.to_numeric(exp["mensajes"]),pd.to_numeric(exp["mejora_estres"]),alpha=.62,color=PALETTE[0],edgecolor="none")
    base_axes(ax,"Mensajes y mejora del estrés · grupo experimental","Mejora del estrés")
    ax.set_xlabel("Mensajes por participante")
    row=corr[(corr["muestra"]=="Solo experimental") & (corr["predictor"]=="messages")].iloc[0]
    ax.text(.02,.96,f"ρ = {fmt_num(row['rho'],4)} · p = {fmt_p(row['p'])}",transform=ax.transAxes,va="top",fontsize=10,color=INK)
    fig.tight_layout(); st.pyplot(fig,use_container_width=True); plt.close(fig)

    section("Regresión ajustada")
    reg=frames["regression"].copy()
    coef=reg[pd.to_numeric(reg["coef"],errors="coerce").notna()].copy().head(5)
    coef["coef"] = pd.to_numeric(coef["coef"]); coef["ic_bajo"] = pd.to_numeric(coef["ic_bajo"]); coef["ic_alto"] = pd.to_numeric(coef["ic_alto"])
    forest_chart(coef,"predictor","coef","ic_bajo","ic_alto","Predictores de la mejora del estrés")
    show_table(clean_table(coef,["predictor","coef","se_hc3","ic_bajo","ic_alto","p"],{
        "predictor":"Predictor","coef":"Coeficiente","se_hc3":"EE HC3","ic_bajo":"IC bajo","ic_alto":"IC alto","p":"p"
    }))
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
    show_table(perf)
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
    show_table(summary)
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
    show=selected_df.copy(); show["porcentaje"]=show["porcentaje"].map(fmt_pct); show_table(show)

    section("Comparabilidad basal")
    comp=frames["baseline_comparability"].copy()
    display=clean_table(comp,["variable","prueba","estadistico","p","gl","efecto","esperada_min","nota"],{
        "variable":"Variable","prueba":"Prueba","estadistico":"Estadístico","p":"p","gl":"gl","efecto":"Efecto","esperada_min":"Frecuencia esperada mínima","nota":"Nota"
    })
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

# --------------------------- DESCARGAS ---------------------------
else:
    section("Archivos públicos y reproducibilidad")
    st.info(
        "Por protección de los registros pseudonimizados, el Excel maestro y las tablas "
        "individuales no se ofrecen para descarga desde el dashboard. Esta sección contiene "
        "únicamente resultados agregados y materiales de reproducibilidad."
    )

    public_export_keys = {
        "parameters", "dass_summary", "ancova", "effects", "mspss_official",
        "whoqol_summary", "experience_summary", "usage_official", "usage_weekly",
        "correlations", "regression", "historical_metrics", "time_bands",
        "pln_official", "pln_metrics", "pln_confusion", "pln_categories",
        "traceability", "quality_control", "exclusions", "socio_descriptives",
        "baseline_comparability", "normality", "ancova_assumptions",
        "nonparametric", "sample_flow", "missing_data", "reproducibility",
        "validation_status",
    }
    public_frames = {
        key: frame for key, frame in frames.items()
        if key in public_export_keys and frame is not None and not frame.empty
    }

    c1,c2,c3=st.columns(3)
    script_path=BASE_DIR/"neuroguia_analisis_oficial_v3.py"
    with c1:
        if script_path.exists():
            st.download_button(
                "Descargar script estadístico", script_path.read_bytes(),
                file_name=script_path.name, mime="text/x-python",
                use_container_width=True,
            )
    json_path=BASE_DIR/"exports"/"NeuroGuIA_resultados_reproducidos_v3.json"
    with c2:
        if json_path.exists():
            st.download_button(
                "Descargar resultados JSON", json_path.read_bytes(),
                file_name=json_path.name, mime="application/json",
                use_container_width=True,
            )
    with c3:
        st.download_button(
            "Descargar tablas agregadas", frames_to_zip(public_frames),
            file_name="neuroguIA_resultados_agregados_v3.zip",
            mime="application/zip", use_container_width=True,
        )

    st.code(payload["master_sha256"],language="text")
    st.caption(
        "SHA-256 del Excel maestro activo. Permite verificar la fuente utilizada sin "
        "exponer el archivo individual."
    )

st.caption(f"Fuente activa: {payload.get('master_name','Documento Maestro v3')} · SHA-256 {payload['master_sha256'][:16]}… · neuroguIA 2026")
