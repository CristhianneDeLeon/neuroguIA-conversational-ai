# -*- coding: utf-8 -*-
"""Regresiones críticas para la versión de defensa de neuroguIA.

Valida:
1) identidad del interlocutor != perfil acompañado;
2) persistencia de nombre/relación entre sesiones;
3) consulta explícita del perfil activo;
4) continuidad referencial tras rechazo de una estrategia;
5) no repetir una rutina inmediatamente después del rechazo.

Usa SQLite temporal y datos completamente ficticios.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.orchestrator_v2 import NeuroGuiaOrchestratorV2
from core.routine_response_guard import RoutineResponseGuard
from core.conversation_continuity_guard import ConversationContinuityGuard
from database.database import initialize_database
from memory.profile_manager import ProfileManager


def response_text(result):
    package = result.get("response_package") or {}
    return str(package.get("response") or package.get("text") or "").strip()


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="neuroguia_defense_regression_") as tmp:
        db_path = str(Path(tmp) / "defense_regression.db")
        db = initialize_database(db_path=db_path)
        db.close()

        pm = ProfileManager(db_path=db_path, backend="sqlite")
        try:
            family_id = pm.create_unit(
                unit_type="family",
                caregiver_alias="Familia Demo Mateo",
                context_notes="Contexto ficticio de validación.",
                support_network="Red ficticia",
                environmental_factors=None,
                global_history=None,
            )
            profile_id = pm.create_profile(
                family_id=family_id,
                alias="Mateo DEMO",
                age=10,
                role="hijo",
                conditions=["Altas capacidades", "TDAH"],
                strengths=["aprende rápido cuando el tema le interesa"],
                triggers=["presión"],
                early_signs=[],
                helpful_strategies=["instrucciones claras y breves"],
                harmful_strategies=[],
                sensory_needs=[],
                emotional_needs=[],
                autonomy_level=None,
                sleep_profile=None,
                school_profile=None,
                executive_profile="dificultad para iniciar tareas",
                evolution_notes=None,
            )
        finally:
            pm.close()

        # Sesión 1: quien escribe declara su identidad.
        orch = NeuroGuiaOrchestratorV2(db_path=db_path)
        try:
            stored = orch.process_message(
                message="Mi nombre es Lucía y soy la mamá de Mateo DEMO.",
                family_id=family_id,
                profile_id=profile_id,
                extra_context={"session_scope_id": "identity-session-1"},
                chat_history=[],
                auto_save_case=False,
                use_llm_stub=True,
            )
            stored_text = response_text(stored)
            assert "Lucía" in stored_text, stored_text
            assert "mamá" in stored_text.lower(), stored_text
        finally:
            orch.close()

        # Sesión 2: debe recordar a quien escribe, no confundirla con Mateo.
        orch = NeuroGuiaOrchestratorV2(db_path=db_path)
        try:
            who = orch.process_message(
                message="¿Quién soy?",
                family_id=family_id,
                profile_id=profile_id,
                extra_context={"session_scope_id": "identity-session-2"},
                chat_history=[],
                auto_save_case=False,
                use_llm_stub=True,
            )
            who_text = response_text(who)
            assert "Lucía" in who_text, who_text
            assert "mamá" in who_text.lower(), who_text
            assert not who_text.startswith("Eres Mateo DEMO"), who_text

            # La app aplica dos guardas finales. Ninguna debe reinterpretar
            # una respuesta determinista de identidad como rutina o follow-up.
            routine_guard = RoutineResponseGuard()
            guarded_who = routine_guard.ensure(
                message="¿Quién soy?",
                result=who,
                previous_frame={},
                active_profile=who.get("active_profile") or {},
                extra_context={},
                chat_history=[],
            )
            continuity_guard = ConversationContinuityGuard()
            guarded_who = continuity_guard.ensure(
                message="¿Quién soy?",
                result=guarded_who,
                chat_history=[],
                previous_result={},
                active_profile=who.get("active_profile") or {},
            )
            assert response_text(guarded_who) == who_text, response_text(guarded_who)

            # Identidad nunca debe imponerse sobre una necesidad de apoyo o riesgo.
            mixed_support = orch.process_message(
                message="Mi nombre es Lucía y estoy muy ansiosa; no sé cómo calmarme.",
                family_id=family_id,
                profile_id=profile_id,
                extra_context={"session_scope_id": "identity-session-2"},
                chat_history=[],
                auto_save_case=False,
                use_llm_stub=True,
            )
            mixed_source = str(
                (mixed_support.get("response_package") or {}).get("response_source")
                or ((mixed_support.get("response_package") or {}).get("response_metadata") or {}).get("response_source")
                or ""
            )
            assert mixed_source != "speaker_identity_memory", mixed_source

            mixed_risk = orch.process_message(
                message="¿Quién soy? Estoy en crisis y siento que puedo lastimarme.",
                family_id=family_id,
                profile_id=profile_id,
                extra_context={"session_scope_id": "identity-session-2"},
                chat_history=[],
                auto_save_case=False,
                use_llm_stub=True,
            )
            risk_source = str(
                (mixed_risk.get("response_package") or {}).get("response_source")
                or ((mixed_risk.get("response_package") or {}).get("response_metadata") or {}).get("response_source")
                or ""
            )
            assert risk_source != "speaker_identity_memory", risk_source

            profile = orch.process_message(
                message="¿Con qué perfil estamos trabajando?",
                family_id=family_id,
                profile_id=profile_id,
                extra_context={"session_scope_id": "identity-session-2"},
                chat_history=[],
                auto_save_case=False,
                use_llm_stub=True,
            )
            profile_text = response_text(profile)
            assert "Mateo DEMO" in profile_text, profile_text
            assert "perfil" in profile_text.lower(), profile_text

            summary = orch.process_message(
                message="¿Qué recuerdas de Mateo?",
                family_id=family_id,
                profile_id=profile_id,
                extra_context={"session_scope_id": "identity-session-2"},
                chat_history=[],
                auto_save_case=False,
                use_llm_stub=True,
            )
            summary_text = response_text(summary)
            assert "Mateo DEMO" in summary_text, summary_text
            assert "TDAH" in summary_text, summary_text
            assert "instrucciones claras y breves" in summary_text.lower(), summary_text

            guarded_summary = routine_guard.ensure(
                message="¿Qué recuerdas de Mateo?",
                result=summary,
                previous_frame={},
                active_profile=summary.get("active_profile") or {},
                extra_context={},
                chat_history=[],
            )
            guarded_summary = continuity_guard.ensure(
                message="¿Qué recuerdas de Mateo?",
                result=guarded_summary,
                chat_history=[],
                previous_result={},
                active_profile=summary.get("active_profile") or {},
            )
            assert response_text(guarded_summary) == summary_text, response_text(guarded_summary)
        finally:
            orch.close()

        # Continuidad: si rechaza una vía, no debe reaparecer la rutina completa.
        orch = NeuroGuiaOrchestratorV2(db_path=db_path)
        try:
            first_message = "Me cuesta muchísimo empezar la tarea de matemáticas."
            first = orch.process_message(
                message=first_message,
                family_id=family_id,
                profile_id=profile_id,
                extra_context={"session_scope_id": "continuity-session"},
                chat_history=[],
                auto_save_case=False,
                use_llm_stub=True,
            )
            first_text = response_text(first)

            second = orch.process_message(
                message="¿Y si eso no me funciona?",
                family_id=family_id,
                profile_id=profile_id,
                extra_context={
                    "session_scope_id": "continuity-session",
                    "conversation_frame": first.get("conversation_frame") or {},
                },
                chat_history=[{"user": first_message, "assistant": first_text}],
                auto_save_case=False,
                use_llm_stub=True,
            )
            second_text = response_text(second)
            second_frame = second.get("conversation_frame") or {}
            assert second_frame.get("repair_type") == "strategy_rejection", second_frame
            assert not bool(second.get("routine_payload")), second.get("routine_payload")
            assert "no repetimos" in second_text.lower() or "no insistimos" in second_text.lower(), second_text
        finally:
            orch.close()

        print("DEFENSE_CRITICAL_REGRESSIONS_OK")
        print("Interlocutor/perfil, persistencia de identidad y continuidad referencial: OK")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
