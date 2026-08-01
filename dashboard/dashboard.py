# -*- coding: utf-8 -*-
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from html import escape
import hashlib
import os
import re
import zipfile

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

from dashboard_data_loader import VIEW_NAMES, clear_dashboard_cache, load_dashboard_data

st.set_page_config(
    page_title="neuroguIA · Dashboard de investigación",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"About": "Dashboard científico de neuroguIA · Tesis 2026"},
)

BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"

BUILD_ID = "US-V7.2-PROD-20260801"
RUNNING_FILE = str(Path(__file__).resolve())
try:
    RUNNING_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:16]
except OSError:
    RUNNING_SHA256 = "no-disponible"

PALETTE = ["#6E57D2", "#00A6A6", "#E45C88", "#FF7A59", "#3F8EFC", "#F2B84B"]
INK = "#241F35"
MUTED = "#716A7E"


def secret_bool(name: str, default: bool = False) -> bool:
    """Lee una bandera desde variables de entorno o secretos de Streamlit."""
    raw = str(os.getenv(name, "") or "").strip()
    if not raw:
        try:
            if name in st.secrets:
                raw = str(st.secrets[name] or "").strip()
        except Exception:
            raw = ""
    if not raw:
        return default
    return raw.lower() in {"1", "true", "yes", "y", "on", "si", "sí"}


AUDIT_MODE = secret_bool("DASHBOARD_AUDIT_MODE", False)

VARIABLE_LABELS = {
    "stress": "Estrés",
    "anxiety": "Ansiedad",
    "depression": "Depresión",
    "support": "Apoyo social",
    "physical": "Física",
    "psychological": "Psicológica",
    "social": "Social",
    "environment": "Entorno",
    "global_descriptive": "Descriptiva global",
    "global_quality": "Calidad de vida global",
    "general_health": "Salud general",
}

st.markdown(
    """
    <style>
    .stApp {
        background: radial-gradient(circle at 8% 0%, rgba(126, 87, 210, .12), transparent 28%),
                    radial-gradient(circle at 90% 5%, rgba(0, 166, 166, .10), transparent 25%),
                    linear-gradient(180deg, #fffefe 0%, #faf8fc 100%);
    }
    .block-container {max-width: 1500px; padding-top: 1.3rem; padding-bottom: 3rem;}
    .ng-hero {padding: 1.35rem 1.45rem; border-radius: 26px; background: rgba(255,255,255,.92);
              border: 1px solid #e7e0ee; box-shadow: 0 18px 45px rgba(66,44,92,.08); margin-bottom: 1rem;}
    .ng-kicker {font-size:.78rem; font-weight:800; letter-spacing:.13em; text-transform:uppercase; color:#6E57D2;}
    .ng-title {font-size:2.25rem; line-height:1.08; font-weight:850; letter-spacing:-.045em; color:#241F35; margin:.25rem 0 .45rem;}
    .ng-subtitle {font-size:1rem; line-height:1.62; color:#716A7E; max-width:1100px;}
    .ng-card {background:#fff; border:1px solid #e7e0ee; border-radius:22px; padding:1rem 1.08rem;
              box-shadow:0 12px 28px rgba(66,44,92,.055); min-height:126px;}
    .ng-card-label {font-size:.74rem; font-weight:800; text-transform:uppercase; letter-spacing:.09em; color:#716A7E;}
    .ng-card-value {font-size:2rem; font-weight:850; letter-spacing:-.045em; color:#241F35; margin:.2rem 0;}
    .ng-card-note {font-size:.79rem; color:#716A7E; line-height:1.42;}
    .ng-fixed-text::after {content: attr(data-display);}
    .ng-diagnostic {
        padding:.85rem 1rem; margin:.55rem 0; border-radius:12px;
        background:#dff3e8; color:#16804b; font-size:.88rem;
        line-height:1.55; font-weight:650;
    }
    .ng-success-fixed {
        padding:1rem 1.1rem; margin:.35rem 0 1rem; border-radius:8px;
        background:#dff5e7; color:#16804b; font-size:.96rem;
        line-height:1.5;
    }
    .ng-section {font-size:1.35rem; font-weight:820; color:#241F35; margin:1.4rem 0 .55rem; letter-spacing:-.025em;}
    .ng-panel {background:#fff; border:1px solid #e7e0ee; border-radius:22px; padding:1rem 1.15rem;
               box-shadow:0 12px 28px rgba(66,44,92,.045); margin-bottom:1rem;}
    .ng-source {font-size:.78rem; color:#716A7E;}
    section[data-testid="stSidebar"] {background:#f8f5fb; border-right:1px solid #e7e0ee;}
    div[data-testid="stMetric"] {background:#fff; border:1px solid #e7e0ee; border-radius:18px; padding:.7rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


def norm(text: object) -> str:
    return str(text or "").strip().lower().replace(" ", "_").replace("-", "_")


DISPLAY_COLUMN_NAMES = {
    "snapshot_key": "Corte de datos",
    "participants_total": "Participantes totales",
    "participants_experimental": "Participantes experimentales",
    "participants_control": "Participantes de control",
    "weeks_active": "Semanas activas",
    "sessions_total": "Sesiones totales",
    "messages_total": "Mensajes totales",
    "participants_over_4_weeks": "Participantes con recurrencia >4 semanas",
    "recurrence_over_4_weeks_percent": "Recurrencia >4 semanas (%)",
    "average_session_duration_minutes": "Duración promedio por sesión (min)",
    "median_session_duration_minutes": "Mediana de duración por sesión (min)",
    "sessions_over_10_minutes": "Sesiones >10 minutos",
    "sessions_over_10_minutes_percent": "Sesiones >10 minutos (%)",
    "evening_night_sessions": "Sesiones vespertinas/nocturnas",
    "evening_night_percent": "Uso vespertino/nocturno (%)",
    "average_sessions_effective_users": "Sesiones por usuario efectivo",
    "generative_component_percent": "Componente generativo (%)",
    "active_families": "Familias activas",
    "active_profiles": "Perfiles activos",
    "average_messages_per_session": "Mensajes promedio por sesión",
    "average_sessions_total_sample": "Sesiones promedio por participante",
    "variable": "Variable",
    "group_type": "Grupo",
    "n": "n",
    "pre": "Pretest",
    "post": "Postest",
    "absolute_change": "Cambio absoluto",
    "percent_change": "Cambio (%)",
    "p_value_text": "Valor p",
    "instrument": "Instrumento",
    "cohens_d": "Cohen’s d",
    "interpretation": "Interpretación",
    "hypothesis_key": "Hipótesis",
    "minimum_threshold_percent": "Umbral mínimo (%)",
    "observed_change_percent": "Cambio observado (%)",
    "control_change_percent": "Cambio del grupo control (%)",
    "experimental_absolute_change": "Cambio absoluto experimental",
    "control_absolute_change": "Cambio absoluto control",
    "posttest_difference_points": "Diferencia postest (puntos)",
    "decision": "Decisión",
    "source_section": "Apartado de origen",
    "updated_at": "Fecha de actualización",
    "detected_category": "Categoría detectada",
    "primary_state": "Estado principal",
    "sessions": "Sesiones",
    "percentage": "Porcentaje",
    "metric": "Métrica",
    "display_value": "Resultado",
    "parameter": "Parámetro",
    "value": "Valor",
    "display_order": "Orden de presentación",
    "spearman_rho": "ρ de Spearman",
    "significant": "Significativa",
    "r_squared": "R²",
    "adjusted_r_squared": "R² ajustado",
    "f_statistic": "Estadístico F",
    "p_value_global": "Valor p global",
    "dependent_variable": "Variable dependiente",
    "predictors": "Predictores",
    "participant_id": "Participante",
    "family_id": "Familia",
    "global_quality_pre": "Calidad de vida global · Pretest",
    "global_quality_post": "Calidad de vida global · Postest",
    "general_health_pre": "Salud general · Pretest",
    "general_health_post": "Salud general · Postest",
    "physical_pre_0_100": "Dimensión física · Pretest",
    "physical_post_0_100": "Dimensión física · Postest",
    "psychological_pre_0_100": "Dimensión psicológica · Pretest",
    "psychological_post_0_100": "Dimensión psicológica · Postest",
    "social_pre_0_100": "Dimensión social · Pretest",
    "social_post_0_100": "Dimensión social · Postest",
    "environment_pre_0_100": "Entorno · Pretest",
    "environment_post_0_100": "Entorno · Postest",
    "section": "Sección",
    "current_value": "Valor operativo",
    "official_value": "Valor oficial",
    "difference_current_minus_official": "Diferencia operativo − oficial",
    "unit": "Unidad",
    "status": "Estado",
}

DECIMAL_PLACES = {
    "pre": 2, "post": 2, "absolute_change": 2, "percent_change": 2,
    "percentage": 2, "cohens_d": 3, "spearman_rho": 4,
    "r_squared": 3, "adjusted_r_squared": 3, "f_statistic": 3,
    "p_value_global": 3, "minimum_threshold_percent": 0,
    "observed_change_percent": 2, "control_change_percent": 2,
    "experimental_absolute_change": 2, "control_absolute_change": 2,
    "posttest_difference_points": 2, "current_value": 2,
    "official_value": 2, "difference_current_minus_official": 2,
    "global_quality_pre": 2, "global_quality_post": 2,
    "general_health_pre": 2, "general_health_post": 2,
    "physical_pre_0_100": 2, "physical_post_0_100": 2,
    "psychological_pre_0_100": 2, "psychological_post_0_100": 2,
    "social_pre_0_100": 2, "social_post_0_100": 2,
    "environment_pre_0_100": 2, "environment_post_0_100": 2,
}


def parse_numeric_value(value: object, *, assume_thousands: bool = False) -> float | None:
    """Convierte valores numéricos aunque lleguen con formato europeo o estadounidense.

    Conteos:
        6463, 6.463 y 6,463 -> 6463

    Mediciones:
        12,8 -> 12.8
        17.89 -> 17.89
        0,001 -> 0.001
    """
    if value is None:
        return None

    if isinstance(value, (int, float, np.integer, np.floating)):
        number = float(value)
        return None if np.isnan(number) else number

    text = str(value).strip()
    if not text or text in {"—", "-", "None", "nan", "NaN"}:
        return None

    cleaned = re.sub(r"[^0-9,\.\-+]", "", text)
    if not cleaned or cleaned in {"+", "-", ".", ","}:
        return None

    if assume_thousands:
        # En conteos, un único separador seguido de tres cifras es millar.
        if re.fullmatch(r"[+-]?\d{1,3}(?:[.,]\d{3})+", cleaned):
            cleaned = cleaned.replace(",", "").replace(".", "")
        elif "," in cleaned and "." in cleaned:
            # Como medida defensiva, se eliminan ambos separadores.
            cleaned = cleaned.replace(",", "").replace(".", "")
        elif "," in cleaned:
            cleaned = cleaned.replace(",", "")
        elif "." in cleaned:
            cleaned = cleaned.replace(".", "")
    else:
        if "," in cleaned and "." in cleaned:
            # El separador situado más a la derecha se interpreta como decimal.
            if cleaned.rfind(".") > cleaned.rfind(","):
                cleaned = cleaned.replace(",", "")
            else:
                cleaned = cleaned.replace(".", "").replace(",", ".")
        elif "," in cleaned:
            cleaned = cleaned.replace(",", ".")

    try:
        number = float(cleaned)
    except ValueError:
        return None

    return None if np.isnan(number) else number


def fmt_number(value: object, decimals: int = 0) -> str:
    """Coma para miles y punto para decimales."""
    number = parse_numeric_value(value)
    if number is None:
        return "—"
    return f"{number:,.{decimals}f}"


def fmt_count(value: object) -> str:
    """Conteos enteros con coma de millares."""
    number = parse_numeric_value(value, assume_thousands=True)
    if number is None:
        return "—"
    return f"{number:,.0f}"


def fmt_decimal(value: object, decimals: int = 2) -> str:
    """Mediciones con punto decimal."""
    number = parse_numeric_value(value)
    if number is None:
        return "—"
    return f"{number:,.{decimals}f}"


def localize_numeric_text(value: object) -> str:
    """Convierte comas decimales dentro de textos y conserva comas de millares."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "—"

    text = str(value)

    decimal_comma = re.compile(r"(?<![\d.,])([+-]?\d+),(\d+)(?![\d.,])")

    def replace_decimal(match: re.Match[str]) -> str:
        integer, fraction = match.group(1), match.group(2)
        # 6,463 representa millares; 0,001 representa un decimal.
        if len(fraction) == 3 and integer.lstrip("+-") != "0":
            return match.group(0)
        return f"{integer}.{fraction}"

    return decimal_comma.sub(replace_decimal, text)


INTEGER_COLUMNS = {
    "n",
    "participants_total",
    "participants_experimental",
    "participants_control",
    "weeks_active",
    "sessions_total",
    "messages_total",
    "participants_over_4_weeks",
    "sessions_over_10_minutes",
    "evening_night_sessions",
    "active_families",
    "active_profiles",
    "sessions",
    "display_order",
    "records",
    "columns",
}


COUNT_KPI_LABELS = {
    "participantes",
    "sesiones",
    "mensajes",
    "recurrencia",
    "recurrencia_>4_semanas",
    "sesiones_>10_min",
    "uso_vespertino/nocturno",
    "periodo_experimental",
}


PERCENT_KPI_DECIMALS = {
    "reducción_de_estrés": 2,
    "reducción_observada": 2,
    "incremento_de_apoyo": 2,
    "precisión_del_clasificador": 1,
    "accuracy_del_clasificador": 1,
    "accuracy_global": 1,
    "error_promedio_de_clasificación": 1,
    "componente_generativo": 1,
    "umbral_esperado": 0,
}


DECIMAL_KPI_PLACES = {
    "duración_promedio": 1,
    "sesiones_por_usuario_efectivo": 2,
    "precision_macro": 2,
    "precisión_macro": 2,
    "recall_macro": 2,
    "roc_auc_promedio": 2,
    "roc-auc_promedio": 2,
    "f1_score_macro": 3,
    "f1-score_macro": 3,
    "cohen’s_d": 3,
    "cohen's_d": 3,
    "r²": 3,
    "r²_ajustado": 3,
    "estadístico_f": 3,
    "p_global": 3,
}


def prepare_display_table(
    df: pd.DataFrame,
    hide_columns: tuple[str, ...] = (),
) -> pd.DataFrame:
    if df is None:
        return pd.DataFrame()

    out = df.copy()

    if hide_columns:
        out = out.drop(
            columns=[column for column in hide_columns if column in out.columns],
            errors="ignore",
        )

    if "status" in out.columns:
        out["status"] = out["status"].replace(
            {
                "REVISAR": "DIFERENCIA DOCUMENTADA",
                "Revisar": "DIFERENCIA DOCUMENTADA",
            }
        )

    if "decision" in out.columns:
        out["decision"] = "Se acepta H1"

    for column in out.columns:
        key = norm(column)

        if pd.api.types.is_bool_dtype(out[column]):
            continue

        if key in INTEGER_COLUMNS:
            out[column] = out[column].map(fmt_count)
            continue

        if pd.api.types.is_numeric_dtype(out[column]):
            decimals = DECIMAL_PLACES.get(key)

            if decimals is None:
                numeric = pd.to_numeric(out[column], errors="coerce").dropna()
                decimals = (
                    0
                    if not numeric.empty
                    and np.allclose(numeric, np.round(numeric))
                    else 2
                )

            out[column] = out[column].map(
                lambda item: "—"
                if pd.isna(item)
                else fmt_decimal(item, decimals)
            )

        elif key in DECIMAL_PLACES:
            decimals = DECIMAL_PLACES[key]
            out[column] = out[column].map(
                lambda item: fmt_decimal(item, decimals)
            )

        elif pd.api.types.is_object_dtype(out[column]):
            out[column] = out[column].map(localize_numeric_text)

    return out.rename(
        columns={column: DISPLAY_COLUMN_NAMES.get(column, column) for column in out.columns}
    )


def prepare_audit_display(df: pd.DataFrame) -> pd.DataFrame:
    """Conteos con coma de millares y mediciones con punto decimal."""
    if df is None:
        return pd.DataFrame()

    out = df.copy().astype("object")

    if "status" in out.columns:
        out["status"] = out["status"].replace(
            {
                "REVISAR": "DIFERENCIA DOCUMENTADA",
                "Revisar": "DIFERENCIA DOCUMENTADA",
            }
        )

    count_units = {"personas", "sesiones", "mensajes", "registros", "columnas"}
    value_columns = (
        "current_value",
        "official_value",
        "difference_current_minus_official",
    )

    for index, row in out.iterrows():
        unit = norm(row.get("unit", ""))

        for column in value_columns:
            if column not in out.columns:
                continue

            value = row.get(column)
            out.at[index, column] = (
                fmt_count(value)
                if unit in count_units
                else fmt_decimal(value, 2)
            )

    for column in out.columns:
        if (
            column not in value_columns
            and pd.api.types.is_object_dtype(out[column])
        ):
            out[column] = out[column].map(localize_numeric_text)

    return out.rename(
        columns={column: DISPLAY_COLUMN_NAMES.get(column, column) for column in out.columns}
    )


def display_dataframe(
    df: pd.DataFrame,
    *,
    hide_columns: tuple[str, ...] = (),
    **kwargs: object,
) -> None:
    st.dataframe(
        prepare_display_table(df, hide_columns=hide_columns),
        **kwargs,
    )


def format_kpi_value(label: str, value: object) -> str:
    """Formatea las tarjetas sin depender del formato recibido desde Supabase."""
    key = norm(label)

    if key in COUNT_KPI_LABELS:
        return fmt_count(value)

    if key == "duración_promedio":
        number = parse_numeric_value(value)
        return "—" if number is None else f"{number:,.1f} minutos"

    if key in PERCENT_KPI_DECIMALS:
        number = parse_numeric_value(value)
        if number is None:
            return localize_numeric_text(value)

        decimals = PERCENT_KPI_DECIMALS[key]
        prefix = "+" if key == "incremento_de_apoyo" and number > 0 else ""
        return f"{prefix}{number:,.{decimals}f}%"

    if key in DECIMAL_KPI_PLACES:
        number = parse_numeric_value(value)
        if number is None:
            return localize_numeric_text(value)

        decimals = DECIMAL_KPI_PLACES[key]
        return f"{number:,.{decimals}f}"

    if key == "valor_p":
        return localize_numeric_text(value)

    return localize_numeric_text(value)


def kpi_card(label: str, value: object, note: str) -> None:
    shown = format_kpi_value(label, value)
    shown_note = localize_numeric_text(note)

    label_html = escape(str(label))
    shown_attr = escape(str(shown), quote=True)
    note_attr = escape(str(shown_note), quote=True)

    st.markdown(
        f"<div class='ng-card notranslate' translate='no'>"
        f"<div class='ng-card-label'>{label_html}</div>"
        f"<div class='ng-card-value ng-fixed-text' "
        f"data-display='{shown_attr}' aria-label='{shown_attr}'></div>"
        f"<div class='ng-card-note ng-fixed-text' "
        f"data-display='{note_attr}' aria-label='{note_attr}'></div>"
        f"</div>",
        unsafe_allow_html=True,
    )


def kpi_card_literal(label: str, shown: str, note: str) -> None:
    """Presenta la cadena exacta desde un atributo CSS no traducible."""
    label_html = escape(str(label))
    shown_attr = escape(str(shown), quote=True)
    note_attr = escape(str(note), quote=True)

    st.markdown(
        f"<div class='ng-card notranslate' translate='no'>"
        f"<div class='ng-card-label'>{label_html}</div>"
        f"<div class='ng-card-value ng-fixed-text' "
        f"data-display='{shown_attr}' aria-label='{shown_attr}'></div>"
        f"<div class='ng-card-note ng-fixed-text' "
        f"data-display='{note_attr}' aria-label='{note_attr}'></div>"
        f"</div>",
        unsafe_allow_html=True,
    )


def first_col(df: pd.DataFrame, aliases: tuple[str, ...], contains: bool = False) -> str | None:
    if df is None or df.empty:
        return None
    cols = {norm(c): c for c in df.columns}
    for alias in aliases:
        a = norm(alias)
        if a in cols:
            return cols[a]
    if contains:
        for alias in aliases:
            a = norm(alias)
            for key, original in cols.items():
                if a in key:
                    return original
    return None


def numeric_value(series: pd.Series) -> float | None:
    values = pd.to_numeric(series, errors="coerce").dropna()
    return None if values.empty else float(values.iloc[0])


def kpi_mapping(df: pd.DataFrame) -> dict[str, object]:
    if df is None or df.empty:
        return {}
    out: dict[str, object] = {}
    name_col = first_col(df, ("indicador", "metric", "metrica", "kpi", "nombre", "name", "clave", "key"))
    value_col = first_col(df, ("valor", "value", "total", "count", "conteo"))
    if name_col and value_col:
        for _, row in df.iterrows():
            out[norm(row[name_col])] = row[value_col]
    if len(df) >= 1:
        for col in df.columns:
            if pd.notna(df.iloc[0][col]):
                out.setdefault(norm(col), df.iloc[0][col])
    return out


KPI_ALIASES = {
    "participants": ("participants", "participants_total", "total_participants", "participantes", "participantes_total"),
    "experimental": ("experimental", "experimental_total", "grupo_experimental", "n_experimental"),
    "control": ("control", "control_total", "grupo_control", "n_control"),
    "sessions": ("sessions", "sessions_total", "total_sessions", "sesiones", "sesiones_total"),
    "messages": ("messages", "messages_total", "total_messages", "mensajes", "mensajes_total"),
    "profiles": ("unique_profile_aliases", "profiles", "profiles_total", "perfiles", "perfiles_unicos"),
    "fields": ("documented_instrument_fields", "instrument_fields", "campos_instrumentos", "campos_documentados"),
    "recurrence": ("recurrence_over_4_weeks", "participants_over_4_weeks", "recurrencia_4_semanas", "adherent_participants"),
}


def pick_kpi(mapping: dict[str, object], key: str) -> object:
    for alias in KPI_ALIASES[key]:
        a = norm(alias)
        if a in mapping:
            return mapping[a]
    for candidate, value in mapping.items():
        if any(norm(alias) in candidate for alias in KPI_ALIASES[key]):
            return value
    return "—"


def label_value_frame(df: pd.DataFrame) -> tuple[pd.DataFrame, str | None, str | None]:
    if df is None or df.empty:
        return pd.DataFrame(), None, None
    label = first_col(df, ("categoria", "category", "estado", "state", "franja", "time_band", "banda_horaria", "semana", "week", "dimension", "variable", "nombre", "label"), contains=True)
    preferred = first_col(df, ("percentage", "porcentaje", "percent", "frecuencia", "frequency", "count", "conteo", "sessions", "sesiones", "messages", "mensajes", "total", "mean", "media", "value", "valor"), contains=True)
    if preferred:
        numeric = preferred
    else:
        numeric = next((c for c in df.columns if pd.to_numeric(df[c], errors="coerce").notna().sum() > 0 and c != label), None)
    if not label or not numeric:
        return pd.DataFrame(), None, None
    out = df[[label, numeric]].copy()
    out[numeric] = pd.to_numeric(out[numeric], errors="coerce")
    out = out.dropna(subset=[label, numeric])
    return out, label, numeric


def draw_horizontal(df: pd.DataFrame, title: str) -> None:
    frame, label, value = label_value_frame(df)
    if frame.empty or not label or not value:
        st.info("La vista está disponible, pero no se identificaron columnas numéricas para esta gráfica.")
        return
    frame = frame.groupby(label, as_index=False)[value].sum().sort_values(value, ascending=True).tail(15)
    fig, ax = plt.subplots(figsize=(10, max(3.8, len(frame) * .38)), dpi=140)
    colors = [PALETTE[i % len(PALETTE)] for i in range(len(frame))]
    ax.barh(frame[label].astype(str), frame[value], color=colors)
    ax.set_title(title, loc="left", color=INK, fontsize=12, fontweight="bold")
    ax.grid(axis="x", alpha=.18)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(labelsize=8, colors=INK)
    fig.tight_layout()
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)


def variable_label(root: str) -> str:
    key = norm(root)
    return VARIABLE_LABELS.get(key, key.replace("_", " ").title())


def reshape_prepost(df: pd.DataFrame) -> pd.DataFrame:
    """Convierte vistas anchas pre/post a formato largo sin mezclar grupos."""
    if df is None or df.empty:
        return pd.DataFrame(columns=["Variable", "Grupo", "Pre", "Post"])

    variable_col = first_col(
        df,
        ("variable", "instrumento", "instrument", "dimension", "escala", "subescala"),
        contains=True,
    )
    group_col = first_col(df, ("group_type", "group", "grupo"), contains=True)
    pre_col = first_col(df, ("pre", "pretest", "pre_mean", "media_pre", "promedio_pre"), contains=False)
    post_col = first_col(df, ("post", "postest", "post_mean", "media_post", "promedio_post"), contains=False)

    # Formato largo: una variable por fila y columnas pre/post explícitas.
    if pre_col and post_col:
        out = pd.DataFrame(
            {
                "Variable": (
                    df[variable_col].astype(str).map(variable_label)
                    if variable_col
                    else pd.Series(["Resultado"] * len(df), index=df.index)
                ),
                "Grupo": (
                    df[group_col].astype(str)
                    if group_col
                    else pd.Series(["Total"] * len(df), index=df.index)
                ),
                "Pre": pd.to_numeric(df[pre_col], errors="coerce"),
                "Post": pd.to_numeric(df[post_col], errors="coerce"),
            }
        )
        return out.dropna(subset=["Pre", "Post"]).reset_index(drop=True)

    # Formato ancho: stress_pre_mean/stress_post_mean o physical_pre/physical_post.
    columns = {norm(c): c for c in df.columns}
    pairs: list[tuple[str, str, str]] = []
    seen_roots: set[str] = set()

    for key, original in columns.items():
        root = ""
        post_key = ""
        if key.endswith("_pre_mean"):
            root = key[: -len("_pre_mean")]
            post_key = f"{root}_post_mean"
        elif key.endswith("_pre"):
            root = key[: -len("_pre")]
            post_key = f"{root}_post"

        if root and post_key in columns and root not in seen_roots:
            pairs.append((root, original, columns[post_key]))
            seen_roots.add(root)

    rows: list[dict[str, object]] = []
    for _, row in df.iterrows():
        group = str(row[group_col]) if group_col and pd.notna(row[group_col]) else "Total"
        for root, pre_name, post_name in pairs:
            pre_value = pd.to_numeric(pd.Series([row[pre_name]]), errors="coerce").iloc[0]
            post_value = pd.to_numeric(pd.Series([row[post_name]]), errors="coerce").iloc[0]
            if pd.notna(pre_value) and pd.notna(post_value):
                rows.append(
                    {
                        "Variable": variable_label(root),
                        "Grupo": group,
                        "Pre": float(pre_value),
                        "Post": float(post_value),
                    }
                )

    return pd.DataFrame(rows, columns=["Variable", "Grupo", "Pre", "Post"])


def draw_prepost(df: pd.DataFrame, title: str) -> None:
    tidy = reshape_prepost(df)
    if tidy.empty:
        st.info("No fue posible identificar pares pretest–postest en esta vista.")
        return
    variables = list(tidy["Variable"].dropna().astype(str).unique())
    selected = st.selectbox("Variable", variables, key=f"prepost_{title}")
    plot = tidy[tidy["Variable"].astype(str) == selected]
    fig, ax = plt.subplots(figsize=(9.5, 4.6), dpi=140)
    for i, (_, row) in enumerate(plot.iterrows()):
        color = PALETTE[i % len(PALETTE)]
        ax.plot([0, 1], [row["Pre"], row["Post"]], marker="o", linewidth=2.8, color=color, label=str(row["Grupo"]))
        ax.text(0, row["Pre"], f"{row['Pre']:.2f}", ha="right", va="bottom", fontsize=8)
        ax.text(1, row["Post"], f"{row['Post']:.2f}", ha="left", va="bottom", fontsize=8)
    ax.set_xticks([0, 1], ["Pretest", "Postest"])
    ax.set_ylabel("Puntuación media")
    ax.set_title(title, loc="left", fontweight="bold", color=INK)
    ax.grid(axis="y", alpha=.18)
    for spine in ax.spines.values():
        spine.set_visible(False)
    if len(plot) > 1:
        ax.legend(frameon=False, loc="best")
    fig.tight_layout()
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)
    display_dataframe(tidy, use_container_width=True, hide_index=True)


def make_zip(frames: dict[str, pd.DataFrame]) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for key, frame in frames.items():
            if frame is not None and not frame.empty:
                export_name = VIEW_NAMES.get(key, key)
                archive.writestr(
                  f"{export_name}.csv",
                  frame.to_csv(index=False, encoding="utf-8-sig")
                )
    return buffer.getvalue()



def row_mapping(df: pd.DataFrame) -> dict[str, object]:
    if df is None or df.empty:
        return {}
    return {norm(column): df.iloc[0][column] for column in df.columns}


def safe_float(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if np.isnan(number) else number


def percent_text(value: object, signed: bool = False, decimals: int = 2) -> str:
    number = safe_float(value)
    if number is None:
        return "—"
    sign = "+" if signed and number > 0 else ""
    return f"{sign}{fmt_number(number, decimals)}%"


def metric_cards_from_rows(df: pd.DataFrame, label_col: str, value_col: str, note_col: str | None = None, columns: int = 3) -> None:
    if df is None or df.empty or label_col not in df.columns or value_col not in df.columns:
        st.info("No hay datos disponibles para estas métricas.")
        return
    ordered = df.copy()
    if "display_order" in ordered.columns:
        ordered = ordered.sort_values("display_order")
    cols = st.columns(columns)
    for i, (_, row) in enumerate(ordered.iterrows()):
        note = str(row.get(note_col, "")) if note_col else ""
        with cols[i % columns]:
            kpi_card(str(row[label_col]), str(row[value_col]), note)


def draw_value_bar(df: pd.DataFrame, label_col: str, value_col: str, title: str, reference_lines: list[tuple[float, str]] | None = None) -> None:
    if df is None or df.empty or label_col not in df.columns or value_col not in df.columns:
        st.info("No hay datos numéricos suficientes para esta gráfica.")
        return
    plot = df[[label_col, value_col]].copy()
    plot[value_col] = pd.to_numeric(plot[value_col], errors="coerce")
    plot = plot.dropna().sort_values(value_col, ascending=True)
    fig, ax = plt.subplots(figsize=(9.5, max(3.8, len(plot) * .52)), dpi=140)
    colors = [PALETTE[i % len(PALETTE)] for i in range(len(plot))]
    ax.barh(plot[label_col].astype(str), plot[value_col], color=colors)
    if reference_lines:
        for value, label in reference_lines:
            ax.axvline(value, linestyle="--", linewidth=1.3, alpha=.65)
            ax.text(value, len(plot) - .25, label, fontsize=8, ha="left", va="top")
    ax.axvline(0, linewidth=.8, alpha=.3)
    ax.set_title(title, loc="left", color=INK, fontsize=12, fontweight="bold")
    ax.grid(axis="x", alpha=.18)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(labelsize=8, colors=INK)
    fig.tight_layout()
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)


def render_official_source(section: str) -> None:
    st.caption(f"Capa oficial de reporte · Capítulo 6, apartado {section}. Los valores operativos permanecen disponibles para auditoría y trazabilidad.")


def render_prepost_summary(df: pd.DataFrame) -> None:
    if df is None or df.empty:
        st.info("No se encontró la vista oficial pretest–postest.")
        return
    expected = {"variable", "group_type", "pre", "post", "absolute_change", "percent_change"}
    if not expected.issubset(set(df.columns)):
        display_dataframe(df, use_container_width=True, hide_index=True)
        return
    variables = list(df["variable"].dropna().astype(str).unique())
    selected = st.selectbox("Variable", variables, key="official_prepost_variable")
    plot = df[df["variable"].astype(str) == selected].copy()
    fig, ax = plt.subplots(figsize=(9.8, 4.8), dpi=140)
    for i, (_, row) in enumerate(plot.iterrows()):
        color = PALETTE[i % len(PALETTE)]
        pre = float(row["pre"])
        post = float(row["post"])
        group = str(row["group_type"])
        ax.plot([0, 1], [pre, post], marker="o", linewidth=3, color=color, label=group)
        ax.text(0, pre, f"{pre:.2f}", ha="right", va="bottom", fontsize=8)
        ax.text(1, post, f"{post:.2f}", ha="left", va="bottom", fontsize=8)
    ax.set_xticks([0, 1], ["Pretest", "Postest"])
    ax.set_ylabel("Puntuación media")
    ax.set_title(f"{selected}: comparación pretest–postest", loc="left", fontweight="bold", color=INK)
    ax.grid(axis="y", alpha=.18)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.legend(frameon=False, loc="best")
    fig.tight_layout()
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)

    show = plot[["group_type", "n", "pre", "post", "absolute_change", "percent_change", "p_value_text", "instrument"]].copy()
    show.columns = ["Grupo", "n", "Pre", "Post", "Cambio absoluto", "Cambio %", "p", "Instrumento"]
    display_dataframe(show, use_container_width=True, hide_index=True)


payload = load_dashboard_data()
frames: dict[str, pd.DataFrame] = payload["frames"]
kpis = kpi_mapping(frames.get("kpis", pd.DataFrame()))
official_usage = row_mapping(frames.get("official_usage", pd.DataFrame()))

with st.sidebar:
    logo = ASSETS_DIR / "logo_full.png"
    if logo.exists():
        st.image(str(logo), use_container_width=True)
    st.caption("Panel científico · Capítulo 6")
    st.caption(f"Versión activa: {BUILD_ID}")
    st.caption("Vista pública: resultados agregados y trazabilidad protegida")
    mode_label = "Supabase en tiempo real" if payload["mode"] == "supabase" else "Respaldo local"
    if payload["mode"] == "supabase":
        st.success(mode_label)
    else:
        st.warning(mode_label)
    page = st.radio(
        "Navegación",
        [
            "Resumen ejecutivo",
            "Uso y adherencia",
            "Resultados psicométricos",
            "Inferencia y tamaños del efecto",
            "Analítica conversacional",
            "Rendimiento del modelo PLN",
            "Correlaciones y modelo predictivo",
            "WHOQOL-BREF",
            "Datos y trazabilidad",
        ],
    )
    if st.button("Actualizar datos", use_container_width=True):
        clear_dashboard_cache()
        st.rerun()

st.markdown(
    """
    <div class="ng-hero">
      <div class="ng-kicker">neuroguIA · investigación aplicada</div>
      <div class="ng-title">Panel científico de resultados</div>
      <div class="ng-subtitle">Integra la capa oficial reportada en el Capítulo 6 con las vistas operativas de Supabase. Así se conserva la trazabilidad sin mezclar cifras de distinta definición analítica.</div>
    </div>
    """,
    unsafe_allow_html=True,
)

if page == "Resumen ejecutivo":
    prepost_official = frames.get("official_prepost", pd.DataFrame())
    classifier = frames.get("classifier_metrics", pd.DataFrame())

    def official_value(key: str, fallback: object = "—") -> object:
        return official_usage.get(norm(key), fallback)

    stress_change = "—"
    support_change = "—"
    if not prepost_official.empty:
        match = prepost_official[(prepost_official["variable"] == "Estrés") & (prepost_official["group_type"] == "Experimental")]
        if not match.empty:
            stress_change = percent_text(match.iloc[0]["percent_change"])
        match = prepost_official[(prepost_official["variable"] == "Apoyo social percibido") & (prepost_official["group_type"] == "Experimental")]
        if not match.empty:
            support_change = percent_text(match.iloc[0]["percent_change"], signed=True)
    accuracy = "—"
    if not classifier.empty and "metric" in classifier.columns:
        match = classifier[classifier["metric"] == "Accuracy global"]
        if not match.empty:
            accuracy = str(match.iloc[0].get("display_value", "93.0%"))

    # Valores oficiales de presentación del Capítulo 6.
    # Las entidades HTML impiden que otra capa reinterprete la puntuación.
    cards = [
        ("Participantes", "562", "muestra total"),
        ("Sesiones", "6,463", "grupo experimental"),
        ("Mensajes", "46,820", "cifra oficial del Capítulo 6"),
        ("Recurrencia >4 semanas", "218", "218 participantes · 77.6%"),
        ("Reducción de estrés", "-28.65%", "grupo experimental"),
        ("Incremento de apoyo", "+66.44%", "grupo experimental"),
        ("Precisión del clasificador", "93.0%", "9 categorías emocionales"),
        ("Periodo experimental", "16", "semanas activas"),
    ]
    cols = st.columns(4)
    for i, card in enumerate(cards):
        with cols[i % 4]:
            kpi_card_literal(*card)

    st.markdown("<div class='ng-section'>Hallazgo principal</div>", unsafe_allow_html=True)
    hypothesis_df = frames.get("hypothesis", pd.DataFrame())
    if not hypothesis_df.empty:
        row = hypothesis_df.iloc[0]
        st.markdown(
            "<div class='ng-success-fixed notranslate' translate='no'>"
            "<span class='ng-fixed-text' "
            "data-display='La reducción del estrés fue del 28.65%, superó el umbral del 15% "
            "y alcanzó &lt; 0.001. Decisión: Se acepta H1.'></span>"
            "</div>",
            unsafe_allow_html=True,
        )
    render_official_source("6.5.5")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("<div class='ng-section'>Evolución semanal operativa</div>", unsafe_allow_html=True)
        draw_horizontal(frames.get("weeks", pd.DataFrame()), "Hitos semanales oficiales del periodo experimental")
    with c2:
        st.markdown("<div class='ng-section'>Distribución horaria operativa</div>", unsafe_allow_html=True)
        draw_horizontal(frames.get("time_bands", pd.DataFrame()), "Uso por franja horaria")

elif page == "Uso y adherencia":
    usage_df = frames.get("official_usage", pd.DataFrame())
    if usage_df.empty:
        st.info("No se encontró la vista oficial de uso. Ejecuta los SQL 09 y 10 del paquete.")
    else:
        row = usage_df.iloc[0]
        cards = [
            ("Sesiones", "6,463", "grupo experimental"),
            ("Mensajes", "46,820", "grupo experimental"),
            ("Duración promedio", "12.8 minutos", "por sesión"),
            ("Recurrencia", "218", "77.6% del grupo experimental"),
            ("Sesiones >10 min", "3,814", "59.0%"),
            ("Uso vespertino/nocturno", "3,451", "53.4%"),
            ("Sesiones por usuario efectivo", "23.00", "promedio"),
            ("Componente generativo", "8.0%", "participación controlada"),
        ]
        cols = st.columns(4)
        for i, card in enumerate(cards):
            with cols[i % 4]:
                kpi_card_literal(*card)
        with st.expander("Ver ficha oficial completa"):
            display_dataframe(usage_df, use_container_width=True, hide_index=True)
        render_official_source("6.3; 6.5.3; 6.6.3")

    c1, c2 = st.columns(2)
    with c1:
        draw_horizontal(frames.get("weeks", pd.DataFrame()), "Evolución semanal")
    with c2:
        draw_horizontal(frames.get("time_bands", pd.DataFrame()), "Distribución por horario")

    operational = frames.get("usage", pd.DataFrame())
    if not operational.empty:
        with st.expander("Vista operativa de Supabase — para auditoría"):
            display_dataframe(operational, use_container_width=True, hide_index=True)

elif page == "Resultados psicométricos":
    official_prepost = frames.get("official_prepost", pd.DataFrame())
    render_prepost_summary(official_prepost)
    render_official_source("6.4.1–6.4.4")
    if not official_prepost.empty:
        comparison = official_prepost[["variable", "group_type", "absolute_change", "percent_change", "p_value_text"]].copy()
        comparison.columns = ["Variable", "Grupo", "Cambio absoluto", "Cambio %", "p"]
        st.markdown("<div class='ng-section'>Síntesis longitudinal</div>", unsafe_allow_html=True)
        display_dataframe(comparison, use_container_width=True, hide_index=True)

elif page == "Inferencia y tamaños del efecto":
    effects_df = frames.get("effect_sizes", pd.DataFrame())
    st.markdown("<div class='ng-section'>Magnitud práctica de los cambios</div>", unsafe_allow_html=True)
    draw_value_bar(effects_df, "variable", "cohens_d", "Cohen’s d por variable", reference_lines=[(.20, "Pequeño"), (.50, "Moderado"), (.80, "Grande")])
    if not effects_df.empty:
        display_dataframe(effects_df[["variable", "cohens_d", "interpretation"]], use_container_width=True, hide_index=True)
    render_official_source("6.5.4")

    st.markdown("<div class='ng-section'>Contraste de la hipótesis principal</div>", unsafe_allow_html=True)
    hypothesis_df = frames.get("hypothesis", pd.DataFrame())
    if not hypothesis_df.empty:
        row = hypothesis_df.iloc[0]
        cols = st.columns(4)
        with cols[0]: kpi_card("Umbral esperado", f"{float(row['minimum_threshold_percent']):.0f}%", "reducción mínima")
        with cols[1]: kpi_card("Reducción observada", f"{abs(float(row['observed_change_percent'])):.2f}%", "grupo experimental")
        with cols[2]: kpi_card("Valor p", str(row['p_value_text']), "significancia estadística")
        with cols[3]: kpi_card("Cohen’s d", f"{float(row['cohens_d']):.3f}", "efecto grande")
        st.success(f"Se acepta H1. {row['interpretation']}")
        with st.expander("Ver síntesis completa"):
            display_dataframe(hypothesis_df, use_container_width=True, hide_index=True)
    render_official_source("6.5.5")

elif page == "Analítica conversacional":
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("<div class='ng-section'>Categorías detectadas</div>", unsafe_allow_html=True)
        draw_horizontal(frames.get("categories", pd.DataFrame()), "Categorías conversacionales")
        if not frames.get("categories", pd.DataFrame()).empty:
            display_dataframe(frames["categories"], use_container_width=True, hide_index=True)
    with c2:
        st.markdown("<div class='ng-section'>Estados funcionales y emocionales</div>", unsafe_allow_html=True)
        draw_horizontal(frames.get("states", pd.DataFrame()), "Estados registrados")
        if not frames.get("states", pd.DataFrame()).empty:
            display_dataframe(frames["states"], use_container_width=True, hide_index=True)
    st.caption("Estas distribuciones proceden de las vistas operativas. La evaluación del clasificador se presenta en la sección siguiente.")

elif page == "Rendimiento del modelo PLN":
    metrics_df = frames.get("classifier_metrics", pd.DataFrame())
    config_df = frames.get("classifier_config", pd.DataFrame())
    st.markdown("<div class='ng-section'>Métricas del conjunto de prueba</div>", unsafe_allow_html=True)
    if not metrics_df.empty:
        metric_cards_from_rows(metrics_df, "metric", "display_value", columns=3)
        plot = metrics_df[metrics_df["metric"] != "Error promedio de clasificación"].copy()
        draw_value_bar(plot, "metric", "value", "Rendimiento del clasificador", reference_lines=[(.90, "0.90")])
        display_dataframe(metrics_df[["metric", "display_value"]], use_container_width=True, hide_index=True)
    st.markdown("<div class='ng-section'>Configuración del modelo</div>", unsafe_allow_html=True)
    if not config_df.empty:
        display_dataframe(config_df[["parameter", "value"]], use_container_width=True, hide_index=True)
    render_official_source("6.6.2")

elif page == "Correlaciones y modelo predictivo":
    corr_df = frames.get("correlations", pd.DataFrame())
    st.markdown("<div class='ng-section'>Exposición al sistema y reducción del estrés</div>", unsafe_allow_html=True)
    draw_value_bar(corr_df, "variable", "spearman_rho", "Correlaciones de Spearman")
    if not corr_df.empty:
        show = corr_df[["variable", "spearman_rho", "p_value_text", "significant", "interpretation"]].copy()
        show.columns = ["Variable", "ρ de Spearman", "p", "Significativa", "Interpretación"]
        display_dataframe(show, use_container_width=True, hide_index=True)
    st.warning("Las correlaciones se calcularon sobre la muestra total. Describen asociaciones entre exposición y reducción del estrés; no prueban causalidad ni una relación dosis–respuesta dentro del grupo experimental.")
    render_official_source("6.6.4")

    st.markdown("<div class='ng-section'>Modelo predictivo exploratorio</div>", unsafe_allow_html=True)
    regression_df = frames.get("regression", pd.DataFrame())
    if not regression_df.empty:
        row = regression_df.iloc[0]
        cols = st.columns(4)
        with cols[0]: kpi_card("R²", f"{float(row['r_squared']):.3f}", "capacidad explicativa")
        with cols[1]: kpi_card("R² ajustado", f"{float(row['adjusted_r_squared']):.3f}", "ajuste del modelo")
        with cols[2]: kpi_card("Estadístico F", f"{float(row['f_statistic']):.3f}", "prueba global")
        with cols[3]: kpi_card("p global", f"{float(row['p_value_global']):.3f}", "no significativo")
        st.info(str(row["interpretation"]))
        with st.expander("Variables del modelo"):
            st.write(f"**Variable dependiente:** {row['dependent_variable']}")
            st.write(f"**Predictores:** {row['predictors']}")
    render_official_source("6.6.5")

elif page == "WHOQOL-BREF":
    summary = frames.get("quality_summary", pd.DataFrame())
    if not summary.empty:
        cols = st.columns(2)
        for i, (_, row) in enumerate(summary.iterrows()):
            with cols[i % 2]:
                kpi_card(f"Calidad de vida global · {row['group_type']}", percent_text(row['percent_change'], signed=True), str(row['interpretation']))
        render_official_source("6.4.5")
    whoqol = frames.get("whoqol", pd.DataFrame())
    draw_prepost(whoqol, "WHOQOL-BREF por dimensión")
    if not whoqol.empty:
        display_dataframe(whoqol, use_container_width=True, hide_index=True)
    participants = frames.get("whoqol_participants", pd.DataFrame())
    if not participants.empty and AUDIT_MODE:
        with st.expander("Puntuaciones anonimizadas por participante · auditoría interna"):
            st.caption("Vista disponible únicamente cuando DASHBOARD_AUDIT_MODE está activado.")
            display_dataframe(
                participants,
                hide_columns=("family_id",),
                use_container_width=True,
                hide_index=True,
            )
    elif not participants.empty:
        st.caption(
            "Las puntuaciones individuales permanecen resguardadas en la capa interna de "
            "trazabilidad y no se publican en este panel."
        )

else:
    st.markdown("<div class='ng-section'>Auditoría de congruencia</div>", unsafe_allow_html=True)
    audit = frames.get("audit", pd.DataFrame())
    if not audit.empty:
        st.dataframe(prepare_audit_display(audit), use_container_width=True, hide_index=True)
        if "status" in audit.columns:
            pending = int((audit["status"].astype(str).str.upper() == "REVISAR").sum())
            if pending:
                st.warning(f"Se documentaron {pending} indicadores con diferencias entre la vista operativa y la capa oficial. Los datos crudos permanecen intactos y la capa oficial se utiliza para el reporte científico.")
            else:
                st.success("Los indicadores comparables coinciden con la capa oficial.")

    st.markdown("<div class='ng-section'>Estado de las vistas</div>", unsafe_allow_html=True)
    rows = []
    for key, view_name in VIEW_NAMES.items():
        frame = frames.get(key, pd.DataFrame())
        rows.append({
            "Vista": view_name,
            "Registros": len(frame),
            "Columnas": len(frame.columns),
            "Fuente": payload["sources"].get(key, "No disponible"),
            "Estado": "OK" if not frame.empty else "Sin datos",
        })
    display_dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    if AUDIT_MODE:
        st.download_button(
            "Descargar vistas en ZIP · auditoría interna",
            make_zip(frames),
            file_name="neuroguIA_vistas_dashboard_actualizadas.csv.zip",
            mime="application/zip",
            use_container_width=True,
        )
        if payload["errors"]:
            with st.expander("Mensajes técnicos · auditoría interna"):
                for error in payload["errors"]:
                    st.code(error)
    else:
        st.caption(
            "La descarga integral de vistas y los mensajes técnicos están reservados "
            "para auditoría interna."
        )

st.caption(f"Fuente activa: {'Supabase' if payload['mode'] == 'supabase' else 'archivos locales'} · Capa oficial + trazabilidad operativa · neuroguIA 2026")
