# -*- coding: utf-8 -*-
"""Valida el contrato de compatibilidad SQLite ↔ Supabase de neuroguIA.

Esta prueba:
- no se conecta a Supabase;
- no utiliza credenciales;
- no modifica la base de datos;
- no ejecuta DDL;
- no altera versiones ni resultados.

Solo verifica estáticamente que app.py conserve el puente documentado
entre nombres históricos/locales y las tablas canónicas ng_*.
"""

from __future__ import annotations

import ast
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[1]

OUTPUT_DIR = ROOT / "validation_outputs"
OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


EXPECTED_BRIDGE = {
    "response_memory": "ng_response_memory",
    "user_context_memory": "ng_user_context_memory",
    "routines": "ng_routines",
    "learned_patterns": "ng_learned_patterns",
    "case_memory": "ng_case_memory",
    "families": "ng_families",
    "profiles": "ng_profiles",
}


def read(rel_path: str) -> str:
    """Lee un archivo UTF-8 del repositorio."""

    return (
        ROOT / rel_path
    ).read_text(
        encoding="utf-8",
        errors="replace",
    )


def make_check(
    name: str,
    passed: bool,
    detail: str,
) -> Dict[str, Any]:
    """Construye una entrada normalizada del reporte."""

    return {
        "check": name,
        "passed": bool(passed),
        "detail": detail,
    }


def find_function(
    tree: ast.AST,
    function_name: str,
) -> ast.FunctionDef | None:
    """Localiza una función de nivel superior por nombre."""

    for node in ast.walk(tree):

        if (
            isinstance(node, ast.FunctionDef)
            and node.name == function_name
        ):
            return node

    return None


def extract_bridge_mapping(
    function_node: ast.FunctionDef,
) -> Dict[str, str]:
    """Extrae el diccionario bridge_views sin ejecutar app.py."""

    for node in ast.walk(function_node):

        if not isinstance(node, ast.Assign):
            continue

        target_names = [
            target.id
            for target in node.targets
            if isinstance(target, ast.Name)
        ]

        if "bridge_views" not in target_names:
            continue

        if not isinstance(node.value, ast.Dict):
            return {}

        mapping: Dict[str, str] = {}

        for key, value in zip(
            node.value.keys,
            node.value.values,
        ):

            if (
                isinstance(key, ast.Constant)
                and isinstance(key.value, str)
                and isinstance(value, ast.Constant)
                and isinstance(value.value, str)
            ):
                mapping[key.value] = value.value

        return mapping

    return {}


def function_calls(
    function_node: ast.FunctionDef,
    target_name: str,
) -> bool:
    """Comprueba si una función llama a otra por nombre."""

    for node in ast.walk(function_node):

        if not isinstance(node, ast.Call):
            continue

        if (
            isinstance(node.func, ast.Name)
            and node.func.id == target_name
        ):
            return True

    return False


def function_contains_name(
    function_node: ast.FunctionDef,
    name: str,
) -> bool:
    """Busca una referencia a un identificador dentro de una función."""

    return any(
        isinstance(node, ast.Name)
        and node.id == name
        for node in ast.walk(function_node)
    )


def function_contains_string(
    function_node: ast.FunctionDef,
    value: str,
) -> bool:
    """Busca una constante textual dentro de una función."""

    return any(
        isinstance(node, ast.Constant)
        and node.value == value
        for node in ast.walk(function_node)
    )


def main() -> int:
    """Ejecuta todas las validaciones del puente."""

    checks: List[Dict[str, Any]] = []

    app_path = ROOT / "app.py"

    # -----------------------------------------------------
    # 1. app.py debe existir
    # -----------------------------------------------------

    checks.append(
        make_check(
            "app_exists",
            app_path.exists(),
            "app.py localizado en la raíz del repositorio.",
        )
    )

    if not app_path.exists():

        print("FALLO | app.py no existe.")
        return 1

    source = read("app.py")

    try:
        tree = ast.parse(source)

    except SyntaxError as exc:

        print(
            "FALLO | app.py no pudo analizarse:",
            exc,
        )

        return 1

    # -----------------------------------------------------
    # 2. Función de compatibilidad
    # -----------------------------------------------------

    bridge_function = find_function(
        tree,
        "ensure_supabase_compatibility_views",
    )

    checks.append(
        make_check(
            "bridge_function_exists",
            bridge_function is not None,
            (
                "Existe ensure_supabase_compatibility_views()."
                if bridge_function
                else (
                    "No existe "
                    "ensure_supabase_compatibility_views()."
                )
            ),
        )
    )

    detected_bridge: Dict[str, str] = {}

    if bridge_function is not None:

        detected_bridge = extract_bridge_mapping(
            bridge_function
        )

    # -----------------------------------------------------
    # 3. Correspondencias exactas
    # -----------------------------------------------------

    mapping_ok = (
        detected_bridge
        == EXPECTED_BRIDGE
    )

    checks.append(
        make_check(
            "bridge_mapping",
            mapping_ok,
            (
                "Las siete correspondencias "
                "SQLite/Supabase coinciden con "
                "el contrato documentado."
                if mapping_ok
                else (
                    "Correspondencias detectadas: "
                    + json.dumps(
                        detected_bridge,
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                )
            ),
        )
    )

    # -----------------------------------------------------
    # 4. El puente solo debe ser relevante para postgres
    # -----------------------------------------------------

    postgres_guard_ok = False

    if bridge_function is not None:

        postgres_guard_ok = (
            function_contains_name(
                bridge_function,
                "derive_database_backend",
            )
            and function_contains_string(
                bridge_function,
                "postgres",
            )
        )

    checks.append(
        make_check(
            "postgres_backend_guard",
            postgres_guard_ok,
            (
                "El puente conserva la separación "
                "entre SQLite local y PostgreSQL/Supabase."
            ),
        )
    )

    # -----------------------------------------------------
    # 5. Debe conservar creación de vistas puente
    # -----------------------------------------------------

    create_view_ok = (
        "create or replace view public.{legacy_name}"
        in source
        and
        "select * from public.{canonical_name}"
        in source
    )

    checks.append(
        make_check(
            "compatibility_views",
            create_view_ok,
            (
                "app.py conserva la creación "
                "de vistas de compatibilidad."
            ),
        )
    )

    # -----------------------------------------------------
    # 6. main() debe activar el puente
    # -----------------------------------------------------

    main_function = find_function(
        tree,
        "main",
    )

    main_calls_bridge = (
        main_function is not None
        and function_calls(
            main_function,
            "ensure_supabase_compatibility_views",
        )
    )

    checks.append(
        make_check(
            "bridge_called_from_main",
            main_calls_bridge,
            (
                "main() activa el puente durante "
                "el arranque de la aplicación."
            ),
        )
    )

    # -----------------------------------------------------
    # 7. Documentación asociada
    # -----------------------------------------------------

    docs_path = (
        ROOT
        / "docs"
        / "SUPABASE_COMPATIBILITY.md"
    )

    docs_ok = docs_path.exists()

    if docs_ok:

        docs_source = docs_path.read_text(
            encoding="utf-8",
            errors="replace",
        )

        docs_ok = all(
            item in docs_source
            for item in (
                "COMPATIBLE_WITH_BRIDGE",
                "ng_families",
                "ng_profiles",
                "ng_case_memory",
                "ng_response_memory",
                "ng_user_context_memory",
                "ng_routines",
            )
        )

    checks.append(
        make_check(
            "bridge_documentation",
            docs_ok,
            (
                "El puente está documentado "
                "en docs/SUPABASE_COMPATIBILITY.md."
            ),
        )
    )

    # -----------------------------------------------------
    # Reporte
    # -----------------------------------------------------

    failures = [
        row
        for row in checks
        if not row["passed"]
    ]

    report = {
        "name":
            "neuroguIA SQLite-Supabase bridge contract",

        "generated_at_utc":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "connects_to_database":
            False,

        "modifies_database":
            False,

        "expected_status":
            "COMPATIBLE_WITH_BRIDGE",

        "passed":
            not failures,

        "checks_passed":
            len(checks) - len(failures),

        "checks_total":
            len(checks),

        "expected_bridge":
            EXPECTED_BRIDGE,

        "detected_bridge":
            detected_bridge,

        "checks":
            checks,
    }

    output_path = (
        OUTPUT_DIR
        / "supabase_bridge_contract.json"
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
    # Consola
    # -----------------------------------------------------

    print("=" * 92)

    print(
        "NEUROGUIA - "
        "CONTRATO DE COMPATIBILIDAD "
        "SQLITE ↔ SUPABASE"
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
        "Estado esperado:",
        "COMPATIBLE_WITH_BRIDGE",
    )

    print(
        "Reporte:",
        output_path,
    )

    return 1 if failures else 0

if __name__ == "__main__":
    raise SystemExit(main())
