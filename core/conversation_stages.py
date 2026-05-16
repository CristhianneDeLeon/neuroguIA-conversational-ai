from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Optional


class ConversationStages:
    """
    Single owner of conversational progression.

    This layer decides:
    - stage
    - domain phase progression
    - clarification handling without losing domain continuity
    - crisis progression from containment to concrete guided steps
    """

    STAGE_CONFIGS = {
        "reception_containment": {
            "tone": "calm_containment",
            "length": "very_short",
            "max_questions": 0,
            "validation_weight": "high",
            "should_offer_microaction": True,
            "should_close_with_followup": False,
            "memory_mode": "low",
            "output_structure": "containment_first",
        },
        "focus_clarification": {
            "tone": "warm_clear",
            "length": "short",
            "max_questions": 1,
            "validation_weight": "medium",
            "should_offer_microaction": True,
            "should_close_with_followup": True,
            "memory_mode": "medium",
            "output_structure": "clarify_without_reset",
        },
        "functional_classification": {
            "tone": "warm_explanatory",
            "length": "short",
            "max_questions": 1,
            "validation_weight": "medium",
            "should_offer_microaction": False,
            "should_close_with_followup": True,
            "memory_mode": "medium",
            "output_structure": "explain_current_focus",
        },
        "adaptive_intervention": {
            "tone": "warm_practical",
            "length": "short",
            "max_questions": 1,
            "validation_weight": "medium",
            "should_offer_microaction": True,
            "should_close_with_followup": True,
            "memory_mode": "high",
            "output_structure": "guided_progression",
        },
        "closure_continuity": {
            "tone": "warm_structured",
            "length": "short",
            "max_questions": 1,
            "validation_weight": "medium",
            "should_offer_microaction": True,
            "should_close_with_followup": True,
            "memory_mode": "high",
            "output_structure": "summary_then_bridge",
        },
        "case_learning": {
            "tone": "warm_reflective",
            "length": "short",
            "max_questions": 1,
            "validation_weight": "medium",
            "should_offer_microaction": False,
            "should_close_with_followup": False,
            "memory_mode": "high",
            "output_structure": "reflective_feedback",
        },
    }

    PHASE_PATHS = {
        "crisis_activa": [
            "containment",
            "guided_steps",
            "check_response",
            "stabilize_safety",
        ],
        "escalada_emocional": [
            "early_intervention",
            "identify_earliest_shift",
            "lower_demand",
            "repeatable_response",
        ],
        "prevencion_escalada": [
            "mapping_signals",
            "pattern_detection",
            "prepare_early_response",
            "stabilize_plan",
        ],
        "regulacion_post_evento": [
            "repair",
            "brief_reflection",
            "repair_phrase",
            "next_time_bridge",
        ],
        "ansiedad_cognitiva": [
            "cognitive_unloading",
            "prioritize",
            "anti_overload_phrase",
            "next_step_commitment",
        ],
        "disfuncion_ejecutiva": [
            "micro_start",
            "reduce_friction",
            "start_ritual",
            "consolidate",
        ],
        "sobrecarga_sensorial": [
            "environment_adjustment",
            "identify_main_trigger",
            "reduce_one_stimulus",
            "stabilize_reference",
        ],
        "transicion_rigidez": [
            "anticipation",
            "make_transition_script",
            "first_transition_step",
            "stabilize_transition",
        ],
        "sueno_regulacion": [
            "sleep_scan",
            "wind_down",
            "reduce_activation",
            "protect_next_sleep_window",
        ],
        "sobrecarga_cuidador": [
            "relief",
            "single_priority",
            "release_one_load",
            "protect_capacity",
        ],
        "apoyo_general": [
            "clarification",
            "focus",
            "one_helpful_step",
        ],
    }

    LEGACY_CATEGORY_ALIASES = {
        "crisis_emocional": "crisis_activa",
        "saturacion_sensorial": "sobrecarga_sensorial",
        "bloqueo_ejecutivo": "disfuncion_ejecutiva",
        "sleep": "sueno_regulacion",
        "agotamiento_cuidador": "sobrecarga_cuidador",
        "sueno_descanso": "sueno_regulacion",
        "transicion": "transicion_rigidez",
    }

    CLARIFICATION_MARKERS = {
        "no entiendo",
        "no comprendo",
        "explicamelo",
        "explicame",
        "explicalo mas simple",
        "dilo mas simple",
        "me perdi",
        "aclarame",
    }

    FOLLOWUP_ACCEPTANCE_WORDS = {
        "si",
        "ok",
        "okay",
        "va",
        "aja",
        "ajá",
        "de",
        "acuerdo",
        "dale",
        "claro",
        "yes",
        "continua",
        "continua",
        "continuar",
        "continuemos",
        "sigue",
        "seguimos",
        "ayudame",
        "ayuda",
        "por",
        "favor",
        "guiame",
    }

    FOLLOWUP_REQUIRED_WORDS = {
        "si",
        "ok",
        "okay",
        "va",
        "dale",
        "yes",
        "continua",
        "continuar",
        "continuemos",
        "sigue",
        "seguimos",
        "ayudame",
        "ayuda",
        "guiame",
    }

    DOMAIN_SHIFT_KEYWORDS = {
        "crisis_activa": [
            "crisis",
            "gritando",
            "golpeando",
            "riesgo",
            "no la puedo calmar",
            "no lo puedo calmar",
        ],
        "sueno_regulacion": [
            "sueno",
            "dormir",
            "dormi",
            "no dormi",
            "desvelo",
            "insomnio",
            "no me deja dormir",
            "no ha dormido",
            "no duerme",
            "cansancio",
        ],
        "sobrecarga_cuidador": [
            "agotamiento",
            "agotada",
            "agotado",
            "cuidar",
            "cuidado",
            "mi hija",
            "mi hijo",
            "ya no puedo",
        ],
        "transicion_rigidez": [
            "cambio de plan",
            "cambios de plan",
            "cambio inesperado",
            "transicion",
            "transición",
            "rigido",
            "rigida",
        ],
    }

    STALL_MARKERS = {
        "no se",
        "no lo se",
        "no se como",
        "no se que hacer",
        "no tengo una idea clara",
        "no tengo ninguna",
        "no lo tengo claro",
        "no tengo claro",
        "que hago",
        "que hago ahora",
        "que hago ahorita",
        "por donde empiezo",
        "por donde comienzo",
        "pero que hago",
    }

    MORE_HELP_MARKERS = {
        "ya",
        "y luego",
        "que mas",
        "que sigue",
        "y ahora",
        "pero",
        "todavia no",
        "sigo igual",
        "eso no",
        "no funciona",
    }

    DIRECTNESS_MARKERS = {
        "que hago",
        "que hago ahora",
        "que hago ahorita",
        "pero que hago",
        "dime que hago",
        "dime que hago ahora",
        "no se como",
        "no lo se",
        "no tengo una idea clara",
        "no tengo ninguna",
        "por donde empiezo",
        "guiame",
    }

    POST_ACTION_MARKERS = {
        "ya y ahora que",
        "y ahora que",
        "ok que mas",
        "que mas",
        "pero despues que",
        "despues que",
        "despues que sigue",
        "y luego",
        "que sigue",
    }

    SPECIFIC_ACTION_MARKERS = {
        "que hago",
        "que hago ahora",
        "que hago ahorita",
        "por donde empiezo",
        "por donde comienzo",
        "con que empiezo",
        "como empiezo",
    }

    LITERAL_PHRASE_MARKERS = {
        "que le digo",
        "que puedo decirle",
        "que le digo ahora",
        "que le puedo decir",
    }

    VALIDATION_MARKERS = {
        "esto es normal",
        "es normal",
        "esta bien que",
        "esta mal que",
        "eso es normal",
        "es grave",
        "es demasiado",
        "es raro",
        "es esperable",
    }

    CLOSURE_MARKERS = {
        "ya estuvo",
        "por ahora ya",
        "por ahora paro",
        "lo dejo aqui",
        "aqui paro",
        "con eso basta",
        "por ahora basta",
        "ya no necesito mas",
        "despues sigo",
    }

    META_QUESTION_MARKERS = {
        "quien eres",
        "para que sirves",
        "como ayudas",
        "como funcionas",
        "como puedo llamarte",
        "como te llamo",
        "como quieres que te diga",
        "como puedo decirte",
        "que puedes hacer",
        "que no puedes hacer",
        "eres un bot",
        "eres una ia",
        "eres inteligencia artificial",
    }

    STRATEGY_REJECTION_MARKERS = {
        "eso no me sirve",
        "no otra cosa",
        "no otra via",
        "otra cosa",
        "no me ayuda",
        "eso no funciona",
        "no funciona eso",
        "eso no aplica",
        "no aplica eso",
        "esa no",
    }

    OUTCOME_NO_CHANGE_MARKERS = {
        "sigo igual",
        "no cambio nada",
        "no cambió nada",
        "no funciono",
        "no funcionó",
        "no noto cambio",
        "quedo igual",
    }

    OUTCOME_WORSE_MARKERS = {
        "empeoro",
        "empeoró",
        "se puso peor",
        "subio mas",
        "subió más",
        "me altero mas",
        "me alteró más",
        "se intensifico",
        "se intensificó",
    }

    OUTCOME_PARTIAL_RELIEF_MARKERS = {
        "ya bajo un poco",
        "bajo un poco",
        "bajó un poco",
        "funciono un poco",
        "funcionó un poco",
        "ayudo un poco",
        "ayudó un poco",
        "un poco mejor",
        "aflojo un poco",
        "aflojó un poco",
    }

    OUTCOME_IMPROVED_MARKERS = {
        "ya bajo",
        "ya bajó",
        "ya mejoro",
        "ya mejoró",
        "mejoro",
        "mejoró",
        "ya paso",
        "ya pasó",
        "ya funciono",
        "ya funcionó",
    }

    ACTIONABLE_RESPONSE_SHAPES = {
        "single_action",
        "guided_steps",
        "concrete_action",
        "guided_decision",
        "direct_instruction",
        "grounding",
        "sleep_settle",
        "load_relief",
        "literal_phrase",
        "check_effect",
        "hold_line",
        "strategy_switch",
    }

    TURN_FAMILIES = {
        "new_request",
        "meta_question",
        "followup_acceptance",
        "clarification_request",
        "strategy_rejection",
        "outcome_report",
        "blocked_followup",
        "specific_action_request",
        "literal_phrase_request",
        "post_action_followup",
        "simple_question",
        "validation_request",
        "context_shift",
        "closure_or_pause",
    }

    INTERVENTION_LADDERS = {
        "crisis_activa": {
            "containment": 1,
            "guided_steps": 3,
            "check_response": 4,
            "stabilize_safety": 5,
        },
        "ansiedad_cognitiva": {
            "cognitive_unloading": 1,
            "prioritize": 2,
            "anti_overload_phrase": 3,
            "next_step_commitment": 4,
        },
        "disfuncion_ejecutiva": {
            "micro_start": 1,
            "reduce_friction": 2,
            "start_ritual": 3,
            "consolidate": 4,
        },
        "sueno_regulacion": {
            "sleep_scan": 1,
            "wind_down": 2,
            "reduce_activation": 3,
            "protect_next_sleep_window": 4,
        },
        "sobrecarga_cuidador": {
            "relief": 1,
            "single_priority": 2,
            "release_one_load": 3,
            "protect_capacity": 4,
        },
        "sobrecarga_sensorial": {
            "environment_adjustment": 1,
            "identify_main_trigger": 2,
            "reduce_one_stimulus": 3,
            "stabilize_reference": 4,
        },
        "transicion_rigidez": {
            "anticipation": 1,
            "make_transition_script": 2,
            "first_transition_step": 3,
            "stabilize_transition": 4,
        },
        "prevencion_escalada": {
            "mapping_signals": 1,
            "pattern_detection": 2,
            "prepare_early_response": 3,
            "stabilize_plan": 4,
        },
        "regulacion_post_evento": {
            "repair": 1,
            "brief_reflection": 2,
            "repair_phrase": 3,
            "next_time_bridge": 4,
        },
        "escalada_emocional": {
            "early_intervention": 1,
            "identify_earliest_shift": 2,
            "lower_demand": 3,
            "repeatable_response": 4,
        },
        "apoyo_general": {
            "clarification": 1,
            "focus": 2,
            "one_helpful_step": 3,
        },
    }

    MAX_INTERVENTION_LEVEL = 5

    def resolve_conversation_control(
        self,
        message: str,
        previous_frame: Optional[Dict[str, Any]] = None,
        context_override: Optional[Dict[str, Any]] = None,
        state_analysis: Optional[Dict[str, Any]] = None,
        category_analysis: Optional[Dict[str, Any]] = None,
        intent_analysis: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        previous_frame = previous_frame or {}
        state_analysis = state_analysis or {}
        category_analysis = category_analysis or {}
        intent_analysis = intent_analysis or {}
        context_override = self._normalize_context_override(context_override, message)

        previous_domain = self._canonicalize_category(previous_frame.get("conversation_domain"))
        previous_phase = previous_frame.get("conversation_phase")
        detected_category = self._canonicalize_category(category_analysis.get("detected_category"))
        category_confidence = float(category_analysis.get("confidence", 0.0) or 0.0)
        clarification_mode = self._detect_clarification_mode(message=message, intent_analysis=intent_analysis)
        domain_shift = self._detect_domain_shift(
            message=message,
            previous_frame=previous_frame,
            context_override=context_override,
            category_analysis=category_analysis,
            clarification_mode=clarification_mode,
        )
        progression_signals = self._detect_progression_signals(
            message=message,
            previous_frame=previous_frame,
            context_override=context_override,
            clarification_mode=clarification_mode,
            domain_shift=domain_shift,
            intent_analysis=intent_analysis,
        )
        turn_family = self._resolve_turn_family(
            message=message,
            previous_frame=previous_frame,
            context_override=context_override,
            intent_analysis=intent_analysis,
            clarification_mode=clarification_mode,
            domain_shift=domain_shift,
            progression_signals=progression_signals,
        )
        turn_type = self._resolve_turn_type(
            turn_family=turn_family,
            previous_frame=previous_frame,
        )
        domain = self._resolve_conversation_domain(
            previous_domain=previous_domain,
            detected_category=detected_category,
            category_confidence=category_confidence,
            turn_type=turn_type,
            turn_family=turn_family,
            clarification_mode=clarification_mode,
            context_override=context_override,
            domain_shift=domain_shift,
        )
        crisis_guided_mode = self._resolve_crisis_guided_mode(
            message=message,
            domain=domain,
            previous_domain=previous_domain,
            turn_type=turn_type,
        )
        intervention_level = self._resolve_intervention_level(
            domain=domain,
            previous_frame=previous_frame,
            turn_type=turn_type,
            turn_family=turn_family,
            clarification_mode=clarification_mode,
            context_override=context_override,
            crisis_guided_mode=crisis_guided_mode,
            progression_signals=progression_signals,
        )

        return {
            "turn_type": turn_type,
            "turn_family": turn_family,
            "domain": domain,
            "phase": previous_phase if domain == previous_domain else None,
            "clarification_mode": clarification_mode,
            "context_override": context_override,
            "domain_shift": domain_shift,
            "crisis_guided_mode": crisis_guided_mode,
            "last_guided_action": previous_frame.get("last_guided_action"),
            "previous_domain": previous_domain,
            "previous_phase": previous_phase,
            "source_message": message,
            "effective_message": message,
            "is_followup_acceptance": self._is_followup_acceptance(message),
            "previous_turn_family": previous_frame.get("turn_family"),
            "intervention_level": intervention_level,
            "previous_intervention_level": int(previous_frame.get("intervention_level", 0) or 0),
            "stuck_followup_count": progression_signals.get("stuck_followup_count", 0),
            "progression_signals": progression_signals,
            "previous_strategy_signature": previous_frame.get("last_strategy_signature"),
            "previous_response_shape": previous_frame.get("last_response_shape"),
            "previous_form_variant": previous_frame.get("response_form_variant"),
            "strategy_repeat_count": int(previous_frame.get("strategy_repeat_count", 0) or 0),
            "recent_strategy_history": list(previous_frame.get("recent_strategy_history") or []),
            "current_primary_state": state_analysis.get("primary_state"),
            "current_intent": intent_analysis.get("detected_intent"),
        }

    def determine_stage(
        self,
        message: str,
        state_analysis: Optional[Dict[str, Any]] = None,
        category_analysis: Optional[Dict[str, Any]] = None,
        intent_analysis: Optional[Dict[str, Any]] = None,
        case_context: Optional[Dict[str, Any]] = None,
        memory_summary: Optional[Dict[str, Any]] = None,
        memory_payload: Optional[Dict[str, Any]] = None,
        response_memory_payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        state_analysis = state_analysis or {}
        intent_analysis = intent_analysis or {}
        case_context = case_context or {}

        primary_state = state_analysis.get("primary_state")
        detected_intent = intent_analysis.get("detected_intent")
        conversation_control = case_context.get("conversation_control", {}) or {}

        domain = conversation_control.get("domain") or case_context.get("conversation_domain") or "apoyo_general"
        previous_domain = conversation_control.get("previous_domain")
        previous_phase = conversation_control.get("previous_phase")
        turn_type = conversation_control.get("turn_type") or "new_request"
        turn_family = conversation_control.get("turn_family") or "new_request"
        clarification_mode = conversation_control.get("clarification_mode") or "none"
        context_override = self._normalize_context_override(
            conversation_control.get("context_override"),
            conversation_control.get("effective_message") or message,
        )
        crisis_guided_mode = conversation_control.get("crisis_guided_mode") or "none"
        domain_shift = conversation_control.get("domain_shift", {}) or {}
        last_guided_action = conversation_control.get("last_guided_action")
        intervention_level = int(conversation_control.get("intervention_level", 0) or 0)
        progression_signals = conversation_control.get("progression_signals", {}) or {}
        stuck_followup_count = int(conversation_control.get("stuck_followup_count", 0) or 0)

        phase, phase_reason, phase_changed = self._resolve_phase(
            domain=domain,
            previous_domain=previous_domain,
            previous_phase=previous_phase,
            turn_type=turn_type,
            turn_family=turn_family,
            clarification_mode=clarification_mode,
            context_override=context_override,
            crisis_guided_mode=crisis_guided_mode,
            domain_shift=domain_shift,
            intervention_level=intervention_level,
        )

        stage = self._resolve_stage(
            domain=domain,
            phase=phase,
            turn_type=turn_type,
            turn_family=turn_family,
            clarification_mode=clarification_mode,
            detected_intent=detected_intent,
            primary_state=primary_state,
        )

        should_close_with_followup = bool(
            self.STAGE_CONFIGS[stage].get("should_close_with_followup", False)
        )
        if domain == "crisis_activa" and phase in {"containment", "guided_steps"}:
            should_close_with_followup = False
        if clarification_mode != "none":
            should_close_with_followup = False
        if context_override.get("active"):
            should_close_with_followup = False
        if turn_type in {"followup_acceptance", "followup_request"} and domain != "apoyo_general":
            should_close_with_followup = False
        if turn_family in {
            "meta_question",
            "strategy_rejection",
            "outcome_report",
            "blocked_followup",
            "specific_action_request",
            "literal_phrase_request",
            "post_action_followup",
            "simple_question",
            "validation_request",
            "closure_or_pause",
        }:
            should_close_with_followup = False
        if detected_intent == "urgent_support":
            should_close_with_followup = False
        if intervention_level >= 3 or progression_signals.get("needs_direct_instruction"):
            should_close_with_followup = False
        if stuck_followup_count >= 1:
            should_close_with_followup = False

        return {
            "stage": stage,
            "reason": self._build_reason(
                stage=stage,
                domain=domain,
                phase=phase,
                turn_type=turn_type,
                clarification_mode=clarification_mode,
                phase_reason=phase_reason,
            ),
            "config": self.STAGE_CONFIGS[stage],
            "should_close_with_followup": should_close_with_followup,
            "conversation_domain": domain,
            "conversation_phase": phase,
            "continuity_phase": phase,
            "phase_changed": phase_changed,
            "phase_progression_reason": phase_reason,
            "turn_type": turn_type,
            "turn_family": turn_family,
            "clarification_mode": clarification_mode,
            "context_override": context_override,
            "crisis_guided_mode": crisis_guided_mode,
            "domain_shift": domain_shift,
            "last_guided_action": last_guided_action,
            "intervention_level": intervention_level,
            "stuck_followup_count": stuck_followup_count,
            "progression_signals": progression_signals,
        }

    def _detect_clarification_mode(
        self,
        message: str,
        intent_analysis: Dict[str, Any],
    ) -> str:
        normalized = self._normalize_followup_text(message)
        if intent_analysis.get("detected_intent") == "clarification_request":
            return "simplify_last_guidance"
        if normalized in {self._normalize_followup_text(item) for item in self.CLARIFICATION_MARKERS}:
            return "simplify_last_guidance"
        if any(self._text_contains_keyword(normalized, self._normalize_followup_text(item)) for item in self.CLARIFICATION_MARKERS):
            return "simplify_last_guidance"
        return "none"

    def _resolve_turn_family(
        self,
        message: str,
        previous_frame: Dict[str, Any],
        context_override: Dict[str, Any],
        intent_analysis: Dict[str, Any],
        clarification_mode: str,
        domain_shift: Dict[str, Any],
        progression_signals: Dict[str, Any],
    ) -> str:
        if clarification_mode != "none":
            return "clarification_request"
        if progression_signals.get("is_meta_question") or intent_analysis.get("detected_intent") == "about_system":
            return "meta_question"
        if domain_shift.get("detected"):
            return "context_shift"

        detected_intent = intent_analysis.get("detected_intent")
        has_previous_domain = bool(previous_frame.get("conversation_domain"))
        normalized = self._normalize_followup_text(message)

        if has_previous_domain and progression_signals.get("asks_closure_or_pause"):
            return "closure_or_pause"
        if has_previous_domain and (
            progression_signals.get("strategy_rejection")
            or context_override.get("reason") == "explicit_invalidation"
        ):
            return "strategy_rejection"
        if has_previous_domain and progression_signals.get("outcome_status"):
            return "outcome_report"
        if has_previous_domain and context_override.get("active") and context_override.get("reason") == "explicit_action_completed":
            return "post_action_followup"
        if has_previous_domain and context_override.get("active") and context_override.get("type") == "override_hard":
            if progression_signals.get("asks_specific_action"):
                return "specific_action_request"
            return "blocked_followup"
        if progression_signals.get("asks_specific_action"):
            return "specific_action_request"
        if progression_signals.get("asks_literal_phrase"):
            return "literal_phrase_request"
        if has_previous_domain and progression_signals.get("asks_post_action_followup"):
            return "post_action_followup"
        if progression_signals.get("asks_validation"):
            return "validation_request"
        if has_previous_domain and progression_signals.get("persistent_block"):
            return "blocked_followup"
        if progression_signals.get("is_simple_question"):
            return "simple_question"
        if self._is_followup_acceptance(message) and has_previous_domain:
            return "followup_acceptance"
        if detected_intent in {"followup", "strategy_feedback"} and has_previous_domain:
            return "blocked_followup" if progression_signals.get("wants_progression") else "followup_acceptance"
        if detected_intent in {"general_support", "routine_request", "urgent_support"} and has_previous_domain and len(normalized.split()) <= 5:
            return "blocked_followup"
        return "new_request"

    def _resolve_turn_type(
        self,
        turn_family: str,
        previous_frame: Dict[str, Any],
    ) -> str:
        if turn_family == "clarification_request":
            return "clarification"
        if turn_family == "meta_question":
            return "system_meta"
        if turn_family == "context_shift":
            return "domain_shift"
        if turn_family == "followup_acceptance":
            return "followup_acceptance"
        if turn_family in {
            "strategy_rejection",
            "outcome_report",
            "blocked_followup",
            "specific_action_request",
            "literal_phrase_request",
            "post_action_followup",
            "validation_request",
        }:
            return "followup_request" if previous_frame.get("conversation_domain") else "new_request"
        if turn_family == "closure_or_pause":
            return "closure"
        if turn_family == "simple_question":
            return "continuation" if previous_frame.get("conversation_domain") else "new_request"
        return "new_request"

    def _resolve_conversation_domain(
        self,
        previous_domain: Optional[str],
        detected_category: Optional[str],
        category_confidence: float,
        turn_type: str,
        turn_family: str,
        clarification_mode: str,
        context_override: Dict[str, Any],
        domain_shift: Dict[str, Any],
    ) -> str:
        if domain_shift.get("detected"):
            shifted = self._canonicalize_category(domain_shift.get("shift_domain"))
            return shifted or detected_category or previous_domain or "apoyo_general"
        if turn_family == "meta_question" and previous_domain:
            return previous_domain
        if clarification_mode != "none" and previous_domain:
            return previous_domain
        if context_override.get("active"):
            if (
                detected_category
                and detected_category not in {None, "", previous_domain, "apoyo_general"}
                and category_confidence >= (0.5 if context_override.get("type") == "override_contextual" else 0.58)
            ):
                return detected_category
            if previous_domain:
                return previous_domain
        if turn_type in {"followup_acceptance", "followup_request", "continuation", "closure"} and previous_domain:
            if detected_category in {None, "", previous_domain, "apoyo_general"} or category_confidence < 0.72:
                return previous_domain
        return detected_category or previous_domain or "apoyo_general"

    def _resolve_crisis_guided_mode(
        self,
        message: str,
        domain: str,
        previous_domain: Optional[str],
        turn_type: str,
    ) -> str:
        normalized = self._normalize_followup_text(message)
        guidance_acceptance_markers = {
            "si",
            "ok",
            "dale",
            "ayudame",
            "ayudame por favor",
            "que hago",
            "que hago ahora",
            "guiame",
            "sigue",
        }
        if domain != "crisis_activa":
            return "none"
        if previous_domain == "crisis_activa" and (
            turn_type in {"followup_acceptance", "followup_request", "continuation"}
            or normalized in guidance_acceptance_markers
            or any(self._text_contains_keyword(normalized, marker) for marker in guidance_acceptance_markers)
        ):
            return "guided_steps"
        return "none"

    def _detect_domain_shift(
        self,
        message: str,
        previous_frame: Dict[str, Any],
        context_override: Dict[str, Any],
        category_analysis: Optional[Dict[str, Any]] = None,
        clarification_mode: str = "none",
    ) -> Dict[str, Any]:
        previous_domain = self._canonicalize_category(previous_frame.get("conversation_domain"))
        normalized_message = self._normalize_followup_text(message)
        category_analysis = category_analysis or {}
        detected_category = self._canonicalize_category(category_analysis.get("detected_category"))
        category_confidence = float(category_analysis.get("confidence", 0.0) or 0.0)

        result = {
            "detected": False,
            "shift_domain": None,
            "previous_domain": previous_domain,
            "matched_keywords": [],
            "reason": None,
        }

        if not previous_domain or not normalized_message:
            return result

        if clarification_mode != "none":
            result["reason"] = "clarification_keeps_domain"
            return result

        words = normalized_message.split()
        if self._is_followup_acceptance(message) or (len(words) <= 3 and not context_override.get("active")):
            result["reason"] = "short_or_followup_continuity"
            return result

        if (
            context_override.get("active")
            and detected_category
            and detected_category not in {previous_domain, "apoyo_general"}
            and category_confidence >= (0.5 if context_override.get("type") == "override_contextual" else 0.58)
        ):
            result.update(
                {
                    "detected": True,
                    "shift_domain": detected_category,
                    "matched_keywords": ["context_override_category_shift"],
                    "reason": "context_override_category_change",
                }
            )
            return result

        if detected_category and detected_category not in {previous_domain, "apoyo_general"} and category_confidence >= 0.58:
            result.update(
                {
                    "detected": True,
                    "shift_domain": detected_category,
                    "matched_keywords": ["category_shift"],
                    "reason": "category_change_with_confidence",
                }
            )
            return result

        for domain, keywords in self.DOMAIN_SHIFT_KEYWORDS.items():
            canonical_domain = self._canonicalize_category(domain)
            if canonical_domain == previous_domain:
                continue
            matches = [
                keyword
                for keyword in keywords
                if self._text_contains_keyword(normalized_message, self._normalize_followup_text(keyword))
            ]
            if matches:
                result.update(
                    {
                        "detected": True,
                        "shift_domain": canonical_domain,
                        "matched_keywords": matches,
                        "reason": "new_domain_keywords",
                    }
                )
                return result

        return result

    def _resolve_phase(
        self,
        domain: str,
        previous_domain: Optional[str],
        previous_phase: Optional[str],
        turn_type: str,
        turn_family: str,
        clarification_mode: str,
        context_override: Dict[str, Any],
        crisis_guided_mode: str,
        domain_shift: Dict[str, Any],
        intervention_level: int,
    ) -> tuple[str, str, bool]:
        path = list(self.PHASE_PATHS.get(domain, self.PHASE_PATHS["apoyo_general"]))
        default_phase = path[0]

        if clarification_mode != "none":
            return (
                previous_phase or default_phase,
                "clarification_keeps_current_phase",
                False,
            )

        if turn_family == "meta_question" and previous_domain == domain and previous_phase:
            return previous_phase, "meta_question_keeps_current_phase", False

        if context_override.get("active") and previous_domain == domain and previous_phase:
            if context_override.get("type") == "override_hard":
                return previous_phase, f"context_override_{context_override.get('reason')}", False
            return previous_phase, f"context_override_{context_override.get('reason')}", False

        if turn_family in {"strategy_rejection", "outcome_report"} and previous_domain == domain and previous_phase:
            return previous_phase, f"{turn_family}_keeps_current_phase", False

        if domain_shift.get("detected") or (
            previous_domain and domain != previous_domain and turn_type == "domain_shift"
        ):
            target_phase = self._phase_for_level(domain, intervention_level, default_phase)
            return target_phase, "domain_shift_resets_phase", True

        if domain == "crisis_activa" and crisis_guided_mode == "guided_steps":
            if turn_family in {"followup_acceptance", "specific_action_request", "literal_phrase_request", "blocked_followup"}:
                target_phase = "guided_steps"
            else:
                target_phase = self._phase_for_level(domain, max(intervention_level, 3), "guided_steps")
            return target_phase, "crisis_acceptance_moves_to_guided_steps", previous_phase != target_phase

        if not previous_phase or previous_domain != domain:
            target_phase = self._phase_for_level(domain, intervention_level, default_phase)
            reason = "new_domain_initial_phase" if target_phase == default_phase else "new_domain_escalated_entry"
            return target_phase, reason, True

        if turn_type in {"followup_acceptance", "followup_request", "continuation"}:
            sequential_phase = self._next_phase(path=path, current_phase=previous_phase)
            escalated_phase = self._phase_for_level(domain, intervention_level, sequential_phase)
            next_phase = self._furthest_phase(path, sequential_phase, escalated_phase)
            reason = "followup_progression" if next_phase == sequential_phase else "followup_escalation"
            return next_phase, reason, next_phase != previous_phase

        escalated_phase = self._phase_for_level(domain, intervention_level, previous_phase)
        if escalated_phase != previous_phase:
            return escalated_phase, "escalation_without_domain_change", True
        return previous_phase, "maintain_phase", False

    def _next_phase(self, path: List[str], current_phase: str) -> str:
        if current_phase not in path:
            return path[0]
        index = path.index(current_phase)
        return path[min(index + 1, len(path) - 1)]

    def _phase_for_level(self, domain: str, target_level: int, fallback_phase: str) -> str:
        ladder = self.INTERVENTION_LADDERS.get(domain, {})
        if not ladder:
            return fallback_phase
        ordered = sorted(ladder.items(), key=lambda item: item[1])
        selected_phase = ordered[0][0]
        for phase, level in ordered:
            if level <= max(target_level, 1):
                selected_phase = phase
        return selected_phase or fallback_phase

    def _phase_level(self, domain: str, phase: Optional[str]) -> int:
        if not phase:
            return 1
        ladder = self.INTERVENTION_LADDERS.get(domain, {})
        return int(ladder.get(phase, 1) or 1)

    def _furthest_phase(self, path: List[str], phase_a: str, phase_b: str) -> str:
        if phase_a not in path:
            return phase_b
        if phase_b not in path:
            return phase_a
        return phase_a if path.index(phase_a) >= path.index(phase_b) else phase_b

    def _resolve_intervention_level(
        self,
        domain: str,
        previous_frame: Dict[str, Any],
        turn_type: str,
        turn_family: str,
        clarification_mode: str,
        context_override: Dict[str, Any],
        crisis_guided_mode: str,
        progression_signals: Dict[str, Any],
    ) -> int:
        previous_domain = self._canonicalize_category(previous_frame.get("conversation_domain"))
        previous_phase = previous_frame.get("conversation_phase")
        previous_level = int(previous_frame.get("intervention_level", 0) or 0)
        if previous_level <= 0:
            previous_level = self._phase_level(previous_domain or domain, previous_phase)

        if clarification_mode != "none":
            return max(previous_level, 1)

        if context_override.get("active"):
            if previous_domain != domain and domain:
                return 1
            override_reason = str(context_override.get("reason") or "")
            if context_override.get("type") == "override_contextual":
                return max(1, min(previous_level or 1, self.MAX_INTERVENTION_LEVEL))
            if override_reason == "explicit_action_completed":
                return max(1, min(max(previous_level, 2), self.MAX_INTERVENTION_LEVEL))
            if override_reason == "explicit_impossibility":
                if domain == "crisis_activa":
                    return max(2, min(previous_level, 3))
                return max(1, min(previous_level, 2))
            if override_reason == "explicit_invalidation" or override_reason.startswith("explicit_contradiction"):
                if domain == "crisis_activa":
                    return max(2, min(previous_level, 4))
                return max(2, min(previous_level or 2, self.MAX_INTERVENTION_LEVEL))

        if turn_family in {"meta_question", "simple_question", "validation_request", "closure_or_pause"}:
            return max(1, min(previous_level or 1, self.MAX_INTERVENTION_LEVEL))

        if turn_family == "strategy_rejection":
            if domain == "crisis_activa":
                return max(3, min(previous_level or 3, 4))
            return max(2, min(previous_level or 2, self.MAX_INTERVENTION_LEVEL))

        if turn_family == "outcome_report":
            outcome_status = str(progression_signals.get("outcome_status") or "")
            if outcome_status == "worse":
                if domain == "crisis_activa":
                    return max(2, min(previous_level or 2, 3))
                return max(1, min(previous_level or 1, 2))
            if outcome_status == "no_change":
                return max(2, min(max(previous_level, 2), self.MAX_INTERVENTION_LEVEL))
            if outcome_status in {"partial_relief", "improved"}:
                return max(1, min(previous_level or 1, self.MAX_INTERVENTION_LEVEL))

        if previous_domain != domain:
            target_level = 1
        else:
            target_level = max(previous_level, self._phase_level(domain, previous_phase))

        same_domain_followup = bool(progression_signals.get("same_domain_followup"))

        if turn_type in {"followup_acceptance", "followup_request", "continuation"} and previous_domain == domain:
            target_level = min(target_level + 1, self.MAX_INTERVENTION_LEVEL)

        if turn_family == "post_action_followup" and previous_domain == domain:
            target_level = max(target_level, min(max(previous_level, 2), self.MAX_INTERVENTION_LEVEL))

        if same_domain_followup and progression_signals.get("wants_progression"):
            target_level = min(target_level + 1, self.MAX_INTERVENTION_LEVEL)
        if same_domain_followup and progression_signals.get("persistent_block"):
            target_level = min(target_level + 1, self.MAX_INTERVENTION_LEVEL)
        if same_domain_followup and progression_signals.get("avoid_strategy_loop"):
            target_level = min(max(target_level, previous_level + 1), self.MAX_INTERVENTION_LEVEL)

        stuck_followup_count = int(progression_signals.get("stuck_followup_count", 0) or 0)
        if domain == "crisis_activa":
            if crisis_guided_mode == "guided_steps":
                target_level = max(target_level, 3)
            if same_domain_followup and progression_signals.get("needs_direct_instruction"):
                target_level = max(target_level, 4)
            if stuck_followup_count >= 2:
                target_level = max(target_level, 5)
        elif domain == "ansiedad_cognitiva":
            if stuck_followup_count >= 1:
                target_level = max(target_level, 3)
            if same_domain_followup and progression_signals.get("needs_direct_instruction"):
                target_level = max(target_level, 4)
            if stuck_followup_count >= 2:
                target_level = max(target_level, 5)
        elif domain == "disfuncion_ejecutiva":
            if stuck_followup_count >= 1:
                target_level = max(target_level, 3)
            if same_domain_followup and progression_signals.get("needs_direct_instruction"):
                target_level = max(target_level, 4)
            if stuck_followup_count >= 2:
                target_level = max(target_level, 5)
        else:
            if stuck_followup_count >= 1:
                target_level = max(target_level, 2)
            if same_domain_followup and progression_signals.get("needs_direct_instruction"):
                target_level = max(target_level, 3)

        return max(1, min(target_level, self.MAX_INTERVENTION_LEVEL))

    def _detect_progression_signals(
        self,
        message: str,
        previous_frame: Dict[str, Any],
        context_override: Dict[str, Any],
        clarification_mode: str,
        domain_shift: Dict[str, Any],
        intent_analysis: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        normalized = self._normalize_followup_text(message)
        previous_message = previous_frame.get("source_message") or previous_frame.get("effective_message") or ""
        previous_normalized = self._normalize_followup_text(previous_message)
        has_previous_domain = bool(previous_frame.get("conversation_domain"))
        same_request_repeated = bool(
            normalized
            and previous_normalized
            and (
                normalized == previous_normalized
                or (len(normalized.split()) >= 2 and normalized in previous_normalized)
                or (len(previous_normalized.split()) >= 2 and previous_normalized in normalized)
            )
        )
        asks_for_guidance = any(self._text_contains_keyword(normalized, marker) for marker in self.STALL_MARKERS)
        asks_for_more = any(self._text_contains_keyword(normalized, marker) for marker in self.MORE_HELP_MARKERS)
        pushes_back = any(self._text_contains_keyword(normalized, marker) for marker in {"pero", "todavia no", "sigo igual", "no funciona", "eso no"})
        needs_direct_instruction = any(self._text_contains_keyword(normalized, marker) for marker in self.DIRECTNESS_MARKERS)
        asks_post_action_followup = any(self._text_contains_keyword(normalized, marker) for marker in self.POST_ACTION_MARKERS)
        asks_specific_action = any(self._text_contains_keyword(normalized, marker) for marker in self.SPECIFIC_ACTION_MARKERS)
        asks_literal_phrase = any(self._text_contains_keyword(normalized, marker) for marker in self.LITERAL_PHRASE_MARKERS)
        asks_validation = any(self._text_contains_keyword(normalized, marker) for marker in self.VALIDATION_MARKERS)
        asks_closure_or_pause = any(self._text_contains_keyword(normalized, marker) for marker in self.CLOSURE_MARKERS)
        previous_response_shape = str(previous_frame.get("last_response_shape") or "")
        previous_response_actionable = previous_response_shape in self.ACTIONABLE_RESPONSE_SHAPES
        strategy_rejection = self._detect_strategy_rejection(
            normalized=normalized,
            has_previous_domain=has_previous_domain,
            previous_response_actionable=previous_response_actionable,
            context_override=context_override,
        )
        outcome_status = self._detect_outcome_status(
            normalized=normalized,
            has_previous_domain=has_previous_domain,
            previous_response_actionable=previous_response_actionable,
        )
        is_meta_question = self._looks_like_meta_question(
            message=message,
            normalized=normalized,
            intent_analysis=intent_analysis or {},
        )
        if strategy_rejection:
            outcome_status = None
        if asks_post_action_followup and not previous_response_actionable:
            asks_post_action_followup = False
        if context_override.get("active") and context_override.get("reason") == "explicit_action_completed" and previous_response_actionable:
            asks_post_action_followup = True
        if outcome_status and previous_response_actionable:
            asks_post_action_followup = True

        same_domain_followup = (
            has_previous_domain
            and clarification_mode == "none"
            and not domain_shift.get("detected")
        )
        previous_stuck_followup_count = int(previous_frame.get("stuck_followup_count", 0) or 0)
        previous_strategy_repeat_count = int(previous_frame.get("strategy_repeat_count", 0) or 0)
        recent_strategy_history = [
            item
            for item in list(previous_frame.get("recent_strategy_history") or [])
            if isinstance(item, dict)
        ]
        override_active = bool(context_override.get("active"))
        if normalized == "ya" and previous_response_actionable:
            asks_post_action_followup = True
        stuck_now = same_domain_followup and not override_active and (
            asks_for_guidance or asks_for_more or pushes_back or same_request_repeated
        )
        stuck_followup_count = previous_stuck_followup_count + 1 if stuck_now else 0
        persistent_block = stuck_followup_count >= 2 or (stuck_now and previous_strategy_repeat_count >= 1)
        wants_progression = asks_for_guidance or asks_for_more or pushes_back or same_request_repeated or bool(outcome_status)
        repeated_post_action_followup = (
            asks_post_action_followup
            and sum(
                1
                for entry in recent_strategy_history[-4:]
                if str(entry.get("response_goal") or "") in {
                    "check_effect_after_step",
                    "give_next_distinct_step",
                    "decide_stop_or_continue",
                    "hold_without_adding_demand",
                    "close_after_action",
                    "change_modality_after_no_effect",
                    "replace_rejected_strategy",
                }
                or str(entry.get("response_shape") or "") in {
                    "check_effect",
                    "hold_line",
                    "closure_pause",
                    "guided_decision",
                    "strategy_switch",
                    "concrete_action",
                    "single_action",
                }
            ) >= 2
        )
        is_simple_question = self._looks_like_simple_question(
            message=message,
            normalized=normalized,
            asks_specific_action=asks_specific_action,
            asks_literal_phrase=asks_literal_phrase,
            asks_validation=asks_validation,
            asks_post_action_followup=asks_post_action_followup,
            asks_closure_or_pause=asks_closure_or_pause,
            persistent_block=persistent_block,
            is_meta_question=is_meta_question,
            strategy_rejection=strategy_rejection,
            outcome_status=outcome_status,
        )

        return {
            "asks_for_guidance": asks_for_guidance,
            "asks_for_more": asks_for_more,
            "pushes_back": pushes_back,
            "strategy_rejection": strategy_rejection,
            "outcome_status": outcome_status,
            "asks_post_action_followup": asks_post_action_followup,
            "asks_specific_action": asks_specific_action,
            "asks_literal_phrase": asks_literal_phrase,
            "asks_validation": asks_validation,
            "asks_closure_or_pause": asks_closure_or_pause,
            "is_simple_question": is_simple_question,
            "is_meta_question": is_meta_question,
            "override_active": override_active,
            "override_type": context_override.get("type"),
            "override_reason": context_override.get("reason"),
            "override_target": context_override.get("target"),
            "override_confidence": float(context_override.get("confidence", 0.0) or 0.0),
            "repeats_request": same_request_repeated,
            "same_domain_followup": same_domain_followup,
            "repeated_post_action_followup": repeated_post_action_followup,
            "stuck_followup_count": stuck_followup_count,
            "persistent_block": persistent_block,
            "needs_direct_instruction": needs_direct_instruction,
            "wants_progression": wants_progression,
            "avoid_strategy_loop": same_domain_followup and previous_strategy_repeat_count >= 1,
            "previous_response_actionable": previous_response_actionable,
        }

    def _resolve_stage(
        self,
        domain: str,
        phase: str,
        turn_type: str,
        turn_family: str,
        clarification_mode: str,
        detected_intent: Optional[str],
        primary_state: Optional[str],
    ) -> str:
        if clarification_mode != "none" or detected_intent == "clarification_request":
            return "focus_clarification"

        if turn_family in {"meta_question", "simple_question", "validation_request"}:
            return "functional_classification"

        if detected_intent == "profile_question":
            return "functional_classification"

        if domain == "crisis_activa":
            if phase == "containment" or primary_state in {"meltdown", "shutdown"}:
                return "reception_containment"
            return "adaptive_intervention"

        if turn_type == "reflection_feedback":
            return "case_learning"

        if turn_type == "closure":
            return "closure_continuity"

        return "adaptive_intervention"

    def _build_reason(
        self,
        stage: str,
        domain: str,
        phase: str,
        turn_type: str,
        clarification_mode: str,
        phase_reason: str,
    ) -> str:
        parts = [stage, domain, phase, turn_type, phase_reason]
        if clarification_mode != "none":
            parts.append(clarification_mode)
        return "_".join([part for part in parts if part])

    def _canonicalize_category(self, category: Optional[str]) -> Optional[str]:
        if not category:
            return category
        return self.LEGACY_CATEGORY_ALIASES.get(category, category)

    def _normalize(self, text: Optional[str]) -> str:
        return " ".join((text or "").strip().lower().split())

    def _normalize_followup_text(self, text: str) -> str:
        normalized = self._normalize(text)
        normalized = unicodedata.normalize("NFKD", normalized)
        normalized = "".join(char for char in normalized if not unicodedata.combining(char))
        normalized = re.sub(r"[^a-z0-9\\s]", " ", normalized)
        return " ".join(normalized.split())

    def _text_contains_keyword(self, text: str, keyword: str) -> bool:
        text = self._normalize_followup_text(text)
        keyword = self._normalize_followup_text(keyword)
        if not text or not keyword:
            return False
        if " " in keyword:
            return keyword in text
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])", text))

    def _is_followup_acceptance(self, message: str) -> bool:
        normalized = self._normalize_followup_text(message)
        if not normalized:
            return False
        words = normalized.split()
        if not words:
            return False
        if not set(words).intersection(self.FOLLOWUP_REQUIRED_WORDS):
            return False
        return all(word in self.FOLLOWUP_ACCEPTANCE_WORDS for word in words)

    def get_next_stage(
        self,
        current_stage: str,
        response_applied: bool = False,
        user_feedback_present: bool = False,
        followup_needed: bool = False,
    ) -> str:
        if current_stage == "reception_containment":
            return "adaptive_intervention"
        if current_stage == "focus_clarification":
            return "adaptive_intervention"
        if current_stage == "functional_classification":
            return "adaptive_intervention"
        if current_stage == "adaptive_intervention" and followup_needed:
            return "closure_continuity"
        if current_stage == "closure_continuity" and user_feedback_present:
            return "case_learning"
        if current_stage == "adaptive_intervention" and response_applied:
            return "closure_continuity"
        return "adaptive_intervention"

    def build_stage_prompt_hints(self, stage_result: Dict[str, Any]) -> Dict[str, Any]:
        stage = stage_result["stage"]
        config = stage_result["config"]

        return {
            "stage": stage,
            "opening_style": self._get_opening_style(stage),
            "body_style": self._get_body_style(stage, config),
            "closing_style": self._get_closing_style(stage),
            "max_questions": config.get("max_questions", 1),
            "must_include_validation": config.get("validation_weight") in {"high", "medium"},
            "must_include_microaction": config.get("should_offer_microaction", False),
            "must_include_followup_bridge": stage_result.get("should_close_with_followup", False),
            "memory_mode": config.get("memory_mode"),
            "continuity_phase": stage_result.get("conversation_phase"),
            "turn_type": stage_result.get("turn_type"),
            "turn_family": stage_result.get("turn_family"),
            "context_override": stage_result.get("context_override"),
            "clarification_mode": stage_result.get("clarification_mode"),
            "crisis_guided_mode": stage_result.get("crisis_guided_mode"),
            "phase_changed": stage_result.get("phase_changed", False),
            "intervention_level": stage_result.get("intervention_level"),
            "stuck_followup_count": stage_result.get("stuck_followup_count"),
        }

    def _normalize_context_override(
        self,
        context_override: Optional[Dict[str, Any]],
        message: str,
    ) -> Dict[str, Any]:
        normalized = dict(context_override or {})
        effective_message = normalized.get("effective_message") or message
        return {
            "active": bool(normalized.get("active", False)),
            "type": normalized.get("type"),
            "reason": normalized.get("reason"),
            "confidence": float(normalized.get("confidence", 0.0) or 0.0),
            "target": normalized.get("target"),
            "source_message": normalized.get("source_message") or message,
            "effective_message": effective_message,
        }

    def _looks_like_simple_question(
        self,
        message: str,
        normalized: str,
        asks_specific_action: bool,
        asks_literal_phrase: bool,
        asks_validation: bool,
        asks_post_action_followup: bool,
        asks_closure_or_pause: bool,
        persistent_block: bool,
        is_meta_question: bool,
        strategy_rejection: bool,
        outcome_status: Optional[str],
    ) -> bool:
        if asks_specific_action or asks_literal_phrase or asks_validation or asks_post_action_followup or asks_closure_or_pause:
            return False
        if is_meta_question or strategy_rejection or outcome_status:
            return False
        if persistent_block:
            return False
        question_starts = {
            "que",
            "como",
            "cuando",
            "donde",
            "por que",
            "porque",
            "puedo",
            "debo",
            "conviene",
            "esto",
            "es",
        }
        if not normalized:
            return False
        starts_like_question = any(
            normalized.startswith(prefix + " ") or normalized == prefix
            for prefix in question_starts
        )
        if "?" in (message or ""):
            return starts_like_question or len(normalized.split()) <= 6
        return starts_like_question

    def _looks_like_meta_question(
        self,
        message: str,
        normalized: str,
        intent_analysis: Dict[str, Any],
    ) -> bool:
        if intent_analysis.get("detected_intent") == "about_system":
            return True
        if not normalized:
            return False
        return any(
            self._text_contains_keyword(normalized, marker)
            for marker in self.META_QUESTION_MARKERS
        )

    def _detect_strategy_rejection(
        self,
        normalized: str,
        has_previous_domain: bool,
        previous_response_actionable: bool,
        context_override: Dict[str, Any],
    ) -> bool:
        if not normalized or not has_previous_domain:
            return False
        if context_override.get("reason") == "explicit_invalidation":
            return True
        explicit_rejection_markers = {marker for marker in self.STRATEGY_REJECTION_MARKERS if marker != "otra cosa"}
        if any(self._text_contains_keyword(normalized, marker) for marker in explicit_rejection_markers):
            return True
        if previous_response_actionable and normalized in {"otra cosa", "no otra cosa"}:
            return True
        if previous_response_actionable and any(
            self._text_contains_keyword(normalized, marker)
            for marker in {"no me sirve", "no me ayuda", "otra cosa", "eso no"}
        ):
            return True
        return False

    def _detect_outcome_status(
        self,
        normalized: str,
        has_previous_domain: bool,
        previous_response_actionable: bool,
    ) -> Optional[str]:
        if not normalized or not has_previous_domain or not previous_response_actionable:
            return None
        if any(self._text_contains_keyword(normalized, marker) for marker in self.OUTCOME_WORSE_MARKERS):
            return "worse"
        if any(self._text_contains_keyword(normalized, marker) for marker in self.OUTCOME_PARTIAL_RELIEF_MARKERS):
            return "partial_relief"
        if any(self._text_contains_keyword(normalized, marker) for marker in self.OUTCOME_IMPROVED_MARKERS):
            return "improved"
        if any(self._text_contains_keyword(normalized, marker) for marker in self.OUTCOME_NO_CHANGE_MARKERS):
            return "no_change"
        return None

    def _get_opening_style(self, stage: str) -> str:
        mapping = {
            "reception_containment": "brief_validation",
            "focus_clarification": "simplify_without_reset",
            "functional_classification": "name_current_focus",
            "adaptive_intervention": "progressive_support",
            "closure_continuity": "bridge_to_next_turn",
            "case_learning": "reflective_wrap",
        }
        return mapping.get(stage, "warm_entry")

    def _get_body_style(self, stage: str, config: Dict[str, Any]) -> str:
        structure = config.get("output_structure")
        mapping = {
            "containment_first": "low_demand_steps",
            "clarify_without_reset": "single_instruction_or_question",
            "explain_current_focus": "brief_explanation",
            "guided_progression": "phase_specific_guidance",
            "summary_then_bridge": "short_summary",
            "reflective_feedback": "light_reflection",
        }
        return mapping.get(structure, "brief_guidance")

    def _get_closing_style(self, stage: str) -> str:
        mapping = {
            "reception_containment": "stabilize_without_pressure",
            "focus_clarification": "check_understanding",
            "functional_classification": "prepare_next_step",
            "adaptive_intervention": "one_next_move",
            "closure_continuity": "soft_bridge",
            "case_learning": "gentle_close",
        }
        return mapping.get(stage, "soft_close")
