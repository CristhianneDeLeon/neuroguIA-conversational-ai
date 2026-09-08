# -*- coding: utf-8 -*-
"""Valida recuperación conversacional de rutinas entre sesiones.

Prueba el flujo:
solicitud de rutina -> persistencia -> cierre de sesión -> nueva sesión
-> petición explícita de recuerdo -> recuperación del mismo registro.

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


def main() -> int:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(
            Path(tmpdir)
            / "routine_conversational_recall.db"
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
                    "de recuperación conversacional."
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
                        "defense-routine-recall-session-1"
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
            routine_name = str(
                first_payload.get("routine_name")
                or ""
            ).strip()
            first_steps = list(
                first_payload.get("steps")
                or []
            )

            assert routine_id
            assert routine_name
            assert first_steps

        finally:
            first_orchestrator.close()

        print("Sesión 1: rutina generada y persistida: OK")

        # =====================================================
        # 4. SESIÓN 2: RECUPERACIÓN CONVERSACIONAL
        # =====================================================

        second_orchestrator = NeuroGuiaOrchestratorV2(
            db_path=db_path
        )

        try:
            recall_result = second_orchestrator.process_message(
                message=(
                    "¿Recuerdas la rutina que hicimos "
                    "para las mañanas de Leo? Muéstrame la rutina."
                ),
                family_id=family_id,
                profile_id=profile_id,
                extra_context={
                    "session_scope_id":
                        "defense-routine-recall-session-2"
                },
                chat_history=[],
                use_llm_stub=True,
                auto_save_case=True,
            )

            retrieval = (
                recall_result.get(
                    "routine_retrieval_result"
                )
                or {}
            )

            assert retrieval.get("found") is True, (
                "La nueva sesión no recuperó la rutina persistida. "
                f"Resultado: {retrieval}"
            )

            assert (
                str(retrieval.get("routine_id") or "")
                == routine_id
            ), (
                "Se recuperó una rutina distinta."
            )

            recalled_payload = (
                recall_result.get("routine_payload")
                or {}
            )

            assert (
                recalled_payload.get("routine_id")
                == routine_id
            )

            response_package = (
                recall_result.get("response_package")
                or {}
            )
            response_text = str(
                response_package.get("response")
                or response_package.get("text")
                or ""
            ).strip()

            assert response_text, (
                "La recuperación no produjo respuesta visible."
            )

            assert routine_name in response_text, (
                "La respuesta no muestra el nombre "
                "de la rutina recuperada."
            )

            first_step = str(first_steps[0] or "").strip()
            assert first_step in response_text, (
                "La respuesta no muestra los pasos "
                "de la rutina persistida."
            )

            metadata = (
                response_package.get("response_metadata")
                or {}
            )

            assert (
                metadata.get("response_source")
                == "routine_memory_recall"
            )

            assert (
                metadata.get("routine_retrieved")
                is True
            )

        finally:
            second_orchestrator.close()

        print("Sesión 2: recuperación conversacional: OK")
        print("Mismo routine_id entre sesiones: OK")
        print("Rutina visible en respuesta: OK")

        # =====================================================
        # 5. AISLAMIENTO: OTRO PERFIL NO PUEDE RECUPERARLA
        # =====================================================

        other_orchestrator = NeuroGuiaOrchestratorV2(
            db_path=db_path
        )

        try:
            other_result = other_orchestrator.process_message(
                message=(
                    "¿Recuerdas la rutina que guardamos? "
                    "Muéstrame la rutina."
                ),
                family_id=family_id,
                profile_id=other_profile_id,
                extra_context={
                    "session_scope_id":
                        "defense-routine-recall-session-other"
                },
                chat_history=[],
                use_llm_stub=True,
                auto_save_case=True,
            )

            other_retrieval = (
                other_result.get(
                    "routine_retrieval_result"
                )
                or {}
            )

            assert (
                other_retrieval.get("found")
                is False
            ), (
                "Una rutina fue recuperada desde un perfil "
                "al que no pertenece."
            )

            assert (
                other_retrieval.get("reason")
                == "no_active_routine"
            )

        finally:
            other_orchestrator.close()

        print("Aislamiento conversacional por perfil: OK")

        # =====================================================
        # RESULTADO
        # =====================================================

        print()
        print("ROUTINE_CONVERSATIONAL_RECALL_OK")
        print(
            "Generación → persistencia → nueva sesión "
            "→ recuerdo conversacional → aislamiento: OK"
        )

        return 0

if __name__ == "__main__":
    raise SystemExit(main())
