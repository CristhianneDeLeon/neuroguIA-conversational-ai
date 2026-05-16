from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


class ConfidenceEngine:
    """
    Motor premium calibrado de confianza interna para NeuroGuía.

    Objetivo:
    estimar qué tan capaz es NeuroGuía de responder adecuadamente
    con sus propios recursos antes de activar fallback al LLM.

    Esta versión refinada:
    - evita colapsar fácilmente a 0.0 en casos ambiguos
    - distingue mejor entre ambigüedad y falta total de cobertura
    - favorece respuesta interna si ya existe una microacción o rutina utilizable
    - hace el fallback más inteligente y menos impulsivo
    """

    DEFAULT_WEIGHTS = {
        "intent": 0.13,
        "category": 0.15,
        "state": 0.18,
        "case_memory": 0.11,
        "response_memory": 0.16,
        "intervention_availability": 0.17,
        "context_stability": 0.10,
    }

    def evaluate(
        self,
        intent_analysis: Optional[Dict[str, Any]] = None,
        category_analysis: Optional[Dict[str, Any]] = None,
        state_analysis: Optional[Dict[str, Any]] = None,
        support_plan: Optional[Dict[str, Any]] = None,
        memory_summary: Optional[Dict[str, Any]] = None,
        memory_payload: Optional[Dict[str, Any]] = None,
        response_memory_payload: Optional[Dict[str, Any]] = None,
        routine_payload: Optional[Dict[str, Any]] = None,
        case_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        intent_analysis = intent_analysis or {}
        category_analysis = category_analysis or {}
        state_analysis = state_analysis or {}
        support_plan = support_plan or {}
        memory_summary = memory_summary or {}
        memory_payload = memory_payload or {}
        response_memory_payload = response_memory_payload or {}
        routine_payload = routine_payload or {}
        case_context = case_context or {}

        intent_score = self._score_intent(intent_analysis)
        category_score = self._score_category(category_analysis)
        state_score = self._score_state(state_analysis)
        case_memory_score = self._score_case_memory(memory_summary, memory_payload)
        response_memory_score = self._score_response_memory(response_memory_payload)
        intervention_score = self._score_intervention_availability(
            support_plan=support_plan,
            memory_payload=memory_payload,
            routine_payload=routine_payload,
            category_analysis=category_analysis,
            state_analysis=state_analysis,
        )
        context_stability_score = self._score_context_stability(case_context, state_analysis)

        breakdown = {
            "intent": round(intent_score, 4),
            "category": round(category_score, 4),
            "state": round(state_score, 4),
            "case_memory": round(case_memory_score, 4),
            "response_memory": round(response_memory_score, 4),
            "intervention_availability": round(intervention_score, 4),
            "context_stability": round(context_stability_score, 4),
        }

        weighted_total = (
            intent_score * self.DEFAULT_WEIGHTS["intent"]
            + category_score * self.DEFAULT_WEIGHTS["category"]
            + state_score * self.DEFAULT_WEIGHTS["state"]
            + case_memory_score * self.DEFAULT_WEIGHTS["case_memory"]
            + response_memory_score * self.DEFAULT_WEIGHTS["response_memory"]
            + intervention_score * self.DEFAULT_WEIGHTS["intervention_availability"]
            + context_stability_score * self.DEFAULT_WEIGHTS["context_stability"]
        )

        complexity_penalty = self._complexity_penalty(support_plan)
        low_capacity_penalty = self._low_capacity_penalty(case_context)
        ambiguity_penalty = self._ambiguity_penalty(intent_analysis, category_analysis, state_analysis)

        raw_confidence = weighted_total - complexity_penalty - low_capacity_penalty - ambiguity_penalty
        raw_confidence = max(min(raw_confidence, 1.0), 0.0)

        overall_confidence = self._apply_confidence_floor(
            raw_confidence=raw_confidence,
            intent_analysis=intent_analysis,
            category_analysis=category_analysis,
            state_analysis=state_analysis,
            routine_payload=routine_payload,
            memory_payload=memory_payload,
            response_memory_payload=response_memory_payload,
        )

        fallback_recommended, fallback_reason = self._determine_fallback_recommendation(
            overall_confidence=overall_confidence,
            breakdown=breakdown,
            response_memory_payload=response_memory_payload,
            routine_payload=routine_payload,
            category_analysis=category_analysis,
            state_analysis=state_analysis,
            case_context=case_context,
            memory_payload=memory_payload,
        )

        confidence_level = self._label_confidence(overall_confidence)

        return {
            "overall_confidence": round(overall_confidence, 4),
            "raw_confidence": round(raw_confidence, 4),
            "confidence_level": confidence_level,
            "confidence_breakdown": breakdown,
            "penalties": {
                "complexity_penalty": round(complexity_penalty, 4),
                "low_capacity_penalty": round(low_capacity_penalty, 4),
                "ambiguity_penalty": round(ambiguity_penalty, 4),
            },
            "fallback_recommended": fallback_recommended,
            "reason": fallback_reason,
            "strengths": self._extract_strengths(breakdown),
            "weak_points": self._extract_weak_points(breakdown),
            "decision_hints": self._build_decision_hints(
                overall_confidence=overall_confidence,
                breakdown=breakdown,
                fallback_recommended=fallback_recommended,
                case_context=case_context,
                response_memory_payload=response_memory_payload,
                routine_payload=routine_payload,
                memory_payload=memory_payload,
            ),
        }

    # =========================================================
    # SCORING POR COMPONENTE
    # =========================================================
    def _score_intent(self, intent_analysis: Dict[str, Any]) -> float:
        base = float(intent_analysis.get("confidence", 0.0) or 0.0)
        detected_intent = intent_analysis.get("detected_intent")
        alternatives = intent_analysis.get("alternatives", []) or []
        reasoning = intent_analysis.get("reasoning", {}) or {}

        if detected_intent and base == 0.0:
            base = 0.22

        if alternatives and len(alternatives) >= 2:
            base -= 0.03

        question_density = float(reasoning.get("question_density", 0.0) or 0.0)
        if question_density > 0.10 and detected_intent == "clarification_request":
            base += 0.03

        if detected_intent in {"urgent_support", "general_support", "emotional_venting"} and base < 0.35:
            base = max(base, 0.35)

        base += self._classic_ml_agreement_bonus(
            analysis=intent_analysis,
            detected_label=detected_intent,
        )
        base += self._semantic_agreement_bonus(
            analysis=intent_analysis,
            detected_label=detected_intent,
        )

        return max(min(base, 1.0), 0.0)

    def _score_category(self, category_analysis: Dict[str, Any]) -> float:
        base = float(category_analysis.get("confidence", 0.0) or 0.0)
        detected_category = category_analysis.get("detected_category")
        alternatives = category_analysis.get("alternative_categories", []) or []
        matched_keywords = (category_analysis.get("reasoning", {}) or {}).get("matched_keywords", []) or []

        if detected_category and base == 0.0:
            base = 0.24

        if len(matched_keywords) >= 2:
            base += 0.04

        if alternatives and len(alternatives) >= 2:
            base -= 0.02

        if detected_category in {"crisis_emocional", "saturacion_sensorial", "bloqueo_ejecutivo", "sleep"} and base < 0.36:
            base = 0.36

        base += self._classic_ml_agreement_bonus(
            analysis=category_analysis,
            detected_label=detected_category,
        )
        base += self._semantic_agreement_bonus(
            analysis=category_analysis,
            detected_label=detected_category,
        )

        return max(min(base, 1.0), 0.0)

    def _score_state(self, state_analysis: Dict[str, Any]) -> float:
        detected_states = state_analysis.get("detected_states", []) or []
        primary_state = state_analysis.get("primary_state")

        if not detected_states:
            if primary_state and primary_state != "general_distress":
                return 0.34
            return 0.26

        primary = detected_states[0]
        primary_score = float(primary.get("score", 0.0) or 0.0)
        secondary_states = state_analysis.get("secondary_states", []) or []
        flags = state_analysis.get("flags", {}) or {}

        score = max(primary_score, 0.30)

        if secondary_states:
            score -= min(len(secondary_states) * 0.015, 0.05)

        if flags.get("needs_low_demand_language"):
            score -= 0.02

        if primary_state in {"meltdown", "shutdown", "burnout", "executive_dysfunction", "sensory_overload"}:
            score = max(score, 0.42)

        return max(min(score, 1.0), 0.0)

    def _score_case_memory(
        self,
        memory_summary: Dict[str, Any],
        memory_payload: Dict[str, Any],
    ) -> float:
        total_cases = int(memory_summary.get("total_cases", 0) or 0)
        success_rate = float(memory_summary.get("success_rate", 0.0) or 0.0)
        similar_cases = int(memory_payload.get("similar_case_count", 0) or 0)
        successful_similar = int(memory_payload.get("successful_similar_case_count", 0) or 0)
        avg_usefulness = float(memory_payload.get("average_usefulness_in_similar_cases", 0.0) or 0.0)

        score = 0.0
        score += min(total_cases / 20.0, 1.0) * 0.16
        score += min(similar_cases / 8.0, 1.0) * 0.34
        score += min(successful_similar / 5.0, 1.0) * 0.24
        score += min(success_rate, 1.0) * 0.13
        score += min(avg_usefulness, 1.0) * 0.13

        if similar_cases == 0 and total_cases == 0:
            return 0.10

        return max(min(score, 1.0), 0.0)

    def _score_response_memory(self, response_memory_payload: Dict[str, Any]) -> float:
        reuse_confidence = float(response_memory_payload.get("reuse_confidence", 0.0) or 0.0)
        candidates = response_memory_payload.get("response_candidates", []) or []
        can_reuse_directly = bool(response_memory_payload.get("can_reuse_directly", False))
        best_response = response_memory_payload.get("best_response")

        score = max(reuse_confidence * 0.70, 0.08 if candidates else 0.05)
        score += min(len(candidates) / 6.0, 1.0) * 0.16

        if can_reuse_directly:
            score += 0.12

        if best_response and best_response.get("approved_for_reuse"):
            score += 0.08

        return max(min(score, 1.0), 0.0)

    def _score_intervention_availability(
        self,
        support_plan: Dict[str, Any],
        memory_payload: Dict[str, Any],
        routine_payload: Dict[str, Any],
        category_analysis: Dict[str, Any],
        state_analysis: Dict[str, Any],
    ) -> float:
        support_priorities = support_plan.get("support_priorities", []) or []
        recommended_strategies = memory_payload.get("recommended_strategies", []) or []
        recommended_microactions = memory_payload.get("recommended_microactions", []) or []
        routine_steps = routine_payload.get("steps", []) or []
        routine_short = routine_payload.get("short_version", []) or []
        category = category_analysis.get("detected_category")
        primary_state = state_analysis.get("primary_state")

        score = 0.12  # base mínima si hay pipeline funcionando

        if support_priorities:
            score += min(len(support_priorities) / 4.0, 1.0) * 0.18

        if recommended_strategies:
            score += min(len(recommended_strategies) / 3.0, 1.0) * 0.16

        if recommended_microactions:
            score += min(len(recommended_microactions) / 3.0, 1.0) * 0.16

        if routine_steps:
            score += min(len(routine_steps) / 4.0, 1.0) * 0.22

        if routine_short:
            score += 0.08

        if category in {"sleep", "bloqueo_ejecutivo", "necesidad_rutina", "transicion"}:
            score += 0.05

        if primary_state in {"burnout", "shutdown", "meltdown"} and (routine_short or recommended_microactions):
            score += 0.05

        return max(min(score, 1.0), 0.0)

    def _score_context_stability(
        self,
        case_context: Dict[str, Any],
        state_analysis: Dict[str, Any],
    ) -> float:
        caregiver_capacity = case_context.get("caregiver_capacity")
        emotional_intensity = case_context.get("emotional_intensity")
        followup_needed = bool(case_context.get("followup_needed", False))
        primary_state = state_analysis.get("primary_state")

        score = 0.60

        if caregiver_capacity is not None:
            try:
                cap = float(caregiver_capacity)
                score = (score + max(min(cap, 1.0), 0.0)) / 2.0
            except (TypeError, ValueError):
                pass

        if emotional_intensity is not None:
            try:
                intensity = float(emotional_intensity)
                score -= min(intensity * 0.18, 0.18)
            except (TypeError, ValueError):
                pass

        if followup_needed:
            score -= 0.03

        if primary_state in {"meltdown", "shutdown"}:
            score -= 0.10
        elif primary_state == "burnout":
            score -= 0.08

        return max(min(score, 1.0), 0.0)

    # =========================================================
    # PENALIZACIONES
    # =========================================================
    def _complexity_penalty(self, support_plan: Dict[str, Any]) -> float:
        level = str(support_plan.get("complexity_level") or "").lower()

        if level == "triple_or_high_complexity":
            return 0.07
        if level == "double_exceptionality_or_cooccurrence":
            return 0.035
        return 0.0

    def _low_capacity_penalty(self, case_context: Dict[str, Any]) -> float:
        caregiver_capacity = case_context.get("caregiver_capacity")
        emotional_intensity = case_context.get("emotional_intensity")

        penalty = 0.0
        try:
            if caregiver_capacity is not None and float(caregiver_capacity) <= 0.35:
                penalty += 0.04
        except (TypeError, ValueError):
            pass

        try:
            if emotional_intensity is not None and float(emotional_intensity) >= 0.70:
                penalty += 0.03
        except (TypeError, ValueError):
            pass

        return penalty

    def _classic_ml_agreement_bonus(
        self,
        analysis: Dict[str, Any],
        detected_label: Optional[str],
    ) -> float:
        """
        Bonus pequeno y conservador cuando reglas y baseline clasico
        coinciden en la misma etiqueta.
        """
        if not detected_label:
            return 0.0

        classic_signal = analysis.get("classic_ml_signal") or {}
        if not classic_signal.get("available"):
            return 0.0

        predicted_label = classic_signal.get("predicted_label")
        if predicted_label != detected_label:
            return 0.0

        try:
            signal_confidence = float(classic_signal.get("confidence", 0.0) or 0.0)
        except (TypeError, ValueError):
            return 0.0

        if signal_confidence >= 0.70:
            return 0.03
        if signal_confidence >= 0.55:
            return 0.02
        if signal_confidence >= 0.40:
            return 0.01
        return 0.0

    def _semantic_agreement_bonus(
        self,
        analysis: Dict[str, Any],
        detected_label: Optional[str],
    ) -> float:
        """
        Bonus pequeno y conservador cuando la senal semantica basada en
        embeddings coincide con la etiqueta elegida por reglas.
        """
        if not detected_label:
            return 0.0

        semantic_signal = analysis.get("semantic_signal") or {}
        if not semantic_signal.get("available"):
            return 0.0

        predicted_label = semantic_signal.get("predicted_label")
        if predicted_label != detected_label:
            return 0.0

        try:
            similarity = float(semantic_signal.get("similarity", 0.0) or 0.0)
        except (TypeError, ValueError):
            return 0.0

        if similarity >= 0.75:
            return 0.03
        if similarity >= 0.62:
            return 0.02
        if similarity >= 0.50:
            return 0.01
        return 0.0

    def _ambiguity_penalty(
        self,
        intent_analysis: Dict[str, Any],
        category_analysis: Dict[str, Any],
        state_analysis: Dict[str, Any],
    ) -> float:
        penalty = 0.0

        intent_conf = float(intent_analysis.get("confidence", 0.0) or 0.0)
        cat_conf = float(category_analysis.get("confidence", 0.0) or 0.0)
        detected_states = state_analysis.get("detected_states", []) or []
        state_conf = float(detected_states[0].get("score", 0.0) or 0.0) if detected_states else 0.0

        if intent_conf < 0.35:
            penalty += 0.025
        if cat_conf < 0.35:
            penalty += 0.04
        if state_conf < 0.30 and state_analysis.get("primary_state") in {None, "", "general_distress"}:
            penalty += 0.03

        return penalty

    def _apply_confidence_floor(
        self,
        raw_confidence: float,
        intent_analysis: Dict[str, Any],
        category_analysis: Dict[str, Any],
        state_analysis: Dict[str, Any],
        routine_payload: Dict[str, Any],
        memory_payload: Dict[str, Any],
        response_memory_payload: Dict[str, Any],
    ) -> float:
        detected_intent = intent_analysis.get("detected_intent")
        detected_category = category_analysis.get("detected_category")
        primary_state = state_analysis.get("primary_state")
        has_routine = bool((routine_payload.get("steps") or []) or (routine_payload.get("short_version") or []))
        has_microactions = bool(memory_payload.get("recommended_microactions") or [])
        has_response_candidates = bool(response_memory_payload.get("response_candidates") or [])

        floor = 0.0
        if detected_intent or detected_category or primary_state:
            floor = 0.18

        if detected_category and primary_state:
            floor = max(floor, 0.24)

        if has_routine:
            floor = max(floor, 0.32)

        if has_microactions or has_response_candidates:
            floor = max(floor, 0.28)

        return max(raw_confidence, floor)

    # =========================================================
    # RECOMENDACIÓN DE FALLBACK
    # =========================================================
    def _determine_fallback_recommendation(
        self,
        overall_confidence: float,
        breakdown: Dict[str, float],
        response_memory_payload: Dict[str, Any],
        routine_payload: Dict[str, Any],
        category_analysis: Dict[str, Any],
        state_analysis: Dict[str, Any],
        case_context: Dict[str, Any],
        memory_payload: Dict[str, Any],
    ) -> Tuple[bool, str]:
        reuse_confidence = float(response_memory_payload.get("reuse_confidence", 0.0) or 0.0)
        can_reuse_directly = bool(response_memory_payload.get("can_reuse_directly", False))
        routine_steps = routine_payload.get("steps", []) or []
        routine_short = routine_payload.get("short_version", []) or []
        recommended_microactions = memory_payload.get("recommended_microactions", []) or []
        primary_state = state_analysis.get("primary_state")
        detected_category = category_analysis.get("detected_category")
        emotional_intensity = case_context.get("emotional_intensity")

        if can_reuse_directly and reuse_confidence >= 0.70:
            return False, "high_reuse_confidence"

        if overall_confidence >= 0.74:
            return False, "high_internal_confidence"

        if overall_confidence >= 0.58 and (routine_steps or routine_short or recommended_microactions):
            return False, "moderate_confidence_with_actionable_support"

        if primary_state in {"meltdown", "shutdown"} and (routine_short or recommended_microactions) and overall_confidence >= 0.45:
            return False, "critical_state_but_controlled_internal_support_available"

        if detected_category in {"sleep", "bloqueo_ejecutivo", "transicion"} and routine_steps and overall_confidence >= 0.48:
            return False, "category_supported_by_structured_routine"

        # fallback solo cuando hay vacíos más claros
        if reuse_confidence < 0.30 and not routine_steps and not routine_short and not recommended_microactions:
            return True, "low_memory_and_low_intervention_coverage"

        if breakdown["category"] < 0.32 and breakdown["intent"] < 0.32 and breakdown["intervention_availability"] < 0.30:
            return True, "high_ambiguity_and_low_actionability"

        try:
            if emotional_intensity is not None and float(emotional_intensity) >= 0.88 and overall_confidence < 0.52 and not (routine_short or recommended_microactions):
                return True, "very_high_intensity_with_insufficient_internal_support"
        except (TypeError, ValueError):
            pass

        if overall_confidence < 0.42 and not (routine_steps or routine_short or recommended_microactions):
            return True, "overall_confidence_below_threshold_without_actionable_support"

        return False, "sufficient_internal_guidance"

    # =========================================================
    # SALIDAS EXPLICABLES
    # =========================================================
    def _label_confidence(self, score: float) -> str:
        if score >= 0.78:
            return "high"
        if score >= 0.60:
            return "medium_high"
        if score >= 0.45:
            return "medium"
        return "low"

    def _extract_strengths(self, breakdown: Dict[str, float]) -> List[str]:
        return [key for key, value in breakdown.items() if value >= 0.62]

    def _extract_weak_points(self, breakdown: Dict[str, float]) -> List[str]:
        return [key for key, value in breakdown.items() if value < 0.42]

    def _build_decision_hints(
        self,
        overall_confidence: float,
        breakdown: Dict[str, float],
        fallback_recommended: bool,
        case_context: Dict[str, Any],
        response_memory_payload: Dict[str, Any],
        routine_payload: Dict[str, Any],
        memory_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        caregiver_capacity = case_context.get("caregiver_capacity")
        emotional_intensity = case_context.get("emotional_intensity")
        reuse_confidence = float(response_memory_payload.get("reuse_confidence", 0.0) or 0.0)
        has_routine = bool((routine_payload.get("steps") or []) or (routine_payload.get("short_version") or []))
        has_microactions = bool(memory_payload.get("recommended_microactions") or [])

        hints = {
            "prefer_reuse_response_memory": reuse_confidence >= 0.70,
            "prefer_system_response": overall_confidence >= 0.55 and not fallback_recommended,
            "prefer_microaction_over_long_response": False,
            "prefer_low_demand_output": False,
            "fallback_priority": "none",
        }

        try:
            if caregiver_capacity is not None and float(caregiver_capacity) <= 0.35:
                hints["prefer_microaction_over_long_response"] = True
        except (TypeError, ValueError):
            pass

        try:
            if emotional_intensity is not None and float(emotional_intensity) >= 0.70:
                hints["prefer_low_demand_output"] = True
                hints["prefer_microaction_over_long_response"] = True
        except (TypeError, ValueError):
            pass

        if has_routine or has_microactions:
            hints["prefer_system_response"] = True

        if fallback_recommended:
            if breakdown["response_memory"] < 0.30 and breakdown["intervention_availability"] < 0.30:
                hints["fallback_priority"] = "high"
            elif overall_confidence < 0.42:
                hints["fallback_priority"] = "medium"
            else:
                hints["fallback_priority"] = "low"

        return hints


def evaluate_internal_confidence(
    intent_analysis: Optional[Dict[str, Any]] = None,
    category_analysis: Optional[Dict[str, Any]] = None,
    state_analysis: Optional[Dict[str, Any]] = None,
    support_plan: Optional[Dict[str, Any]] = None,
    memory_summary: Optional[Dict[str, Any]] = None,
    memory_payload: Optional[Dict[str, Any]] = None,
    response_memory_payload: Optional[Dict[str, Any]] = None,
    routine_payload: Optional[Dict[str, Any]] = None,
    case_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    engine = ConfidenceEngine()
    return engine.evaluate(
        intent_analysis=intent_analysis,
        category_analysis=category_analysis,
        state_analysis=state_analysis,
        support_plan=support_plan,
        memory_summary=memory_summary,
        memory_payload=memory_payload,
        response_memory_payload=response_memory_payload,
        routine_payload=routine_payload,
        case_context=case_context,
    )
