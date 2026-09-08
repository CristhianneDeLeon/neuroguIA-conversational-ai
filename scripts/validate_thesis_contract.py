# -*- coding: utf-8 -*-
"""Valida que el repositorio conserve el contrato técnico documentado en la tesis final.

Este script NO modifica versiones, datos, resultados ni configuración.
Solo comprueba elementos estructurales y constantes que deben permanecer
congruentes durante la preparación de la defensa.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Set


ROOT = Path(__file__).resolve().parents[1]

OUTPUT_DIR = ROOT / "validation_outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


EXPECTED_FUNCTIONAL_CATEGORIES: Set[str] = {
    "regulacion_emocional",
    "acompanamiento_escolar",
    "organizacion_familiar",
    "regulacion_sensorial",
    "bienestar_cuidador",
    "manejo_crisis",
    "rutinas_habitos",
}


REQUIRED_FILES = [
    "app.py",
    "core/orchestrator_v2.py",
    "core/semantic_encoder.py",
    "core/llm_gateway.py",
    "core/functional_category_router.py",
    "core/routine_builder_v2.py",
    "core/routine_activation_engine.py",
    "core/fallback_manager.py",
    "memory/user_context_memory.py",
    "memory/case_memory.py",
    "memory/response_memory.py",
    "memory/profile_manager.py",
    "database/supabase_adapter.py",
    "dashboard/dashboard.py",
]


CANONICAL_PERSISTENCE_NAMES = {
    "ng_families",
    "ng_profiles",
    "ng_messages",
    "ng_case_memory",
    "ng_response_memory",
    "ng_user_context_memory",
    "ng_routines",
}


def read(rel_path: str) -> str:
    """Lee un archivo del repositorio."""
    return (
        ROOT / rel_path
    ).read_text(
        encoding="utf-8",
        errors="replace",
    )


def check(
    name: str,
    passed: bool,
    detail: str,
) -> Dict[str, Any]:
    """Construye un registro de validación."""
    return {
        "check": name,
        "passed": bool(passed),
        "detail": detail,
    }


def extract_functional_categories(
    source: str,
) -> Set[str]:
    """Extrae las categorías definidas en FunctionalCategoryRouter."""

    match = re.search(
        r"DEFINITIONS\s*:\s*Dict\[.*?\]\s*=\s*\{"
        r"(.*?)\n\s*\}\n\n\s*RULES",
        source,
        flags=re.S,
    )

    if not match:
        return set()

    return set(
        re.findall(
            r'^\s*"([a-z_]+)"\s*:\s*\{',
            match.group(1),
            flags=re.M,
        )
    )


def main() -> int:
    checks: List[Dict[str, Any]] = []

    # -------------------------------------------------
    # 1. Archivos estructurales requeridos
    # -------------------------------------------------

    missing_files = [
        path
        for path in REQUIRED_FILES
        if not (ROOT / path).exists()
    ]

    checks.append(
        check(
            "required_files",
            not missing_files,
            (
                "Archivos técnicos requeridos presentes."
                if not missing_files
                else "Faltan: " + ", ".join(missing_files)
            ),
        )
    )

    # -------------------------------------------------
    # 2. Modelo de embeddings documentado
    # -------------------------------------------------

    semantic_source = read(
        "core/semantic_encoder.py"
    )

    embedding_ok = (
        'DEFAULT_EMBEDDING_MODEL = "all-MiniLM-L6-v2"'
        in semantic_source
    )

    checks.append(
        check(
            "embedding_model",
            embedding_ok,
            (
                "Se conserva all-MiniLM-L6-v2 "
                "para recuperación semántica."
            ),
        )
    )

    # -------------------------------------------------
    # 3. OpenAI Responses API
    # -------------------------------------------------

    llm_source = read(
        "core/llm_gateway.py"
    )

    responses_api_ok = (
        "responses.create"
        in llm_source
    )

    checks.append(
        check(
            "responses_api",
            responses_api_ok,
            (
                "Se conserva OpenAI Responses API "
                "como capa generativa supervisada."
            ),
        )
    )

    # -------------------------------------------------
    # 4. Siete propósitos funcionales consolidados
    # -------------------------------------------------

    functional_source = read(
        "core/functional_category_router.py"
    )

    detected_categories = (
        extract_functional_categories(
            functional_source
        )
    )

    categories_ok = (
        detected_categories
        == EXPECTED_FUNCTIONAL_CATEGORIES
    )

    checks.append(
        check(
            "seven_functional_categories",
            categories_ok,
            (
                "Categorías detectadas: "
                + ", ".join(
                    sorted(detected_categories)
                )
            ),
        )
    )

    # -------------------------------------------------
    # 5. Persistencia canónica documentada
    # -------------------------------------------------

    app_source = read("app.py")

    missing_names = [
        name
        for name in sorted(
            CANONICAL_PERSISTENCE_NAMES
        )
        if not re.search(
            rf"\b{re.escape(name)}\b",
            app_source,
        )
    ]

    checks.append(
        check(
            "canonical_persistence_names",
            not missing_names,
            (
                "La aplicación conserva las "
                "estructuras ng_* documentadas."
                if not missing_names
                else (
                    "No localizadas: "
                    + ", ".join(missing_names)
                )
            ),
        )
    )

    # -------------------------------------------------
    # 6. Ventana experimental congelada
    # -------------------------------------------------

    dashboard_source = read(
        "dashboard/dashboard.py"
    )

    has_18_weeks = (
        "18 semanas"
        in dashboard_source
    )

    has_window = any(
        text in dashboard_source
        for text in (
            "12 enero - 17 mayo de 2026",
            "12 ene–17 may 2026",
            "12 ene-17 may 2026",
        )
    )

    checks.append(
        check(
            "experimental_window",
            has_18_weeks and has_window,
            (
                "Se conserva la intervención "
                "de 18 semanas, "
                "12 ene–17 may 2026."
            ),
        )
    )

    # -------------------------------------------------
    # 7. Componentes de la arquitectura híbrida
    # -------------------------------------------------

    orchestrator_source = read(
        "core/orchestrator_v2.py"
    )

    required_components = [
        "FunctionalCategoryRouter",
        "RoutineActivationEngine",
        "LLMGateway",
        "UserContextMemory",
        "CaseMemory",
        "ResponseMemory",
    ]

    missing_components = [
        component
        for component in required_components
        if component
        not in orchestrator_source
    ]

    checks.append(
        check(
            "hybrid_orchestration",
            not missing_components,
            (
                "El orquestador conserva "
                "clasificación funcional, rutinas, "
                "memoria y generación supervisada."
                if not missing_components
                else (
                    "No localizados: "
                    + ", ".join(
                        missing_components
                    )
                )
            ),
        )
    )

    # -------------------------------------------------
    # Reporte final
    # -------------------------------------------------

    failures = [
        row
        for row in checks
        if not row["passed"]
    ]

    report = {
        "name":
            "neuroguIA thesis-defense technical contract",

        "modifies_versions":
            False,

        "passed":
            not failures,

        "failures":
            len(failures),

        "checks":
            checks,
    }

    output_path = (
        OUTPUT_DIR
        / "thesis_contract_validation.json"
    )

    output_path.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("=" * 92)

    print(
        "CONTRATO TÉCNICO "
        "TESIS ↔ REPOSITORIO"
    )

    print("=" * 92)

    for row in checks:

        status = (
            "OK"
            if row["passed"]
            else "FALLO"
        )

        print(
            f"{status:<5} | "
            f"{row['check']}: "
            f"{row['detail']}"
        )

    print("-" * 92)

    print(
        f"Resultado: "
        f"{len(checks) - len(failures)}"
        f"/{len(checks)} "
        "verificaciones superadas"
    )

    print(
        f"Reporte: {output_path}"
    )

    return 1 if failures else 0

if __name__ == "__main__":
    raise SystemExit(main())
