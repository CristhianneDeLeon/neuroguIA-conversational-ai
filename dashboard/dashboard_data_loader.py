# -*- coding: utf-8 -*-
"""Carga canónica del dashboard neuroguIA v3.

El dashboard se alimenta exclusivamente del Documento Maestro Oficial v3 auditado.
No sustituye cifras con constantes, CSV históricos ni vistas operativas de Supabase.
"""
from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any
import hashlib
import os
import re
import zipfile

import pandas as pd
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_MASTER = BASE_DIR / "data" / "NeuroGuIA_Documento_Maestro_Oficial_v3_AUDITADO.xlsx"

SHEETS = {
    "parameters": "M02_PARAMETROS",
    "dass_summary": "M06_DASS_RESUMEN",
    "ancova": "M07_ANCOVA",
    "effects": "M08_EFECTOS",
    "mspss_official": "M09_MSPSS_OFICIAL",
    "support_individual": "M10_APOYO_AUXILIAR",
    "whoqol_summary": "M12_WHOQOL_RESUMEN",
    "whoqol_scores": "M12A_WHOQOL_PUNTAJES",
    "experience_summary": "M13_EXPERIENCIA_POST",
    "experience_scores": "M13A_EXPERIENCIA_PUNTAJES",
    "usage_official": "M14_USO_OFICIAL",
    "usage_participant": "M14A_USO_PARTICIPANTE",
    "usage_weekly": "M14B_USO_SEMANAL",
    "correlations": "M14C_CORRELACIONES",
    "regression": "M14D_REGRESION_USO",
    "historical_metrics": "M14E_METRICAS_HIST",
    "time_bands": "M16_FRANJAS_HORARIAS",
    "pln_official": "M17_PLN_OFICIAL",
    "pln_metrics": "M17B_PLN_METRICAS",
    "pln_confusion": "M17C_PLN_CONFUSION",
    "pln_categories": "M17D_PLN_CATEGORIAS",
    "traceability": "M21_TRAZABILIDAD",
    "quality_control": "M22_CONTROL_CALIDAD",
    "exclusions": "M23_EXCLUSIONES",
    "id_crosswalk": "M24_ID_CROSSWALK",
    "socio_descriptives": "M27_SOCIO_DESCRIPT",
    "baseline_comparability": "M28_COMPARABILIDAD",
    "normality": "M29_NORMALIDAD",
    "ancova_assumptions": "M30_SUPUESTOS_ANCOVA",
    "nonparametric": "M31_NO_PARAMETRICAS",
    "sample_flow": "M33_FLUJO_MUESTRA",
    "missing_data": "M34_DATOS_FALTANTES",
    "reproducibility": "M35_REPRODUCIBILIDAD",
    "validation_status": "M36_VALIDACION_ESTADO",
}

def _master_path() -> Path:
    configured = str(os.getenv("NEUROGUIA_MASTER_XLSX", "") or "").strip()
    return Path(configured).expanduser().resolve() if configured else DEFAULT_MASTER


def _snake(value: object) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("%", " pct ").replace("²", "2").replace("ρ", "rho")
    text = re.sub(r"[^0-9a-záéíóúüñ]+", "_", text, flags=re.IGNORECASE)
    return text.strip("_")


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    out.columns = [_snake(c) for c in out.columns]
    out = out.dropna(how="all").reset_index(drop=True)
    for column in out.select_dtypes(include=["object"]).columns:
        out[column] = out[column].map(lambda x: x.strip() if isinstance(x, str) else x)
    return out


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@st.cache_data(show_spinner=False)
def _read_required_sheets(path_text: str, mtime_ns: int, sheet_names: tuple[str, ...]) -> dict[str, pd.DataFrame]:
    del mtime_ns  # fuerza invalidación de caché cuando cambia el archivo
    raw = pd.read_excel(path_text, sheet_name=list(sheet_names), header=2, engine="openpyxl")
    return {name: _normalize(frame) for name, frame in raw.items()}


@st.cache_data(show_spinner=False)
def _sheet_names(path_text: str, mtime_ns: int) -> list[str]:
    del mtime_ns
    with pd.ExcelFile(path_text, engine="openpyxl") as workbook:
        return list(workbook.sheet_names)


def load_dashboard_data() -> dict[str, Any]:
    path = _master_path()
    errors: list[str] = []
    warnings: list[str] = []
    frames: dict[str, pd.DataFrame] = {}

    if not path.exists():
        return {
            "frames": frames,
            "errors": [f"No se encontró el maestro canónico: {path}"],
            "warnings": warnings,
            "master_path": str(path),
            "master_sha256": "",
            "loaded_at": datetime.now(timezone.utc).isoformat(),
        }

    stat = path.stat()
    try:
        available = set(_sheet_names(str(path), stat.st_mtime_ns))
    except Exception as exc:
        return {
            "frames": frames,
            "errors": [f"No fue posible abrir el Excel maestro: {type(exc).__name__}: {exc}"],
            "warnings": warnings,
            "master_path": str(path),
            "master_sha256": "",
            "loaded_at": datetime.now(timezone.utc).isoformat(),
        }

    present_names = tuple(name for name in SHEETS.values() if name in available)
    try:
        loaded = _read_required_sheets(str(path), stat.st_mtime_ns, present_names)
    except Exception as exc:
        loaded = {}
        errors.append(f"No fue posible leer las hojas del maestro: {type(exc).__name__}: {exc}")

    for key, sheet_name in SHEETS.items():
        if sheet_name not in available:
            frames[key] = pd.DataFrame()
            errors.append(f"Falta la hoja requerida {sheet_name} ({key}).")
        else:
            frames[key] = loaded.get(sheet_name, pd.DataFrame())

    # Reglas de consistencia mínimas para evitar publicar un dashboard desalineado.
    params = parameter_map(frames.get("parameters", pd.DataFrame()))
    expected = {
        "n total": 562,
        "n experimental": 281,
        "n control": 281,
        "familias": 281,
        "sesiones técnicas totales": 6463,
        "mensajes técnicos totales": 47670,
        "sesiones ventana activa": 1325,
    }
    for label, expected_value in expected.items():
        actual = params.get(label)
        try:
            if actual is None or float(actual) != float(expected_value):
                warnings.append(f"Parámetro '{label}': esperado {expected_value}, encontrado {actual}.")
        except Exception:
            warnings.append(f"Parámetro '{label}' no es numérico: {actual!r}.")

    crosswalk = frames.get("id_crosswalk", pd.DataFrame())
    if not crosswalk.empty:
        if len(crosswalk) != 562:
            warnings.append(f"El crosswalk contiene {len(crosswalk)} filas; se esperaban 562.")
        if "family_code" in crosswalk.columns and crosswalk["family_code"].nunique(dropna=True) != 281:
            warnings.append("El crosswalk no contiene exactamente 281 family_code canónicos.")

    return {
        "frames": frames,
        "errors": errors,
        "warnings": warnings,
        "master_path": str(path),
        "master_name": path.name,
        "master_sha256": _sha256(path),
        "master_bytes": stat.st_size,
        "loaded_at": datetime.now(timezone.utc).isoformat(),
    }


def parameter_map(df: pd.DataFrame) -> dict[str, object]:
    if df is None or df.empty or not {"parámetro", "valor"}.issubset(df.columns):
        return {}
    return {
        str(row["parámetro"]).strip().lower(): row["valor"]
        for _, row in df.dropna(subset=["parámetro"]).iterrows()
    }


def indicator_map(df: pd.DataFrame) -> dict[str, object]:
    if df is None or df.empty or not {"indicador", "valor"}.issubset(df.columns):
        return {}
    return {
        str(row["indicador"]).strip().lower(): row["valor"]
        for _, row in df.dropna(subset=["indicador"]).iterrows()
    }


def clear_dashboard_cache() -> None:
    st.cache_data.clear()


def frames_to_zip(frames: dict[str, pd.DataFrame]) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for key, frame in frames.items():
            if frame is None or frame.empty:
                continue
            archive.writestr(f"{key}.csv", frame.to_csv(index=False).encode("utf-8-sig"))
    return buffer.getvalue()
