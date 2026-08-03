# -*- coding: utf-8 -*-
"""Valida las siete categorías funcionales y la generación de rutinas de neuroguIA.

Ejecución desde la raíz del proyecto:
    python scripts/validate_functional_support.py

El script usa una base SQLite temporal y no necesita secretos ni conexión a Supabase.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.orchestrator_v2 import NeuroGuiaOrchestratorV2
from database.database import initialize_database


CASES: List[Dict[str, str]] = [
    {
        "id": "F01",
        "message": "Estoy muy ansiosa y no sé cómo calmarme",
        "expected_category": "regulacion_emocional",
        "expected_routine": "emotional_landing",
    },
    {
        "id": "F02",
        "message": "Mi hijo no puede empezar la tarea de la escuela",
        "expected_category": "acompanamiento_escolar",
        "expected_routine": "school_support",
    },
    {
        "id": "F03",
        "message": "En casa nadie sabe qué responsabilidad le toca",
        "expected_category": "organizacion_familiar",
        "expected_routine": "family_organization",
    },
    {
        "id": "F04",
        "message": "El ruido y las luces le provocan sobrecarga sensorial",
        "expected_category": "regulacion_sensorial",
        "expected_routine": "sensory_regulation",
    },
    {
        "id": "F05",
        "message": "Estoy agotada de cuidar y todo recae en mí",
        "expected_category": "bienestar_cuidador",
        "expected_routine": "caregiver_recovery",
    },
    {
        "id": "F06",
        "message": "Está en crisis y se puede lastimar",
        "expected_category": "manejo_crisis",
        "expected_routine": "crisis_safety",
    },
    {
        "id": "F07",
        "message": "Necesito una rutina para organizar las mañanas",
        "expected_category": "rutinas_habitos",
        "expected_routine": "morning_organization",
    },
]


def process(
    orchestrator: NeuroGuiaOrchestratorV2,
    message: str,
    previous_frame: Dict[str, Any] | None = None,
    chat_history: List[Dict[str, str]] | None = None,
) -> Dict[str, Any]:
    return orchestrator.process_message(
        message=message,
        chat_history=chat_history or [],
        extra_context={"conversation_frame": previous_frame or {}},
        auto_save_case=False,
        auto_store_system_response=False,
        auto_store_curated_llm_response=False,
        use_llm_stub=True,
    )


def main() -> int:
    rows: List[Dict[str, Any]] = []
    failures = 0

    with tempfile.TemporaryDirectory(prefix="neuroguia_functional_validation_") as tmp:
        db_path = str(Path(tmp) / "functional_validation.db")
        initialize_database(db_path=db_path)
        orchestrator = NeuroGuiaOrchestratorV2(db_path=db_path)

        try:
            for case in CASES:
                result = process(orchestrator, case["message"])
                functional = result.get("functional_analysis") or {}
                routine = result.get("routine_payload") or {}
                response = str((result.get("response_package") or {}).get("response") or "")

                category = functional.get("functional_category")
                routine_type = routine.get("routine_type")
                visible = bool(
                    response.strip()
                    and routine_type
                    and (
                        str(routine.get("routine_name") or "").lower() in response.lower()
                        or "1." in response
                    )
                )
                passed = (
                    category == case["expected_category"]
                    and routine_type == case["expected_routine"]
                    and visible
                )
                failures += int(not passed)
                rows.append(
                    {
                        "id": case["id"],
                        "message": case["message"],
                        "expected_category": case["expected_category"],
                        "detected_category": category,
                        "expected_routine": case["expected_routine"],
                        "generated_routine": routine_type,
                        "routine_visible": visible,
                        "passed": passed,
                    }
                )

            # La aplicación no debe imponer una rutina cuando la persona la rechaza.
            rejection = process(
                orchestrator,
                "No quiero una rutina, solo quiero hablar un momento",
            )
            rejection_passed = not bool(rejection.get("routine_payload"))
            failures += int(not rejection_passed)
            rows.append(
                {
                    "id": "N01",
                    "message": "No quiero una rutina, solo quiero hablar un momento",
                    "expected_category": "cualquier categoría compatible",
                    "detected_category": (rejection.get("functional_analysis") or {}).get(
                        "functional_category"
                    ),
                    "expected_routine": None,
                    "generated_routine": (rejection.get("routine_payload") or {}).get(
                        "routine_type"
                    ),
                    "routine_visible": False,
                    "passed": rejection_passed,
                }
            )

            # Evita repetir el mismo bloque completo en un seguimiento inmediato.
            first_message = "Tengo demasiados pendientes y me da ansiedad pensar en todo"
            first = process(orchestrator, first_message)
            first_response = str((first.get("response_package") or {}).get("response") or "")
            second = process(
                orchestrator,
                "Además sigo con muchos pendientes y todavía me cuesta empezar",
                previous_frame=first.get("conversation_frame") or {},
                chat_history=[{"user": first_message, "assistant": first_response}],
            )
            first_routine = (first.get("routine_payload") or {}).get("routine_type")
            second_routine = (second.get("routine_payload") or {}).get("routine_type")
            dedup_passed = bool(first_routine) and second_routine is None
            failures += int(not dedup_passed)
            rows.append(
                {
                    "id": "N02",
                    "message": "Seguimiento consecutivo de la misma necesidad",
                    "expected_category": (first.get("functional_analysis") or {}).get(
                        "functional_category"
                    ),
                    "detected_category": (second.get("functional_analysis") or {}).get(
                        "functional_category"
                    ),
                    "expected_routine": "no repetir la rutina anterior",
                    "generated_routine": second_routine,
                    "routine_visible": bool(second_routine),
                    "passed": dedup_passed,
                }
            )

            # En una crisis activa sí se conserva la secuencia de seguridad aunque sea seguimiento.
            crisis_first_message = "Está en crisis y puede lastimarse"
            crisis_first = process(orchestrator, crisis_first_message)
            crisis_response = str(
                (crisis_first.get("response_package") or {}).get("response") or ""
            )
            crisis_second = process(
                orchestrator,
                "Sigue en crisis y todavía hay riesgo",
                previous_frame=crisis_first.get("conversation_frame") or {},
                chat_history=[
                    {"user": crisis_first_message, "assistant": crisis_response}
                ],
            )
            crisis_second_routine = (crisis_second.get("routine_payload") or {}).get(
                "routine_type"
            )
            crisis_passed = crisis_second_routine == "crisis_safety"
            failures += int(not crisis_passed)
            rows.append(
                {
                    "id": "N03",
                    "message": "Seguimiento con crisis activa",
                    "expected_category": "manejo_crisis",
                    "detected_category": (
                        crisis_second.get("functional_analysis") or {}
                    ).get("functional_category"),
                    "expected_routine": "crisis_safety",
                    "generated_routine": crisis_second_routine,
                    "routine_visible": bool(crisis_second_routine),
                    "passed": crisis_passed,
                }
            )
        finally:
            orchestrator.close()

    output_dir = ROOT / "validation_outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "functional_support_validation.json"
    output_path.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("=" * 92)
    print("VALIDACIÓN FUNCIONAL DE NEUROGUIA")
    print("=" * 92)
    for row in rows:
        state = "OK" if row["passed"] else "FALLO"
        print(
            f"{row['id']:>3} | {state:<5} | "
            f"categoría={row['detected_category']} | rutina={row['generated_routine']}"
        )
    print("-" * 92)
    print(f"Resultado: {len(rows) - failures}/{len(rows)} pruebas superadas")
    print(f"Reporte: {output_path}")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
