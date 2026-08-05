from __future__ import annotations

from pathlib import Path
import hashlib
import pandas as pd

BASE = Path(__file__).resolve().parent
MASTER = BASE / "data" / "NeuroGuIA_Documento_Maestro_Oficial_v3_AUDITADO.xlsx"
REQUIRED = {
    "M02_PARAMETROS", "M05_DASS_PREPOST", "M06_DASS_RESUMEN", "M07_ANCOVA",
    "M08_EFECTOS", "M09_MSPSS_OFICIAL", "M10_APOYO_AUXILIAR",
    "M12_WHOQOL_RESUMEN", "M14_USO_OFICIAL", "M14A_USO_PARTICIPANTE",
    "M14B_USO_SEMANAL", "M14C_CORRELACIONES", "M17_PLN_OFICIAL",
    "M17D_PLN_CATEGORIAS", "M22_CONTROL_CALIDAD", "M24_ID_CROSSWALK",
    "M25_BASE_INTEGRADA", "M35_REPRODUCIBILIDAD",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read(name: str) -> pd.DataFrame:
    return pd.read_excel(MASTER, sheet_name=name, header=2, engine="openpyxl").dropna(how="all")


def main() -> None:
    if not MASTER.exists():
        raise SystemExit(f"Falta el archivo maestro: {MASTER}")
    with pd.ExcelFile(MASTER, engine="openpyxl") as xf:
        missing = sorted(REQUIRED - set(xf.sheet_names))
    if missing:
        raise SystemExit(f"Faltan hojas: {missing}")

    params = read("M02_PARAMETROS")
    p = dict(zip(params["Parámetro"].astype(str), params["Valor"]))
    expected = {
        "N total": 562, "N experimental": 281, "N control": 281, "Familias": 281,
        "Sesiones técnicas totales": 6463, "Mensajes técnicos totales": 47670,
        "Sesiones ventana activa": 1325,
    }
    failures = [f"{k}: {p.get(k)} != {v}" for k, v in expected.items() if float(p.get(k, -1)) != float(v)]

    cross = read("M24_ID_CROSSWALK")
    if len(cross) != 562 or cross["family_code"].nunique() != 281:
        failures.append(f"Crosswalk inválido: filas={len(cross)}, familias={cross['family_code'].nunique()}")

    weekly = read("M14B_USO_SEMANAL")
    active = weekly[weekly["estado"].astype(str).str.contains("Intervención", case=False, na=False)]
    if len(active) != 18 or int(active["sesiones"].sum()) != 1325:
        failures.append(f"Ventana semanal inválida: semanas={len(active)}, sesiones={active['sesiones'].sum()}")

    if failures:
        raise SystemExit("\n".join(failures))

    print("SELF-CHECK OK")
    print(f"Archivo: {MASTER.name}")
    print(f"SHA-256: {sha256(MASTER)}")
    print("Participantes: 562 · Familias: 281 · Semanas: 18 · Sesiones activas: 1,325")


if __name__ == "__main__":
    main()
