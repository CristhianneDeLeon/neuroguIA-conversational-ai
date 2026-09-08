# -*- coding: utf-8 -*-
"""Valida el flujo real:
mensaje → generación de rutina → persistencia → recuperación.

La prueba utiliza exclusivamente:
- SQLite temporal;
- familia ficticia;
- perfil ficticio;
- mensajes ficticios.

No utiliza:
- Supabase real;
- OpenAI real;
- credenciales;
- participantes;
- conversaciones del estudio.
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


from core.orchestrator_v2 import NeuroGuiaOrchestratorV2
from database.database import initialize_database
from memory.profile_manager import ProfileManager
from memory.routine_memory import RoutineMemory


def main() -> int:

    with tempfile.TemporaryDirectory() as tmpdir:

        db_path = str(
            Path(tmpdir)
            / "orchestrator_routine_validation.db"
        )

        # =====================================================
        # 1. CREAR BASE TEMPORAL
        # =====================================================

        database = initialize_database(
            db_path=db_path
        )

        database.close()

        # =====================================================
        # 2. CREAR FAMILIA Y PERFILES FICTICIOS
        # =====================================================

        profile_manager = ProfileManager(
            db_path=db_path,
            backend="sqlite",
        )

        try:

            family_id = profile_manager.create_unit(
                unit_type="family",
                caregiver_alias="Familia de validación",
                context_notes=(
                    "Contexto ficticio utilizado únicamente "
                    "para pruebas automatizadas."
                ),
                support_network="Red ficticia de validación",
                environmental_factors=None,
                global_history=None,
            )

            assert family_id, (
                "No fue posible crear la familia ficticia."
            )

            profile_id = profile_manager.create_profile(
                family_id=family_id,
                alias="Leo",
                age=9,
                role="hijo",
                conditions=[],
                strengths=[],
                triggers=[],
                early_signs=[],
                helpful_strategies=[],
                harmful_strategies=[],
                sensory_needs=[],
                emotional_needs=[],
                autonomy_level=None,
                sleep_profile=None,
                school_profile=None,
                executive_profile=None,
                evolution_notes=None,
            )

            assert profile_id, (
                "No fue posible crear el perfil ficticio."
            )

            other_profile_id = profile_manager.create_profile(
                family_id=family_id,
                alias="Perfil B",
                age=11,
                role="hijo",
                conditions=[],
                strengths=[],
                triggers=[],
                early_signs=[],
                helpful_strategies=[],
                harmful_strategies=[],
                sensory_needs=[],
                emotional_needs=[],
                autonomy_level=None,
                sleep_profile=None,
                school_profile=None,
                executive_profile=None,
                evolution_notes=None,
            )

            assert other_profile_id, (
                "No fue posible crear "
                "el segundo perfil ficticio."
            )

        finally:

            profile_manager.close()

        # =====================================================
        # 3. PRIMERA SESIÓN:
        #    PEDIR UNA RUTINA A NEUROGUIA
        # =====================================================

        orchestrator = NeuroGuiaOrchestratorV2(
            db_path=db_path
        )

        try:

            result = orchestrator.process_message(
                message=(
                    "Necesito una rutina visual "
                    "para organizar las mañanas "
                    "de mi hijo Leo."
                ),
                family_id=family_id,
                profile_id=profile_id,
                extra_context={
                    "session_scope_id":
                        "defense-routine-session-1"
                },
                chat_history=[],
                use_llm_stub=True,
                auto_save_case=True,
            )

            # =================================================
            # 4. COMPROBAR GENERACIÓN
            # =================================================

            routine_payload = (
                result.get("routine_payload")
                or {}
            )

            assert routine_payload, (
                "El orquestador procesó el mensaje "
                "pero no generó routine_payload."
            )

            routine_type = str(
                routine_payload.get("routine_type")
                or ""
            ).strip()

            assert routine_type, (
                "La rutina generada no contiene "
                "routine_type."
            )

            routine_name = str(
                routine_payload.get("routine_name")
                or ""
            ).strip()

            assert routine_name, (
                "La rutina generada no contiene "
                "routine_name."
            )

            # =================================================
            # 5. COMPROBAR PERSISTENCIA REPORTADA
            # =================================================

            routine_store_result = (
                result.get(
                    "routine_store_result"
                )
                or {}
            )

            assert (
                routine_store_result.get("stored")
                is True
            ), (
                "La rutina fue generada, pero "
                "el orquestador no logró almacenarla. "
                f"Resultado: {routine_store_result}"
            )

            routine_id = str(
                routine_store_result.get(
                    "routine_id"
                )
                or ""
            ).strip()

            assert routine_id, (
                "La rutina fue almacenada "
                "sin routine_id."
            )

            # =================================================
            # 6. COMPROBAR CASO
            # =================================================

            case_id = str(
                result.get("case_id")
                or ""
            ).strip()

            assert case_id, (
                "El turno no generó un case_id."
            )

            print(
                "Mensaje → rutina: OK"
            )

            print(
                "Rutina → persistencia: OK"
            )

            print(
                "Caso generado: OK"
            )

        finally:

            orchestrator.close()

        # =====================================================
        # 7. SEGUNDA SESIÓN:
        #    ABRIR NUEVA INSTANCIA DE MEMORIA
        # =====================================================

        routine_memory = RoutineMemory(
            db_path=db_path,
            backend="sqlite",
        )

        try:

            recovered = (
                routine_memory.get_active_routine(
                    family_id=family_id,
                    profile_id=profile_id,
                    routine_type=routine_type,
                )
            )

            assert recovered is not None, (
                "La rutina no pudo recuperarse "
                "después de cerrar el orquestador."
            )

            assert (
                recovered.get("routine_id")
                == routine_id
            ), (
                "La rutina recuperada no coincide "
                "con la almacenada."
            )

            assert (
                recovered.get("family_id")
                == family_id
            ), (
                "La rutina recuperada pertenece "
                "a otra familia."
            )

            assert (
                recovered.get("profile_id")
                == profile_id
            ), (
                "La rutina recuperada pertenece "
                "a otro perfil."
            )

            # =================================================
            # 8. VINCULACIÓN CON EL CASO
            # =================================================

            assert (
                recovered.get("source_case_id")
                == case_id
            ), (
                "La rutina no quedó vinculada "
                "al caso conversacional que la originó."
            )

            print(
                "Rutina ↔ caso: OK"
            )

            print(
                "Recuperación entre sesiones: OK"
            )

            # =================================================
            # 9. AISLAMIENTO ENTRE PERFILES
            # =================================================

            wrong_profile_result = (
                routine_memory.get_active_routine(
                    family_id=family_id,
                    profile_id=other_profile_id,
                    routine_type=routine_type,
                )
            )

            assert (
                wrong_profile_result
                is None
            ), (
                "La rutina de Leo apareció "
                "en un perfil diferente."
            )

            print(
                "Aislamiento por perfil: OK"
            )

            # =================================================
            # 10. MODIFICAR RUTINA
            # =================================================

            original_steps = list(
                recovered.get("steps")
                or []
            )

            assert original_steps, (
                "La rutina recuperada "
                "no contiene pasos."
            )

            updated_steps = list(
                original_steps
            )

            updated_steps.append(
                "Revisar mochila antes de salir."
            )

            update_result = (
                routine_memory.update_routine(
                    routine_id=routine_id,
                    family_id=family_id,
                    profile_id=profile_id,
                    steps=updated_steps,
                    followup_question=(
                        "¿El nuevo paso hizo "
                        "más sencilla la salida?"
                    ),
                )
            )

            assert (
                update_result.get("updated")
                is True
            ), (
                "No fue posible modificar "
                "la rutina almacenada."
            )

            updated_routine = (
                routine_memory.get_routine(
                    routine_id
                )
            )

            assert updated_routine is not None

            assert (
                updated_routine.get("steps")
                == updated_steps
            ), (
                "Los pasos actualizados "
                "no fueron persistidos."
            )

            assert (
                updated_routine.get(
                    "followup_question"
                )
                ==
                "¿El nuevo paso hizo "
                "más sencilla la salida?"
            )

            print(
                "Actualización de rutina: OK"
            )

            # =================================================
            # 11. IMPEDIR ACTUALIZACIÓN DESDE OTRO PERFIL
            # =================================================

            forbidden_update = (
                routine_memory.update_routine(
                    routine_id=routine_id,
                    family_id=family_id,
                    profile_id=other_profile_id,
                    goal=(
                        "Este cambio "
                        "no debe guardarse."
                    ),
                )
            )

            assert (
                forbidden_update.get("updated")
                is False
            ), (
                "Un perfil distinto logró "
                "modificar la rutina."
            )

            assert (
                forbidden_update.get("reason")
                ==
                "routine_not_found_in_scope"
            )

            print(
                "Protección de actualización "
                "por perfil: OK"
            )

        finally:

            routine_memory.close()

        # =====================================================
        # RESULTADO FINAL
        # =====================================================

        print()
        print(
            "ORCHESTRATOR_ROUTINE_PERSISTENCE_OK"
        )

        print(
            "Mensaje → generación → caso "
            "→ persistencia → recuperación "
            "→ modificación: OK"
        )

        return 0

if __name__ == "__main__":
    raise SystemExit(main())
