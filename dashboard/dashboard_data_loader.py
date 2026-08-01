from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID
import json
import os

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

BASE_DIR = Path(__file__).resolve().parent
OUTPUTS_DIR = BASE_DIR / "outputs"

VIEW_NAMES = {
    "kpis": "v_dashboard_kpis",
    "sessions": "v_dashboard_sessions",
    "prepost": "v_dashboard_prepost",
    "usage": "v_dashboard_usage",
    "categories": "v_dashboard_categories",
    "states": "v_dashboard_states",
    "time_bands": "v_dashboard_time_bands",
    "weeks": "v_dashboard_weeks",
    "whoqol": "v_dashboard_whoqol",
    "whoqol_participants": "v_whoqol_participant_scores",
    "official_usage": "v_dashboard_usage_official",
    "official_prepost": "v_dashboard_prepost_official",
    "effect_sizes": "v_dashboard_effect_sizes",
    "hypothesis": "v_dashboard_hypothesis",
    "classifier_config": "v_dashboard_classifier_config",
    "classifier_metrics": "v_dashboard_classifier_metrics",
    "correlations": "v_dashboard_correlations",
    "regression": "v_dashboard_regression",
    "quality_summary": "v_dashboard_quality_summary",
    "audit": "v_dashboard_consistency_audit",
}

LOCAL_FALLBACKS = {
    "kpis": ("v_dashboard_kpis.csv", "dashboard_kpis.json"),
    "sessions": ("v_dashboard_sessions.csv", "usage_metrics_summary.csv", "master_results_dataset.csv"),
    "prepost": ("v_dashboard_prepost.csv", "prepost_group_comparison.csv", "chapter6_summary_results.csv", "master_results_dataset.csv"),
    "usage": ("v_dashboard_usage.csv", "usage_metrics_summary.csv", "master_results_dataset.csv"),
    "categories": ("v_dashboard_categories.csv", "ai_metrics_summary.csv"),
    "states": ("v_dashboard_states.csv", "ai_metrics_summary.csv"),
    "time_bands": ("v_dashboard_time_bands.csv", "usage_metrics_summary.csv"),
    "weeks": ("v_dashboard_weeks.csv", "usage_metrics_summary.csv"),
    "whoqol": ("v_dashboard_whoqol.csv", "master_results_dataset.csv"),
    "whoqol_participants": ("v_whoqol_participant_scores.csv", "master_results_dataset.csv"),
    "official_usage": ("dashboard_official_usage.csv",),
    "official_prepost": ("dashboard_official_prepost.csv",),
    "effect_sizes": ("dashboard_effect_sizes.csv",),
    "hypothesis": ("dashboard_hypothesis.csv",),
    "classifier_config": ("dashboard_classifier_config.csv",),
    "classifier_metrics": ("dashboard_classifier_metrics.csv",),
    "correlations": ("dashboard_correlations.csv",),
    "regression": ("dashboard_regression.csv",),
    "quality_summary": ("dashboard_quality_summary.csv",),
    "audit": ("auditoria_dashboard_vs_capitulo6.csv",),
}


def _secret(name: str) -> str:
    value = str(os.getenv(name, "") or "").strip()
    if value:
        return value
    try:
        secrets = st.secrets
    except Exception:
        return ""
    try:
        if name in secrets:
            return str(secrets[name] or "").strip()
    except Exception:
        pass
    for section_name in ("database", "DATABASE", "supabase", "SUPABASE"):
        try:
            section = secrets.get(section_name)
        except Exception:
            section = None
        if hasattr(section, "get"):
            for candidate in (name, name.lower()):
                try:
                    value = section.get(candidate)
                except Exception:
                    value = None
                if value:
                    return str(value).strip()
    return ""


def _sqlalchemy_url(raw_url: str) -> str:
    url = raw_url.strip()
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


@st.cache_resource(show_spinner=False)
def _engine(database_url: str) -> Engine:
    return create_engine(
        _sqlalchemy_url(database_url),
        pool_pre_ping=True,
        pool_recycle=300,
        connect_args={"connect_timeout": 15},
    )


def _safe_cell(value: object) -> object:
    """Convierte tipos de PostgreSQL que Arrow/Streamlit no representa bien."""
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    if isinstance(value, memoryview):
        return bytes(value).hex()
    return value


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    out.columns = (
        out.columns.astype(str)
        .str.strip()
        .str.lower()
        .str.replace(" ", "_", regex=False)
        .str.replace("-", "_", regex=False)
    )
    for column in out.select_dtypes(include=["object"]).columns:
        out[column] = out[column].map(_safe_cell)
    return out.dropna(how="all").reset_index(drop=True)


@st.cache_data(ttl=300, show_spinner=False)
def _read_view(database_url: str, view_name: str) -> pd.DataFrame:
    if view_name not in VIEW_NAMES.values():
        raise ValueError(f"Vista no permitida: {view_name}")
    query = text(f'SELECT * FROM public."{view_name}"')
    with _engine(database_url).connect() as connection:
        return _normalize(pd.read_sql_query(query, connection))


def _find_local(names: tuple[str, ...]) -> Path | None:
    folders = (OUTPUTS_DIR, BASE_DIR / "exports", BASE_DIR / "data", BASE_DIR)
    for folder in folders:
        for name in names:
            candidate = folder / name
            if candidate.exists() and candidate.is_file():
                return candidate
    return None


def _read_local(key: str) -> tuple[pd.DataFrame, str | None]:
    candidate = _find_local(LOCAL_FALLBACKS.get(key, ()))
    if candidate is None:
        return pd.DataFrame(), None
    try:
        if candidate.suffix.lower() == ".json":
            payload = json.loads(candidate.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return _normalize(pd.DataFrame([payload])), str(candidate.relative_to(BASE_DIR))
            return _normalize(pd.DataFrame(payload)), str(candidate.relative_to(BASE_DIR))
        return _normalize(pd.read_csv(candidate)), str(candidate.relative_to(BASE_DIR))
    except Exception:
        return pd.DataFrame(), str(candidate.relative_to(BASE_DIR))


def load_dashboard_data() -> dict[str, Any]:
    database_url = _secret("DATABASE_URL")
    frames: dict[str, pd.DataFrame] = {}
    errors: list[str] = []
    sources: dict[str, str] = {}

    if database_url:
        for key, view_name in VIEW_NAMES.items():
            try:
                frames[key] = _read_view(database_url, view_name)
                sources[key] = f"Supabase · public.{view_name}"
            except Exception as exc:
                frames[key] = pd.DataFrame()
                errors.append(f"{view_name}: {type(exc).__name__}: {exc}")
        mode = "supabase"
    else:
        for key in VIEW_NAMES:
            frame, source = _read_local(key)
            frames[key] = frame
            if source:
                sources[key] = f"Archivo local · {source}"
        errors.append("DATABASE_URL no está configurada; se utilizó el respaldo local disponible.")
        mode = "local"

    return {
        "frames": frames,
        "sources": sources,
        "errors": errors,
        "mode": mode,
        "loaded_at": datetime.now(timezone.utc).isoformat(),
    }


def clear_dashboard_cache() -> None:
    st.cache_data.clear()
    st.cache_resource.clear()
