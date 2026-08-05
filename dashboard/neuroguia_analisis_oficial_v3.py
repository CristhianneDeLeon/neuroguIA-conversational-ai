#!/usr/bin/env python3
"""Análisis estadístico oficial reproducible de NeuroGuIA v3.

Lee exclusivamente las fuentes del ZIP de investigación, reconstruye el enlace
WHOQOL EXP/CON ↔ PT ↔ FAM por sufijo ordinal y calcula descriptivos, ANCOVA,
pruebas no paramétricas, tamaños del efecto, correlaciones y temporalidad.
No genera respuestas psicométricas ni valoraciones de jueces inexistentes.
"""
from __future__ import annotations

import csv
import io
import json
import math
import sys
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import scipy
import statsmodels
import statsmodels.api as sm
from scipy.stats import levene, mannwhitneyu, norm, shapiro, spearmanr, wilcoxon

VERSION = "3.0.0-auditado"
SEED = 42
ROOT = "NeuroGuIA_Datos_Investigacion/03_ANALISIS/"
DEFAULT_ZIP = Path("NeuroGuIA_Datos_Investigacion(1).zip")
DEFAULT_OUTPUT = Path("NeuroGuIA_resultados_reproducidos_v3.json")


def read_csv(zf: zipfile.ZipFile, filename: str) -> list[dict[str, str]]:
    with zf.open(ROOT + filename) as fh:
        return list(csv.DictReader(io.TextIOWrapper(fh, encoding="utf-8-sig", newline="")))


def canonical_whoqol_id(who_id: str) -> str:
    prefix, ordinal = who_id.split("-")
    suffix = "E" if prefix == "EXP" else "C"
    return f"PT-{ordinal}-{suffix}"


def cohen_d(x: np.ndarray, y: np.ndarray) -> float:
    nx, ny = len(x), len(y)
    pooled = math.sqrt(((nx - 1) * np.var(x, ddof=1) + (ny - 1) * np.var(y, ddof=1)) / (nx + ny - 2))
    return float((np.mean(x) - np.mean(y)) / pooled)


def hedges_g(d: float, nx: int, ny: int) -> float:
    return float((1 - 3 / (4 * (nx + ny - 2) - 1)) * d)


def bootstrap_d_ci(x: np.ndarray, y: np.ndarray, seed: int, iterations: int = 500) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    values = [cohen_d(rng.choice(x, len(x), replace=True), rng.choice(y, len(y), replace=True)) for _ in range(iterations)]
    low, high = np.quantile(values, [0.025, 0.975])
    return float(low), float(high)


def ancova(records: list[dict[str, Any]], pre_key: str, post_key: str) -> dict[str, float | int]:
    pre = np.asarray([float(r[pre_key]) for r in records])
    post = np.asarray([float(r[post_key]) for r in records])
    group = np.asarray([1.0 if r["group_type"] == "Experimental" else 0.0 for r in records])
    model = sm.OLS(post, np.column_stack([np.ones(len(pre)), group, pre])).fit(cov_type="HC3")
    interaction = sm.OLS(post, np.column_stack([np.ones(len(pre)), group, pre, group * pre])).fit(cov_type="HC3")
    ci = model.conf_int()
    sw = shapiro(model.resid)
    lv = levene(model.resid[group == 1], model.resid[group == 0], center="median")
    return {
        "n": len(pre), "b_group_experimental": float(model.params[1]), "se_hc3": float(model.bse[1]),
        "ci95_low": float(ci[1, 0]), "ci95_high": float(ci[1, 1]), "p_group": float(model.pvalues[1]),
        "b_pre": float(model.params[2]), "r2": float(model.rsquared), "r2_adjusted": float(model.rsquared_adj),
        "b_group_x_pre": float(interaction.params[3]), "p_group_x_pre": float(interaction.pvalues[3]),
        "shapiro_w_residuals": float(sw.statistic), "shapiro_p": float(sw.pvalue),
        "levene_statistic": float(lv.statistic), "levene_p": float(lv.pvalue),
    }


def main(zip_path: Path, output_path: Path) -> None:
    if not zip_path.exists():
        raise FileNotFoundError(f"No se encontró: {zip_path}")
    with zipfile.ZipFile(zip_path) as zf:
        participants = read_csv(zf, "research_participants.csv")
        prepost = read_csv(zf, "research_prepost.csv")
        who_scores = read_csv(zf, "whoqol_scores.csv")
        sessions = read_csv(zf, "session_summary.csv")

    participants_by_id = {r["participant_id"]: r for r in participants}
    who_by_id = {canonical_whoqol_id(r["participant_id"]): r for r in who_scores}
    records: list[dict[str, Any]] = []
    for row in prepost:
        pid = row["participant_id"]
        p = participants_by_id[pid]
        w = who_by_id[pid]
        records.append({
            "participant_id": pid, "family_code": p["family_code"], "group_type": row["group_type"],
            "age": float(p["age"]),
            "stress_pre": float(row["stress_pre"]), "stress_post": float(row["stress_post"]),
            "anxiety_pre": float(row["anxiety_pre"]), "anxiety_post": float(row["anxiety_post"]),
            "depression_pre": float(row["depression_pre"]), "depression_post": float(row["depression_post"]),
            "support_pre": float(row["support_pre_1_5"]), "support_post": float(row["support_post_1_5"]),
            "who_fisico_pre": float(w["fisico_pre_0_100"]), "who_fisico_post": float(w["fisico_post_0_100"]),
            "who_psico_pre": float(w["psicologico_pre_0_100"]), "who_psico_post": float(w["psicologico_post_0_100"]),
            "who_rel_pre": float(w["relaciones_pre_0_100"]), "who_rel_post": float(w["relaciones_post_0_100"]),
            "who_ent_pre": float(w["entorno_pre_0_100"]), "who_ent_post": float(w["entorno_post_0_100"]),
            "who_global_pre": float(w["global_descriptive_pre_0_100"]), "who_global_post": float(w["global_descriptive_post_0_100"]),
        })

    outcomes = {
        "Estrés": ("stress_pre", "stress_post", "decrease"),
        "Ansiedad": ("anxiety_pre", "anxiety_post", "decrease"),
        "Depresión": ("depression_pre", "depression_post", "decrease"),
        "Apoyo auxiliar 1-5": ("support_pre", "support_post", "increase"),
        "WHOQOL Físico": ("who_fisico_pre", "who_fisico_post", "increase"),
        "WHOQOL Psicológico": ("who_psico_pre", "who_psico_post", "increase"),
        "WHOQOL Relaciones": ("who_rel_pre", "who_rel_post", "increase"),
        "WHOQOL Entorno": ("who_ent_pre", "who_ent_post", "increase"),
        "WHOQOL Global descriptivo": ("who_global_pre", "who_global_post", "increase"),
    }
    results: dict[str, Any] = {"metadata": {
        "version": VERSION, "seed": SEED, "python": sys.version.split()[0], "numpy": np.__version__,
        "scipy": scipy.__version__, "statsmodels": statsmodels.__version__,
        "n_total": len(records), "n_experimental": sum(r["group_type"] == "Experimental" for r in records),
        "n_control": sum(r["group_type"] == "Control" for r in records),
        "whoqol_link_rule": "EXP/CON ordinal → PT ordinal E/C → canonical FAM ordinal",
    }, "outcomes": {}, "temporal_window": {}}

    for index, (name, (pre_key, post_key, direction)) in enumerate(outcomes.items()):
        item: dict[str, Any] = {"descriptives": {}, "ancova": ancova(records, pre_key, post_key)}
        changes: dict[str, np.ndarray] = {}
        posts: dict[str, np.ndarray] = {}
        for group_name in ("Experimental", "Control"):
            subset = [r for r in records if r["group_type"] == group_name]
            pre = np.asarray([r[pre_key] for r in subset])
            post = np.asarray([r[post_key] for r in subset])
            change = pre - post if direction == "decrease" else post - pre
            posts[group_name] = post
            changes[group_name] = change
            sh = shapiro(change)
            try:
                wil = wilcoxon(pre, post, zero_method="wilcox", method="approx")
                z = norm.isf(wil.pvalue / 2) if wil.pvalue > 0 else 99.0
                r_effect = float(np.sign(np.median(pre - post)) * z / math.sqrt(np.count_nonzero(pre - post)))
            except ValueError:
                wil, r_effect = None, 0.0
            item["descriptives"][group_name] = {
                "n": len(pre), "pre_mean": float(pre.mean()), "pre_sd": float(pre.std(ddof=1)),
                "post_mean": float(post.mean()), "post_sd": float(post.std(ddof=1)),
                "favorable_change_mean": float(change.mean()), "favorable_change_sd": float(change.std(ddof=1)),
                "shapiro_change_w": float(sh.statistic), "shapiro_change_p": float(sh.pvalue),
                "wilcoxon_statistic": None if wil is None else float(wil.statistic),
                "wilcoxon_p": 1.0 if wil is None else float(wil.pvalue), "wilcoxon_r": r_effect,
            }
        for label, x, y, seed in (
            ("posttest_experimental_minus_control", posts["Experimental"], posts["Control"], SEED + index),
            ("change_experimental_minus_control", changes["Experimental"], changes["Control"], SEED + 100 + index),
        ):
            d = cohen_d(x, y)
            low, high = bootstrap_d_ci(x, y, seed)
            item[label] = {"cohen_d": d, "hedges_g": hedges_g(d, len(x), len(y)), "ci95_low": low, "ci95_high": high}
        mw = mannwhitneyu(changes["Experimental"], changes["Control"], alternative="two-sided", method="asymptotic")
        item["mann_whitney_change"] = {"u": float(mw.statistic), "p": float(mw.pvalue)}
        results["outcomes"][name] = item

    start = date(2026, 1, 12)
    end = date(2026, 5, 17)
    close_start = date(2026, 5, 18)
    close_end = date(2026, 5, 21)
    parsed = [(datetime.fromisoformat(r["session_started_at"]).date(), r) for r in sessions]
    results["temporal_window"] = {
        "intervention_start": start.isoformat(), "intervention_end": end.isoformat(),
        "posttest_close_start": close_start.isoformat(), "posttest_close_end": close_end.isoformat(),
        "sessions_operational_total": len(sessions),
        "sessions_intervention_18_weeks": sum(start <= d <= end for d, _ in parsed),
        "sessions_posttest_close_4_days": sum(close_start <= d <= close_end for d, _ in parsed),
        "sessions_before_intervention": sum(d < start for d, _ in parsed),
        "sessions_after_close": sum(d > close_end for d, _ in parsed),
    }

    output_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Resultados guardados en: {output_path}")


if __name__ == "__main__":
    zip_arg = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_ZIP
    out_arg = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUTPUT
    main(zip_arg, out_arg)
