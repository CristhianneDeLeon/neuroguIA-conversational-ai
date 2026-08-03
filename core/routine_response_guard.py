from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.functional_category_router import FunctionalCategoryRouter
from core.routine_activation_engine import RoutineActivationEngine
from core.routine_builder_v2 import RoutineBuilderV2, attach_routine_to_response


class RoutineResponseGuard:
    """Garantiza que una rutina solicitada llegue al texto visible.

    Funciona como una capa final de seguridad. El orquestador sigue siendo la
    fuente principal; esta clase solo interviene cuando detecta una solicitud
    de rutina y la respuesta recibida no contiene todavía una rutina visible.
    """

    def __init__(self) -> None:
        self.functional_router = FunctionalCategoryRouter()
        self.activation_engine = RoutineActivationEngine()
        self.builder = RoutineBuilderV2()

    def ensure(
        self,
        *,
        message: str,
        result: Optional[Dict[str, Any]],
        previous_frame: Optional[Dict[str, Any]] = None,
        active_profile: Optional[Dict[str, Any]] = None,
        extra_context: Optional[Dict[str, Any]] = None,
        chat_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        output = dict(result or {})
        previous_frame = dict(previous_frame or {})
        active_profile = dict(active_profile or output.get("active_profile") or {})
        extra_context = dict(extra_context or {})
        chat_history = list(chat_history or [])

        normalized_message = str(message or "").strip().lower()
        refers_to_previous_routine = any(
            marker in normalized_message
            for marker in (
                "rutina que te ped", "la rutina que te ped", "esa rutina",
                "ahora genera la rutina", "ahora haz la rutina", "hazla ahora",
            )
        )
        effective_message = str(message or "").strip()
        if refers_to_previous_routine:
            for turn in reversed(chat_history[-8:]):
                if not isinstance(turn, dict):
                    continue
                prior_user = str(turn.get("user") or "").strip()
                prior_normalized = prior_user.lower()
                if any(token in prior_normalized for token in ("rutina", "plan", "organizar")):
                    effective_message = f"{message}\nContexto previo: {prior_user}"
                    break

        response_package = dict(output.get("response_package") or {})
        response_metadata = dict(response_package.get("response_metadata") or {})
        existing_routine = dict(
            output.get("routine_payload")
            or response_package.get("routine_payload")
            or {}
        )

        functional = dict(output.get("functional_analysis") or {})
        state_analysis = dict(output.get("state_analysis") or {})
        category_analysis = dict(output.get("category_analysis") or {})
        conversation_frame = dict(output.get("conversation_frame") or {})
        conversation_control = dict(output.get("conversation_control") or {})

        technical_category = (
            output.get("detected_category")
            or category_analysis.get("detected_category")
            or response_metadata.get("detected_category")
            or response_metadata.get("route_id")
        )
        primary_state = (
            output.get("primary_state")
            or state_analysis.get("primary_state")
            or response_metadata.get("primary_state")
        )

        if not functional:
            functional = self.functional_router.route(
                message=effective_message,
                technical_category=technical_category,
                primary_state=primary_state,
                conversation_domain=conversation_frame.get("conversation_domain")
                or technical_category,
                profile=active_profile,
                previous_frame=previous_frame,
            )

        activation = dict(output.get("routine_activation") or {})
        if not activation:
            activation = self.activation_engine.evaluate(
                message=effective_message,
                functional_analysis=functional,
                technical_category=technical_category,
                primary_state=primary_state,
                turn_family=conversation_control.get("turn_family")
                or conversation_frame.get("turn_family"),
                emotional_intensity=output.get("emotional_intensity")
                or state_analysis.get("emotional_intensity"),
                caregiver_capacity=output.get("caregiver_capacity")
                or state_analysis.get("caregiver_capacity"),
                previous_frame=previous_frame,
            )

        routine = existing_routine
        if activation.get("should_generate") and not routine:
            routine = self.builder.build_routine(
                profile=active_profile,
                state_analysis=state_analysis,
                stage_result=dict(output.get("stage_result") or {}),
                memory_payload=dict(output.get("memory_payload") or {}),
                routine_type=activation.get("routine_type"),
                caregiver_capacity=output.get("caregiver_capacity")
                or state_analysis.get("caregiver_capacity"),
                emotional_intensity=output.get("emotional_intensity")
                or state_analysis.get("emotional_intensity"),
                context={
                    "detected_category": technical_category,
                    "functional_category": functional.get("functional_category"),
                    "functional_category_label": functional.get("functional_category_label"),
                    "functional_category_purpose": functional.get("functional_category_purpose"),
                    "display_mode": activation.get("display_mode"),
                    "activation_reason": activation.get("reason"),
                    "text_hint": effective_message,
                    "conversation_domain": conversation_frame.get("conversation_domain"),
                    "support_goal": conversation_frame.get("support_goal"),
                    "conversation_phase": conversation_frame.get("conversation_phase"),
                    **extra_context,
                },
            )
            routine["activation"] = dict(activation)

        if routine:
            response_package = attach_routine_to_response(
                response_package=response_package,
                routine_payload=routine,
                functional_analysis=functional,
                routine_activation=activation,
            )
            output["response_package"] = response_package
            output["routine_payload"] = routine
            output["functional_analysis"] = functional
            output["routine_activation"] = activation

            frame = dict(output.get("conversation_frame") or {})
            frame["functional_category"] = functional.get("functional_category")
            frame["functional_category_label"] = functional.get("functional_category_label")
            frame["functional_category_purpose"] = functional.get("functional_category_purpose")
            frame["last_routine_type"] = routine.get("routine_type")
            frame["last_routine_generated"] = True
            output["conversation_frame"] = frame

        return output
