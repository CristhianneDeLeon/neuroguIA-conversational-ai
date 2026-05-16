from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Optional


class DecisionEngine:
    """
    Strategic planner for the turn.

    This layer does not decide the final wording.
    It only decides the objective, content priorities, candidate actions and
    safety constraints that the LLM or fallback renderer can realize.
    """

    LEGACY_CATEGORY_ALIASES = {
        "crisis_emocional": "crisis_activa",
        "saturacion_sensorial": "sobrecarga_sensorial",
        "bloqueo_ejecutivo": "disfuncion_ejecutiva",
        "sleep": "sueno_regulacion",
        "agotamiento_cuidador": "sobrecarga_cuidador",
        "sueno_descanso": "sueno_regulacion",
        "transicion": "transicion_rigidez",
    }

    ROUTINE_BY_DOMAIN = {
        "crisis_activa": "post_crisis",
        "escalada_emocional": "early_regulation",
        "prevencion_escalada": "prevention_monitoring",
        "regulacion_post_evento": "post_crisis_reflection",
        "ansiedad_cognitiva": "anxiety_grounding",
        "disfuncion_ejecutiva": "executive_start",
        "sobrecarga_sensorial": "sensory_regulation",
        "transicion_rigidez": "transition_support",
        "sueno_regulacion": "sleep",
        "sobrecarga_cuidador": "caregiver_recovery",
    }

    def decide(
        self,
        intent_analysis: Optional[Dict[str, Any]] = None,
        category_analysis: Optional[Dict[str, Any]] = None,
        state_analysis: Optional[Dict[str, Any]] = None,
        support_plan: Optional[Dict[str, Any]] = None,
        stage_result: Optional[Dict[str, Any]] = None,
        confidence_payload: Optional[Dict[str, Any]] = None,
        memory_payload: Optional[Dict[str, Any]] = None,
        response_memory_payload: Optional[Dict[str, Any]] = None,
        routine_payload: Optional[Dict[str, Any]] = None,
        case_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        intent_analysis = intent_analysis or {}
        category_analysis = category_analysis or {}
        state_analysis = state_analysis or {}
        support_plan = support_plan or {}
        stage_result = stage_result or {}
        response_memory_payload = response_memory_payload or {}
        routine_payload = routine_payload or {}
        case_context = case_context or {}

        conversation_control = case_context.get("conversation_control", {}) or {}
        conversation_frame = case_context.get("conversation_frame", {}) or {}

        domain = self._canonicalize_category(
            stage_result.get("conversation_domain")
            or conversation_control.get("domain")
            or case_context.get("conversation_domain")
            or category_analysis.get("detected_category")
            or "apoyo_general"
        )
        phase = (
            stage_result.get("conversation_phase")
            or conversation_control.get("phase")
            or case_context.get("conversation_phase")
            or "clarification"
        )
        stage = stage_result.get("stage") or "adaptive_intervention"
        turn_type = stage_result.get("turn_type") or conversation_control.get("turn_type") or "new_request"
        turn_family = stage_result.get("turn_family") or conversation_control.get("turn_family") or conversation_frame.get("turn_family") or "new_request"
        clarification_mode = stage_result.get("clarification_mode") or conversation_control.get("clarification_mode") or "none"
        crisis_guided_mode = stage_result.get("crisis_guided_mode") or conversation_control.get("crisis_guided_mode") or "none"
        primary_state = state_analysis.get("primary_state")
        detected_intent = intent_analysis.get("detected_intent")
        last_guided_action = (
            conversation_control.get("last_guided_action")
            or conversation_frame.get("last_guided_action")
            or case_context.get("last_guided_action")
        )
        progression_state = {
            "intervention_level": int(
                stage_result.get("intervention_level")
                or conversation_control.get("intervention_level")
                or conversation_frame.get("intervention_level")
                or 1
            ),
            "stuck_followup_count": int(
                stage_result.get("stuck_followup_count")
                or conversation_control.get("stuck_followup_count")
                or conversation_frame.get("stuck_followup_count")
                or 0
            ),
            "progression_signals": stage_result.get("progression_signals")
            or conversation_control.get("progression_signals")
            or {},
            "turn_family": turn_family,
            "context_override": stage_result.get("context_override")
            or conversation_control.get("context_override")
            or conversation_frame.get("context_override")
            or {},
            "previous_strategy_signature": conversation_control.get("previous_strategy_signature")
            or conversation_frame.get("last_strategy_signature"),
            "previous_response_shape": conversation_control.get("previous_response_shape")
            or conversation_frame.get("last_response_shape"),
            "previous_form_variant": conversation_control.get("previous_form_variant")
            or conversation_frame.get("response_form_variant"),
            "strategy_repeat_count": int(
                conversation_control.get("strategy_repeat_count")
                or conversation_frame.get("strategy_repeat_count")
                or 0
            ),
            "recent_strategy_history": conversation_control.get("recent_strategy_history")
            or conversation_frame.get("recent_strategy_history")
            or [],
        }
        source_message = (
            conversation_control.get("effective_message")
            or conversation_control.get("source_message")
            or conversation_frame.get("effective_message")
            or conversation_frame.get("source_message")
            or ""
        )

        response_goal = self._build_response_goal(
            domain=domain,
            phase=phase,
            stage=stage,
            turn_type=turn_type,
            turn_family=turn_family,
            detected_intent=detected_intent,
            primary_state=primary_state,
            clarification_mode=clarification_mode,
            crisis_guided_mode=crisis_guided_mode,
            last_guided_action=last_guided_action,
            routine_payload=routine_payload,
            support_plan=support_plan,
            source_message=source_message,
            progression_state=progression_state,
        )

        selected_strategy = response_goal.get("selected_strategy")
        selected_microaction = response_goal.get("selected_microaction")
        selected_routine_type = (
            response_goal.get("selected_routine_type")
            or routine_payload.get("routine_type")
            or self.ROUTINE_BY_DOMAIN.get(domain)
        )

        best_response = response_memory_payload.get("best_response") or {}
        reuse_confidence = float(response_memory_payload.get("reuse_confidence", 0.0) or 0.0)
        can_reuse_directly = bool(response_memory_payload.get("can_reuse_directly", False))

        decision_mode = "planned_response"
        reuse_response_candidate = None
        reuse_sensitive_turn = bool(
            response_goal.get("visible_shift_required")
            or turn_family in {
                "blocked_followup",
                "specific_action_request",
                "literal_phrase_request",
                "post_action_followup",
                "strategy_rejection",
                "outcome_report",
            }
            or response_goal.get("response_shape") not in {
                "simple_answer",
                "validation_answer",
                "meta_answer",
                "closure_pause",
                "hold_line",
            }
        )
        if (
            can_reuse_directly
            and reuse_confidence >= 0.84
            and clarification_mode == "none"
            and domain != "crisis_activa"
            and turn_type != "domain_shift"
            and not (progression_state.get("context_override", {}) or {}).get("active")
            and best_response
            and not response_goal.get("keep_minimal")
            and not reuse_sensitive_turn
        ):
            decision_mode = "reuse_response_memory"
            reuse_response_candidate = best_response

        avoid = self._build_avoid_list(
            state_avoid=state_analysis.get("response_plan", {}).get("avoid", []) or [],
            response_alerts=support_plan.get("response_alerts", []) or [],
            response_goal=response_goal,
            domain=domain,
            stage=stage,
            primary_state=primary_state,
            clarification_mode=clarification_mode,
        )

        decision_flags = {
            "prefer_llm_response": True,
            "prefer_system_response": False,
            "critical_case": domain == "crisis_activa" or primary_state in {"meltdown", "shutdown"},
            "clarification_case": clarification_mode != "none",
            "guided_crisis_case": crisis_guided_mode == "guided_steps",
            "minimal_response_ok": bool(response_goal.get("keep_minimal") or response_goal.get("should_stay_with_validation")),
            "followup_guided_intervention": turn_type in {"followup_acceptance", "followup_request", "continuation"},
        }

        return {
            "decision_mode": decision_mode,
            "intervention_type": response_goal.get("intervention_type"),
            "selected_strategy": selected_strategy,
            "selected_microaction": selected_microaction,
            "selected_routine_type": selected_routine_type,
            "reuse_response_candidate": reuse_response_candidate,
            "priority_order": response_goal.get("priority_order", []),
            "avoid": avoid,
            "decision_flags": decision_flags,
            "response_goal": response_goal,
            "response_plan": response_goal,
        }

    def _build_response_goal(
        self,
        domain: str,
        phase: str,
        stage: str,
        turn_type: str,
        turn_family: str,
        detected_intent: Optional[str],
        primary_state: Optional[str],
        clarification_mode: str,
        crisis_guided_mode: str,
        last_guided_action: Optional[str],
        routine_payload: Dict[str, Any],
        support_plan: Dict[str, Any],
        source_message: str,
        progression_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        message_cues = self._message_cues(source_message)
        context_override = progression_state.get("context_override", {}) or {}
        if clarification_mode != "none" or stage == "focus_clarification":
            return self._clarification_goal(
                domain=domain,
                last_guided_action=last_guided_action,
                source_message=source_message,
            )
        if turn_family == "meta_question":
            return self._meta_question_goal(source_message=source_message, progression_state=progression_state)
        if turn_family == "closure_or_pause":
            return self._closure_goal(domain=domain, progression_state=progression_state)
        if context_override.get("active"):
            override_goal = self._context_override_goal(
                domain=domain,
                phase=phase,
                turn_family=turn_family,
                source_message=source_message,
                message_cues=message_cues,
                progression_state=progression_state,
            )
            if override_goal:
                return override_goal
        corridor_goal = self._corridor_followup_goal(
            domain=domain,
            phase=phase,
            turn_type=turn_type,
            turn_family=turn_family,
            source_message=source_message,
            progression_state=progression_state,
        )
        if corridor_goal:
            return corridor_goal
        if turn_family == "strategy_rejection":
            return self._strategy_rejection_goal(
                domain=domain,
                phase=phase,
                source_message=source_message,
                progression_state=progression_state,
            )
        if turn_family == "outcome_report":
            return self._outcome_report_goal(
                domain=domain,
                phase=phase,
                source_message=source_message,
                progression_state=progression_state,
            )
        if turn_family == "simple_question":
            return self._simple_question_goal(domain=domain, source_message=source_message, progression_state=progression_state)
        if turn_family == "validation_request":
            return self._validation_goal(domain=domain, source_message=source_message, progression_state=progression_state)
        if turn_family == "literal_phrase_request" and domain != "crisis_activa":
            return self._literal_phrase_goal(domain=domain, progression_state=progression_state)
        if domain == "crisis_activa":
            return self._crisis_goal(
                phase=phase,
                turn_family=turn_family,
                crisis_guided_mode=crisis_guided_mode,
                source_message=source_message,
                message_cues=message_cues,
                progression_state=progression_state,
            )

        builders = {
            "ansiedad_cognitiva": self._anxiety_goal,
            "disfuncion_ejecutiva": self._executive_goal,
            "sueno_regulacion": self._sleep_goal,
            "sobrecarga_cuidador": self._caregiver_goal,
            "prevencion_escalada": self._prevention_goal,
            "sobrecarga_sensorial": self._sensory_goal,
            "transicion_rigidez": self._transition_goal,
            "escalada_emocional": self._escalation_goal,
            "regulacion_post_evento": self._post_event_goal,
        }
        if domain in builders:
            return builders[domain](
                phase=phase,
                turn_type=turn_type,
                turn_family=turn_family,
                support_plan=support_plan,
                source_message=source_message,
                message_cues=message_cues,
                progression_state=progression_state,
            )
        if message_cues.get("expresses_uncertainty"):
            return self._uncertainty_goal(
                domain=domain,
                source_message=source_message,
                progression_state=progression_state,
            )
        return self._general_goal(
            detected_intent=detected_intent,
            primary_state=primary_state,
            turn_family=turn_family,
            routine_payload=routine_payload,
            source_message=source_message,
            message_cues=message_cues,
            progression_state=progression_state,
        )

    def _clarification_goal(
        self,
        domain: str,
        last_guided_action: Optional[str],
        source_message: str,
    ) -> Dict[str, Any]:
        action = last_guided_action or self._default_microaction_for_domain(domain)
        return self._goal(
            goal="clarify_last_guidance",
            priority="clarity",
            guidance_level="high",
            intervention_type="clarification",
            suggested_content=[self._clarification_line(domain, action), "mantener el mismo tema", "usar una sola idea concreta"],
            candidate_actions=[action] if action else [],
            possible_questions=[],
            safety_constraints=["no_abrir_temas_nuevos", "no_repetir_misma_formulacion"],
            keep_minimal=True,
            should_offer_action=bool(action),
            should_offer_question=False,
            selected_strategy="reformular una sola idea antes de avanzar",
            selected_microaction=action,
            selected_routine_type=self.ROUTINE_BY_DOMAIN.get(domain),
            priority_order=["claridad", "continuidad", "baja_carga"],
            should_stay_with_validation=False,
            response_shape="clarify_simple",
            domain_focus=self._domain_focus(domain),
            followup_policy="avoid",
            intervention_level=1,
            form_variant="simple_rephrase",
        )

    def _simple_question_goal(
        self,
        domain: str,
        source_message: str,
        progression_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        answer = self._simple_answer_line(domain, source_message)
        return self._goal(
            goal="answer_simple_question",
            priority="clarity",
            guidance_level="moderate",
            intervention_type="brief_answer",
            suggested_content=[answer, "responder directo y breve", "no abrir una intervencion larga"],
            candidate_actions=[],
            possible_questions=[],
            safety_constraints=["no_sobrecargar", "no_convertir_en_protocolo"],
            keep_minimal=True,
            should_offer_action=False,
            should_offer_question=False,
            selected_strategy="responder la consulta puntual sin entrar a una intervencion prolongada",
            selected_microaction=None,
            selected_routine_type=self.ROUTINE_BY_DOMAIN.get(domain),
            priority_order=["respuesta_directa", "claridad", "brevedad"],
            should_stay_with_validation=False,
            response_shape="simple_answer",
            domain_focus=self._domain_focus(domain),
            followup_policy="avoid",
            intervention_level=self._goal_level(progression_state, minimum=1),
            form_variant="simple_answer",
        )

    def _validation_goal(
        self,
        domain: str,
        source_message: str,
        progression_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        answer = self._validation_line(domain, source_message)
        return self._goal(
            goal="validate_or_normalize",
            priority="clarity",
            guidance_level="moderate",
            intervention_type="brief_validation",
            suggested_content=[answer, "responder si es esperable de forma clara", "no dramatizar ni abrir un protocolo nuevo"],
            candidate_actions=[],
            possible_questions=[],
            safety_constraints=["no_sobrecargar", "no_abrir_intervencion_innecesaria"],
            keep_minimal=True,
            should_offer_action=False,
            should_offer_question=False,
            selected_strategy="validar o normalizar de forma breve y clara",
            selected_microaction=None,
            selected_routine_type=self.ROUTINE_BY_DOMAIN.get(domain),
            priority_order=["validacion", "claridad", "brevedad"],
            should_stay_with_validation=True,
            response_shape="validation_answer",
            domain_focus=self._domain_focus(domain),
            followup_policy="avoid",
            intervention_level=self._goal_level(progression_state, minimum=1),
            form_variant="validation_answer",
        )

    def _meta_question_goal(
        self,
        source_message: str,
        progression_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        answer, variant = self._about_system_line(source_message)
        return self._goal(
            goal="answer_about_system_briefly",
            priority="clarity",
            guidance_level="low",
            intervention_type="system_meta",
            suggested_content=[answer, "responder directo, humano y breve"],
            candidate_actions=[],
            possible_questions=[],
            safety_constraints=["no_abrir_intervencion_larga"],
            keep_minimal=True,
            should_offer_action=False,
            should_offer_question=False,
            selected_strategy="responder directo y cercano sobre nombre, identidad o alcance",
            selected_microaction=None,
            selected_routine_type=None,
            priority_order=["respuesta_directa", "cercania", "brevedad"],
            should_stay_with_validation=True,
            response_shape="meta_answer",
            domain_focus="respuesta directa y cercana",
            followup_policy="avoid",
            intervention_level=1,
            form_variant=variant,
        )

    def _closure_goal(
        self,
        domain: str,
        progression_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        return self._goal(
            goal="close_after_action",
            priority="emotional_safety",
            guidance_level="low",
            intervention_type="closure_pause",
            suggested_content=["cerrar sin empujar otra accion", "dejar permiso de pausa", "no reabrir el protocolo"],
            candidate_actions=[],
            possible_questions=[],
            safety_constraints=["no_reabrir_la_intervencion"],
            keep_minimal=True,
            should_offer_action=False,
            should_offer_question=False,
            selected_strategy="cerrar o pausar sin agregar demanda",
            selected_microaction=None,
            selected_routine_type=self.ROUTINE_BY_DOMAIN.get(domain),
            priority_order=["cierre", "pausa", "baja_demanda"],
            should_stay_with_validation=True,
            response_shape="closure_pause",
            domain_focus=self._domain_focus(domain),
            followup_policy="avoid",
            intervention_level=self._goal_level(progression_state, minimum=1),
            form_variant="close_after_action",
        )

    def _literal_phrase_goal(self, domain: str, progression_state: Dict[str, Any]) -> Dict[str, Any]:
        phrase = "Puedes decirlo asi: ahora mismo no puedo entrar en todo eso; voy con una sola cosa."
        if domain == "ansiedad_cognitiva":
            phrase = "Puedes decirte esto: ahora no voy a resolver todo; solo una cosa a la vez."
        elif domain == "disfuncion_ejecutiva":
            phrase = "Di esto en corto: no voy a ordenar todo; voy a empezar por una sola parte."
        return self._goal(
            goal="give_literal_phrase",
            priority="clarity",
            guidance_level="high",
            intervention_type="literal_phrase_support",
            suggested_content=["dar una frase usable", "no quedarse en estrategia general"],
            candidate_actions=["usar una sola frase breve y luego parar"],
            possible_questions=[],
            safety_constraints=["no_abrir_mas_analisis"],
            keep_minimal=True,
            should_offer_action=True,
            should_offer_question=False,
            selected_strategy="dar una frase literal breve y usable",
            selected_microaction="usar una sola frase breve y luego parar",
            selected_routine_type=self.ROUTINE_BY_DOMAIN.get(domain),
            priority_order=["frase_literal", "claridad", "brevedad"],
            should_stay_with_validation=False,
            allow_literal_phrase=True,
            literal_phrase_candidates=[phrase],
            response_shape="literal_phrase",
            domain_focus=self._domain_focus(domain),
            followup_policy="avoid",
            intervention_level=max(self._goal_level(progression_state, minimum=1), 3),
            form_variant="literal_then_pause",
        )

    def _goal_level(self, progression_state: Dict[str, Any], minimum: int = 1) -> int:
        level = int(progression_state.get("intervention_level", 0) or 0)
        return max(level, minimum)

    def _progression_flags(self, progression_state: Dict[str, Any]) -> Dict[str, bool]:
        signals = progression_state.get("progression_signals", {}) or {}
        return {
            "needs_direct_instruction": bool(signals.get("needs_direct_instruction")),
            "persistent_block": bool(signals.get("persistent_block")),
            "wants_progression": bool(signals.get("wants_progression")),
            "avoid_strategy_loop": bool(signals.get("avoid_strategy_loop")),
            "asks_post_action_followup": bool(signals.get("asks_post_action_followup")),
            "repeated_post_action_followup": bool(signals.get("repeated_post_action_followup")),
        }

    def _outcome_status(self, progression_state: Dict[str, Any]) -> Optional[str]:
        signals = progression_state.get("progression_signals", {}) or {}
        outcome_status = str(signals.get("outcome_status") or "").strip()
        return outcome_status or None

    def _context_override(self, progression_state: Dict[str, Any]) -> Dict[str, Any]:
        override = progression_state.get("context_override", {}) or {}
        return {
            "active": bool(override.get("active", False)),
            "type": override.get("type"),
            "reason": override.get("reason"),
            "confidence": float(override.get("confidence", 0.0) or 0.0),
            "target": override.get("target"),
            "source_message": override.get("source_message"),
            "effective_message": override.get("effective_message"),
        }

    def _recent_strategy_history(self, progression_state: Dict[str, Any]) -> List[Dict[str, Any]]:
        history = progression_state.get("recent_strategy_history") or []
        return [item for item in history if isinstance(item, dict)]

    def _is_post_action_corridor_entry(self, entry: Dict[str, Any]) -> bool:
        if not isinstance(entry, dict):
            return False
        goal = str(entry.get("response_goal") or "")
        shape = str(entry.get("response_shape") or "")
        form_variant = str(entry.get("form_variant") or "")
        return (
            goal in {
                "check_effect_after_step",
                "hold_without_adding_demand",
                "give_next_distinct_step",
                "close_after_action",
                "decide_stop_or_continue",
                "hold_or_close_after_partial_effect",
                "hold_or_close_after_effect",
            }
            or shape in {"check_effect", "hold_line", "closure_pause"}
            or form_variant in {
                "effect_scan",
                "effect_scan_exec",
                "hold_steady",
                "next_distinct_step",
                "adjust_safety_step",
                "stop_or_continue",
                "close_after_action",
                "close_with_permission",
                "partial_relief_hold",
                "improved_close",
            }
        )

    def _is_action_seed_entry(self, entry: Dict[str, Any]) -> bool:
        if not isinstance(entry, dict):
            return False
        goal = str(entry.get("response_goal") or "")
        shape = str(entry.get("response_shape") or "")
        return (
            goal in {
                "choose_first_safe_crisis_step",
                "guide_safe_steps_now",
                "lower_anxiety_demand_now",
                "shift_anxiety_into_one_action",
                "convert_anxiety_into_concrete_action",
                "make_one_anxiety_decision_for_user",
                "choose_first_executive_step",
                "give_next_distinct_step",
                "change_modality_after_no_effect",
                "replace_rejected_strategy",
            }
            or shape in {
                "single_action",
                "concrete_action",
                "guided_steps",
                "guided_decision",
                "direct_instruction",
                "grounding",
                "literal_phrase",
                "strategy_switch",
                "crisis_containment",
                "permission_pause",
                "load_relief",
                "sleep_settle",
            }
        )

    def _has_repeated_post_action_followup(self, progression_state: Dict[str, Any]) -> bool:
        signals = progression_state.get("progression_signals", {}) or {}
        if signals.get("repeated_post_action_followup"):
            return True
        if not (
            signals.get("asks_post_action_followup")
            or signals.get("asks_for_more")
            or signals.get("wants_progression")
        ):
            return False
        history = self._recent_strategy_history(progression_state)[-4:]
        if len(history) < 2:
            return False
        saw_action = any(self._is_action_seed_entry(entry) for entry in history)
        saw_followup = any(
            str(entry.get("response_goal") or "") == "check_effect_after_step"
            or str(entry.get("response_shape") or "") == "check_effect"
            for entry in history
        )
        saw_adjustment = any(
            str(entry.get("response_goal") or "") in {
                "give_next_distinct_step",
                "decide_stop_or_continue",
                "hold_without_adding_demand",
                "close_after_action",
                "change_modality_after_no_effect",
                "replace_rejected_strategy",
                "hold_or_close_after_partial_effect",
                "hold_or_close_after_effect",
            }
            or str(entry.get("form_variant") or "") in {
                "next_distinct_step",
                "adjust_safety_step",
                "stop_or_continue",
                "close_after_action",
                "close_with_permission",
                "close_arranque",
                "improved_close",
                "partial_relief_hold",
            }
            for entry in history
        )
        return saw_action and saw_followup and saw_adjustment

    def _has_new_crisis_safety_signal(self, source_message: str) -> bool:
        normalized = self._normalize(source_message)
        return any(
            token in normalized
            for token in {
                "riesgo",
                "se golpea",
                "se golpeo",
                "se pegó",
                "se pega",
                "se escapo",
                "se escapó",
                "hay peligro",
                "esta peor",
                "está peor",
            }
        )

    def _should_prevent_protocol_backtrack(
        self,
        domain: str,
        turn_type: str,
        turn_family: str,
        source_message: str,
        progression_state: Dict[str, Any],
    ) -> bool:
        if turn_type == "domain_shift":
            return False
        if (progression_state.get("context_override") or {}).get("active"):
            return False
        if turn_family not in {"post_action_followup", "outcome_report", "strategy_rejection", "blocked_followup", "specific_action_request"}:
            return False
        if domain == "crisis_activa" and self._has_new_crisis_safety_signal(source_message):
            return False
        history = self._recent_strategy_history(progression_state)
        return any(self._is_post_action_corridor_entry(entry) for entry in history[-3:])

    def _corridor_followup_goal(
        self,
        domain: str,
        phase: str,
        turn_type: str,
        turn_family: str,
        source_message: str,
        progression_state: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        if not self._should_prevent_protocol_backtrack(
            domain=domain,
            turn_type=turn_type,
            turn_family=turn_family,
            source_message=source_message,
            progression_state=progression_state,
        ):
            return None
        if turn_family == "strategy_rejection":
            return self._strategy_rejection_goal(
                domain=domain,
                phase=phase,
                source_message=source_message,
                progression_state=progression_state,
            )
        if turn_family == "outcome_report":
            return self._outcome_report_goal(
                domain=domain,
                phase=phase,
                source_message=source_message,
                progression_state=progression_state,
            )
        if turn_family in {"post_action_followup", "blocked_followup", "specific_action_request"}:
            return self._post_action_goal(domain=domain, phase=phase, progression_state=progression_state)
        return None

    def _distinct_strategy_goal(
        self,
        domain: str,
        phase: str,
        progression_state: Dict[str, Any],
        trigger: str,
    ) -> Dict[str, Any]:
        previous_shape = str(progression_state.get("previous_response_shape") or "")
        previous_variant = str(progression_state.get("previous_form_variant") or "")
        level = max(self._goal_level(progression_state, minimum=2), 2)
        trigger_label = "rejection" if trigger == "rejection" else "no_change"

        if domain == "crisis_activa":
            if previous_shape in {"single_action", "guided_steps", "direct_instruction", "crisis_containment", "check_effect"}:
                literal_phrase = "Estoy aqui. No voy a discutir. Vamos a bajar esto."
                return self._goal(
                    goal="replace_rejected_strategy" if trigger == "rejection" else "change_modality_after_no_effect",
                    priority="physical_and_emotional_safety",
                    guidance_level="high",
                    intervention_type="strategy_switch",
                    suggested_content=["soltar la via anterior", "cambiar del entorno a una frase breve y segura", "no repetir el mismo paso"],
                    candidate_actions=["di una sola frase breve y luego guarda silencio unos segundos"],
                    possible_questions=[],
                    safety_constraints=["no_repetir_protocolo", "no_sumar_demanda"],
                    keep_minimal=True,
                    should_offer_action=True,
                    should_offer_question=False,
                    selected_strategy="cambiar del entorno a una frase breve y segura",
                    selected_microaction="di una sola frase breve y luego guarda silencio unos segundos",
                    selected_routine_type=self.ROUTINE_BY_DOMAIN.get(domain),
                    priority_order=["seguridad", "cambio_real", "menos_palabras"],
                    should_stay_with_validation=False,
                    allow_literal_phrase=True,
                    literal_phrase_candidates=[literal_phrase],
                    response_shape="literal_phrase",
                    domain_focus="seguridad inmediata con menos palabras",
                    followup_policy="avoid",
                    intervention_level=max(level, 3),
                    form_variant="crisis_to_communication",
                    strategy_signature=f"{trigger_label}:crisis:communication:{previous_variant or previous_shape or phase}",
                    visible_shift_required=True,
                )
            action = "sin seguir hablando, mueve la situacion a un punto con menos gente o menos ruido"
            return self._goal(
                goal="replace_rejected_strategy" if trigger == "rejection" else "change_modality_after_no_effect",
                priority="physical_and_emotional_safety",
                guidance_level="high",
                intervention_type="strategy_switch",
                suggested_content=["soltar la via anterior", "pasar de hablar a mover el entorno", "no reabrir la misma secuencia"],
                candidate_actions=[action],
                possible_questions=[],
                safety_constraints=["no_repetir_protocolo", "no_analisis_extenso"],
                keep_minimal=True,
                should_offer_action=True,
                should_offer_question=False,
                selected_strategy="cambiar de palabras a ajuste de entorno",
                selected_microaction=action,
                selected_routine_type=self.ROUTINE_BY_DOMAIN.get(domain),
                priority_order=["seguridad", "cambio_real", "menos_estimulo"],
                should_stay_with_validation=False,
                response_shape="single_action",
                domain_focus="seguridad inmediata y ajuste de entorno",
                followup_policy="avoid",
                intervention_level=max(level, 3),
                form_variant="crisis_to_environment",
                strategy_signature=f"{trigger_label}:crisis:environment:{previous_variant or previous_shape or phase}",
                visible_shift_required=True,
            )

        if domain == "ansiedad_cognitiva":
            if previous_shape in {"grounding", "permission_phrase", "check_effect"}:
                action = "abre una nota y deja escrita una sola frase: que si requiere respuesta hoy"
                return self._goal(
                    goal="replace_rejected_strategy" if trigger == "rejection" else "change_modality_after_no_effect",
                    priority="emotional_safety",
                    guidance_level="high",
                    intervention_type="strategy_switch",
                    suggested_content=["cambiar del cuerpo a una accion visible", "dejar una sola tarea concreta", "no repetir regulacion"],
                    candidate_actions=[action],
                    possible_questions=[],
                    safety_constraints=["no_repetir_secuencia", "no_multiples_tareas_a_la_vez"],
                    keep_minimal=True,
                    should_offer_action=True,
                    should_offer_question=False,
                    selected_strategy="cambiar del cuerpo a una accion visible",
                    selected_microaction=action,
                    selected_routine_type=self.ROUTINE_BY_DOMAIN.get(domain),
                    priority_order=["cambio_de_modalidad", "accion_visible", "baja_carga"],
                    should_stay_with_validation=False,
                    response_shape="concrete_action",
                    domain_focus="accion visible para bajar ruido mental",
                    followup_policy="avoid",
                    intervention_level=max(level, 3),
                    form_variant="body_to_action",
                    strategy_signature=f"{trigger_label}:anxiety:body_to_action:{previous_variant or previous_shape or phase}",
                    visible_shift_required=True,
                )
            if previous_shape in {"single_action", "concrete_action", "direct_instruction", "strategy_switch"}:
                action = "decidelo asi: si no vence hoy, no entra hoy; si si vence hoy, te quedas solo con eso"
                return self._goal(
                    goal="replace_rejected_strategy" if trigger == "rejection" else "change_modality_after_no_effect",
                    priority="emotional_safety",
                    guidance_level="high",
                    intervention_type="strategy_switch",
                    suggested_content=["cambiar de tarea a decision cerrada", "bajar opciones", "no repetir la misma accion"],
                    candidate_actions=[action],
                    possible_questions=[],
                    safety_constraints=["no_repetir_secuencia", "no_abrir_mas_frentes"],
                    keep_minimal=True,
                    should_offer_action=True,
                    should_offer_question=False,
                    selected_strategy="cambiar de accion a decision cerrada",
                    selected_microaction=action,
                    selected_routine_type=self.ROUTINE_BY_DOMAIN.get(domain),
                    priority_order=["decision", "cambio_real", "baja_carga"],
                    should_stay_with_validation=False,
                    response_shape="guided_decision",
                    domain_focus="cerrar opciones y decidir una sola cosa",
                    followup_policy="avoid",
                    intervention_level=max(level, 3),
                    form_variant="action_to_decision",
                    strategy_signature=f"{trigger_label}:anxiety:action_to_decision:{previous_variant or previous_shape or phase}",
                    visible_shift_required=True,
                )
            action = "apoya los pies en el piso y suelta el aire mas largo una vez"
            return self._goal(
                goal="replace_rejected_strategy" if trigger == "rejection" else "change_modality_after_no_effect",
                priority="emotional_safety",
                guidance_level="high",
                intervention_type="strategy_switch",
                suggested_content=["salir de la decision y volver al cuerpo", "bajar activacion", "no seguir empujando lo mismo"],
                candidate_actions=[action],
                possible_questions=[],
                safety_constraints=["no_repetir_secuencia", "no_multiples_tareas_a_la_vez"],
                keep_minimal=True,
                should_offer_action=True,
                should_offer_question=False,
                selected_strategy="cambiar de decision a anclaje corporal",
                selected_microaction=action,
                selected_routine_type=self.ROUTINE_BY_DOMAIN.get(domain),
                priority_order=["cambio_de_modalidad", "cuerpo", "baja_carga"],
                should_stay_with_validation=True,
                response_shape="grounding",
                domain_focus="bajar activacion y volver al presente",
                followup_policy="avoid",
                intervention_level=max(level, 2),
                form_variant="decision_to_body",
                strategy_signature=f"{trigger_label}:anxiety:decision_to_body:{previous_variant or previous_shape or phase}",
                visible_shift_required=True,
            )

        if domain == "disfuncion_ejecutiva":
            if previous_shape in {"single_action", "concrete_action", "check_effect", "strategy_switch"}:
                action = "voy a cerrarte la decision: abre el archivo correcto y escribe solo el titulo"
                return self._goal(
                    goal="replace_rejected_strategy" if trigger == "rejection" else "change_modality_after_no_effect",
                    priority="functional_activation",
                    guidance_level="high",
                    intervention_type="strategy_switch",
                    suggested_content=["cambiar del arranque a una microdecision guiada", "cerrar opciones", "no repetir la misma orden"],
                    candidate_actions=[action],
                    possible_questions=[],
                    safety_constraints=["no_repetir_arranque", "no_hablar_en_abstracto"],
                    keep_minimal=True,
                    should_offer_action=True,
                    should_offer_question=False,
                    selected_strategy="cambiar del arranque a una microdecision guiada",
                    selected_microaction=action,
                    selected_routine_type=self.ROUTINE_BY_DOMAIN.get(domain),
                    priority_order=["microdecision", "cambio_de_via", "menos_friccion"],
                    should_stay_with_validation=False,
                    response_shape="guided_decision",
                    domain_focus="cerrar la decision para arrancar",
                    followup_policy="avoid",
                    intervention_level=max(level, 2),
                    form_variant="action_to_guided_decision",
                    strategy_signature=f"{trigger_label}:executive:action_to_decision:{previous_variant or previous_shape or phase}",
                    visible_shift_required=True,
                )
            action = "sin decidir mas, deja visible solo el material correcto y para ahi"
            return self._goal(
                goal="replace_rejected_strategy" if trigger == "rejection" else "change_modality_after_no_effect",
                priority="functional_activation",
                guidance_level="high",
                intervention_type="strategy_switch",
                suggested_content=["cambiar de decision a gesto visible", "mover una sola pieza", "no volver al mismo carril"],
                candidate_actions=[action],
                possible_questions=[],
                safety_constraints=["no_repetir_arranque", "no_retroceder_al_plan_completo"],
                keep_minimal=True,
                should_offer_action=True,
                should_offer_question=False,
                selected_strategy="cambiar de decision a gesto visible",
                selected_microaction=action,
                selected_routine_type=self.ROUTINE_BY_DOMAIN.get(domain),
                priority_order=["salida_visible", "cambio_de_via", "menos_friccion"],
                should_stay_with_validation=False,
                response_shape="single_action",
                domain_focus="mover una sola pieza visible",
                followup_policy="avoid",
                intervention_level=max(level, 2),
                form_variant="decision_to_visible_step",
                strategy_signature=f"{trigger_label}:executive:decision_to_action:{previous_variant or previous_shape or phase}",
                visible_shift_required=True,
            )

        action = "cambia de forma: toma una decision pequena ahora o para aqui por hoy"
        if previous_shape in {"guided_decision", "closure_pause", "hold_line"}:
            action = "vamos a dejarlo aqui por ahora y no abrir otra vuelta"
        return self._goal(
            goal="replace_rejected_strategy" if trigger == "rejection" else "change_modality_after_no_effect",
            priority="clarity",
            guidance_level="high",
            intervention_type="strategy_switch",
            suggested_content=["cambiar de modalidad real", "no repetir la misma ayuda", "dejar una salida breve y usable"],
            candidate_actions=[] if action.startswith("vamos a dejarlo aqui") else [action],
            possible_questions=[],
            safety_constraints=["no_repetir_misma_ayuda"],
            keep_minimal=True,
            should_offer_action=not action.startswith("vamos a dejarlo aqui"),
            should_offer_question=False,
            selected_strategy="cambiar de via ante rechazo o sin cambio",
            selected_microaction=None if action.startswith("vamos a dejarlo aqui") else action,
            selected_routine_type=self.ROUTINE_BY_DOMAIN.get(domain),
            priority_order=["cambio_de_via", "brevedad"],
            should_stay_with_validation=action.startswith("vamos a dejarlo aqui"),
            response_shape="closure_pause" if action.startswith("vamos a dejarlo aqui") else "guided_decision",
            domain_focus=self._domain_focus(domain),
            followup_policy="avoid",
            intervention_level=level,
            form_variant="generic_close" if action.startswith("vamos a dejarlo aqui") else "generic_decision_shift",
            strategy_signature=f"{trigger_label}:generic:{previous_variant or previous_shape or phase}",
            visible_shift_required=True,
        )

    def _repeated_post_action_resolution_goal(
        self,
        domain: str,
        phase: str,
        progression_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        previous_shape = str(progression_state.get("previous_response_shape") or "")
        previous_variant = str(progression_state.get("previous_form_variant") or "")
        level = max(self._goal_level(progression_state, minimum=2), 2)

        if domain == "ansiedad_cognitiva":
            action = "te la cierro asi: si esto no vence hoy, lo sueltas por ahora; si si vence hoy, te quedas solo con eso"
            return self._goal(
                goal="close_post_action_loop_with_decision",
                priority="emotional_safety",
                guidance_level="high",
                intervention_type="post_action_resolution",
                suggested_content=["cerrar el loop", "tomar una decision concreta", "no seguir empujando otro paso"],
                candidate_actions=[action],
                possible_questions=[],
                safety_constraints=["no_reabrir_la_secuencia"],
                keep_minimal=True,
                should_offer_action=True,
                should_offer_question=False,
                selected_strategy="cerrar el seguimiento con una decision concreta",
                selected_microaction=action,
                selected_routine_type=self.ROUTINE_BY_DOMAIN.get(domain),
                priority_order=["decision", "cierre", "baja_carga"],
                should_stay_with_validation=False,
                response_shape="guided_decision",
                domain_focus="cerrar opciones y soltar lo que no toca hoy",
                followup_policy="avoid",
                intervention_level=max(level, 3),
                form_variant="repeated_followup_decision",
                strategy_signature=f"post_action:anxiety:resolve_loop:{previous_variant or previous_shape or phase}",
                visible_shift_required=True,
            )

        if domain == "crisis_activa":
            close_line = "Aqui ya no hace falta meter otro paso. Mantente cerca, con pocas palabras, y para ahi."
            return self._goal(
                goal="close_post_action_loop",
                priority="physical_and_emotional_safety",
                guidance_level="high",
                intervention_type="post_action_resolution",
                suggested_content=[close_line, "cerrar el loop", "sostener seguridad sin agregar demanda"],
                candidate_actions=[],
                possible_questions=[],
                safety_constraints=["no_reabrir_la_secuencia", "no_sumar_demanda"],
                keep_minimal=True,
                should_offer_action=False,
                should_offer_question=False,
                selected_strategy="cerrar el seguimiento y sostener seguridad sin sumar otro paso",
                selected_microaction=None,
                selected_routine_type=self.ROUTINE_BY_DOMAIN.get(domain),
                priority_order=["cierre", "seguridad", "baja_demanda"],
                should_stay_with_validation=True,
                response_shape="closure_pause",
                domain_focus="seguridad y cierre temporal",
                followup_policy="avoid",
                intervention_level=max(level, 3),
                form_variant="repeated_followup_close",
                strategy_signature=f"post_action:crisis:resolve_loop:{previous_variant or previous_shape or phase}",
                visible_shift_required=True,
            )

        if domain == "disfuncion_ejecutiva":
            close_line = "Con lo que ya moviste alcanza por ahora. No hace falta sacar otro paso."
            return self._goal(
                goal="close_post_action_loop",
                priority="functional_activation",
                guidance_level="low",
                intervention_type="post_action_resolution",
                suggested_content=[close_line, "cerrar el loop", "dejar el movimiento como suficiente por ahora"],
                candidate_actions=[],
                possible_questions=[],
                safety_constraints=["no_reabrir_organizacion"],
                keep_minimal=True,
                should_offer_action=False,
                should_offer_question=False,
                selected_strategy="cerrar el arranque para que no se vuelva una cadena infinita",
                selected_microaction=None,
                selected_routine_type=self.ROUTINE_BY_DOMAIN.get(domain),
                priority_order=["cierre", "movimiento", "pausa"],
                should_stay_with_validation=True,
                response_shape="closure_pause",
                domain_focus="cierre despues de mover una pieza",
                followup_policy="avoid",
                intervention_level=max(level, 2),
                form_variant="repeated_followup_close",
                strategy_signature=f"post_action:executive:resolve_loop:{previous_variant or previous_shape or phase}",
                visible_shift_required=True,
            )

        close_line = "Con esto basta por ahora. No hace falta abrir otra vuelta."
        return self._goal(
            goal="close_post_action_loop",
            priority="clarity",
            guidance_level="low",
            intervention_type="post_action_resolution",
            suggested_content=[close_line, "cerrar el loop", "permitir pausar"],
            candidate_actions=[],
            possible_questions=[],
            safety_constraints=["no_repetir_ayuda"],
            keep_minimal=True,
            should_offer_action=False,
            should_offer_question=False,
            selected_strategy="cerrar despues de accion, seguimiento y ajuste",
            selected_microaction=None,
            selected_routine_type=self.ROUTINE_BY_DOMAIN.get(domain),
            priority_order=["cierre", "pausa"],
            should_stay_with_validation=True,
            response_shape="closure_pause",
            domain_focus=self._domain_focus(domain),
            followup_policy="avoid",
            intervention_level=level,
            form_variant="repeated_followup_close",
            strategy_signature=f"post_action:generic:resolve_loop:{previous_variant or previous_shape or phase}",
            visible_shift_required=True,
        )

    def _strategy_rejection_goal(
        self,
        domain: str,
        phase: str,
        source_message: str,
        progression_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        return self._distinct_strategy_goal(
            domain=domain,
            phase=phase,
            progression_state=progression_state,
            trigger="rejection",
        )

    def _outcome_report_goal(
        self,
        domain: str,
        phase: str,
        source_message: str,
        progression_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        outcome_status = self._outcome_status(progression_state) or "no_change"
        previous_shape = str(progression_state.get("previous_response_shape") or "")
        previous_variant = str(progression_state.get("previous_form_variant") or "")
        level = max(self._goal_level(progression_state, minimum=2), 2)

        if outcome_status == "worse":
            action = "para esa via y vuelve solo a menos demanda, menos palabras y menos estimulo"
            if domain == "ansiedad_cognitiva":
                action = "para esa via; no sigas escribiendo ni pensando mas y vuelve solo a apoyar pies, espalda o silencio breve"
            elif domain == "disfuncion_ejecutiva":
                action = "para el empuje; deja solo el material visible o cambia apenas la postura, y no pidas mas ahora"
            elif domain == "crisis_activa":
                action = "para de agregar pasos y vuelve a seguridad basica: distancia, menos gente y una sola frase si hace falta"
            return self._goal(
                goal="reevaluate_or_reduce_demand",
                priority="physical_and_emotional_safety" if domain == "crisis_activa" else "emotional_safety",
                guidance_level="high",
                intervention_type="outcome_followup",
                suggested_content=["si empeoro, no insistir con la misma via", "bajar exigencia inmediatamente", "reevaluar antes de seguir"],
                candidate_actions=[action],
                possible_questions=[],
                safety_constraints=["no_repetir_estrategia", "no_retroceder_a_protocolo_inicial"],
                keep_minimal=True,
                should_offer_action=True,
                should_offer_question=False,
                selected_strategy="reducir demanda cuando el resultado empeora",
                selected_microaction=action,
                selected_routine_type=self.ROUTINE_BY_DOMAIN.get(domain),
                priority_order=["bajar_demanda", "reevaluar", "seguridad"],
                should_stay_with_validation=False,
                response_shape="strategy_switch",
                domain_focus=self._domain_focus(domain),
                followup_policy="avoid",
                intervention_level=max(level, 2),
                form_variant="outcome_worse",
                strategy_signature=f"outcome:worse:{domain}:{previous_variant or previous_shape or phase}",
                visible_shift_required=True,
            )

        if outcome_status == "partial_relief":
            action = "si ya bajo un poco, sosten eso y no agregues otra cosa por ahora"
            if domain == "disfuncion_ejecutiva":
                action = "si ya hubo algo de arranque, deja solo el siguiente punto listo y para ahi"
            return self._goal(
                goal="hold_or_close_after_partial_effect",
                priority="emotional_safety",
                guidance_level="moderate",
                intervention_type="outcome_followup",
                suggested_content=["si funciono un poco, sostener sin abrir otra secuencia", "evitar sobreintervenir"],
                candidate_actions=[action],
                possible_questions=[],
                safety_constraints=["no_repetir_protocolo"],
                keep_minimal=True,
                should_offer_action=True,
                should_offer_question=False,
                selected_strategy="sostener una mejoria parcial sin volver al protocolo",
                selected_microaction=action,
                selected_routine_type=self.ROUTINE_BY_DOMAIN.get(domain),
                priority_order=["sostener", "no_sumar", "cierre_parcial"],
                should_stay_with_validation=True,
                response_shape="hold_line",
                domain_focus=self._domain_focus(domain),
                followup_policy="avoid",
                intervention_level=level,
                form_variant="partial_relief_hold",
                strategy_signature=f"outcome:partial:{domain}:{previous_variant or previous_shape or phase}",
                visible_shift_required=True,
            )

        if outcome_status == "improved":
            return self._goal(
                goal="hold_or_close_after_effect",
                priority="emotional_safety",
                guidance_level="low",
                intervention_type="outcome_followup",
                suggested_content=["si ya mejoro, cerrar sin seguir empujando", "no volver a abrir el protocolo"],
                candidate_actions=[],
                possible_questions=[],
                safety_constraints=["no_reabrir_la_intervencion"],
                keep_minimal=True,
                should_offer_action=False,
                should_offer_question=False,
                selected_strategy="cerrar despues de una mejoria clara",
                selected_microaction=None,
                selected_routine_type=self.ROUTINE_BY_DOMAIN.get(domain),
                priority_order=["cierre", "no_sumar", "mantener_efecto"],
                should_stay_with_validation=True,
                response_shape="closure_pause",
                domain_focus=self._domain_focus(domain),
                followup_policy="avoid",
                intervention_level=level,
                form_variant="improved_close",
                strategy_signature=f"outcome:improved:{domain}:{previous_variant or previous_shape or phase}",
                visible_shift_required=True,
            )

        return self._distinct_strategy_goal(
            domain=domain,
            phase=phase,
            progression_state=progression_state,
            trigger="no_change",
        )

    def _context_override_goal(
        self,
        domain: str,
        phase: str,
        turn_family: str,
        source_message: str,
        message_cues: Dict[str, bool],
        progression_state: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        override = self._context_override(progression_state)
        if not override.get("active"):
            return None

        if turn_family == "strategy_rejection":
            return self._strategy_rejection_goal(
                domain=domain,
                phase=phase,
                source_message=source_message,
                progression_state=progression_state,
            )

        if override.get("type") == "override_contextual":
            return self._contextual_override_goal(
                domain=domain,
                source_message=source_message,
                progression_state=progression_state,
            )
        if override.get("reason") == "explicit_action_completed":
            if domain == "ansiedad_cognitiva":
                return self._anxiety_override_goal(source_message=source_message, progression_state=progression_state)
            if domain == "disfuncion_ejecutiva":
                return self._executive_override_goal(source_message=source_message, progression_state=progression_state)
            return self._post_action_goal(domain=domain, phase=phase, progression_state=progression_state)
        if domain == "crisis_activa":
            return self._crisis_override_goal(source_message=source_message, progression_state=progression_state)
        if domain == "ansiedad_cognitiva":
            return self._anxiety_override_goal(source_message=source_message, progression_state=progression_state)
        if domain == "disfuncion_ejecutiva":
            return self._executive_override_goal(source_message=source_message, progression_state=progression_state)
        return self._generic_override_goal(domain=domain, source_message=source_message, progression_state=progression_state)

    def _crisis_override_goal(
        self,
        source_message: str,
        progression_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        override = self._context_override(progression_state)
        normalized = self._normalize(source_message)
        if override.get("reason", "").startswith("explicit_contradiction") or override.get("reason") == "explicit_invalidation":
            action = "deja de buscar mas estimulos para quitar y cambia a una sola frase breve con distancia segura"
            if "no puedo" in normalized:
                action = "si no puedes mover el entorno, usa una sola frase breve y baja la exigencia verbal"
            return self._goal(
                goal="replace_incompatible_crisis_step",
                priority="physical_and_emotional_safety",
                guidance_level="high",
                intervention_type="guided_crisis_alternative",
                suggested_content=["reemplazar la accion que no aplica", "mantener seguridad", "no repetir protocolo incompatible"],
                candidate_actions=[action],
                possible_questions=[],
                safety_constraints=["no_repetir_protocolo_incompatible", "no_analisis_extenso"],
                keep_minimal=True,
                should_offer_action=True,
                should_offer_question=False,
                selected_strategy="cambiar a una alternativa compatible con la realidad actual",
                selected_microaction=action,
                selected_routine_type=self.ROUTINE_BY_DOMAIN.get("crisis_activa"),
                priority_order=["seguridad", "alternativa_real", "baja_demanda"],
                should_stay_with_validation=False,
                response_shape="single_action",
                domain_focus="seguridad inmediata y alternativa compatible",
                followup_policy="avoid",
                intervention_level=max(self._goal_level(progression_state, minimum=2), 2),
                form_variant="alternative_step",
                strategy_signature=f"context_override:crisis:{override.get('reason')}:{override.get('target')}",
                visible_shift_required=True,
            )
        return self._goal(
            goal="hold_without_adding_demand",
            priority="physical_and_emotional_safety",
            guidance_level="high",
            intervention_type="guided_crisis_hold",
            suggested_content=["si la accion previa no sirve, bajar demanda", "no insistir con lo mismo", "sostener seguridad con menos carga"],
            candidate_actions=["si nada de eso cabe ahora, manten una sola frase breve y no agregues otra demanda"],
            possible_questions=[],
            safety_constraints=["no_repetir_protocolo_incompatible"],
            keep_minimal=True,
            should_offer_action=True,
            should_offer_question=False,
            selected_strategy="bajar exigencia cuando la accion previa no cabe",
            selected_microaction="si nada de eso cabe ahora, manten una sola frase breve y no agregues otra demanda",
            selected_routine_type=self.ROUTINE_BY_DOMAIN.get("crisis_activa"),
            priority_order=["seguridad", "baja_demanda", "alternativa_real"],
            should_stay_with_validation=True,
            response_shape="hold_line",
            domain_focus="seguridad inmediata sin insistir con lo mismo",
            followup_policy="avoid",
            intervention_level=max(self._goal_level(progression_state, minimum=2), 2),
            form_variant="hold_steady",
            strategy_signature=f"context_override:crisis:hold:{override.get('reason')}",
            visible_shift_required=True,
        )

    def _anxiety_override_goal(
        self,
        source_message: str,
        progression_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        override = self._context_override(progression_state)
        previous_shape = str(progression_state.get("previous_response_shape") or "")
        normalized = self._normalize(source_message)

        if override.get("reason") == "explicit_impossibility":
            action = "solo apoya la espalda o los pies donde puedas y afloja la mandibula una vez"
            if "ni levantarme" in normalized or "ni moverme" in normalized:
                return self._goal(
                    goal="hold_without_adding_demand",
                    priority="emotional_safety",
                    guidance_level="high",
                    intervention_type="anxiety_low_demand_override",
                    suggested_content=["bajar exigencia inmediatamente", "permitir no hacer mas", "quedarse en algo corporal minimo o en pausa"],
                    candidate_actions=[],
                    possible_questions=[],
                    safety_constraints=["no_insistir_con_la_misma_accion", "no_sobrecargar"],
                    keep_minimal=True,
                    should_offer_action=False,
                    should_offer_question=False,
                    selected_strategy="bajar exigencia porque ahora ni siquiera esa accion cabe",
                    selected_microaction=None,
                    selected_routine_type=self.ROUTINE_BY_DOMAIN.get("ansiedad_cognitiva"),
                    priority_order=["baja_exigencia", "pausa", "regulacion"],
                    should_stay_with_validation=True,
                    response_shape="permission_pause",
                    domain_focus="regular ansiedad con minima exigencia",
                    followup_policy="avoid",
                    intervention_level=1,
                    form_variant="permission_pause",
                    strategy_signature=f"context_override:anxiety:pause:{override.get('reason')}",
                    visible_shift_required=True,
                )
            return self._goal(
                goal="replace_impossible_anxiety_action",
                priority="emotional_safety",
                guidance_level="high",
                intervention_type="anxiety_override",
                suggested_content=["cambiar la accion por algo fisicamente posible", "no repetir escritura o tareas imposibles", "bajar exigencia ya"],
                candidate_actions=[action],
                possible_questions=[],
                safety_constraints=["no_repetir_la_misma_accion", "no_multiples_tareas_a_la_vez"],
                keep_minimal=True,
                should_offer_action=True,
                should_offer_question=False,
                selected_strategy="cambiar a una accion corporal minima y posible",
                selected_microaction=action,
                selected_routine_type=self.ROUTINE_BY_DOMAIN.get("ansiedad_cognitiva"),
                priority_order=["accion_posible", "baja_exigencia", "regulacion"],
                should_stay_with_validation=True,
                response_shape="grounding",
                domain_focus="regular ansiedad sin pedir una accion imposible",
                followup_policy="avoid",
                intervention_level=1,
                form_variant="soft_anchor",
                strategy_signature=f"context_override:anxiety:possible:{override.get('reason')}",
                visible_shift_required=True,
            )

        action = "deja de escribir por ahora y cambia de enfoque: mira tres cosas quietas a tu alrededor y suelta el aire una vez"
        if previous_shape in {"grounding", "permission_pause"}:
            action = "si el cuerpo ya lo intentaste, cambia a entorno: nombra tres cosas quietas que ves y para ahi"
        elif previous_shape in {"single_action", "concrete_action", "direct_instruction"}:
            action = "si ya probaste esa via, sal del pensamiento y cambia un minuto de lugar o moja tus manos"
        return self._goal(
            goal="give_next_distinct_step",
            priority="emotional_safety",
            guidance_level="high",
            intervention_type="anxiety_override",
            suggested_content=["no repetir lo ya intentado", "cambiar de canal entre cuerpo, entorno o pensamiento", "usar una sola alternativa"],
            candidate_actions=[action],
            possible_questions=[],
            safety_constraints=["no_repetir_la_misma_accion", "no_multiples_tareas_a_la_vez"],
            keep_minimal=True,
            should_offer_action=True,
            should_offer_question=False,
            selected_strategy="cambiar de enfoque cuando la accion previa no aplica o ya se hizo",
            selected_microaction=action,
            selected_routine_type=self.ROUTINE_BY_DOMAIN.get("ansiedad_cognitiva"),
            priority_order=["alternativa_real", "cambio_de_enfoque", "baja_exigencia"],
            should_stay_with_validation=False,
            response_shape="concrete_action",
            domain_focus="regular ansiedad con una alternativa distinta",
            followup_policy="avoid",
            intervention_level=max(self._goal_level(progression_state, minimum=2), 2),
            form_variant="override_alternative",
            strategy_signature=f"context_override:anxiety:{override.get('reason')}:{previous_shape or 'none'}",
            visible_shift_required=True,
        )

    def _executive_override_goal(
        self,
        source_message: str,
        progression_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        override = self._context_override(progression_state)
        normalized = self._normalize(source_message)

        if override.get("reason") == "explicit_impossibility":
            if "ni levantarme" in normalized or "ni moverme" in normalized:
                return self._goal(
                    goal="hold_without_adding_demand",
                    priority="functional_activation",
                    guidance_level="high",
                    intervention_type="executive_low_demand_override",
                    suggested_content=["bajar exigencia fisica de inmediato", "no pedir abrir nada", "permitir una accion minima o pausa"],
                    candidate_actions=["si solo sale esto, cambia apenas la postura o mueve una mano; si ni eso sale, no empujes mas ahora"],
                    possible_questions=[],
                    safety_constraints=["no_pedir_abrir_archivo", "no_sobrecargar"],
                    keep_minimal=True,
                    should_offer_action=True,
                    should_offer_question=False,
                    selected_strategy="reducir la accion a algo fisicamente posible",
                    selected_microaction="si solo sale esto, cambia apenas la postura o mueve una mano; si ni eso sale, no empujes mas ahora",
                    selected_routine_type=self.ROUTINE_BY_DOMAIN.get("disfuncion_ejecutiva"),
                    priority_order=["accion_posible", "baja_exigencia", "cuerpo"],
                    should_stay_with_validation=True,
                    response_shape="permission_pause",
                    domain_focus="arranque minimo y compatible con el estado real",
                    followup_policy="avoid",
                    intervention_level=1,
                    form_variant="permission_pause",
                    strategy_signature=f"context_override:executive:pause:{override.get('reason')}",
                    visible_shift_required=True,
                )
            return self._goal(
                goal="replace_impossible_executive_action",
                priority="functional_activation",
                guidance_level="high",
                intervention_type="executive_override",
                suggested_content=["cambiar a un arranque fisicamente posible", "no insistir con la misma accion", "bajar la friccion real"],
                candidate_actions=["si abrir algo no sale, nombra en voz baja la tarea o piensa solo el primer titulo"],
                possible_questions=[],
                safety_constraints=["no_pedir_abrir_archivo", "no_dar_muchos_pasos"],
                keep_minimal=True,
                should_offer_action=True,
                should_offer_question=False,
                selected_strategy="cambiar a un arranque posible segun el estado actual",
                selected_microaction="si abrir algo no sale, nombra en voz baja la tarea o piensa solo el primer titulo",
                selected_routine_type=self.ROUTINE_BY_DOMAIN.get("disfuncion_ejecutiva"),
                priority_order=["arranque_posible", "baja_friccion", "menos_exigencia"],
                should_stay_with_validation=False,
                response_shape="single_action",
                domain_focus="arranque compatible con la energia disponible",
                followup_policy="avoid",
                intervention_level=1,
                form_variant="override_smallest_start",
                strategy_signature=f"context_override:executive:possible:{override.get('reason')}",
                visible_shift_required=True,
            )

        return self._goal(
            goal="give_next_distinct_step",
            priority="functional_activation",
            guidance_level="high",
            intervention_type="executive_override",
            suggested_content=["no repetir la accion previa", "buscar una alternativa sin el recurso que falta", "mantener el arranque simple"],
            candidate_actions=["si ese recurso no esta, deja solo una salida mental o verbal: nombra la primera tarea y para ahi"],
            possible_questions=[],
            safety_constraints=["no_repetir_la_misma_accion", "no_dar_muchos_pasos"],
            keep_minimal=True,
            should_offer_action=True,
            should_offer_question=False,
            selected_strategy="dar una alternativa real cuando la accion previa no aplica o ya se hizo",
            selected_microaction="si ese recurso no esta, deja solo una salida mental o verbal: nombra la primera tarea y para ahi",
            selected_routine_type=self.ROUTINE_BY_DOMAIN.get("disfuncion_ejecutiva"),
            priority_order=["alternativa_real", "arranque", "baja_friccion"],
            should_stay_with_validation=False,
            response_shape="concrete_action",
            domain_focus="arranque y friccion con una alternativa real",
            followup_policy="avoid",
            intervention_level=max(self._goal_level(progression_state, minimum=2), 2),
            form_variant="override_alternative",
            strategy_signature=f"context_override:executive:{override.get('reason')}",
            visible_shift_required=True,
        )

    def _generic_override_goal(
        self,
        domain: str,
        source_message: str,
        progression_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        override = self._context_override(progression_state)
        if override.get("reason") == "explicit_impossibility":
            return self._goal(
                goal="hold_without_adding_demand",
                priority="clarity",
                guidance_level="high",
                intervention_type="generic_override",
                suggested_content=["bajar exigencia porque lo anterior no cabe", "no insistir con la misma accion"],
                candidate_actions=[],
                possible_questions=[],
                safety_constraints=["no_insistir_con_la_misma_accion"],
                keep_minimal=True,
                should_offer_action=False,
                should_offer_question=False,
                selected_strategy="bajar exigencia cuando el turno actual invalida la accion previa",
                selected_microaction=None,
                selected_routine_type=self.ROUTINE_BY_DOMAIN.get(domain),
                priority_order=["baja_exigencia", "claridad"],
                should_stay_with_validation=True,
                response_shape="permission_pause",
                domain_focus=self._domain_focus(domain),
                followup_policy="avoid",
                intervention_level=1,
                form_variant="permission_pause",
                strategy_signature=f"context_override:generic:pause:{override.get('reason')}",
                visible_shift_required=True,
            )
        return self._goal(
            goal="give_next_distinct_step",
            priority="clarity",
            guidance_level="high",
            intervention_type="generic_override",
            suggested_content=["recalcular la ayuda desde el mensaje actual", "no repetir la accion previa"],
            candidate_actions=["deja una sola alternativa compatible con lo que acabas de decir"],
            possible_questions=[],
            safety_constraints=["no_repetir_la_misma_accion"],
            keep_minimal=True,
            should_offer_action=True,
            should_offer_question=False,
            selected_strategy="recalcular la ayuda segun la informacion nueva",
            selected_microaction="deja una sola alternativa compatible con lo que acabas de decir",
            selected_routine_type=self.ROUTINE_BY_DOMAIN.get(domain),
            priority_order=["alternativa_real", "claridad"],
            should_stay_with_validation=False,
            response_shape="single_action",
            domain_focus=self._domain_focus(domain),
            followup_policy="avoid",
            intervention_level=max(self._goal_level(progression_state, minimum=1), 1),
            form_variant="override_alternative",
            strategy_signature=f"context_override:generic:{override.get('reason')}",
            visible_shift_required=True,
        )

    def _contextual_override_goal(
        self,
        domain: str,
        source_message: str,
        progression_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        override = self._context_override(progression_state)
        normalized = self._normalize(source_message)
        reason = str(override.get("reason") or "")

        if reason == "contextual_condition_answer" and domain == "disfuncion_ejecutiva":
            return self._goal(
                goal="anchor_new_context_before_action",
                priority="functional_activation",
                guidance_level="moderate",
                intervention_type="contextual_override",
                suggested_content=["tomar en cuenta la condicion actual", "no pedir una accion incompatible", "bajar el arranque a algo posible"],
                candidate_actions=["entonces no voy a pedirte abrir nada: si puedes, deja solo una referencia mental del primer paso"],
                possible_questions=[],
                safety_constraints=["no_pedir_una_accion_incompatible"],
                keep_minimal=True,
                should_offer_action=True,
                should_offer_question=False,
                selected_strategy="ajustar la accion al estado corporal actual",
                selected_microaction="entonces no voy a pedirte abrir nada: si puedes, deja solo una referencia mental del primer paso",
                selected_routine_type=self.ROUTINE_BY_DOMAIN.get(domain),
                priority_order=["contexto_actual", "accion_compatible", "baja_exigencia"],
                should_stay_with_validation=False,
                response_shape="single_action",
                domain_focus="arranque y friccion ajustados al estado actual",
                followup_policy="avoid",
                intervention_level=1,
                form_variant="contextual_adjustment",
                strategy_signature=f"context_override:contextual:{domain}:{reason}",
                visible_shift_required=True,
            )

        if reason == "contextual_time_answer" and domain == "ansiedad_cognitiva":
            return self._goal(
                goal="anchor_new_context_before_action",
                priority="emotional_safety",
                guidance_level="moderate",
                intervention_type="contextual_override",
                suggested_content=["usar el momento del dia como foco real", "no hablar en general", "dejar una accion ligada a esa franja"],
                candidate_actions=["entonces piensa solo en esa franja: deja una sola descarga breve antes de la tarde y no en todo el dia"],
                possible_questions=[],
                safety_constraints=["no_generalizar_demasiado"],
                keep_minimal=True,
                should_offer_action=True,
                should_offer_question=False,
                selected_strategy="ajustar la ayuda al momento real en que pega mas",
                selected_microaction="entonces piensa solo en esa franja: deja una sola descarga breve antes de la tarde y no en todo el dia",
                selected_routine_type=self.ROUTINE_BY_DOMAIN.get(domain),
                priority_order=["contexto_actual", "accion_ajustada", "baja_carga"],
                should_stay_with_validation=False,
                response_shape="single_action",
                domain_focus="regular ansiedad segun el momento real",
                followup_policy="avoid",
                intervention_level=max(self._goal_level(progression_state, minimum=1), 1),
                form_variant="contextual_adjustment",
                strategy_signature=f"context_override:contextual:{domain}:{reason}",
                visible_shift_required=True,
            )

        if reason == "contextual_time_answer" and domain == "sueno_regulacion":
            return self._goal(
                goal="anchor_new_context_before_action",
                priority="regulation",
                guidance_level="moderate",
                intervention_type="contextual_override",
                suggested_content=["usar esa franja horaria como foco", "no responder como si fuera toda la jornada"],
                candidate_actions=["entonces el foco es esa hora: prepara una sola bajada de activacion antes de la tarde"],
                possible_questions=[],
                safety_constraints=["no_generalizar_demasiado"],
                keep_minimal=True,
                should_offer_action=True,
                should_offer_question=False,
                selected_strategy="ajustar el apoyo al momento real que mencionaste",
                selected_microaction="entonces el foco es esa hora: prepara una sola bajada de activacion antes de la tarde",
                selected_routine_type=self.ROUTINE_BY_DOMAIN.get(domain),
                priority_order=["contexto_actual", "descanso", "accion_ajustada"],
                should_stay_with_validation=False,
                response_shape="single_action",
                domain_focus="descanso ajustado al momento real",
                followup_policy="avoid",
                intervention_level=1,
                form_variant="contextual_adjustment",
                strategy_signature=f"context_override:contextual:{domain}:{reason}",
                visible_shift_required=True,
            )

        if reason == "contextual_location_answer":
            return self._goal(
                goal="anchor_new_context_before_action",
                priority="clarity",
                guidance_level="moderate",
                intervention_type="contextual_override",
                suggested_content=["usar el lugar real como referencia", "no responder en abstracto"],
                candidate_actions=["entonces ajustemos eso ahi: cambia una sola cosa del lugar donde pasa, no de todo el contexto"],
                possible_questions=[],
                safety_constraints=["no_generalizar_demasiado"],
                keep_minimal=True,
                should_offer_action=True,
                should_offer_question=False,
                selected_strategy="anclar la ayuda al lugar real que acabas de dar",
                selected_microaction="entonces ajustemos eso ahi: cambia una sola cosa del lugar donde pasa, no de todo el contexto",
                selected_routine_type=self.ROUTINE_BY_DOMAIN.get(domain),
                priority_order=["contexto_actual", "ajuste_local"],
                should_stay_with_validation=False,
                response_shape="single_action",
                domain_focus=self._domain_focus(domain),
                followup_policy="avoid",
                intervention_level=max(self._goal_level(progression_state, minimum=1), 1),
                form_variant="contextual_adjustment",
                strategy_signature=f"context_override:contextual:{domain}:{reason}",
                visible_shift_required=True,
            )

        if reason == "contextual_numeric_answer":
            value = next((token for token in normalized.split() if token.isdigit()), "ese numero")
            return self._goal(
                goal="anchor_new_context_before_action",
                priority="clarity",
                guidance_level="low",
                intervention_type="contextual_override",
                suggested_content=[f"tomo {value} como referencia actual", "usar ese dato y no ignorarlo"],
                candidate_actions=[],
                possible_questions=[],
                safety_constraints=["no_ignorar_el_dato_actual"],
                keep_minimal=True,
                should_offer_action=False,
                should_offer_question=False,
                selected_strategy="integrar el dato corto al contexto actual",
                selected_microaction=None,
                selected_routine_type=self.ROUTINE_BY_DOMAIN.get(domain),
                priority_order=["contexto_actual", "referencia"],
                should_stay_with_validation=False,
                response_shape="simple_answer",
                domain_focus=self._domain_focus(domain),
                followup_policy="avoid",
                intervention_level=max(self._goal_level(progression_state, minimum=1), 1),
                form_variant="contextual_number",
                strategy_signature=f"context_override:contextual:{domain}:{reason}",
                visible_shift_required=True,
            )

        return self._goal(
            goal="anchor_new_context_before_action",
            priority="clarity",
            guidance_level="moderate",
            intervention_type="contextual_override",
            suggested_content=["tomar en cuenta lo nuevo que acabas de decir", "ajustar la respuesta desde ahi"],
            candidate_actions=["voy a ajustar el siguiente paso a ese contexto y no al anterior tal cual"],
            possible_questions=[],
            safety_constraints=["no_ignorar_el_contexto_actual"],
            keep_minimal=True,
            should_offer_action=True,
            should_offer_question=False,
            selected_strategy="anclar la ayuda al contexto nuevo sin romper la coherencia",
            selected_microaction="voy a ajustar el siguiente paso a ese contexto y no al anterior tal cual",
            selected_routine_type=self.ROUTINE_BY_DOMAIN.get(domain),
            priority_order=["contexto_actual", "ajuste"],
            should_stay_with_validation=False,
            response_shape="single_action",
            domain_focus=self._domain_focus(domain),
            followup_policy="avoid",
            intervention_level=max(self._goal_level(progression_state, minimum=1), 1),
            form_variant="contextual_adjustment",
            strategy_signature=f"context_override:contextual:{domain}:{reason}",
            visible_shift_required=True,
        )

    def _post_action_goal(
        self,
        domain: str,
        phase: str,
        progression_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        if self._has_repeated_post_action_followup(progression_state):
            return self._repeated_post_action_resolution_goal(
                domain=domain,
                phase=phase,
                progression_state=progression_state,
            )
        if domain == "crisis_activa":
            return self._crisis_post_action_goal(phase=phase, progression_state=progression_state)
        if domain == "ansiedad_cognitiva":
            return self._anxiety_post_action_goal(phase=phase, progression_state=progression_state)
        if domain == "disfuncion_ejecutiva":
            return self._executive_post_action_goal(phase=phase, progression_state=progression_state)
        return self._generic_post_action_goal(domain=domain, phase=phase, progression_state=progression_state)

    def _crisis_post_action_goal(self, phase: str, progression_state: Dict[str, Any]) -> Dict[str, Any]:
        previous_shape = str(progression_state.get("previous_response_shape") or "")
        previous_variant = str(progression_state.get("previous_form_variant") or "")
        level = max(self._goal_level(progression_state, minimum=3), 3)

        if previous_variant not in {"effect_scan", "hold_steady", "close_after_action"}:
            return self._goal(
                goal="check_effect_after_step",
                priority="physical_and_emotional_safety",
                guidance_level="high",
                intervention_type="post_action_check",
                suggested_content=["verificar si el entorno bajo o sigue igual", "mirar seguridad antes de agregar otra cosa", "no repetir la lista anterior"],
                candidate_actions=["mira solo si hay menos ruido, menos tension o mas espacio que hace un minuto"],
                possible_questions=[],
                safety_constraints=["no_repetir_protocolo", "no_sumar_demanda"],
                keep_minimal=True,
                should_offer_action=True,
                should_offer_question=False,
                selected_strategy="pasar de la accion a una verificacion breve de seguridad",
                selected_microaction="mira solo si hay menos ruido, menos tension o mas espacio que hace un minuto",
                selected_routine_type=self.ROUTINE_BY_DOMAIN.get("crisis_activa"),
                priority_order=["seguridad", "verificar_efecto", "baja_demanda"],
                should_stay_with_validation=False,
                response_shape="check_effect",
                domain_focus="seguridad inmediata y observacion breve",
                followup_policy="avoid",
                intervention_level=level,
                form_variant="effect_scan",
                strategy_signature=f"post_action:crisis:check_effect:{previous_shape or phase}",
                visible_shift_required=True,
            )
        if previous_variant == "effect_scan":
            return self._goal(
                goal="hold_without_adding_demand",
                priority="physical_and_emotional_safety",
                guidance_level="high",
                intervention_type="post_action_hold",
                suggested_content=["si bajo un poco, no sumar otra exigencia", "mantener una frase breve o silencio", "sostener seguridad sin reiniciar el protocolo"],
                candidate_actions=["si ya bajo un poco, repite una frase breve y no agregues nada mas por ahora"],
                possible_questions=[],
                safety_constraints=["no_repetir_protocolo", "no_subir_exigencia"],
                keep_minimal=True,
                should_offer_action=True,
                should_offer_question=False,
                selected_strategy="sostener sin agregar demanda despues del primer protocolo",
                selected_microaction="si ya bajo un poco, repite una frase breve y no agregues nada mas por ahora",
                selected_routine_type=self.ROUTINE_BY_DOMAIN.get("crisis_activa"),
                priority_order=["seguridad", "sostener", "pausa"],
                should_stay_with_validation=True,
                response_shape="hold_line",
                domain_focus="seguridad inmediata y no agregar mas demanda",
                followup_policy="avoid",
                intervention_level=level,
                form_variant="hold_steady",
                strategy_signature=f"post_action:crisis:hold:{previous_shape or phase}",
                visible_shift_required=True,
            )
        return self._goal(
            goal="give_next_distinct_step",
            priority="physical_and_emotional_safety",
            guidance_level="high",
            intervention_type="post_action_next_step",
            suggested_content=["dar un siguiente paso distinto si todavia hace falta", "ajustar seguridad sin repetir la lista anterior", "seguir con una sola accion"],
            candidate_actions=["si no bajo nada, mueve a la persona o la situacion a un punto con menos gente o menos ruido"],
            possible_questions=[],
            safety_constraints=["no_repetir_protocolo", "no_abrir_analisis"],
            keep_minimal=True,
            should_offer_action=True,
            should_offer_question=False,
            selected_strategy="dar un siguiente paso distinto en lugar de reciclar el protocolo",
            selected_microaction="si no bajo nada, mueve a la persona o la situacion a un punto con menos gente o menos ruido",
            selected_routine_type=self.ROUTINE_BY_DOMAIN.get("crisis_activa"),
            priority_order=["seguridad", "siguiente_paso", "cambio_real"],
            should_stay_with_validation=False,
            response_shape="single_action",
            domain_focus="seguridad inmediata y ajuste puntual",
            followup_policy="avoid",
            intervention_level=level,
            form_variant="adjust_safety_step",
            strategy_signature=f"post_action:crisis:next_step:{previous_variant or previous_shape or phase}",
            visible_shift_required=True,
        )

    def _anxiety_post_action_goal(self, phase: str, progression_state: Dict[str, Any]) -> Dict[str, Any]:
        previous_shape = str(progression_state.get("previous_response_shape") or "")
        previous_variant = str(progression_state.get("previous_form_variant") or "")
        level = max(self._goal_level(progression_state, minimum=2), 2)

        if previous_variant not in {"effect_scan", "stop_or_continue", "close_with_permission", "next_distinct_step"}:
            return self._goal(
                goal="check_effect_after_step",
                priority="emotional_safety",
                guidance_level="moderate",
                intervention_type="post_action_check",
                suggested_content=["mirar si bajo un poco la activacion", "no repetir la misma escritura o descarga", "medir efecto antes de seguir"],
                candidate_actions=["fijate solo en esto: la presion bajo un poco, sigue igual o subio"],
                possible_questions=[],
                safety_constraints=["no_repetir_secuencia", "no_sumar_mas_tareas"],
                keep_minimal=True,
                should_offer_action=True,
                should_offer_question=False,
                selected_strategy="verificar efecto antes de seguir agregando pasos",
                selected_microaction="fijate solo en esto: la presion bajo un poco, sigue igual o subio",
                selected_routine_type=self.ROUTINE_BY_DOMAIN.get("ansiedad_cognitiva"),
                priority_order=["verificar_efecto", "baja_activacion", "no_repetir"],
                should_stay_with_validation=False,
                response_shape="check_effect",
                domain_focus="regular ansiedad y medir efecto",
                followup_policy="avoid",
                intervention_level=level,
                form_variant="effect_scan",
                strategy_signature=f"post_action:anxiety:check_effect:{previous_shape or phase}",
                visible_shift_required=True,
            )
        if previous_variant == "effect_scan":
            return self._goal(
                goal="decide_stop_or_continue",
                priority="emotional_safety",
                guidance_level="high",
                intervention_type="post_action_decision",
                suggested_content=["decidir si esto requiere accion hoy o no", "cerrar carga cognitiva", "no volver a la misma secuencia"],
                candidate_actions=["decidelo asi: si eso no vence hoy, lo dejas quieto; si si vence hoy, te quedas solo con esa"],
                possible_questions=[],
                safety_constraints=["no_repetir_secuencia", "no_abrir_mas_frentes"],
                keep_minimal=True,
                should_offer_action=True,
                should_offer_question=False,
                selected_strategy="pasar de regular a decidir si seguir o parar",
                selected_microaction="decidelo asi: si eso no vence hoy, lo dejas quieto; si si vence hoy, te quedas solo con esa",
                selected_routine_type=self.ROUTINE_BY_DOMAIN.get("ansiedad_cognitiva"),
                priority_order=["decision", "baja_carga", "cierre_opciones"],
                should_stay_with_validation=False,
                response_shape="guided_decision",
                domain_focus="decidir si seguir o parar",
                followup_policy="avoid",
                intervention_level=max(level, 4),
                form_variant="stop_or_continue",
                strategy_signature=f"post_action:anxiety:stop_continue:{previous_shape or phase}",
                visible_shift_required=True,
            )
        if previous_variant == "stop_or_continue":
            return self._goal(
                goal="close_after_action",
                priority="emotional_safety",
                guidance_level="low",
                intervention_type="post_action_close",
                suggested_content=["cerrar con permiso de parar", "no seguir cargando la conversacion", "dejar claro que con eso basta"],
                candidate_actions=[],
                possible_questions=[],
                safety_constraints=["no_reabrir_la_intervencion"],
                keep_minimal=True,
                should_offer_action=False,
                should_offer_question=False,
                selected_strategy="cerrar con permiso de parar despues de decidir",
                selected_microaction=None,
                selected_routine_type=self.ROUTINE_BY_DOMAIN.get("ansiedad_cognitiva"),
                priority_order=["cierre", "permiso", "baja_carga"],
                should_stay_with_validation=True,
                response_shape="closure_pause",
                domain_focus="cierre y permiso de parar",
                followup_policy="avoid",
                intervention_level=level,
                form_variant="close_with_permission",
                strategy_signature=f"post_action:anxiety:close:{previous_shape or phase}",
                visible_shift_required=True,
            )
        return self._goal(
            goal="give_next_distinct_step",
            priority="emotional_safety",
            guidance_level="high",
            intervention_type="post_action_next_step",
            suggested_content=["dar un paso distinto al anterior", "dejar una sola decision o accion nueva", "no volver a escribir lo mismo"],
            candidate_actions=["si sigue apretando, deja una sola preocupacion que requiera accion hoy y todo lo demas fuera por ahora"],
            possible_questions=[],
            safety_constraints=["no_repetir_secuencia", "no_multiples_tareas_a_la_vez"],
            keep_minimal=True,
            should_offer_action=True,
            should_offer_question=False,
            selected_strategy="dar un siguiente paso distinto cuando la primera descarga no alcanza",
            selected_microaction="si sigue apretando, deja una sola preocupacion que requiera accion hoy y todo lo demas fuera por ahora",
            selected_routine_type=self.ROUTINE_BY_DOMAIN.get("ansiedad_cognitiva"),
            priority_order=["siguiente_paso", "decision", "cambio_de_forma"],
            should_stay_with_validation=False,
            response_shape="concrete_action",
            domain_focus="paso distinto para bajar ruido mental",
            followup_policy="avoid",
            intervention_level=max(level, 3),
            form_variant="next_distinct_step",
            strategy_signature=f"post_action:anxiety:next_step:{previous_variant or previous_shape or phase}",
            visible_shift_required=True,
        )

    def _executive_post_action_goal(self, phase: str, progression_state: Dict[str, Any]) -> Dict[str, Any]:
        previous_shape = str(progression_state.get("previous_response_shape") or "")
        previous_variant = str(progression_state.get("previous_form_variant") or "")
        level = max(self._goal_level(progression_state, minimum=2), 2)

        if previous_variant not in {"effect_scan_exec", "next_distinct_step", "close_arranque"}:
            return self._goal(
                goal="check_effect_after_step",
                priority="functional_activation",
                guidance_level="moderate",
                intervention_type="post_action_check",
                suggested_content=["ver si ya hubo arranque visible", "no repetir la misma orden", "medir si hace falta seguir"],
                candidate_actions=["mira solo si ya quedo algo visible: un archivo abierto, un titulo puesto o una primera linea escrita"],
                possible_questions=[],
                safety_constraints=["no_repetir_orden", "no_abrir_organizacion_larga"],
                keep_minimal=True,
                should_offer_action=True,
                should_offer_question=False,
                selected_strategy="verificar si el arranque ya ocurrio antes de dar otra orden",
                selected_microaction="mira solo si ya quedo algo visible: un archivo abierto, un titulo puesto o una primera linea escrita",
                selected_routine_type=self.ROUTINE_BY_DOMAIN.get("disfuncion_ejecutiva"),
                priority_order=["verificar_efecto", "arranque_visible", "brevedad"],
                should_stay_with_validation=False,
                response_shape="check_effect",
                domain_focus="arranque visible y verificacion breve",
                followup_policy="avoid",
                intervention_level=level,
                form_variant="effect_scan_exec",
                strategy_signature=f"post_action:executive:check_effect:{previous_shape or phase}",
                visible_shift_required=True,
            )
        if previous_variant == "effect_scan_exec":
            return self._goal(
                goal="give_next_distinct_step",
                priority="functional_activation",
                guidance_level="high",
                intervention_type="post_action_next_step",
                suggested_content=["dar el siguiente paso distinto", "seguir moviendo sin volver al mismo arranque", "cerrar otra vez las opciones"],
                candidate_actions=["si ya arrancaste, deja listo solo el siguiente punto o la siguiente linea y para ahi"],
                possible_questions=[],
                safety_constraints=["no_repetir_orden", "no_hablar_en_abstracto"],
                keep_minimal=True,
                should_offer_action=True,
                should_offer_question=False,
                selected_strategy="pasar del arranque a un siguiente paso distinto y concreto",
                selected_microaction="si ya arrancaste, deja listo solo el siguiente punto o la siguiente linea y para ahi",
                selected_routine_type=self.ROUTINE_BY_DOMAIN.get("disfuncion_ejecutiva"),
                priority_order=["siguiente_paso", "salida_visible", "cambio_real"],
                should_stay_with_validation=False,
                response_shape="concrete_action",
                domain_focus="siguiente paso visible sin repetir el arranque",
                followup_policy="avoid",
                intervention_level=max(level, 3),
                form_variant="next_distinct_step",
                strategy_signature=f"post_action:executive:next_step:{previous_shape or phase}",
                visible_shift_required=True,
            )
        return self._goal(
            goal="close_after_action",
            priority="functional_activation",
            guidance_level="low",
            intervention_type="post_action_close",
            suggested_content=["cerrar cuando ya hubo movimiento", "no convertir el arranque en una cadena infinita", "dar permiso de parar"],
            candidate_actions=[],
            possible_questions=[],
            safety_constraints=["no_reabrir_organizacion"],
            keep_minimal=True,
            should_offer_action=False,
            should_offer_question=False,
            selected_strategy="cerrar despues del arranque sin seguir empujando",
            selected_microaction=None,
            selected_routine_type=self.ROUTINE_BY_DOMAIN.get("disfuncion_ejecutiva"),
            priority_order=["cierre", "movimiento", "pausa"],
            should_stay_with_validation=True,
            response_shape="closure_pause",
            domain_focus="cierre despues de mover una pieza",
            followup_policy="avoid",
            intervention_level=level,
            form_variant="close_arranque",
            strategy_signature=f"post_action:executive:close:{previous_variant or previous_shape or phase}",
            visible_shift_required=True,
        )

    def _generic_post_action_goal(
        self,
        domain: str,
        phase: str,
        progression_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        previous_shape = str(progression_state.get("previous_response_shape") or "")
        previous_variant = str(progression_state.get("previous_form_variant") or "")
        if previous_variant != "generic_effect_scan":
            return self._goal(
                goal="check_effect_after_step",
                priority="clarity",
                guidance_level="moderate",
                intervention_type="post_action_check",
                suggested_content=["ver si lo anterior sirvio", "no repetir la misma ayuda", "seguir solo si hace falta"],
                candidate_actions=["mira solo si lo de antes ayudo un poco o si no movio nada"],
                possible_questions=[],
                safety_constraints=["no_repetir_ayuda"],
                keep_minimal=True,
                should_offer_action=True,
                should_offer_question=False,
                selected_strategy="verificar efecto antes de seguir",
                selected_microaction="mira solo si lo de antes ayudo un poco o si no movio nada",
                selected_routine_type=self.ROUTINE_BY_DOMAIN.get(domain),
                priority_order=["verificar_efecto", "claridad", "brevedad"],
                should_stay_with_validation=False,
                response_shape="check_effect",
                domain_focus=self._domain_focus(domain),
                followup_policy="avoid",
                intervention_level=self._goal_level(progression_state, minimum=1),
                form_variant="generic_effect_scan",
                strategy_signature=f"post_action:generic:check_effect:{previous_shape or phase}",
                visible_shift_required=True,
            )
        return self._goal(
            goal="close_after_action",
            priority="clarity",
            guidance_level="low",
            intervention_type="post_action_close",
            suggested_content=["cerrar sin repetir lo mismo", "permitir pausar"],
            candidate_actions=[],
            possible_questions=[],
            safety_constraints=["no_repetir_ayuda"],
            keep_minimal=True,
            should_offer_action=False,
            should_offer_question=False,
            selected_strategy="cerrar despues de verificar el efecto",
            selected_microaction=None,
            selected_routine_type=self.ROUTINE_BY_DOMAIN.get(domain),
            priority_order=["cierre", "pausa"],
            should_stay_with_validation=True,
            response_shape="closure_pause",
            domain_focus=self._domain_focus(domain),
            followup_policy="avoid",
            intervention_level=self._goal_level(progression_state, minimum=1),
            form_variant="close_after_action",
            strategy_signature=f"post_action:generic:close:{previous_variant or previous_shape or phase}",
            visible_shift_required=True,
        )

    def _crisis_goal(
        self,
        phase: str,
        turn_family: str,
        crisis_guided_mode: str,
        source_message: str,
        message_cues: Dict[str, bool],
        progression_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        literal_phrase = self._literal_crisis_phrase(source_message)
        level = self._goal_level(progression_state, minimum=1)
        stuck_followup_count = int(progression_state.get("stuck_followup_count", 0) or 0)
        flags = self._progression_flags(progression_state)
        if turn_family == "post_action_followup":
            return self._post_action_goal(
                domain="crisis_activa",
                phase=phase,
                progression_state=progression_state,
            )
        if message_cues.get("asks_literal_phrase") and literal_phrase:
            return self._goal(
                goal="give_literal_crisis_phrase",
                priority="physical_and_emotional_safety",
                guidance_level="high",
                intervention_type="guided_crisis_phrase",
                suggested_content=["dar una frase breve usable", "bajar estimulos y demanda", "no discutir en ese momento"],
                candidate_actions=["decir una sola frase breve y luego guardar silencio unos segundos"],
                possible_questions=[],
                safety_constraints=["no_analisis_extenso", "no_preguntas_abiertas", "no_dar_muchas_opciones"],
                keep_minimal=True,
                should_offer_action=True,
                should_offer_question=False,
                selected_strategy="dar una frase literal breve y reguladora",
                selected_microaction="decir una sola frase breve y luego guardar silencio unos segundos",
                selected_routine_type=self.ROUTINE_BY_DOMAIN.get("crisis_activa"),
                priority_order=["seguridad", "frase_literal", "baja_demanda"],
                should_stay_with_validation=False,
                allow_literal_phrase=True,
                literal_phrase_candidates=[literal_phrase],
                response_shape="literal_phrase",
                domain_focus="seguridad inmediata y contencion",
                followup_policy="avoid",
                intervention_level=max(level, 4),
                form_variant="literal_then_pause",
            )

        if level >= 5 or (flags.get("persistent_block") and stuck_followup_count >= 2):
            return self._goal(
                goal="direct_crisis_instruction_now",
                priority="physical_and_emotional_safety",
                guidance_level="high",
                intervention_type="guided_crisis_protocol",
                suggested_content=["dar instrucciones directas y seguras", "reducir entorno y demanda", "no abrir analisis"],
                candidate_actions=[
                    "aparta una sola fuente de ruido, gente o exigencia",
                    "ponte de lado, deja espacio y no discutas",
                    "repite una sola frase breve y espera unos segundos",
                ],
                possible_questions=[],
                safety_constraints=["no_analisis_extenso", "no_preguntas_abiertas", "no_dar_muchas_opciones"],
                keep_minimal=True,
                should_offer_action=True,
                should_offer_question=False,
                selected_strategy="dar un protocolo corto y directo",
                selected_microaction="aparta una sola fuente de ruido, gente o exigencia",
                selected_routine_type=self.ROUTINE_BY_DOMAIN.get("crisis_activa"),
                priority_order=["seguridad", "instruccion_directa", "baja_demanda"],
                should_stay_with_validation=False,
                allow_literal_phrase=bool(literal_phrase),
                literal_phrase_candidates=[literal_phrase] if literal_phrase else [],
                response_shape="direct_instruction",
                domain_focus="seguridad inmediata y accion directa",
                followup_policy="avoid",
                intervention_level=5,
                form_variant="directive_steps",
            )

        if message_cues.get("asks_where_to_start") or message_cues.get("asks_what_now") or level >= 4:
            return self._goal(
                goal="choose_first_safe_crisis_step",
                priority="physical_and_emotional_safety",
                guidance_level="high",
                intervention_type="guided_crisis_start",
                suggested_content=["elegir un solo primer paso seguro", "bajar demanda alrededor", "evitar discutir en ese momento"],
                candidate_actions=[
                    "quita una fuente de ruido, exigencia o gente alrededor",
                    "ponte de lado, deja espacio y usa pocas palabras",
                ],
                possible_questions=[],
                safety_constraints=["no_analisis_extenso", "no_preguntas_abiertas", "no_dar_muchas_opciones"],
                keep_minimal=True,
                should_offer_action=True,
                should_offer_question=False,
                selected_strategy="dar un primer paso seguro y concreto",
                selected_microaction="quita una fuente de ruido, exigencia o gente alrededor",
                selected_routine_type=self.ROUTINE_BY_DOMAIN.get("crisis_activa"),
                priority_order=["seguridad", "primer_paso", "baja_demanda"],
                should_stay_with_validation=False,
                response_shape="single_action",
                domain_focus="seguridad inmediata y reduccion de demanda",
                followup_policy="avoid",
                intervention_level=max(level, 3),
                form_variant="immediate_step",
            )

        if crisis_guided_mode == "guided_steps" or phase == "guided_steps" or level >= 3:
            return self._goal(
                goal="guide_safe_steps_now",
                priority="physical_and_emotional_safety",
                guidance_level="high",
                intervention_type="guided_crisis_support",
                suggested_content=["bajar demanda alrededor", "proteger seguridad inmediata", "dar pasos cortos y concretos"],
                candidate_actions=[
                    "lleva la situacion a un lugar con menos ruido o demanda",
                    "mantén distancia segura y no discutas en ese momento",
                    "usa una sola frase breve y repetible",
                ],
                possible_questions=[],
                safety_constraints=["no_analisis_extenso", "no_preguntas_abiertas", "no_dar_muchas_opciones"],
                keep_minimal=True,
                should_offer_action=True,
                should_offer_question=False,
                selected_strategy="pasar de contencion general a guia segura y concreta",
                selected_microaction="lleva la situacion a un lugar con menos ruido o demanda",
                selected_routine_type=self.ROUTINE_BY_DOMAIN.get("crisis_activa"),
                priority_order=["seguridad", "demanda_baja", "guia_concreta"],
                should_stay_with_validation=False,
                allow_literal_phrase=bool(literal_phrase),
                literal_phrase_candidates=[literal_phrase] if literal_phrase else [],
                response_shape="guided_steps",
                domain_focus="seguridad inmediata y guia concreta",
                followup_policy="avoid",
                intervention_level=max(level, 3),
                form_variant="directive_steps",
            )
        return self._goal(
            goal="contain_and_protect_now",
            priority="physical_and_emotional_safety",
            guidance_level="high",
            intervention_type="crisis_containment",
            suggested_content=["contener primero", "bajar estimulos y demanda", "proteger sin razonar demasiado"],
            candidate_actions=["bajar una fuente de estimulo cercana", "mantener voz y frases muy breves"],
            possible_questions=[],
            safety_constraints=["no_reflexionar_en_plena_crisis", "no_dar_listas_largas", "no_subir_exigencia"],
            keep_minimal=True,
            should_offer_action=True,
            should_offer_question=False,
            selected_strategy="contener sin aumentar intensidad",
            selected_microaction="bajar una fuente de estimulo cercana",
            selected_routine_type=self.ROUTINE_BY_DOMAIN.get("crisis_activa"),
            priority_order=["seguridad", "contencion", "baja_demanda"],
            should_stay_with_validation=True,
            response_shape="crisis_containment",
            domain_focus="seguridad inmediata y contencion",
            followup_policy="avoid",
            intervention_level=1,
            form_variant="containment_brief",
        )

    def _anxiety_goal(
        self,
        phase: str,
        turn_type: str,
        turn_family: str,
        support_plan: Dict[str, Any],
        source_message: str,
        message_cues: Dict[str, bool],
        progression_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        level = self._goal_level(progression_state, minimum=1)
        flags = self._progression_flags(progression_state)
        repeat_count = int(progression_state.get("strategy_repeat_count", 0) or 0)
        if turn_family == "post_action_followup":
            return self._post_action_goal(
                domain="ansiedad_cognitiva",
                phase=phase,
                progression_state=progression_state,
            )
        if turn_family == "specific_action_request" and level < 3:
            level = 3
        if turn_family == "literal_phrase_request":
            return self._literal_phrase_goal(domain="ansiedad_cognitiva", progression_state=progression_state)
        if message_cues.get("expresses_uncertainty") and turn_family not in {"specific_action_request", "literal_phrase_request"}:
            return self._uncertainty_goal(
                domain="ansiedad_cognitiva",
                source_message=source_message,
                progression_state=progression_state,
            )

        if level <= 1:
            return self._goal(
                goal="lower_anxiety_demand_now",
                priority="emotional_safety",
                guidance_level="high",
                intervention_type="anxiety_regulation",
                suggested_content=["bajar activacion primero", "no pedir claridad extra", "elegir una sola accion reguladora"],
                candidate_actions=["apoya los pies en el piso y suelta el aire mas largo una vez"],
                possible_questions=[],
                safety_constraints=["no_pedir_resolver_todo", "no_multiples_tareas_a_la_vez"],
                keep_minimal=True,
                should_offer_action=True,
                should_offer_question=False,
                selected_strategy="bajar exigencia y elegir un anclaje por la persona",
                selected_microaction="apoya los pies en el piso y suelta el aire mas largo una vez",
                selected_routine_type=self.ROUTINE_BY_DOMAIN.get("ansiedad_cognitiva"),
                priority_order=["regulacion", "baja_exigencia", "anclaje"],
                should_stay_with_validation=True,
                response_shape="grounding",
                domain_focus="bajar activacion y volver al presente",
                followup_policy="avoid",
                intervention_level=1,
                form_variant="soft_anchor",
            )

        if level == 2:
            return self._goal(
                goal="shift_anxiety_into_one_action",
                priority="emotional_safety",
                guidance_level="moderate",
                intervention_type="anxiety_support",
                suggested_content=["salir de la espiral con una sola accion", "no abrir mas opciones", "hacer algo visible"],
                candidate_actions=["anota en una sola frase lo que mas te aprieta ahora"],
                possible_questions=[],
                safety_constraints=["no_pedir_resolver_todo", "no_multiples_tareas_a_la_vez"],
                keep_minimal=False,
                should_offer_action=True,
                should_offer_question=False,
                selected_strategy="pasar de regulacion a una accion visible",
                selected_microaction="anota en una sola frase lo que mas te aprieta ahora",
                selected_routine_type=self.ROUTINE_BY_DOMAIN.get("ansiedad_cognitiva"),
                priority_order=["regulacion", "accion_visible", "cierre_opciones"],
                should_stay_with_validation=False,
                response_shape="single_action",
                domain_focus="salir de la espiral con una accion",
                followup_policy="avoid",
                intervention_level=2,
                form_variant="action_pivot",
            )

        if level == 3:
            return self._goal(
                goal="convert_anxiety_into_concrete_action",
                priority="emotional_safety",
                guidance_level="high",
                intervention_type="anxiety_support",
                suggested_content=["dar una accion concreta", "cerrar la espiral con una instruccion clara", "no volver a pedir claridad"],
                candidate_actions=["abre una nota y escribe solo esto: lo que mas me aprieta ahora es ____"],
                possible_questions=[],
                safety_constraints=["no_pedir_resolver_todo", "no_multiples_tareas_a_la_vez"],
                keep_minimal=False,
                should_offer_action=True,
                should_offer_question=False,
                selected_strategy="aterrizar una accion concreta antes de seguir hablando",
                selected_microaction="abre una nota y escribe solo esto: lo que mas me aprieta ahora es ____",
                selected_routine_type=self.ROUTINE_BY_DOMAIN.get("ansiedad_cognitiva"),
                priority_order=["accion_concreta", "baja_exigencia", "presente"],
                should_stay_with_validation=False,
                response_shape="concrete_action",
                domain_focus="accion concreta para cortar la espiral",
                followup_policy="avoid",
                intervention_level=3,
                form_variant="concrete_direct",
            )

        if level == 4:
            return self._goal(
                goal="make_one_anxiety_decision_for_user",
                priority="emotional_safety",
                guidance_level="high",
                intervention_type="anxiety_support",
                suggested_content=["elegir una sola decision por la persona", "dejar lo demas quieto", "bajar carga cognitiva"],
                candidate_actions=["deja quietas las demas pendientes y quedate solo con la que vence primero hoy"],
                possible_questions=[],
                safety_constraints=["no_pedir_resolver_todo", "no_multiples_tareas_a_la_vez"],
                keep_minimal=False,
                should_offer_action=True,
                should_offer_question=False,
                selected_strategy="tomar una decision guiada por la persona",
                selected_microaction="deja quietas las demas pendientes y quedate solo con la que vence primero hoy",
                selected_routine_type=self.ROUTINE_BY_DOMAIN.get("ansiedad_cognitiva"),
                priority_order=["decision_guiada", "baja_carga", "un_foco"],
                should_stay_with_validation=False,
                response_shape="guided_decision",
                domain_focus="una sola decision para bajar ruido mental",
                followup_policy="avoid",
                intervention_level=4,
                form_variant="decision_taken",
            )

        if repeat_count >= 1 or flags.get("avoid_strategy_loop"):
            return self._goal(
                goal="direct_anxiety_command_line",
                priority="emotional_safety",
                guidance_level="high",
                intervention_type="anxiety_support",
                suggested_content=["cambiar el formato visible", "dejar una instruccion unica", "no repetir la misma secuencia"],
                candidate_actions=["deja quieto todo lo demas y escribe una sola preocupacion en una frase"],
                possible_questions=[],
                safety_constraints=["no_pedir_resolver_todo", "no_multiples_tareas_a_la_vez"],
                keep_minimal=False,
                should_offer_action=True,
                should_offer_question=False,
                selected_strategy="cambiar a una orden unica para evitar repetir la misma secuencia",
                selected_microaction="deja quieto todo lo demas y escribe una sola preocupacion en una frase",
                selected_routine_type=self.ROUTINE_BY_DOMAIN.get("ansiedad_cognitiva"),
                priority_order=["instruccion_directa", "una_orden", "cambio_de_forma"],
                should_stay_with_validation=False,
                response_shape="concrete_action",
                domain_focus="instruccion unica para salir de la espiral",
                followup_policy="avoid",
                intervention_level=5,
                form_variant="command_line",
            )

        return self._goal(
            goal="direct_anxiety_instruction_now",
            priority="emotional_safety",
            guidance_level="high",
            intervention_type="anxiety_support",
            suggested_content=["dar instruccion directa sin rodeo", "cerrar opciones por la persona", "cortar la espiral con una secuencia corta"],
            candidate_actions=[
                "cierra lo demas que tengas abierto",
                "escribe una sola frase con lo que mas te aprieta",
                "vuelve al aire largo una vez y para ahi",
            ],
            possible_questions=[],
            safety_constraints=["no_pedir_resolver_todo", "no_multiples_tareas_a_la_vez"],
            keep_minimal=False,
            should_offer_action=True,
            should_offer_question=False,
            selected_strategy="dar instruccion directa porque la regulacion suave ya no alcanza",
            selected_microaction="cierra lo demas que tengas abierto",
            selected_routine_type=self.ROUTINE_BY_DOMAIN.get("ansiedad_cognitiva"),
            priority_order=["instruccion_directa", "cierre_opciones", "baja_activacion"],
            should_stay_with_validation=False,
            response_shape="direct_instruction",
            domain_focus="instruccion directa para salir de la espiral",
            followup_policy="avoid",
            intervention_level=5,
            form_variant="directive_now",
        )

    def _executive_goal(
        self,
        phase: str,
        turn_type: str,
        turn_family: str,
        support_plan: Dict[str, Any],
        source_message: str,
        message_cues: Dict[str, bool],
        progression_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        level = self._goal_level(progression_state, minimum=1)
        repeat_count = int(progression_state.get("strategy_repeat_count", 0) or 0)
        if turn_family == "post_action_followup":
            return self._post_action_goal(
                domain="disfuncion_ejecutiva",
                phase=phase,
                progression_state=progression_state,
            )
        if turn_family == "specific_action_request" and level < 2:
            level = 2
        if turn_family == "literal_phrase_request":
            return self._literal_phrase_goal(domain="disfuncion_ejecutiva", progression_state=progression_state)
        if message_cues.get("expresses_uncertainty") and turn_family not in {"specific_action_request", "literal_phrase_request"}:
            return self._uncertainty_goal(
                domain="disfuncion_ejecutiva",
                source_message=source_message,
                progression_state=progression_state,
            )

        if level <= 1:
            return self._goal(
                goal="choose_first_executive_step",
                priority="functional_activation",
                guidance_level="high",
                intervention_type="executive_support",
                suggested_content=["elegir un solo arranque visible", "bajar friccion", "no pedir que organice todo primero"],
                candidate_actions=["abre solo el archivo, cuaderno o material que toca"],
                possible_questions=[],
                safety_constraints=["no_dar_muchos_pasos", "no_hablar_en_abstracto"],
                keep_minimal=True,
                should_offer_action=True,
                should_offer_question=False,
                selected_strategy="elegir un primer gesto visible por la persona",
                selected_microaction="abre solo el archivo, cuaderno o material que toca",
                selected_routine_type=self.ROUTINE_BY_DOMAIN.get("disfuncion_ejecutiva"),
                priority_order=["friccion_baja", "primer_paso", "arranque"],
                should_stay_with_validation=False,
                response_shape="single_action",
                domain_focus="arranque y friccion",
                followup_policy="avoid",
                intervention_level=1,
                form_variant="visible_start",
            )

        if level == 2:
            return self._goal(
                goal="reduce_startup_friction",
                priority="functional_activation",
                guidance_level="moderate",
                intervention_type="executive_support",
                suggested_content=["quitar obstaculos del arranque", "dejar una sola accion disponible", "cerrar opciones"],
                candidate_actions=["deja abierto solo el material que toca y aparta lo demas"],
                possible_questions=[],
                safety_constraints=["no_dar_muchos_pasos", "no_hablar_en_abstracto"],
                keep_minimal=False,
                should_offer_action=True,
                should_offer_question=False,
                selected_strategy="cerrar friccion antes de pedir mas",
                selected_microaction="deja abierto solo el material que toca y aparta lo demas",
                selected_routine_type=self.ROUTINE_BY_DOMAIN.get("disfuncion_ejecutiva"),
                priority_order=["friccion_baja", "arranque", "cierre_opciones"],
                should_stay_with_validation=False,
                response_shape="concrete_action",
                domain_focus="arranque visible y menos friccion",
                followup_policy="avoid",
                intervention_level=2,
                form_variant="friction_cut",
            )

        if level == 3:
            return self._goal(
                goal="force_first_output",
                priority="functional_activation",
                guidance_level="high",
                intervention_type="executive_support",
                suggested_content=["pasar de preparar a hacer", "dejar una instruccion corta", "evitar seguir pensando en organizar"],
                candidate_actions=["escribe solo el titulo o la primera linea, aunque quede fea"],
                possible_questions=[],
                safety_constraints=["no_dar_muchos_pasos", "no_hablar_en_abstracto"],
                keep_minimal=False,
                should_offer_action=True,
                should_offer_question=False,
                selected_strategy="forzar una primera salida visible",
                selected_microaction="escribe solo el titulo o la primera linea, aunque quede fea",
                selected_routine_type=self.ROUTINE_BY_DOMAIN.get("disfuncion_ejecutiva"),
                priority_order=["salida_visible", "arranque", "menos_analisis"],
                should_stay_with_validation=False,
                response_shape="direct_instruction",
                domain_focus="dejar una salida visible ahora",
                followup_policy="avoid",
                intervention_level=3,
                form_variant="direct_start",
            )

        if level == 4:
            return self._goal(
                goal="make_one_executive_decision_for_user",
                priority="functional_activation",
                guidance_level="high",
                intervention_type="executive_support",
                suggested_content=["elegir el arranque por la persona", "cerrar decision", "evitar volver a ordenar todo"],
                candidate_actions=["voy a elegirte el arranque: abre el material y escribe solo un encabezado"],
                possible_questions=[],
                safety_constraints=["no_dar_muchos_pasos", "no_hablar_en_abstracto"],
                keep_minimal=False,
                should_offer_action=True,
                should_offer_question=False,
                selected_strategy="tomar la decision inicial por la persona",
                selected_microaction="abre el material y escribe solo un encabezado",
                selected_routine_type=self.ROUTINE_BY_DOMAIN.get("disfuncion_ejecutiva"),
                priority_order=["decision_guiada", "arranque", "cierre_opciones"],
                should_stay_with_validation=False,
                response_shape="guided_decision",
                domain_focus="decision guiada y arranque",
                followup_policy="avoid",
                intervention_level=4,
                form_variant="decision_taken",
            )

        if repeat_count >= 1:
            return self._goal(
                goal="direct_executive_command_line",
                priority="functional_activation",
                guidance_level="high",
                intervention_type="executive_support",
                suggested_content=["cambiar la forma visible", "dejar una sola orden exacta", "evitar repetir la misma secuencia"],
                candidate_actions=["abre el material y escribe solo el primer punto ahora mismo"],
                possible_questions=[],
                safety_constraints=["no_dar_muchos_pasos", "no_hablar_en_abstracto"],
                keep_minimal=False,
                should_offer_action=True,
                should_offer_question=False,
                selected_strategy="cambiar a una orden unica para romper el bucle",
                selected_microaction="abre el material y escribe solo el primer punto ahora mismo",
                selected_routine_type=self.ROUTINE_BY_DOMAIN.get("disfuncion_ejecutiva"),
                priority_order=["instruccion_directa", "una_orden", "cambio_de_forma"],
                should_stay_with_validation=False,
                response_shape="concrete_action",
                domain_focus="orden unica para arrancar",
                followup_policy="avoid",
                intervention_level=5,
                form_variant="command_line",
            )

        return self._goal(
            goal="direct_executive_instruction_now",
            priority="functional_activation",
            guidance_level="high",
            intervention_type="executive_support",
            suggested_content=["dar una secuencia exacta y corta", "pasar del bloqueo a movimiento", "no pedir organizacion previa"],
            candidate_actions=[
                "abre el material que toca",
                "escribe el titulo o primer punto",
                "deja el cursor listo en la siguiente linea",
            ],
            possible_questions=[],
            safety_constraints=["no_dar_muchos_pasos", "no_hablar_en_abstracto"],
            keep_minimal=False,
            should_offer_action=True,
            should_offer_question=False,
            selected_strategy="dar una secuencia directa porque el microarranque ya no alcanza",
            selected_microaction="abre el material que toca",
            selected_routine_type=self.ROUTINE_BY_DOMAIN.get("disfuncion_ejecutiva"),
            priority_order=["instruccion_directa", "movimiento", "cierre_opciones"],
            should_stay_with_validation=False,
            response_shape="direct_instruction",
            domain_focus="instruccion directa para arrancar",
            followup_policy="avoid",
            intervention_level=5,
            form_variant="directive_now",
        )

    def _sleep_goal(
        self,
        phase: str,
        turn_type: str,
        turn_family: str,
        support_plan: Dict[str, Any],
        source_message: str,
        message_cues: Dict[str, bool],
        progression_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        if turn_family == "post_action_followup":
            return self._post_action_goal(domain="sueno_regulacion", phase=phase, progression_state=progression_state)
        if message_cues.get("expresses_uncertainty") or message_cues.get("asks_what_now"):
            return self._goal(
                goal="lower_sleep_activation_now",
                priority="regulation",
                guidance_level="high",
                intervention_type="sleep_support",
                suggested_content=["bajar activacion primero", "hacer la transicion simple", "no intentar resolver toda la noche ahora"],
                candidate_actions=["baja una sola fuente de luz, ruido o pantalla antes de acostarte"],
                possible_questions=[],
                safety_constraints=["no_sobrecargar", "no_activar_mas"],
                keep_minimal=True,
                should_offer_action=True,
                should_offer_question=False,
                selected_strategy="dejar un solo ajuste de descanso",
                selected_microaction="baja una sola fuente de luz, ruido o pantalla antes de acostarte",
                selected_routine_type=self.ROUTINE_BY_DOMAIN.get("sueno_regulacion"),
                priority_order=["descanso", "baja_activacion", "simplicidad"],
                should_stay_with_validation=True,
                response_shape="sleep_settle",
                domain_focus="descanso y bajada de activacion",
                followup_policy="avoid",
            )

        phase_map = {
            "sleep_scan": (
                "identify_sleep_friction",
                ["detectar que esta activando mas", "diferenciar cansancio de activacion", "bajar complejidad"],
                ["nombra que esta costando mas: apagar mente, ruido o cuerpo activado"],
                "sleep_scan",
                turn_type == "new_request",
            ),
            "wind_down": (
                "support_sleep_transition",
                ["preparar bajada gradual", "reducir una fuente de activacion", "hacer la transicion simple"],
                ["baja una sola fuente de estimulo antes de acostarte"],
                "sleep_settle",
                False,
            ),
            "reduce_activation": (
                "lower_night_activation",
                ["reducir activacion fisiologica", "bajar ritmo", "evitar mas carga"],
                ["haz una sola accion tranquila y repetible durante dos minutos"],
                "sleep_settle",
                False,
            ),
            "protect_next_sleep_window": (
                "protect_next_rest_window",
                ["cuidar la siguiente ventana de descanso", "quitar un saboteador frecuente", "dejar un cierre simple"],
                ["deja decidido un solo ajuste para la proxima noche"],
                "single_action",
                False,
            ),
        }
        goal, suggested_content, candidate_actions, response_shape, should_offer_question = phase_map.get(
            phase,
            phase_map["sleep_scan"],
        )
        questions = ["Que parte del descanso te esta costando mas ahora mismo?"] if should_offer_question else []
        return self._goal(
            goal,
            "regulation",
            "moderate",
            "sleep_support",
            suggested_content,
            candidate_actions,
            questions,
            ["no_sobrecargar", "no_activar_mas"],
            True,
            True,
            bool(questions),
            suggested_content[0],
            candidate_actions[0],
            self.ROUTINE_BY_DOMAIN.get("sueno_regulacion"),
            ["scan", "bajar_activacion", "proteger_descanso"],
            phase == "sleep_scan",
            response_shape=response_shape,
            domain_focus="descanso y activacion",
            followup_policy="brief_check" if questions else "avoid",
        )

    def _caregiver_goal(
        self,
        phase: str,
        turn_type: str,
        turn_family: str,
        support_plan: Dict[str, Any],
        source_message: str,
        message_cues: Dict[str, bool],
        progression_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        if turn_family == "post_action_followup":
            return self._post_action_goal(domain="sobrecarga_cuidador", phase=phase, progression_state=progression_state)
        if message_cues.get("expresses_uncertainty") or message_cues.get("asks_what_now"):
            return self._goal(
                goal="reduce_caregiver_demand_now",
                priority="emotional_safety",
                guidance_level="high",
                intervention_type="caregiver_support",
                suggested_content=["bajar autoexigencia", "soltar una carga", "no pedir mas decision ahora"],
                candidate_actions=["deja una sola cosa para despues sin resolverla hoy"],
                possible_questions=[],
                safety_constraints=["no_culpabilizar", "no_dar_listas_largas"],
                keep_minimal=True,
                should_offer_action=True,
                should_offer_question=False,
                selected_strategy="aliviar una carga primero",
                selected_microaction="deja una sola cosa para despues sin resolverla hoy",
                selected_routine_type=self.ROUTINE_BY_DOMAIN.get("sobrecarga_cuidador"),
                priority_order=["descarga", "baja_exigencia", "aire"],
                should_stay_with_validation=True,
                response_shape="load_relief",
                domain_focus="alivio de carga",
                followup_policy="avoid",
            )

        phase_map = {
            "relief": (
                "reduce_caregiver_load",
                ["validar desgaste real", "bajar autoexigencia", "evitar pedir demasiado"],
                ["nombrar una sola cosa que hoy puede esperar"],
                "load_relief",
                True,
            ),
            "single_priority": (
                "choose_one_caregiver_priority",
                ["dejar una sola prioridad viva", "cerrar lo secundario", "recuperar margen"],
                ["elegir solo lo mas importante para las proximas horas"],
                "single_action",
                False,
            ),
            "release_one_load": (
                "release_one_load_now",
                ["soltar una carga", "reducir demanda", "ganar un poco de aire"],
                ["quitar o delegar una sola tarea no esencial"],
                "load_relief",
                True,
            ),
            "protect_capacity": (
                "protect_remaining_capacity",
                ["cuidar energia disponible", "poner un limite simple", "prevenir desborde"],
                ["decirle no a una sola exigencia que no cabe hoy"],
                "single_action",
                True,
            ),
        }
        goal, suggested_content, candidate_actions, response_shape, validation_only = phase_map.get(
            phase,
            phase_map["relief"],
        )
        return self._goal(
            goal,
            "emotional_safety",
            "moderate",
            "caregiver_support",
            suggested_content,
            candidate_actions,
            [],
            ["no_culpabilizar", "no_dar_listas_largas"],
            True,
            True,
            False,
            suggested_content[0],
            candidate_actions[0],
            self.ROUTINE_BY_DOMAIN.get("sobrecarga_cuidador"),
            ["descarga", "prioridad_unica", "capacidad"],
            validation_only,
            response_shape=response_shape,
            domain_focus="alivio de carga",
            followup_policy="avoid",
        )

    def _prevention_goal(
        self,
        phase: str,
        turn_type: str,
        turn_family: str,
        support_plan: Dict[str, Any],
        source_message: str,
        message_cues: Dict[str, bool],
        progression_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        if turn_family == "post_action_followup":
            return self._post_action_goal(domain="prevencion_escalada", phase=phase, progression_state=progression_state)
        phase_map = {
            "mapping_signals": ("detect_early_signal", ["ubicar primera senal", "hacer visible el inicio de la subida", "mirar antes del pico"], ["nombrar la primera senal que suele aparecer"]),
            "pattern_detection": ("identify_pattern", ["ver detonante y secuencia", "quitar vaguedad", "dar una referencia util"], ["identificar que suele pasar justo antes del cambio"]),
            "prepare_early_response": ("prepare_early_response", ["dejar una respuesta temprana lista", "reducir improvisacion", "hacerla repetible"], ["decidir una sola respuesta para usar apenas aparezca la senal"]),
            "stabilize_plan": ("stabilize_prevention_plan", ["cerrar un mini plan", "dejarlo breve", "hacerlo sostenible"], ["anotar esa respuesta en una frase breve"]),
        }
        goal, suggested_content, candidate_actions = phase_map.get(phase, phase_map["mapping_signals"])
        return self._goal(
            goal,
            "predictability",
            "moderate",
            "prevention_support",
            suggested_content,
            candidate_actions,
            [],
            ["no_multiples_planes"],
            True,
            True,
            False,
            suggested_content[0],
            candidate_actions[0],
            self.ROUTINE_BY_DOMAIN.get("prevencion_escalada"),
            ["senal", "respuesta_temprana", "plan_simple"],
            False,
            response_shape="single_action",
            domain_focus="senal temprana y respuesta temprana",
            followup_policy="avoid",
        )

    def _sensory_goal(
        self,
        phase: str,
        turn_type: str,
        turn_family: str,
        support_plan: Dict[str, Any],
        source_message: str,
        message_cues: Dict[str, bool],
        progression_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        if turn_family == "post_action_followup":
            return self._post_action_goal(domain="sobrecarga_sensorial", phase=phase, progression_state=progression_state)
        phase_map = {
            "environment_adjustment": ("reduce_stimulus_load", ["bajar carga sensorial", "no discutir demasiado", "priorizar entorno"], ["bajar un estimulo concreto ahora mismo"]),
            "identify_main_trigger": ("identify_main_stimulus", ["detectar estimulo dominante", "evitar cambiar todo a la vez", "hacerlo mas claro"], ["decir que molesta mas: ruido, luz, movimiento o gente"]),
            "reduce_one_stimulus": ("remove_one_stimulus", ["quitar solo uno", "probar impacto rapido", "mantener simplicidad"], ["quitar o bajar solo el estimulo que mas pesa"]),
            "stabilize_reference": ("leave_reference", ["dejar una referencia repetible", "hacerlo predecible", "sostener regulacion"], ["dejar una frase o accion que sirva como senal de pausa"]),
        }
        goal, suggested_content, candidate_actions = phase_map.get(phase, phase_map["environment_adjustment"])
        return self._goal(
            goal,
            "regulation",
            "moderate",
            "sensory_support",
            suggested_content,
            candidate_actions,
            [],
            ["no_aumentar_estimulos", "no_forzar_contacto"],
            True,
            True,
            False,
            suggested_content[0],
            candidate_actions[0],
            self.ROUTINE_BY_DOMAIN.get("sobrecarga_sensorial"),
            ["estimulo", "entorno", "referencia"],
            False,
            response_shape="single_action",
            domain_focus="bajar estimulos",
            followup_policy="avoid",
        )

    def _transition_goal(
        self,
        phase: str,
        turn_type: str,
        turn_family: str,
        support_plan: Dict[str, Any],
        source_message: str,
        message_cues: Dict[str, bool],
        progression_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        if turn_family == "post_action_followup":
            return self._post_action_goal(domain="transicion_rigidez", phase=phase, progression_state=progression_state)
        phase_map = {
            "anticipation": ("prepare_for_change", ["anticipar lo que viene", "bajar sorpresa", "dar previsibilidad"], ["decir en una frase que va a pasar despues"]),
            "make_transition_script": ("create_transition_script", ["crear guion breve", "hacer el cambio mas predecible", "reducir ambiguedad"], ["usar siempre la misma frase para anunciar el cambio"]),
            "first_transition_step": ("support_first_transition_step", ["definir primer paso visible", "no dar muchas instrucciones", "hacerlo manejable"], ["pedir solo el primer movimiento del cambio"]),
            "stabilize_transition": ("stabilize_transition_pattern", ["repetir estructura", "conservar previsibilidad", "dejar referencia clara"], ["cerrar la transicion con la misma referencia breve de siempre"]),
        }
        goal, suggested_content, candidate_actions = phase_map.get(phase, phase_map["anticipation"])
        return self._goal(
            goal,
            "predictability",
            "moderate",
            "transition_support",
            suggested_content,
            candidate_actions,
            [],
            ["no_mensajes_ambiguos", "no_cambiar_sin_avisar"],
            True,
            True,
            False,
            suggested_content[0],
            candidate_actions[0],
            self.ROUTINE_BY_DOMAIN.get("transicion_rigidez"),
            ["anticipacion", "guion", "primer_paso"],
            False,
            allow_literal_phrase=True,
            literal_phrase_candidates=["Ahora termina esto. Luego va lo siguiente."],
            response_shape="single_action",
            domain_focus="previsibilidad y guion breve",
            followup_policy="avoid",
        )

    def _escalation_goal(
        self,
        phase: str,
        turn_type: str,
        turn_family: str,
        support_plan: Dict[str, Any],
        source_message: str,
        message_cues: Dict[str, bool],
        progression_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        if turn_family == "post_action_followup":
            return self._post_action_goal(domain="escalada_emocional", phase=phase, progression_state=progression_state)
        return self._goal(
            "deescalate_before_peak",
            "emotional_safety",
            "moderate",
            "deescalation_support",
            ["identificar el cambio mas temprano", "bajar una demanda", "hacer la respuesta repetible"],
            ["quitar una sola demanda apenas aparezca la primera senal"],
            [],
            ["no_subir_exigencia"],
            True,
            True,
            False,
            "bajar una demanda ante la primera senal",
            "quitar una sola demanda apenas aparezca la primera senal",
            self.ROUTINE_BY_DOMAIN.get("escalada_emocional"),
            ["senal_temprana", "baja_demanda", "repeticion"],
            False,
            response_shape="single_action",
            domain_focus="senal temprana y baja demanda",
            followup_policy="avoid",
        )

    def _post_event_goal(
        self,
        phase: str,
        turn_type: str,
        turn_family: str,
        support_plan: Dict[str, Any],
        source_message: str,
        message_cues: Dict[str, bool],
        progression_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        if turn_family == "post_action_followup":
            return self._post_action_goal(domain="regulacion_post_evento", phase=phase, progression_state=progression_state)
        return self._goal(
            "repair_and_learn",
            "repair",
            "moderate",
            "post_event_support",
            ["hablarlo con calma", "rescatar una sola senal util", "dejar un puente para la proxima vez"],
            ["rescatar una sola senal que avisa antes de que todo suba"],
            [],
            ["no_culpa", "no_reconstruir_todo"],
            False,
            True,
            False,
            "rescatar una senal util para la proxima vez",
            "rescatar una sola senal que avisa antes de que todo suba",
            self.ROUTINE_BY_DOMAIN.get("regulacion_post_evento"),
            ["reparacion", "aprendizaje", "puente"],
            True,
            response_shape="single_action",
            domain_focus="reparacion y aprendizaje breve",
            followup_policy="avoid",
        )

    def _general_goal(
        self,
        detected_intent: Optional[str],
        primary_state: Optional[str],
        turn_family: str,
        routine_payload: Dict[str, Any],
        source_message: str,
        message_cues: Dict[str, bool],
        progression_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        level = self._goal_level(progression_state, minimum=1)
        if turn_family == "post_action_followup":
            return self._post_action_goal(domain="apoyo_general", phase="one_helpful_step", progression_state=progression_state)
        if turn_family == "specific_action_request":
            return self._goal(
                "give_next_distinct_step",
                "clarity",
                "high",
                "general_support",
                ["dar una accion concreta y breve", "no abrir un proceso largo"],
                ["elige una sola cosa manejable y hazla en menos de dos minutos"],
                [],
                ["no_sobrecargar"],
                True,
                True,
                False,
                "dar una accion concreta en vez de una estrategia general",
                "elige una sola cosa manejable y hazla en menos de dos minutos",
                routine_payload.get("routine_type"),
                ["accion_concreta", "brevedad"],
                False,
                response_shape="concrete_action",
                domain_focus="claridad y accion concreta",
                followup_policy="avoid",
                intervention_level=max(level, 2),
                form_variant="general_concrete",
                visible_shift_required=True,
            )
        if turn_family == "literal_phrase_request":
            return self._literal_phrase_goal(domain="apoyo_general", progression_state=progression_state)
        routine_steps = [str(step).strip() for step in routine_payload.get("short_version", []) if str(step).strip()]
        if not routine_steps:
            routine_steps = [str(step).strip() for step in routine_payload.get("steps", []) if str(step).strip()]
        candidate_actions = routine_steps[:2] or ["quedarte con una sola cosa manejable por ahora"]
        suggested_content = ["ofrecer ayuda breve", "mantener baja la carga", "dejar algo claro y usable"]
        if primary_state in {"burnout", "parental_fatigue"}:
            return self._goal(
                "reduce_general_load",
                "emotional_safety",
                "moderate",
                "general_support",
                ["bajar exigencia", "dar permiso de pausa", "no pedir mas decision ahora"],
                ["dejar una sola cosa para despues"],
                [],
                ["no_sobrecargar"],
                True,
                True,
                False,
                "bajar exigencia antes de ordenar",
                "dejar una sola cosa para despues",
                routine_payload.get("routine_type"),
                ["baja_exigencia", "alivio", "claridad"],
                True,
                response_shape="permission_pause",
                domain_focus="baja exigencia",
                followup_policy="avoid",
                intervention_level=level,
                form_variant="permission_pause",
            )
        return self._goal(
            "clarify_and_support",
            "emotional_safety",
            "moderate",
            "general_support",
            suggested_content,
            candidate_actions,
            [],
            ["no_sobrecargar"],
            True,
            True,
            False,
            suggested_content[0],
            candidate_actions[0],
            routine_payload.get("routine_type"),
            ["foco", "accion_util"],
            False,
            response_shape="single_action",
            domain_focus="claridad y baja carga",
            followup_policy="avoid",
            intervention_level=level,
            form_variant="general_direct" if level >= 3 else "general_support",
        )

    def _uncertainty_goal(self, domain: str, source_message: str, progression_state: Dict[str, Any]) -> Dict[str, Any]:
        level = self._goal_level(progression_state, minimum=1)
        action = self._default_microaction_for_domain(domain)
        uncertainty_line = self._uncertainty_support_line(domain, source_message)
        goal_name = "reduce_choice_overload_for_user"
        selected_strategy = "reducir opciones y elegir una salida minima"
        response_shape = "single_action"
        should_stay_with_validation = False
        if domain == "ansiedad_cognitiva":
            goal_name = "lower_anxiety_demand_now"
            selected_strategy = "bajar exigencia y elegir un anclaje por la persona"
            response_shape = "grounding"
            should_stay_with_validation = True
        elif domain == "sobrecarga_cuidador":
            goal_name = "reduce_caregiver_demand_now"
            selected_strategy = "aliviar una carga antes de pedir mas claridad"
            response_shape = "load_relief"
            should_stay_with_validation = True
        elif domain == "sueno_regulacion":
            goal_name = "lower_sleep_activation_now"
            selected_strategy = "dejar un solo ajuste de descanso"
            response_shape = "sleep_settle"
            should_stay_with_validation = True
        elif domain == "disfuncion_ejecutiva":
            goal_name = "choose_first_executive_step"
            selected_strategy = "elegir un arranque visible por la persona"
        elif domain == "apoyo_general":
            goal_name = "lower_general_demand_now"
            selected_strategy = "bajar exigencia antes de pedir claridad"
            response_shape = "permission_pause"
            should_stay_with_validation = True
        return self._goal(
            goal_name,
            "clarity",
            "high",
            "choice_reduction",
            [uncertainty_line, "no pedir mas opciones", "elegir una por la persona", "dejar una sola accion minima"],
            [action],
            [],
            ["no_repetir_opciones"],
            True,
            True,
            False,
            selected_strategy,
            action,
            self.ROUTINE_BY_DOMAIN.get(domain),
            ["simplificar", "accion_minima"],
            should_stay_with_validation,
            response_shape=response_shape,
            domain_focus=self._domain_focus(domain),
            followup_policy="avoid",
            intervention_level=level,
            form_variant="grounding_reset" if response_shape in {"grounding", "sleep_settle"} else "uncertainty_relief",
        )

    def _goal(
        self,
        goal: str,
        priority: str,
        guidance_level: str,
        intervention_type: str,
        suggested_content: List[str],
        candidate_actions: List[str],
        possible_questions: List[str],
        safety_constraints: List[str],
        keep_minimal: bool,
        should_offer_action: bool,
        should_offer_question: bool,
        selected_strategy: Optional[str],
        selected_microaction: Optional[str],
        selected_routine_type: Optional[str],
        priority_order: List[str],
        should_stay_with_validation: bool,
        allow_literal_phrase: bool = False,
        literal_phrase_candidates: Optional[List[str]] = None,
        response_shape: str = "single_action",
        domain_focus: Optional[str] = None,
        followup_policy: str = "avoid",
        intervention_level: int = 1,
        form_variant: str = "default",
        strategy_signature: Optional[str] = None,
        visible_shift_required: bool = False,
    ) -> Dict[str, Any]:
        literal_phrase_candidates = literal_phrase_candidates or []
        return {
            "goal": goal,
            "priority": priority,
            "guidance_level": guidance_level,
            "intervention_type": intervention_type,
            "suggested_content": self._deduplicate([item for item in suggested_content if item]),
            "candidate_actions": self._deduplicate([item for item in candidate_actions if item]),
            "possible_questions": self._deduplicate([item for item in possible_questions if item]),
            "safety_constraints": self._deduplicate([item for item in safety_constraints if item]),
            "keep_minimal": bool(keep_minimal),
            "should_offer_action": bool(should_offer_action),
            "should_offer_question": bool(should_offer_question),
            "should_stay_with_validation": bool(should_stay_with_validation),
            "allow_literal_phrase": bool(allow_literal_phrase),
            "literal_phrase_candidates": self._deduplicate([item for item in literal_phrase_candidates if item]),
            "selected_strategy": selected_strategy,
            "selected_microaction": selected_microaction,
            "selected_routine_type": selected_routine_type,
            "priority_order": self._deduplicate([item for item in priority_order if item]),
            "response_shape": response_shape,
            "domain_focus": domain_focus,
            "followup_policy": followup_policy,
            "intervention_level": max(int(intervention_level or 1), 1),
            "form_variant": form_variant,
            "strategy_signature": strategy_signature or f"{goal}:{response_shape}:{form_variant}:{int(intervention_level or 1)}",
            "visible_shift_required": bool(visible_shift_required),
        }

    def _build_avoid_list(self, state_avoid: List[str], response_alerts: List[str], response_goal: Dict[str, Any], domain: str, stage: str, primary_state: Optional[str], clarification_mode: str) -> List[str]:
        avoid = list(state_avoid or [])
        avoid.extend(response_alerts or [])
        avoid.extend(response_goal.get("safety_constraints", []) or [])
        domain_avoid = {
            "crisis_activa": ["explicar_demasiado", "hacer_reflexionar_en_pleno_pico", "dar_listas_largas"],
            "ansiedad_cognitiva": ["decir_relajate", "pedir_que_resuelva_todo", "sobrecargar_con_muchas_tareas"],
            "disfuncion_ejecutiva": ["dejar_la_tarea_abierta", "dar_muchos_pasos_a_la_vez", "hablar_en_abstracto"],
            "sueno_regulacion": ["activar_mas", "dar_instrucciones_largas"],
            "sobrecarga_cuidador": ["culpabilizar", "romantizar_la_resiliencia", "dar_muchas_tareas"],
            "sobrecarga_sensorial": ["aumentar_estimulos", "forzar_contacto"],
            "transicion_rigidez": ["cambiar_sin_avisar", "usar_mensajes_ambiguos"],
        }
        if stage == "focus_clarification" or clarification_mode != "none":
            avoid.extend(["abrir_mas_temas", "repetir_la_misma_formulacion"])
        if primary_state in {"meltdown", "shutdown"}:
            avoid.extend(["preguntas_complejas", "tono_analitico"])
        avoid.extend(domain_avoid.get(domain, []))
        return self._deduplicate([item for item in avoid if item])

    def _default_microaction_for_domain(self, domain: str) -> str:
        mapping = {
            "ansiedad_cognitiva": "apoya los pies en el piso y suelta el aire mas largo una vez",
            "disfuncion_ejecutiva": "abre solo el material que toca",
            "sueno_regulacion": "baja una sola fuente de activacion antes de dormir",
            "sobrecarga_cuidador": "deja una sola cosa para despues",
            "prevencion_escalada": "ubicar la primera senal de subida",
            "sobrecarga_sensorial": "bajar un estimulo concreto",
            "transicion_rigidez": "decir en una frase que sigue ahora",
            "regulacion_post_evento": "rescatar una sola senal util",
            "escalada_emocional": "quitar una demanda en cuanto aparezca la senal",
            "crisis_activa": "bajar estimulos y mantener distancia segura",
        }
        return mapping.get(domain, "quedarte con una sola cosa clara por ahora")

    def _signals_uncertainty(self, source_message: str) -> bool:
        normalized = self._normalize(source_message)
        return any(
            pattern in normalized
            for pattern in [
                "no lo se",
                "no se como",
                "no se que hacer",
                "no se por donde empezar",
                "no tengo una idea clara",
                "no tengo ninguna",
                "no lo tengo claro",
                "no tengo claro",
            ]
        )

    def _uncertainty_support_line(self, domain: str, source_message: str) -> str:
        normalized = self._normalize(source_message)
        if any(pattern in normalized for pattern in ["no tengo una idea clara", "no lo tengo claro", "no tengo claro"]):
            base = "No necesitas encontrar una idea clara ahora."
        elif "no tengo ninguna" in normalized:
            base = "Si no sale ninguna, no hace falta forzarla."
        elif any(pattern in normalized for pattern in ["no lo se", "no se que hacer"]):
            base = "No hace falta saberlo ahora."
        elif any(pattern in normalized for pattern in ["por donde empiezo", "con que empiezo", "que hago ahorita", "que hago ahora", "que hago ya", "que hago"]):
            base = "Voy a dejarte un solo comienzo."
        else:
            base = "No hace falta aclararlo mas por ahora."

        if domain == "ansiedad_cognitiva":
            return f"{base} Vamos solo con una accion para bajar activacion."
        if domain == "disfuncion_ejecutiva":
            return f"{base} Primero hace falta arrancar, no ordenar todo."
        if domain == "sueno_regulacion":
            return f"{base} Vamos solo con un ajuste para bajar activacion."
        if domain == "sobrecarga_cuidador":
            return f"{base} Hoy alcanza con quitar una carga minima."
        if domain == "apoyo_general":
            return f"{base} Podemos dejarlo en una sola cosa."
        return base

    def _clarification_line(self, domain: str, action: Optional[str]) -> str:
        if domain == "crisis_activa":
            return "Me refiero a bajar demanda y sostener seguridad, sin abrir otra conversacion."
        if domain == "ansiedad_cognitiva":
            return "Me refiero a bajar un poco la activacion antes de intentar decidir algo mas."
        if domain == "disfuncion_ejecutiva":
            if action:
                return f"Me refiero a esto: {action}."
            return "Me refiero a dejar una sola salida visible, no a ordenar todo."
        if domain == "sueno_regulacion":
            return "Me refiero a bajar activacion con un solo ajuste sencillo, no a resolver toda la noche."
        if domain == "sobrecarga_cuidador":
            return "Me refiero a soltar una carga pequena primero, no a poder con todo."
        return "Me refiero a dejar una sola idea clara y manejable."

    def _literal_crisis_phrase(self, source_message: str) -> Optional[str]:
        normalized = self._normalize(source_message)
        if "que le digo" in normalized or "que le digo ahora" in normalized or "que le puedo decir" in normalized:
            return "Estoy aqui contigo. No hace falta hablar ahora. Vamos a bajar un poco esto."
        return None

    def _message_cues(self, source_message: str) -> Dict[str, bool]:
        normalized = self._normalize(source_message)
        return {
            "expresses_uncertainty": self._signals_uncertainty(source_message),
            "asks_literal_phrase": any(token in normalized for token in ["que le digo", "que puedo decirle", "que le digo ahora", "que le puedo decir"]),
            "asks_where_to_start": any(token in normalized for token in ["por donde empiezo", "por donde comienzo", "con que empiezo"]),
            "asks_what_now": any(token in normalized for token in ["que hago ahorita", "que hago ahora", "que hago ya", "que hago"]),
            "asks_for_more": any(token in normalized for token in ["que mas", "que sigue", "y luego", "y ahora", "ya"]),
            "pushes_back": any(token in normalized for token in ["pero", "sigo igual", "no funciona", "eso no"]),
            "asks_post_action_followup": any(token in normalized for token in ["ya y ahora que", "y ahora que", "ok que mas", "pero despues que", "despues que", "y luego", "que sigue"]),
            "asks_validation": any(token in normalized for token in ["esto es normal", "es normal", "esta bien que", "esta mal que", "es grave", "es raro"]),
            "asks_closure_or_pause": any(token in normalized for token in ["ya estuvo", "por ahora basta", "lo dejo aqui", "despues sigo"]),
        }

    def _about_system_line(self, source_message: str) -> tuple[str, str]:
        normalized = self._normalize(source_message)
        if any(
            token in normalized
            for token in {
                "como puedo llamarte",
                "como te llamo",
                "como quieres que te diga",
                "como puedo decirte",
            }
        ):
            return (
                "Puedes decirme NeuroGuIA, o como te salga mas natural.",
                "about_name",
            )
        if "quien eres" in normalized or "eres un bot" in normalized or "eres una ia" in normalized:
            return (
                "Soy NeuroGuIA. Estoy aqui para acompanar esta conversacion contigo con calma y claridad.",
                "about_identity",
            )
        if "para que sirves" in normalized or "como ayudas" in normalized:
            return (
                "Estoy para ayudarte a ordenar lo que pasa, bajar carga y encontrar una respuesta util para este momento.",
                "about_purpose",
            )
        if "que no puedes hacer" in normalized:
            return (
                "No puedo ver lo que esta pasando fuera de esta charla ni reemplazar ayuda profesional; trabajo con lo que me vas contando aqui.",
                "about_limits",
            )
        if "que puedes hacer" in normalized or "como funcionas" in normalized:
            return (
                "Puedo ayudarte a aclarar lo que pasa, darte un paso concreto, una frase literal, cerrar opciones o responder dudas simples.",
                "about_capabilities",
            )
        return (
            "Estoy para acompanar esta conversacion de forma breve, clara y cercana.",
            "about_system",
        )

    def _simple_answer_line(self, domain: str, source_message: str) -> str:
        normalized = self._normalize(source_message)
        if "esto es normal" in normalized or "es normal" in normalized:
            return self._validation_line(domain, source_message)
        if domain == "crisis_activa":
            return "Si sigue habiendo riesgo o mucha activacion, la prioridad no es hablar mucho sino bajar demanda y asegurar espacio."
        if domain == "ansiedad_cognitiva":
            return "Si la mente esta acelerada, primero ayuda bajar ruido y despues ver si eso necesita accion hoy."
        if domain == "disfuncion_ejecutiva":
            return "En bloqueo, suele ayudar mas dejar algo visible que intentar ordenar todo."
        if domain == "sueno_regulacion":
            return "Cuando el cansancio pega y la mente sigue alta, conviene bajar activacion antes de intentar dormir a la fuerza."
        return "Vamos a dejarlo simple y concreto."

    def _validation_line(self, domain: str, source_message: str) -> str:
        if domain == "crisis_activa":
            return "Sí, es esperable que en una crisis no salga razonar mucho; primero importa bajar demanda y sostener seguridad."
        if domain == "ansiedad_cognitiva":
            return "Sí, cuando la ansiedad sube es normal que cueste pensar con claridad o decidir."
        if domain == "disfuncion_ejecutiva":
            return "Sí, en bloqueo ejecutivo es bastante común sentirse frenado incluso queriendo empezar."
        if domain == "sueno_regulacion":
            return "Sí, cuando hay cansancio acumulado o activacion alta, dormir bien puede volverse mucho mas dificil."
        if domain == "sobrecarga_cuidador":
            return "Sí, cuando vienes cargando mucho, es esperable sentirte rebasado o sin margen."
        return "Sí, eso puede pasar cuando hay mucha carga o saturacion; no significa que tengas que resolverlo todo ahora."

    def _domain_focus(self, domain: str) -> str:
        mapping = {
            "crisis_activa": "seguridad inmediata y contencion",
            "ansiedad_cognitiva": "regulacion y anclaje",
            "disfuncion_ejecutiva": "arranque y friccion",
            "sueno_regulacion": "descanso y activacion",
            "sobrecarga_cuidador": "alivio de carga",
            "prevencion_escalada": "senal temprana y respuesta temprana",
            "sobrecarga_sensorial": "bajar estimulos",
            "transicion_rigidez": "previsibilidad y guion breve",
            "regulacion_post_evento": "reparacion y aprendizaje breve",
            "escalada_emocional": "senal temprana y baja demanda",
        }
        return mapping.get(domain, "claridad y baja carga")

    def _canonicalize_category(self, category: Optional[str]) -> Optional[str]:
        if not category:
            return category
        return self.LEGACY_CATEGORY_ALIASES.get(category, category)

    def _normalize(self, text: Optional[str]) -> str:
        normalized = " ".join((text or "").strip().lower().split())
        normalized = unicodedata.normalize("NFKD", normalized)
        normalized = "".join(char for char in normalized if not unicodedata.combining(char))
        normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
        return " ".join(normalized.split())

    def _deduplicate(self, items: List[Any]) -> List[Any]:
        result: List[Any] = []
        seen = set()
        for item in items:
            if item not in seen:
                seen.add(item)
                result.append(item)
        return result


def decide_response(**kwargs: Any) -> Dict[str, Any]:
    return DecisionEngine().decide(**kwargs)
