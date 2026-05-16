from __future__ import annotations

from typing import Any, Dict, List, Optional


class ExpertModeAdapter:
    """
    Capa de adaptación experta para NeuroGuIA.

    Responsabilidades:
    - decidir el estilo de respuesta según rol, dominio, fase y estado
    - modular tono, longitud, estructura y cierre
    - bajar o subir carga cognitiva de la respuesta
    - ayudar a que NeuroGuIA suene distinto según el tipo de usuario y situación
    """

    def build_adaptation_plan(
        self,
        conversation_frame: Optional[Dict[str, Any]] = None,
        state_analysis: Optional[Dict[str, Any]] = None,
        category_analysis: Optional[Dict[str, Any]] = None,
        intent_analysis: Optional[Dict[str, Any]] = None,
        stage_result: Optional[Dict[str, Any]] = None,
        active_profile: Optional[Dict[str, Any]] = None,
        case_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        conversation_frame = conversation_frame or {}
        state_analysis = state_analysis or {}
        category_analysis = category_analysis or {}
        intent_analysis = intent_analysis or {}
        stage_result = stage_result or {}
        active_profile = active_profile or {}
        case_context = case_context or {}

        speaker_role = conversation_frame.get("speaker_role") or "usuario"
        domain = conversation_frame.get("conversation_domain") or category_analysis.get("detected_category") or "apoyo_general"
        phase = conversation_frame.get("conversation_phase") or "clarification"
        support_goal = conversation_frame.get("support_goal") or "clarify_and_support"

        primary_state = state_analysis.get("primary_state") or "general_distress"
        secondary_states = state_analysis.get("secondary_states", []) or []
        detected_intent = intent_analysis.get("detected_intent") or "general_support"
        stage = stage_result.get("stage") or "adaptive_intervention"

        emotional_intensity = float(case_context.get("emotional_intensity", 0.0) or 0.0)
        caregiver_capacity = case_context.get("caregiver_capacity")
        profile_age = active_profile.get("age")
        profile_conditions = active_profile.get("conditions", []) or []

        tone_profile = self._resolve_tone_profile(
            speaker_role=speaker_role,
            domain=domain,
            primary_state=primary_state,
            emotional_intensity=emotional_intensity,
            caregiver_capacity=caregiver_capacity,
        )

        structure_profile = self._resolve_structure_profile(
            speaker_role=speaker_role,
            domain=domain,
            phase=phase,
            stage=stage,
            primary_state=primary_state,
            emotional_intensity=emotional_intensity,
            detected_intent=detected_intent,
        )

        language_profile = self._resolve_language_profile(
            speaker_role=speaker_role,
            profile_age=profile_age,
            profile_conditions=profile_conditions,
            primary_state=primary_state,
            emotional_intensity=emotional_intensity,
        )

        followup_policy = self._resolve_followup_policy(
            domain=domain,
            phase=phase,
            primary_state=primary_state,
            emotional_intensity=emotional_intensity,
            detected_intent=detected_intent,
        )

        expert_flags = self._resolve_expert_flags(
            speaker_role=speaker_role,
            domain=domain,
            primary_state=primary_state,
            secondary_states=secondary_states,
            support_goal=support_goal,
            phase=phase,
        )

        return {
            "expert_mode_enabled": True,
            "speaker_role": speaker_role,
            "conversation_domain": domain,
            "conversation_phase": phase,
            "support_goal": support_goal,
            "primary_state": primary_state,
            "tone_profile": tone_profile,
            "structure_profile": structure_profile,
            "language_profile": language_profile,
            "followup_policy": followup_policy,
            "expert_flags": expert_flags,
        }

    # =========================================================
    # TONO
    # =========================================================
    def _resolve_tone_profile(
        self,
        speaker_role: str,
        domain: str,
        primary_state: str,
        emotional_intensity: float,
        caregiver_capacity: Optional[float],
    ) -> Dict[str, Any]:
        warmth = "medium"
        firmness = "medium"
        directness = "medium"
        emotional_validation = "medium"

        if primary_state in {"meltdown", "shutdown"}:
            warmth = "high"
            firmness = "low"
            directness = "high"
            emotional_validation = "high"

        elif primary_state in {"burnout", "parental_fatigue"}:
            warmth = "high"
            firmness = "low"
            directness = "medium"
            emotional_validation = "high"

        elif domain in {"disfuncion_ejecutiva", "ansiedad_cognitiva"}:
            warmth = "high"
            firmness = "medium"
            directness = "high"
            emotional_validation = "medium_high"

        elif domain in {"prevencion_escalada", "transicion_rigidez", "sobrecarga_sensorial"}:
            warmth = "medium_high"
            firmness = "medium"
            directness = "high"
            emotional_validation = "medium"

        if speaker_role == "docente":
            firmness = "medium_high"
            directness = "high"

        if speaker_role == "cuidador":
            warmth = "high"
            emotional_validation = "high"

        if emotional_intensity >= 0.78:
            directness = "high"
            firmness = "low"
            warmth = "high"

        if caregiver_capacity is not None and caregiver_capacity <= 0.35:
            emotional_validation = "high"
            firmness = "low"

        return {
            "warmth": warmth,
            "firmness": firmness,
            "directness": directness,
            "emotional_validation": emotional_validation,
        }

    # =========================================================
    # ESTRUCTURA
    # =========================================================
    def _resolve_structure_profile(
        self,
        speaker_role: str,
        domain: str,
        phase: str,
        stage: str,
        primary_state: str,
        emotional_intensity: float,
        detected_intent: str,
    ) -> Dict[str, Any]:
        opening_style = "empathetic"
        body_style = "guided"
        closing_style = "soft_followup"
        bullet_like_steps = True
        max_steps = 4
        paragraph_density = "medium"
        explanation_depth = "medium"

        if primary_state in {"meltdown", "shutdown"}:
            body_style = "containment"
            closing_style = "stabilizing"
            bullet_like_steps = True
            max_steps = 3
            paragraph_density = "low"
            explanation_depth = "low"

        elif domain == "ansiedad_cognitiva":
            body_style = "cognitive_unloading"
            closing_style = "ordering_followup"
            max_steps = 3
            explanation_depth = "medium"

        elif domain == "disfuncion_ejecutiva":
            body_style = "microstep_guidance"
            closing_style = "tiny_next_step"
            max_steps = 3
            explanation_depth = "low_medium"

        elif domain == "prevencion_escalada":
            body_style = "preventive_mapping"
            closing_style = "signal_followup"
            max_steps = 4
            explanation_depth = "medium"

        elif domain == "regulacion_post_evento":
            body_style = "repair_guidance"
            closing_style = "repair_followup"
            max_steps = 4
            explanation_depth = "medium"

        elif domain == "sobrecarga_sensorial":
            body_style = "environment_adjustment"
            closing_style = "trigger_followup"
            max_steps = 4
            explanation_depth = "low_medium"

        elif domain == "transicion_rigidez":
            body_style = "predictability_guidance"
            closing_style = "transition_followup"
            max_steps = 4
            explanation_depth = "medium"

        if speaker_role == "docente":
            body_style = f"{body_style}_classroom"
            explanation_depth = "medium"
            max_steps = min(max_steps, 4)

        if stage == "focus_clarification":
            body_style = "focus_narrowing"
            max_steps = 3
            explanation_depth = "low"

        if stage == "closure_continuity":
            closing_style = "continuity_bridge"

        if emotional_intensity >= 0.78 or detected_intent == "urgent_support":
            paragraph_density = "low"
            explanation_depth = "low"
            max_steps = min(max_steps, 3)

        return {
            "opening_style": opening_style,
            "body_style": body_style,
            "closing_style": closing_style,
            "bullet_like_steps": bullet_like_steps,
            "max_steps": max_steps,
            "paragraph_density": paragraph_density,
            "explanation_depth": explanation_depth,
        }

    # =========================================================
    # LENGUAJE
    # =========================================================
    def _resolve_language_profile(
        self,
        speaker_role: str,
        profile_age: Optional[int],
        profile_conditions: List[str],
        primary_state: str,
        emotional_intensity: float,
    ) -> Dict[str, Any]:
        sentence_length = "medium"
        vocabulary_level = "clear"
        use_softeners = True
        use_examples = False
        avoid_jargon = True
        avoid_metaphors = False

        if primary_state in {"meltdown", "shutdown"}:
            sentence_length = "short"
            vocabulary_level = "very_clear"
            use_softeners = True
            use_examples = False
            avoid_metaphors = True

        elif primary_state in {"burnout", "parental_fatigue"}:
            sentence_length = "short_medium"
            vocabulary_level = "clear"
            use_examples = False

        if speaker_role == "docente":
            use_examples = True
            vocabulary_level = "clear_professional"

        if speaker_role == "cuidador":
            use_softeners = True
            use_examples = True

        if profile_age is not None and profile_age <= 18:
            sentence_length = "short"
            vocabulary_level = "very_clear"
            use_examples = True

        if any(str(c).upper() in {"TEA", "AUTISMO", "TDAH"} for c in profile_conditions):
            avoid_jargon = True
            use_examples = True

        if emotional_intensity >= 0.78:
            sentence_length = "short"
            avoid_metaphors = True

        return {
            "sentence_length": sentence_length,
            "vocabulary_level": vocabulary_level,
            "use_softeners": use_softeners,
            "use_examples": use_examples,
            "avoid_jargon": avoid_jargon,
            "avoid_metaphors": avoid_metaphors,
        }

    # =========================================================
    # FOLLOWUP
    # =========================================================
    def _resolve_followup_policy(
        self,
        domain: str,
        phase: str,
        primary_state: str,
        emotional_intensity: float,
        detected_intent: str,
    ) -> Dict[str, Any]:
        allow_followup_question = True
        followup_type = "gentle"
        max_followup_questions = 1

        if primary_state in {"meltdown", "shutdown"}:
            allow_followup_question = False
            followup_type = "none"

        elif emotional_intensity >= 0.82:
            allow_followup_question = False
            followup_type = "stabilizing"

        elif domain == "prevencion_escalada":
            followup_type = "signal_detection"

        elif domain == "ansiedad_cognitiva":
            followup_type = "priority_ordering"

        elif domain == "disfuncion_ejecutiva":
            followup_type = "micro_step"

        elif domain == "regulacion_post_evento":
            followup_type = "repair_reflection"

        elif phase in {"brief_reflection", "repair_phrase"}:
            followup_type = "reflective"

        if detected_intent == "urgent_support":
            allow_followup_question = False
            followup_type = "none"

        return {
            "allow_followup_question": allow_followup_question,
            "followup_type": followup_type,
            "max_followup_questions": max_followup_questions,
        }

    # =========================================================
    # FLAGS EXPERTOS
    # =========================================================
    def _resolve_expert_flags(
        self,
        speaker_role: str,
        domain: str,
        primary_state: str,
        secondary_states: List[str],
        support_goal: str,
        phase: str,
    ) -> Dict[str, bool]:
        states = {primary_state, *secondary_states}

        return {
            "needs_ultra_clear_language": bool({"meltdown", "shutdown"}.intersection(states)),
            "needs_high_validation": bool({"burnout", "parental_fatigue", "meltdown"}.intersection(states)),
            "needs_micro_steps": bool(domain in {"disfuncion_ejecutiva", "ansiedad_cognitiva", "prevencion_escalada"}),
            "needs_classroom_translation": speaker_role == "docente",
            "needs_caregiver_support_tone": speaker_role == "cuidador",
            "needs_preventive_structure": domain == "prevencion_escalada",
            "needs_repair_structure": domain == "regulacion_post_evento",
            "needs_environment_guidance": domain == "sobrecarga_sensorial",
            "needs_transition_guidance": domain == "transicion_rigidez",
            "phase_is_progressive": phase in {
                "mapping_signals",
                "pattern_detection",
                "prepare_early_response",
                "prioritize",
                "reduce_friction",
                "brief_reflection",
            },
            "goal_is_functional_support": support_goal in {
                "reduce_mental_overload",
                "enable_first_step",
                "prevent_recurrence",
                "repair_and_learn",
                "reduce_stimulus_load",
                "increase_predictability",
            },
        }


def build_expert_adaptation_plan(**kwargs: Any) -> Dict[str, Any]:
    adapter = ExpertModeAdapter()
    return adapter.build_adaptation_plan(**kwargs)