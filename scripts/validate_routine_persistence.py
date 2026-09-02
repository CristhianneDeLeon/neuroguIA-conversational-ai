# -*- coding: utf-8 -*-
"""Valida persistencia, recuperación, actualización
y aislamiento de rutinas.

La prueba utiliza exclusivamente una base SQLite temporal.

No utiliza:
- Supabase;
- credenciales;
- datos reales;
- conversaciones de participantes.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(ROOT),
    )


from database.database import initialize_database
from memory.routine_memory import RoutineMemory


def main() -> int:

    with tempfile.TemporaryDirectory() as tmpdir:

        db_path = str(
            Path(tmpdir)
            / "routine_validation.db"
        )

        # -------------------------------------------------
        # Crear esquema SQLite temporal
        # -------------------------------------------------

        db = initialize_database(
            db_path=db_path
        )

        db.close()

        memory = RoutineMemory(
            db_path=db_path,
            backend="sqlite",
        )

        try:

            family_id = (
                "family-defense-a"
            )

            profile_id = (
                "profile-defense-a"
            )

            other_profile_id = (
                "profile-defense-b"
            )

            # -------------------------------------------------
            # Rutina de prueba
            # -------------------------------------------------

            payload = {
                "routine_type":
                    "morning_organization",

                "routine_name":
                    "Rutina de mañana con baja carga",

                "goal":
                    "hacer más predecible la salida de casa",

                "steps": [
                    "dejar ropa y mochila preparadas",
                    "seguir una lista visible",
                    "dar una sola indicación a la vez",
                ],

                "short_version": [
                    "preparar",
                    "seguir la lista",
                    "salir con margen",
                ],

                "adjustments": [
                    "reducir decisiones de último momento",
                ],

                "indicators": [
                    "menos recordatorios repetidos",
                ],

                "followup_question":
                    "¿Qué parte de la mañana sigue costando más?",
            }

            # =================================================
            # 1. GUARDAR
            # =================================================

            stored = memory.save_routine(
                routine_payload=payload,
                family_id=family_id,
                profile_id=profile_id,
                source_case_id=None,
            )

            assert (
                stored.get("stored")
                is True
            )

            routine_id = (
                stored.get(
                    "routine_id"
                )
            )

            assert routine_id

            # =================================================
            # 2. RECUPERAR
            # =================================================

            recovered = (
                memory.get_active_routine(
                    family_id=family_id,
                    profile_id=profile_id,
                    routine_type=(
                        "morning_organization"
                    ),
                )
            )

            assert recovered is not None

            assert (
                recovered.get(
                    "routine_id"
                )
                == routine_id
            )

            assert (
                recovered.get(
                    "routine_name"
                )
                == payload[
                    "routine_name"
                ]
            )

            assert (
                recovered.get(
                    "steps"
                )
                == payload["steps"]
            )

            assert (
                recovered.get(
                    "short_version"
                )
                == payload[
                    "short_version"
                ]
            )

            assert (
                recovered.get(
                    "adjustments"
                )
                == payload[
                    "adjustments"
                ]
            )

            assert (
                recovered.get(
                    "indicators"
                )
                == payload[
                    "indicators"
                ]
            )

            # =================================================
            # 3. AISLAMIENTO ENTRE PERFILES
            # =================================================

            isolated = (
                memory.get_active_routine(
                    family_id=family_id,
                    profile_id=(
                        other_profile_id
                    ),
                    routine_type=(
                        "morning_organization"
                    ),
                )
            )

            assert isolated is None, (
                "Una rutina no debe "
                "aparecer en otro perfil."
            )

            # =================================================
            # 4. MODIFICAR LA RUTINA
            # =================================================

            updated_steps = [
                "dejar ropa y mochila preparadas",
                "desayunar antes de revisar pendientes",
                "seguir una lista visible de tres pasos",
            ]

            updated = (
                memory.update_routine(
                    routine_id=routine_id,
                    family_id=family_id,
                    profile_id=profile_id,
                    steps=updated_steps,
                    followup_question=(
                        "¿El nuevo orden redujo "
                        "la tensión de la mañana?"
                    ),
                )
            )

            assert (
                updated.get("updated")
                is True
            )

            recovered_after_update = (
                memory.get_routine(
                    routine_id
                )
            )

            assert (
                recovered_after_update
                is not None
            )

            assert (
                recovered_after_update.get(
                    "steps"
                )
                == updated_steps
            )

            assert (
                recovered_after_update.get(
                    "followup_question"
                )
                ==
                "¿El nuevo orden redujo "
                "la tensión de la mañana?"
            )

            # =================================================
            # 5. BLOQUEAR MODIFICACIÓN DESDE OTRO PERFIL
            # =================================================

            wrong_scope_update = (
                memory.update_routine(
                    routine_id=routine_id,
                    family_id=family_id,
                    profile_id=(
                        other_profile_id
                    ),
                    goal=(
                        "este cambio "
                        "no debe aplicarse"
                    ),
                )
            )

            assert (
                wrong_scope_update.get(
                    "updated"
                )
                is False
            )

            assert (
                wrong_scope_update.get(
                    "reason"
                )
                ==
                "routine_not_found_in_scope"
            )

            # =================================================
            # 6. DESACTIVAR
            # =================================================

            deactivated = (
                memory.deactivate_routine(
                    routine_id=routine_id,
                    family_id=family_id,
                    profile_id=profile_id,
                )
            )

            assert (
                deactivated.get(
                    "updated"
                )
                is True
            )

            active_after_deactivation = (
                memory.get_active_routine(
                    family_id=family_id,
                    profile_id=profile_id,
                    routine_type=(
                        "morning_organization"
                    ),
                )
            )

            assert (
                active_after_deactivation
                is None
            )

            # =================================================
            # RESULTADO
            # =================================================

            print(
                "ROUTINE_PERSISTENCE_OK"
            )

            print(
                "Guardar: OK"
            )

            print(
                "Recuperar: OK"
            )

            print(
                "Actualizar: OK"
            )

            print(
                "Aislamiento por perfil: OK"
            )

            print(
                "Desactivar: OK"
            )

            return 0

        finally:

            memory.close()

if __name__ == "__main__":
    raise SystemExit(main())
