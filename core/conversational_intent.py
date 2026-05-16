from __future__ import annotations

from typing import Any, Dict, Optional


class ConversationalIntentBuilder:
    """
    Builds only the conversational modulation for the current turn.

    This layer must not define domain content, propose actions or inject phrases.
    It only shapes rhythm, pressure, permissiveness and closing style.
    """

    def build(
        self,
        stage_result: Optional[Dict[str, Any]] = None,
        decision_payload: Optional[Dict[str, Any]] = None,
        state_analysis: Optional[Dict[str, Any]] = None,
        category_analysis: Optional[Dict[str, Any]] = None,
        intent_analysis: Optional[Dict[str, Any]] = None,
        case_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        stage_result = stage_result or {}
        decision_payload = decision_payload or {}
        state_analysis = state_analysis or {}
        category_analysis = category_analysis or {}
        intent_analysis = intent_analysis or {}
        case_context = case_context or {}

        conversation_control = case_context.get("conversation_control", {}) or {}
        response_goal = decision_payload.get("response_goal", {}) or {}

        domain = (
            stage_result.get("conversation_domain")
            or conversation_control.get("domain")
            or category_analysis.get("detected_category")
            or "apoyo_general"
        )
        stage = stage_result.get("stage") or "adaptive_intervention"
        turn_family = (
            stage_result.get("turn_family")
            or conversation_control.get("turn_family")
            or "new_request"
        )
        clarification_mode = (
            stage_result.get("clarification_mode")
            or conversation_control.get("clarification_mode")
            or "none"
        )
        crisis_guided_mode = (
            stage_result.get("crisis_guided_mode")
            or conversation_control.get("crisis_guided_mode")
            or "none"
        )
        primary_state = state_analysis.get("primary_state")
        detected_intent = intent_analysis.get("detected_intent")
        response_shape = str(response_goal.get("response_shape") or "single_action")
        followup_policy = str(response_goal.get("followup_policy") or "avoid")

        rhythm = "steady"
        pressure = "low"
        permissiveness = "moderate"
        closing_style = "none"

        if clarification_mode != "none" or stage == "focus_clarification":
            rhythm = "slow"
            pressure = "none"
            permissiveness = "high"
            closing_style = "none"
        elif turn_family in {"meta_question", "simple_question", "validation_request"}:
            rhythm = "steady"
            pressure = "none"
            permissiveness = "moderate"
            closing_style = "none"
        elif turn_family == "closure_or_pause":
            rhythm = "slow"
            pressure = "none"
            permissiveness = "high"
            closing_style = "soft_stop"
        elif domain == "crisis_activa" or primary_state in {"meltdown", "shutdown"}:
            if response_shape in {"literal_phrase", "direct_instruction", "guided_steps"} or crisis_guided_mode == "guided_steps":
                rhythm = "direct"
                pressure = "low"
                permissiveness = "moderate"
            else:
                rhythm = "very_slow"
                pressure = "none"
                permissiveness = "high"
            closing_style = "none"
        elif turn_family in {"specific_action_request", "literal_phrase_request"}:
            rhythm = "direct"
            pressure = "low"
            permissiveness = "moderate"
            closing_style = "none"
        elif turn_family in {"blocked_followup", "strategy_rejection", "post_action_followup", "outcome_report"}:
            rhythm = "direct"
            pressure = "low"
            permissiveness = "moderate"
            closing_style = "none"
        elif response_goal.get("should_stay_with_validation") or response_goal.get("keep_minimal"):
            rhythm = "slow"
            pressure = "none"
            permissiveness = "high"
            closing_style = "soft_stop"
        elif domain in {"ansiedad_cognitiva", "sobrecarga_cuidador", "sueno_regulacion"}:
            rhythm = "slow"
            pressure = "none"
            permissiveness = "high"
            closing_style = "none"
        elif domain in {"disfuncion_ejecutiva", "sobrecarga_sensorial", "transicion_rigidez", "prevencion_escalada"}:
            rhythm = "steady"
            pressure = "low"
            permissiveness = "moderate"
            closing_style = "none"

        if detected_intent == "urgent_support":
            rhythm = "direct" if domain == "crisis_activa" else rhythm
            pressure = "low" if pressure == "none" else pressure
            closing_style = "none"

        if followup_policy == "brief_check" and not response_goal.get("keep_minimal"):
            closing_style = "brief_check"

        if response_goal.get("should_offer_question") and closing_style == "none" and followup_policy in {"optional", "brief_check"}:
            closing_style = "brief_check"

        return {
            "rhythm": rhythm,
            "pressure": pressure,
            "permissiveness": permissiveness,
            "closing_style": closing_style,
            "reason": self._build_reason(
                domain=domain,
                stage=stage,
                turn_family=turn_family,
                clarification_mode=clarification_mode,
                crisis_guided_mode=crisis_guided_mode,
                response_shape=response_shape,
            ),
        }

    def _build_reason(
        self,
        domain: str,
        stage: str,
        turn_family: str,
        clarification_mode: str,
        crisis_guided_mode: str,
        response_shape: str,
    ) -> str:
        parts = [domain or "apoyo_general", stage, turn_family, response_shape]
        if clarification_mode != "none":
            parts.append("clarification")
        if crisis_guided_mode == "guided_steps":
            parts.append("guided_crisis")
        return "_".join(parts)


def build_conversational_intent(**kwargs: Any) -> Dict[str, Any]:
    return ConversationalIntentBuilder().build(**kwargs)
