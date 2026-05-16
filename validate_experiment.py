# validate_experiment.py

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from core.orchestrator_v2 import NeuroGuiaOrchestratorV2
from database.database import initialize_database

OUTPUT_DIR = BASE_DIR / "validation_outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

TEST_CASES: List[Dict[str, Any]] = [
    {
        "case_id": "C01",
        "message": "Estoy agotada y él explotó con el ruido, luego ya no quiso hablar.",
        "family_id": None,
        "profile_id": None,
        "expected_state": "meltdown",
        "expected_category": "crisis_activa",
        "expected_intent": "urgent_support",
    },
    {
        "case_id": "C02",
        "message": "No sé bien qué está pasando. A veces parece sueño y a veces ansiedad.",
        "family_id": None,
        "profile_id": None,
        "expected_state": "general_distress",
        "expected_category": "sueno_regulacion",
        "expected_intent": "general_support",
    },
    {
        "case_id": "C03",
        "message": "No puede empezar la tarea y se bloquea desde que la ve.",
        "family_id": None,
        "profile_id": None,
        "expected_state": "executive_dysfunction",
        "expected_category": "disfuncion_ejecutiva",
        "expected_intent": "general_support",
    },
    {
        "case_id": "C04",
        "message": "Ya no puedo más, siento que todo recae en mí y estoy muy cansada.",
        "family_id": None,
        "profile_id": None,
        "expected_state": "burnout",
        "expected_category": "sobrecarga_cuidador",
        "expected_intent": "urgent_support",
    },
]

def run_validation(db_path: str = "neuroguia_validation.db") -> Path:
    initialize_database(db_path=db_path)
    orch = NeuroGuiaOrchestratorV2(db_path=db_path)
    rows: List[Dict[str, Any]] = []

    try:
        for case in TEST_CASES:
            result = orch.process_message(
                message=case["message"],
                family_id=case["family_id"],
                profile_id=case["profile_id"],
            )

            rows.append({
                "case_id": case["case_id"],
                "message": case["message"],
                "expected_state": case["expected_state"],
                "pred_state": result["state_analysis"].get("primary_state"),
                "expected_category": case["expected_category"],
                "pred_category": result["category_analysis"].get("detected_category"),
                "expected_intent": case["expected_intent"],
                "pred_intent": result["intent_analysis"].get("detected_intent"),
                "confidence": result["confidence_payload"].get("overall_confidence"),
                "confidence_level": result["confidence_payload"].get("confidence_level"),
                "decision_mode": result["decision_payload"].get("decision_mode"),
                "fallback_used": result["fallback_payload"].get("use_llm"),
                "fallback_reason": result["fallback_payload"].get("fallback_reason"),
                "response_mode": result["response_package"].get("mode"),
                "response_text": result["response_package"].get("response"),
            })
    finally:
        orch.close()

    out_csv = OUTPUT_DIR / "validation_results.csv"
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    out_json = OUTPUT_DIR / "validation_results.json"
    out_json.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    return out_csv


if __name__ == "__main__":
    path = run_validation()
    print(f"Validación terminada. Archivo generado: {path}")
