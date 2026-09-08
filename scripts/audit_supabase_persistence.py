# -*- coding: utf-8 -*-
"""Auditoría estática de persistencia Supabase para neuroguIA.

No establece conexiones.
No utiliza credenciales.
No modifica Supabase.
No ejecuta DDL.
No modifica datos.

Su finalidad es identificar qué componentes utilizan
los nombres canónicos ng_* y cuáles conservan nombres
históricos soportados mediante vistas de compatibilidad.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[1]

OUTPUT_DIR = ROOT / "validation_outputs"
OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


CANONICAL_TABLES = {
    "families": "ng_families",
    "profiles": "ng_profiles",
    "case_memory": "ng_case_memory",
    "response_memory": "ng_response_memory",
    "user_context_memory": "ng_user_context_memory",
    "routines": "ng_routines",
}


FILES_TO_AUDIT = [
    "app.py",
    "database/supabase_adapter.py",
    "database/database_postgres.py",
    "memory/profile_manager.py",
    "memory/case_memory.py",
    "memory/response_memory.py",
    "memory/user_context_memory.py",
    "schema_supabase.sql",
]


def read(rel_path: str) -> str:
    path = ROOT / rel_path

    if not path.exists():
        return ""

    return path.read_text(
        encoding="utf-8",
        errors="replace",
    )


def find_reference(
    source: str,
    table_name: str,
) -> bool:
    """Detecta una referencia textual a una tabla."""

    pattern = (
        rf"(?<![A-Za-z0-9_])"
        rf"{re.escape(table_name)}"
        rf"(?![A-Za-z0-9_])"
    )

    return bool(
        re.search(
            pattern,
            source,
        )
    )


def main() -> int:

    rows: List[Dict[str, Any]] = []

    print("=" * 92)
    print(
        "NEUROGUIA - "
        "AUDITORÍA DE PERSISTENCIA SUPABASE"
    )
    print("=" * 92)

    # -----------------------------------------------------
    # Revisar archivos
    # -----------------------------------------------------

    for rel_path in FILES_TO_AUDIT:

        source = read(rel_path)

        canonical_found: List[str] = []
        legacy_found: List[str] = []

        for legacy, canonical in CANONICAL_TABLES.items():

            if find_reference(
                source,
                canonical,
            ):
                canonical_found.append(
                    canonical
                )

            if find_reference(
                source,
                legacy,
            ):
                legacy_found.append(
                    legacy
                )

        row = {
            "file": rel_path,
            "exists": bool(source),
            "canonical_tables":
                sorted(
                    set(canonical_found)
                ),
            "legacy_tables":
                sorted(
                    set(legacy_found)
                ),
        }

        rows.append(row)

    # -----------------------------------------------------
    # Comprobar puente de compatibilidad
    # -----------------------------------------------------

    app_source = read("app.py")

    bridge_expected = {
        '"families": "ng_families"',
        '"profiles": "ng_profiles"',
        '"case_memory": "ng_case_memory"',
        '"response_memory": "ng_response_memory"',
        '"user_context_memory": "ng_user_context_memory"',
        '"routines": "ng_routines"',
    }

    bridge_missing = [
        item
        for item in sorted(
            bridge_expected
        )
        if item not in app_source
    ]

    bridge_ok = (
        not bridge_missing
    )

    # -----------------------------------------------------
    # Componentes ya alineados
    # -----------------------------------------------------

    aligned_components = []

    case_source = read(
        "memory/case_memory.py"
    )

    if "ng_case_memory" in case_source:
        aligned_components.append(
            "memory/case_memory.py"
        )

    response_source = read(
        "memory/response_memory.py"
    )

    if (
        '"ng_response_memory"'
        in response_source
    ):
        aligned_components.append(
            "memory/response_memory.py"
        )

    # -----------------------------------------------------
    # Componentes que todavía requieren puente
    # -----------------------------------------------------

    bridge_dependent = []

    profile_source = read(
        "memory/profile_manager.py"
    )

    if (
        "FROM families" in profile_source
        or
        "INSERT INTO families" in profile_source
        or
        "FROM profiles" in profile_source
        or
        "INSERT INTO profiles" in profile_source
    ):
        bridge_dependent.append(
            "memory/profile_manager.py"
        )

    context_source = read(
        "memory/user_context_memory.py"
    )

    if (
        "user_context_memory"
        in context_source
        and
        "ng_user_context_memory"
        not in context_source
    ):
        bridge_dependent.append(
            "memory/user_context_memory.py"
        )

    adapter_source = read(
        "database/supabase_adapter.py"
    )

    if (
        'table("profiles")'
        in adapter_source
        or
        'table("response_memory")'
        in adapter_source
    ):
        bridge_dependent.append(
            "database/supabase_adapter.py"
        )

    postgres_source = read(
        "database/database_postgres.py"
    )

    if (
        '"families"' in postgres_source
        or
        '"profiles"' in postgres_source
        or
        '"response_memory"'
        in postgres_source
        or
        '"user_context_memory"'
        in postgres_source
        or
        '"routines"'
        in postgres_source
    ):
        bridge_dependent.append(
            "database/database_postgres.py"
        )

    # -----------------------------------------------------
    # Esquema histórico
    # -----------------------------------------------------

    schema_source = read(
        "schema_supabase.sql"
    )

    schema_uses_legacy_names = any(
        phrase in schema_source
        for phrase in (
            "public.families",
            "public.profiles",
            "public.response_memory",
            "public.user_context_memory",
            "public.routines",
        )
    )

    # -----------------------------------------------------
    # Clasificación del estado
    # -----------------------------------------------------

    if bridge_dependent:
        alignment_status = (
            "COMPATIBLE_WITH_BRIDGE"
        )
    else:
        alignment_status = (
            "CANONICAL_DIRECT"
        )

    report = {
        "name":
            "neuroguIA Supabase persistence audit",

        "generated_at_utc":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "connects_to_supabase":
            False,

        "modifies_database":
            False,

        "canonical_tables":
            CANONICAL_TABLES,

        "compatibility_bridge_present":
            bridge_ok,

        "compatibility_bridge_missing":
            bridge_missing,

        "aligned_components":
            sorted(
                aligned_components
            ),

        "bridge_dependent_components":
            sorted(
                set(
                    bridge_dependent
                )
            ),

        "schema_supabase_uses_legacy_names":
            schema_uses_legacy_names,

        "alignment_status":
            alignment_status,

        "files":
            rows,
    }

    output_path = (
        OUTPUT_DIR
        / "supabase_persistence_audit.json"
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
    # Resultado en consola
    # -----------------------------------------------------

    print(
        "Puente de compatibilidad:",
        (
            "OK"
            if bridge_ok
            else "INCOMPLETO"
        ),
    )

    print()

    print(
        "Componentes ya alineados "
        "directamente con ng_*:"
    )

    for item in sorted(
        aligned_components
    ):
        print(
            f"  OK  {item}"
        )

    print()

    print(
        "Componentes que todavía "
        "dependen de nombres históricos:"
    )

    if bridge_dependent:

        for item in sorted(
            set(
                bridge_dependent
            )
        ):
            print(
                f"  AVISO  {item}"
            )

    else:
        print(
            "  Ninguno."
        )

    print()

    print(
        "schema_supabase.sql "
        "usa nomenclatura histórica:",
        schema_uses_legacy_names,
    )

    print()

    print(
        "ESTADO:",
        alignment_status,
    )

    print(
        "Reporte:",
        output_path,
    )

    # -----------------------------------------------------
    # IMPORTANTE:
    # Esta es una auditoría informativa.
    # No falla el pipeline por encontrar compatibilidad
    # histórica. La alineación estricta se realizará
    # posteriormente y será validada antes de fusionar main.
    # -----------------------------------------------------

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
