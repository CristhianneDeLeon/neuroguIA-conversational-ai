# -*- coding: utf-8 -*-
"""Ejecuta las verificaciones técnicas de cierre para la defensa de neuroguIA.

Este script no modifica:
- versiones;
- datos experimentales;
- configuración productiva;
- resultados estadísticos;
- taxonomías.

Únicamente ejecuta validaciones existentes y genera
un resumen reproducible de su resultado.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


# =========================================================
# Configuración general
# =========================================================

ROOT = Path(__file__).resolve().parents[1]

OUTPUT_DIR = ROOT / "validation_outputs"

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# =========================================================
# Validaciones estrictas para el cierre de defensa
# =========================================================

CHECKS = [
    (
        "thesis_contract",
        "scripts/validate_thesis_contract.py",
    ),
    (
        "supabase_bridge_contract",
        "scripts/validate_supabase_bridge_contract.py",
    ),
    (
        "functional_support",
        "scripts/validate_functional_support.py",
    ),
    (
        "routine_delivery",
        "scripts/validate_routine_delivery.py",
    ),
    (
        "routine_persistence",
        "scripts/validate_routine_persistence.py",
    ),
    (
        "orchestrator_routine_persistence",
        "scripts/validate_orchestrator_routine_persistence.py",
    ),
    (
        "routine_conversational_recall",
        "scripts/validate_routine_conversational_recall.py",
    ),
    (
        "routine_conversational_update",
        "scripts/validate_routine_conversational_update.py",
    ),
    (
        "gateway_contract",
        "scripts/validate_gateway_contract.py",
    ),
    (
        "conversation_continuity",
        "scripts/validate_conversation_continuity.py",
    ),
]

def run_check(
    name: str,
    rel_script: str,
) -> Dict[str, Any]:
    """Ejecuta una validación de forma aislada."""

    env = os.environ.copy()

    # Garantiza que la raíz del repositorio
    # esté disponible para los imports.
    current_pythonpath = env.get(
        "PYTHONPATH",
        "",
    )

    env["PYTHONPATH"] = (
        str(ROOT)
        + os.pathsep
        + current_pythonpath
    )

    script_path = ROOT / rel_script

    if not script_path.exists():
        return {
            "name": name,
            "script": rel_script,
            "passed": False,
            "returncode": -1,
            "stdout": "",
            "stderr": (
                f"No se encontró el script: {rel_script}"
            ),
        }

    completed = subprocess.run(
        [
            sys.executable,
            str(script_path),
        ],
        cwd=str(ROOT),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    return {
        "name": name,
        "script": rel_script,
        "passed": (
            completed.returncode == 0
        ),
        "returncode": (
            completed.returncode
        ),
        "stdout": (
            completed.stdout.strip()
        ),
        "stderr": (
            completed.stderr.strip()
        ),
    }


def main() -> int:
    """Ejecuta todas las verificaciones y genera un reporte."""

    rows: List[Dict[str, Any]] = []

    print("=" * 92)

    print(
        "NEUROGUIA - "
        "VALIDACIÓN DE CIERRE PARA DEFENSA"
    )

    print("=" * 92)

    # -----------------------------------------------------
    # Ejecutar cada prueba
    # -----------------------------------------------------

    for name, script in CHECKS:

        print(
            f"Ejecutando: {name}..."
        )

        row = run_check(
            name,
            script,
        )

        rows.append(row)

    # -----------------------------------------------------
    # Determinar resultado general
    # -----------------------------------------------------

    failures = [
        row
        for row in rows
        if not row["passed"]
    ]

    passed_count = (
        len(rows)
        - len(failures)
    )

    # -----------------------------------------------------
    # Construir reporte reproducible
    # -----------------------------------------------------

    report = {
        "name":
            "neuroguIA defense validation gate",

        "generated_at_utc":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "branch_expected":
            "defensa-2026",

        "modifies_versions":
            False,

        "modifies_experimental_results":
            False,

        "passed":
            not failures,

        "checks_passed":
            passed_count,

        "checks_total":
            len(rows),

        "checks":
            rows,
    }

    output_path = (
        OUTPUT_DIR
        / "defense_validation_summary.json"
    )

    output_path.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # -----------------------------------------------------
    # Mostrar resumen en consola
    # -----------------------------------------------------

    print()
    print("-" * 92)

    for row in rows:

        status = (
            "OK"
            if row["passed"]
            else "FALLO"
        )

        print(
            f"{status:<5} | "
            f"{row['name']:<28} | "
            f"{row['script']}"
        )

        if not row["passed"]:

            if row["stderr"]:
                print(
                    "      ERROR: "
                    + row["stderr"]
                    .splitlines()[-1]
                )

            elif row["stdout"]:
                print(
                    "      SALIDA: "
                    + row["stdout"]
                    .splitlines()[-1]
                )

    print("-" * 92)

    print(
        f"Resultado general: "
        f"{passed_count}/"
        f"{len(rows)} "
        "verificaciones superadas"
    )

    print(
        f"Reporte generado: "
        f"{output_path}"
    )

    if failures:

        print()
        print(
            "ESTADO DE DEFENSA: "
            "REQUIERE REVISIÓN"
        )

        return 1

    print()
    print(
        "ESTADO DE DEFENSA: "
        "VALIDACIONES BASE SUPERADAS"
    )

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
