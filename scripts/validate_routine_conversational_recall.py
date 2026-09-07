# -*- coding: utf-8 -*-
"""Valida modificación conversacional de una rutina persistida entre sesiones.

Prueba el flujo:
solicitud de rutina -> persistencia -> cierre de sesión -> nueva sesión
-> orden explícita de modificación -> actualización del mismo registro
-> recuperación del cambio -> aislamiento por perfil.

Usa únicamente SQLite temporal y datos ficticios.
No utiliza Supabase, OpenAI real, credenciales ni datos de participantes.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from core.orchestrator_v2 import NeuroGuiaOrchestratorV2
from database.database import initialize_database
from memory.profile_manager import ProfileManager
from memory.routine_memory import RoutineMemory


def main() -> int:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(
            Path(tmpdir)
            / "routine_conversational_update.db"
        )

        # =====================================================
        # 1. BASE TEMPORAL
        # =====================================================

        database = initialize_database(
            db_path=db_path
        )
        database.close()

        # =====================================================
        # 2. FAMILIA Y DOS PERFILES FICTICIOS
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
                    "Contexto ficticio para prueba "
                    "de modificación conversacional."
                ),
                support_network="Red ficticia",
                environmental_factors=None,
                global_history=None,
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

            assert family_id
            assert profile_id
            assert other_profile_id

        finally:
            profile_manager.close()

        # =====================================================
        # 3. SESIÓN 1: GENERAR Y GUARDAR RUTINA
        # =====================================================

        first_orchestrator = NeuroGuiaOrchestratorV2(
            db_path=db_path
        )

        try:
            first_result = first_orchestrator.process_message(
                message=(
                    "Necesito una rutina visual para organizar "
                    "las mañanas de mi hijo Leo."
                ),
                family_id=family_id,
                profile_id=profile_id,
                extra_context={
                    "session_scope_id":
                        "defense-routine-update-session-1"
                },
                chat_history=[],
                use_llm_stub=True,
                auto_save_case=True,
            )

            first_payload = (
                first_result.get("routine_payload")
                or {}
            )
            first_store = (
                first_result.get("routine_store_result")
                or {}
            )

            assert first_payload, (
                "No se generó la rutina inicial."
            )
            assert first_store.get("stored") is True, (
                "La rutina inicial no fue persistida."
            )

            routine_id = str(
                first_store.get("routine_id")
                or ""
            ).strip()
            first_steps = list(
                first_payload.get("steps")
                or []
            )

            assert routine_id
            assert first_steps, (
                "La rutina inicial no contiene pasos."
            )

            original_first_step = str(
                first_steps[0]
                or ""
            ).strip()
            assert original_first_step

        finally:
            first_orchestrator.close()

        print("Sesión 1: rutina generada y persistida: OK")

        # =====================================================
        # 4. SESIÓN 2: MODIFICACIÓN CONVERSACIONAL
        # =====================================================

        replacement = "Revisar la mochila antes de salir"

        second_orchestrator = NeuroGuiaOrchestratorV2(
            db_path=db_path
        )

        try:
            update_result = second_orchestrator.process_message(
                message=(
                    "Cambia el primer paso de esa rutina por "
                    f"{replacement}."
                ),
                family_id=family_id,
                profile_id=profile_id,
                extra_context={
                    "session_scope_id":
                        "defense-routine-update-session-2"
                },
                chat_history=[],
                use_llm_stub=True,
                auto_save_case=True,
            )

            routine_update = (
                update_result.get(
                    "routine_update_result"
                )
                or {}
            )

            assert routine_update.get("updated") is True, (
                "La nueva sesión no modificó la rutina persistida. "
                f"Resultado: {routine_update}"
            )

            assert (
                str(routine_update.get("routine_id") or "")
                == routine_id
            ), (
                "La modificación se aplicó sobre una rutina distinta."
            )

            assert routine_update.get("step_number") == 1
            assert routine_update.get("replacement") == replacement

            response_package = (
                update_result.get("response_package")
                or {}
            )
            response_text = str(
                response_package.get("response")
                or response_package.get("text")
                or ""
            ).strip()

            assert response_text, (
                "La modificación no produjo respuesta visible."
            )
            assert replacement in response_text, (
                "La respuesta no confirma el nuevo paso."
            )

            metadata = (
                response_package.get("response_metadata")
                or {}
            )
            assert (
                metadata.get("response_source")
                == "routine_memory_update"
            )
            assert metadata.get("routine_updated") is True

        finally:
            second_orchestrator.close()

        print("Sesión 2: modificación conversacional: OK")
        print("Mismo routine_id después del cambio: OK")

        # =====================================================
        # 5. SESIÓN 3: COMPROBAR PERSISTENCIA DEL CAMBIO
        # =====================================================

        routine_memory = RoutineMemory(
            db_path=db_path,
            backend="sqlite",
        )

        try:
            persisted = routine_memory.get_routine(
                routine_id
            )

            assert persisted is not None, (
                "La rutina modificada no pudo recuperarse."
            )

            persisted_steps = list(
                persisted.get("steps")
                or []
            )

            assert persisted_steps, (
                "La rutina modificada perdió sus pasos."
            )

            assert persisted_steps[0] == replacement, (
                "El cambio conversacional no quedó persistido."
            )

            assert persisted_steps[0] != original_first_step, (
                "El primer paso no cambió realmente."
            )

        finally:
            routine_memory.close()

        print("Persistencia del cambio entre sesiones: OK")

        # =====================================================
        # 6. AISLAMIENTO: OTRO PERFIL NO PUEDE MODIFICARLA
        # =====================================================

        other_orchestrator = NeuroGuiaOrchestratorV2(
            db_path=db_path
        )

        try:
            other_result = other_orchestrator.process_message(
                message=(
                    "Cambia el primer paso de esa rutina por "
                    "Este cambio no debe aplicarse."
                ),
                family_id=family_id,
                profile_id=other_profile_id,
                extra_context={
                    "session_scope_id":
                        "defense-routine-update-session-other"
                },
                chat_history=[],
                use_llm_stub=True,
                auto_save_case=True,
            )

            other_update = (
                other_result.get(
                    "routine_update_result"
                )
                or {}
            )

            assert other_update.get("updated") is False, (
                "Un perfil distinto logró modificar la rutina."
            )

            assert (
                other_update.get("reason")
                == "no_active_routine"
            )

        finally:
            other_orchestrator.close()

        print("Aislamiento de modificación por perfil: OK")

        # =====================================================
        # RESULTADO
        # =====================================================

        print()
        print("ROUTINE_CONVERSATIONAL_UPDATE_OK")
        print(
            "Generación → persistencia → nueva sesión → "
            "modificación conversacional → persistencia del cambio "
            "→ aislamiento: OK"
        )

        return 0


if __name__ == "__main__":
    raise SystemExit(main())
