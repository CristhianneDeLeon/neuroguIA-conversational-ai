from __future__ import annotations

from typing import Any, Dict, List, Optional


class FallbackManager:
    """
    Gestor de política LLM para NeuroGuIA.

    Aunque conserva el nombre 'FallbackManager' por compatibilidad con el proyecto,
    en la práctica funciona como un LLM policy manager:

    - decide si conviene usar LLM
    - explica por qué
    - define el modo de prompt
    - agrega restricciones para controlar la salida
    - señala si el caso también podría aportar aprendizaje útil
    """

    def evaluate(
        self,
        decision_payload: Optional[Dict[str, Any]] = None,
        confidence_payload: Optional[Dict[str, Any]] = None,
        response_memory_payload: Optional[Dict[str, Any]] = None,
        state_analysis: Optional[Dict[str, Any]] = None,
        category_analysis: Optional[Dict[str, Any]] = None,
        intent_analysis: Optional[Dict[str, Any]] = None,
        stage_result: Optional[Dict[str, Any]] = None,
        routine_payload: Optional[Dict[str, Any]] = None,
        case_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        decision_payload = decision_payload or {}
        confidence_payload = confidence_payload or {}
        response_memory_payload = response_memory_payload or {}
        state_analysis = state_analysis or {}
        category_analysis = category_analysis or {}
        intent_analysis = intent_analysis or {}
        stage_result = stage_result or {}
        routine_payload = routine_payload or {}
        case_context = case_context or {}

        decision_mode = str(decision_payload.get("decision_mode") or "")
        selected_strategy = decision_payload.get("selected_strategy")
        selected_microaction = decision_payload.get("selected_microaction")
        response_goal = decision_payload.get("response_goal", {}) or {}
        avoid_list = decision_payload.get("avoid", []) or []

        overall_confidence = float(confidence_payload.get("overall_confidence", 0.0) or 0.0)
        fallback_recommended = bool(confidence_payload.get("fallback_recommended", False))
        weak_points = confidence_payload.get("weak_points", []) or []
        confidence_level = str(confidence_payload.get("confidence_level") or "")

        reuse_confidence = float(response_memory_payload.get("reuse_confidence", 0.0) or 0.0)
        can_reuse_directly = bool(response_memory_payload.get("can_reuse_directly", False))
        selected_response = response_memory_payload.get("selected_response")

        primary_state = state_analysis.get("primary_state")
        secondary_states = state_analysis.get("secondary_states", []) or []
        state_flags = state_analysis.get("flags", {}) or {}

        detected_category = category_analysis.get("detected_category")
        detected_intent = intent_analysis.get("detected_intent")
        stage = stage_result.get("stage")

        routine_steps = routine_payload.get("steps", []) or []
        routine_short = routine_payload.get("short_version", []) or []

        conversation_control = case_context.get("conversation_control", {}) or {}
        conversation_domain = case_context.get("conversation_domain")
        conversation_phase = case_context.get("conversation_phase")
        speaker_role = case_context.get("speaker_role")
        emotional_intensity = float(case_context.get("emotional_intensity", 0.0) or 0.0)
        caregiver_capacity = case_context.get("caregiver_capacity")
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
        response_shape = str(response_goal.get("response_shape") or "")

        # -----------------------------------------------------
        # 1) SEÑALES BASE
        # -----------------------------------------------------
        low_confidence = overall_confidence < 0.50
        medium_low_confidence = overall_confidence < 0.62
        missing_strategy = not bool(response_goal.get("goal") or selected_strategy)
        weak_local_structure = not bool(
            response_goal.get("candidate_actions")
            or response_goal.get("suggested_content")
            or selected_microaction
            or routine_steps
            or routine_short
        )
        no_reuse_support = reuse_confidence < 0.35 and not can_reuse_directly
        multi_factor_case = len(secondary_states) >= 2
        phase_sensitive_case = conversation_phase in {
            "repair",
            "brief_reflection",
            "repair_phrase",
            "anti_overload_phrase",
            "identify_main_trigger",
            "make_transition_script",
            "start_ritual",
            "single_priority",
        }

        learnable_case = bool(
            detected_category in {
                "ansiedad_cognitiva",
                "disfuncion_ejecutiva",
                "regulacion_post_evento",
                "sobrecarga_sensorial",
                "transicion_rigidez",
                "prevencion_escalada",
                "sobrecarga_cuidador",
            }
        )
        high_expression_turn = bool(
            clarification_mode != "none"
            or turn_family in {
                "literal_phrase_request",
                "specific_action_request",
                "blocked_followup",
                "strategy_rejection",
                "post_action_followup",
                "outcome_report",
            }
            or response_goal.get("visible_shift_required")
            or response_shape in {
                "literal_phrase",
                "clarify_simple",
                "direct_instruction",
                "concrete_action",
                "guided_decision",
                "guided_steps",
                "grounding",
                "sleep_settle",
                "load_relief",
            }
        )

        # -----------------------------------------------------
        # 2) DECISIÓN CENTRAL DE USO LLM
        # -----------------------------------------------------
        use_llm = False
        fallback_reason = "not_needed"

        if high_expression_turn:
            use_llm = True
            fallback_reason = "high_expression_turn_requires_llm"

        elif decision_mode == "llm_fallback":
            use_llm = True
            fallback_reason = "decision_engine_requested_llm"

        elif fallback_recommended and not can_reuse_directly:
            use_llm = True
            fallback_reason = "confidence_engine_recommended_llm"

        elif low_confidence and weak_local_structure:
            use_llm = True
            fallback_reason = "low_confidence_and_weak_local_structure"

        elif missing_strategy and no_reuse_support:
            use_llm = True
            fallback_reason = "missing_strategy_and_no_reuse_support"

        elif phase_sensitive_case and medium_low_confidence:
            use_llm = True
            fallback_reason = "phase_sensitive_case"

        elif multi_factor_case and detected_category != "crisis_activa":
            use_llm = True
            fallback_reason = "multi_factor_case"

        elif detected_category in {
            "ansiedad_cognitiva",
            "disfuncion_ejecutiva",
            "regulacion_post_evento",
        } and medium_low_confidence:
            use_llm = True
            fallback_reason = "high_value_contextual_support_case"

        # Casos donde preferimos sostener localmente si ya hay contención clara
        if primary_state in {"meltdown", "shutdown"} and selected_microaction and not high_expression_turn:
            use_llm = False
            fallback_reason = "handled_locally_with_safe_microaction"

        # -----------------------------------------------------
        # 3) MODO DE PROMPT
        # -----------------------------------------------------
        prompt_mode = self._select_prompt_mode(
            primary_state=primary_state,
            detected_category=detected_category,
            detected_intent=detected_intent,
            stage=stage,
            conversation_phase=conversation_phase,
            emotional_intensity=emotional_intensity,
        )

        # -----------------------------------------------------
        # 4) RESTRICCIONES PARA EL LLM
        # -----------------------------------------------------
        constraints = self._build_constraints(
            primary_state=primary_state,
            detected_category=detected_category,
            detected_intent=detected_intent,
            speaker_role=speaker_role,
            response_goal=response_goal,
            selected_strategy=selected_strategy,
            selected_microaction=selected_microaction,
            avoid_list=avoid_list,
            emotional_intensity=emotional_intensity,
            state_flags=state_flags,
        )

        # -----------------------------------------------------
        # 5) SEÑAL DE APRENDIZAJE
        # -----------------------------------------------------
        should_learn_if_good = bool(
            use_llm
            and learnable_case
            and detected_category not in {"crisis_activa"}
        )

        learning_priority = self._estimate_learning_priority(
            detected_category=detected_category,
            conversation_phase=conversation_phase,
            speaker_role=speaker_role,
            multi_factor_case=multi_factor_case,
            medium_low_confidence=medium_low_confidence,
        )

        # -----------------------------------------------------
        # 6) CONTEXTO RESULTANTE
        # -----------------------------------------------------
        return {
            "use_llm": use_llm,
            "fallback_reason": fallback_reason,
            "prompt_mode": prompt_mode,
            "constraints": constraints,
            "should_learn_if_good": should_learn_if_good,
            "learning_priority": learning_priority,
            "context": {
                "intent": detected_intent,
                "category": detected_category,
                "state": primary_state,
                "secondary_states": secondary_states,
                "stage": stage,
                "conversation_domain": conversation_domain,
                "conversation_phase": conversation_phase,
                "speaker_role": speaker_role,
                "confidence": overall_confidence,
                "confidence_level": confidence_level,
                "reuse_confidence": reuse_confidence,
                "can_reuse_directly": can_reuse_directly,
                "has_selected_response": bool(selected_response),
                "weak_points": weak_points,
                "has_local_routine": bool(routine_steps or routine_short),
                "has_selected_strategy": bool(selected_strategy),
                "has_selected_microaction": bool(selected_microaction),
                "caregiver_capacity": caregiver_capacity,
                "emotional_intensity": emotional_intensity,
            },
        }

    # =========================================================
    # PROMPT MODE
    # =========================================================
    def _select_prompt_mode(
        self,
        primary_state: Optional[str],
        detected_category: Optional[str],
        detected_intent: Optional[str],
        stage: Optional[str],
        conversation_phase: Optional[str],
        emotional_intensity: float,
    ) -> str:
        if primary_state in {"meltdown", "shutdown"} or detected_category == "crisis_activa":
            return "controlled_crisis_support"

        if primary_state in {"burnout", "parental_fatigue"} or detected_category == "sobrecarga_cuidador":
            return "controlled_low_demand_support"

        if detected_intent == "clarification_request":
            return "controlled_explanatory_support"

        if detected_category in {
            "ansiedad_cognitiva",
            "disfuncion_ejecutiva",
            "sueno_regulacion",
            "transicion_rigidez",
        }:
            return "controlled_structured_support"

        if detected_category in {
            "regulacion_post_evento",
            "sobrecarga_sensorial",
            "prevencion_escalada",
        }:
            return "controlled_adaptive_support"

        if stage in {"case_learning", "closure_continuity"} or conversation_phase in {
            "brief_reflection",
            "repair_phrase",
            "anti_overload_phrase",
        }:
            return "controlled_reflective_feedback"

        if emotional_intensity >= 0.75:
            return "controlled_calm_support"

        return "controlled_support_generation"

    # =========================================================
    # CONSTRAINTS
    # =========================================================
    def _build_constraints(
        self,
        primary_state: Optional[str],
        detected_category: Optional[str],
        detected_intent: Optional[str],
        speaker_role: Optional[str],
        response_goal: Dict[str, Any],
        selected_strategy: Optional[str],
        selected_microaction: Optional[str],
        avoid_list: List[str],
        emotional_intensity: float,
        state_flags: Dict[str, Any],
    ) -> Dict[str, Any]:
        must_include = self._build_must_include(
            response_goal=response_goal,
            selected_strategy=selected_strategy,
            selected_microaction=selected_microaction,
            detected_category=detected_category,
        )

        hard_avoid = list(avoid_list)

        # restricciones por seguridad / tono
        if primary_state in {"meltdown", "shutdown"}:
            hard_avoid.extend([
                "explicaciones_largas",
                "preguntas_complejas",
                "tono_moralizante",
            ])

        if detected_category == "ansiedad_cognitiva":
            hard_avoid.extend([
                "decir_relajate",
                "pedir_que_resuelva_todo",
            ])

        if detected_category == "disfuncion_ejecutiva":
            hard_avoid.extend([
                "dar_demasiados_pasos_a_la_vez",
                "hablar_en_abstracto",
            ])

        if detected_category == "sobrecarga_sensorial":
            hard_avoid.extend([
                "forzar_contacto",
                "aumentar_estimulos",
            ])

        if speaker_role == "docente":
            must_include.append("contexto aplicable al aula")
        elif speaker_role == "cuidador":
            must_include.append("tono de acompañamiento y carga realista")
        else:
            must_include.append("lenguaje claro y concreto")

        followup_policy = str(response_goal.get("followup_policy") or "avoid")
        should_offer_question = bool(response_goal.get("should_offer_question"))
        should_close_with_followup = bool(
            should_offer_question
            and followup_policy in {"optional", "brief_check"}
            and not response_goal.get("keep_minimal")
            and emotional_intensity < 0.78
            and detected_intent not in {"urgent_support", "clarification_request"}
        )
        if followup_policy == "brief_check" and emotional_intensity < 0.72:
            should_close_with_followup = should_offer_question

        return {
            "avoid": self._deduplicate([a for a in hard_avoid if a]),
            "must_include": self._deduplicate([m for m in must_include if m]),
            "max_length": self._suggest_max_length(
                primary_state=primary_state,
                emotional_intensity=emotional_intensity,
            ),
            "should_close_with_followup": should_close_with_followup,
            "prefer_short_sentences": bool(
                emotional_intensity >= 0.70
                or primary_state in {"meltdown", "shutdown", "burnout"}
                or state_flags.get("needs_low_demand_language", False)
            ),
        }

    def _build_must_include(
        self,
        response_goal: Dict[str, Any],
        selected_strategy: Optional[str],
        selected_microaction: Optional[str],
        detected_category: Optional[str],
    ) -> List[str]:
        must_include: List[str] = []

        suggested_content = [str(item).strip() for item in response_goal.get("suggested_content", []) if str(item).strip()]
        candidate_actions = [str(item).strip() for item in response_goal.get("candidate_actions", []) if str(item).strip()]
        literal_phrases = [str(item).strip() for item in response_goal.get("literal_phrase_candidates", []) if str(item).strip()]

        if literal_phrases:
            must_include.append(literal_phrases[0])
        elif response_goal.get("should_offer_action") and candidate_actions:
            must_include.append(candidate_actions[0])
        elif response_goal.get("should_offer_action") and selected_microaction:
            must_include.append(str(selected_microaction))
        elif suggested_content:
            must_include.append(suggested_content[0])
        elif selected_strategy:
            must_include.append(str(selected_strategy))

        category_hints = {
            "prevencion_escalada": "señales tempranas",
            "ansiedad_cognitiva": "una sola prioridad",
            "disfuncion_ejecutiva": "primer paso pequeño",
            "regulacion_post_evento": "hablar después con calma",
            "sobrecarga_sensorial": "bajar estímulos",
            "transicion_rigidez": "anticipar el cambio",
            "sueno_regulacion": "rutina breve y estable",
            "sobrecarga_cuidador": "reducir exigencia",
        }

        if response_goal.get("domain_focus"):
            must_include.append(str(response_goal.get("domain_focus")))
        elif detected_category in category_hints:
            must_include.append(category_hints[detected_category])

        return self._deduplicate(must_include)

    def _suggest_max_length(
        self,
        primary_state: Optional[str],
        emotional_intensity: float,
    ) -> int:
        if primary_state in {"meltdown", "shutdown"}:
            return 90
        if primary_state in {"burnout", "parental_fatigue"}:
            return 120
        if emotional_intensity >= 0.75:
            return 110
        return 170

    # =========================================================
    # LEARNING PRIORITY
    # =========================================================
    def _estimate_learning_priority(
        self,
        detected_category: Optional[str],
        conversation_phase: Optional[str],
        speaker_role: Optional[str],
        multi_factor_case: bool,
        medium_low_confidence: bool,
    ) -> str:
        high_value_categories = {
            "ansiedad_cognitiva",
            "disfuncion_ejecutiva",
            "regulacion_post_evento",
            "sobrecarga_sensorial",
            "transicion_rigidez",
            "prevencion_escalada",
        }

        if detected_category in high_value_categories and (multi_factor_case or medium_low_confidence):
            return "high"

        if conversation_phase in {"brief_reflection", "repair_phrase", "start_ritual"}:
            return "medium_high"

        if speaker_role in {"docente", "cuidador"}:
            return "medium"

        return "low"

    # =========================================================
    # HELPERS
    # =========================================================
    def _deduplicate(self, items: List[Any]) -> List[Any]:
        result: List[Any] = []
        seen = set()
        for item in items:
            if item not in seen:
                seen.add(item)
                result.append(item)
        return result


def evaluate_fallback(**kwargs):
    return FallbackManager().evaluate(**kwargs)
