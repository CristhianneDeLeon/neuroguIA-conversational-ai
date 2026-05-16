from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional


@dataclass
class LearningPattern:
    """
    Patrón reusable derivado de una respuesta curada por LLM.
    """

    pattern_id: str
    conversation_domain: Optional[str]
    support_goal: Optional[str]
    conversation_phase: Optional[str]
    speaker_role: Optional[str]

    detected_intent: Optional[str]
    detected_category: Optional[str]
    primary_state: Optional[str]
    secondary_states: List[str]

    selected_strategy: Optional[str]
    selected_microaction: Optional[str]
    selected_routine_type: Optional[str]

    curated_response_text: str
    quality_score: float

    approved_for_reuse: bool
    should_store_in_memory: bool

    tags: List[str]
    notes: Optional[str] = None


class LearningEngine:
    """
    Motor de aprendizaje estructural para NeuroGuIA.

    Responsabilidades:
    - transformar respuestas curadas del LLM en patrones reutilizables
    - decidir si vale la pena aprender de un caso
    - construir un payload compatible con response_memory
    - intentar guardar el patrón aprendido sin asumir una sola implementación
      de response_memory.py
    """

    MIN_QUALITY_TO_LEARN = 0.62
    MIN_QUALITY_TO_REUSE = 0.74

    def build_learning_payload(
        self,
        llm_curated_payload: Optional[Dict[str, Any]] = None,
        conversation_frame: Optional[Dict[str, Any]] = None,
        decision_payload: Optional[Dict[str, Any]] = None,
        state_analysis: Optional[Dict[str, Any]] = None,
        category_analysis: Optional[Dict[str, Any]] = None,
        intent_analysis: Optional[Dict[str, Any]] = None,
        stage_result: Optional[Dict[str, Any]] = None,
        active_profile: Optional[Dict[str, Any]] = None,
        case_id: Optional[str] = None,
        family_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Construye el payload de aprendizaje a partir de una respuesta LLM ya curada.
        """
        llm_curated_payload = llm_curated_payload or {}
        conversation_frame = conversation_frame or {}
        decision_payload = decision_payload or {}
        state_analysis = state_analysis or {}
        category_analysis = category_analysis or {}
        intent_analysis = intent_analysis or {}
        stage_result = stage_result or {}
        active_profile = active_profile or {}
        tags = tags or []

        approved = bool(llm_curated_payload.get("approved", False))
        curated_text = str(llm_curated_payload.get("curated_response_text") or "").strip()
        quality_score = float(llm_curated_payload.get("quality_score", 0.0) or 0.0)

        if not approved or not curated_text:
            return {
                "should_learn": False,
                "reason": "not_approved_or_empty",
                "pattern": None,
                "memory_payload": None,
            }

        if quality_score < self.MIN_QUALITY_TO_LEARN:
            return {
                "should_learn": False,
                "reason": "quality_below_learning_threshold",
                "pattern": None,
                "memory_payload": None,
            }

        pattern = self._build_pattern(
            llm_curated_payload=llm_curated_payload,
            conversation_frame=conversation_frame,
            decision_payload=decision_payload,
            state_analysis=state_analysis,
            category_analysis=category_analysis,
            intent_analysis=intent_analysis,
            stage_result=stage_result,
            active_profile=active_profile,
            tags=tags,
        )

        memory_payload = self._build_response_memory_payload(
            pattern=pattern,
            llm_curated_payload=llm_curated_payload,
            active_profile=active_profile,
            family_id=family_id,
            stage_result=stage_result,
            case_id=case_id,
        )

        return {
            "should_learn": True,
            "reason": "approved_high_quality_curated_response",
            "pattern": asdict(pattern),
            "memory_payload": memory_payload,
        }

    def try_store_in_response_memory(
        self,
        response_memory: Any,
        learning_payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Intenta guardar el aprendizaje usando el método disponible en response_memory.

        Soporta:
        - create_from_llm_fallback(...)
        - create_response(...)

        Devuelve un learning_store_result estructurado.
        """
        learning_payload = learning_payload or {}

        if not learning_payload.get("should_learn"):
            return {
                "stored": False,
                "reason": learning_payload.get("reason", "not_learning"),
                "response_id": None,
                "memory_payload": learning_payload.get("memory_payload"),
            }

        memory_payload = learning_payload.get("memory_payload") or {}
        if not memory_payload:
            return {
                "stored": False,
                "reason": "empty_memory_payload",
                "response_id": None,
                "memory_payload": None,
            }

        if response_memory is None:
            return {
                "stored": False,
                "reason": "response_memory_not_available",
                "response_id": None,
                "memory_payload": memory_payload,
            }

        if hasattr(response_memory, "create_from_llm_fallback"):
            try:
                response_id = response_memory.create_from_llm_fallback(**memory_payload)
                return {
                    "stored": True,
                    "reason": "stored_with_create_from_llm_fallback",
                    "response_id": response_id,
                    "memory_payload": memory_payload,
                }
            except Exception as exc:
                return {
                    "stored": False,
                    "reason": f"create_from_llm_fallback_failed:{exc}",
                    "response_id": None,
                    "memory_payload": memory_payload,
                }

        if hasattr(response_memory, "create_response"):
            try:
                response_id = response_memory.create_response(**memory_payload)
                return {
                    "stored": True,
                    "reason": "stored_with_create_response",
                    "response_id": response_id,
                    "memory_payload": memory_payload,
                }
            except Exception as exc:
                return {
                    "stored": False,
                    "reason": f"create_response_failed:{exc}",
                    "response_id": None,
                    "memory_payload": memory_payload,
                }

        return {
            "stored": False,
            "reason": "no_compatible_store_method_found",
            "response_id": None,
            "memory_payload": memory_payload,
        }

    # =========================================================
    # CONSTRUCCIÓN DEL PATRÓN
    # =========================================================
    def _build_pattern(
        self,
        llm_curated_payload: Dict[str, Any],
        conversation_frame: Dict[str, Any],
        decision_payload: Dict[str, Any],
        state_analysis: Dict[str, Any],
        category_analysis: Dict[str, Any],
        intent_analysis: Dict[str, Any],
        stage_result: Dict[str, Any],
        active_profile: Dict[str, Any],
        tags: List[str],
    ) -> LearningPattern:
        domain = conversation_frame.get("conversation_domain")
        goal = conversation_frame.get("support_goal")
        phase = conversation_frame.get("conversation_phase")
        speaker_role = conversation_frame.get("speaker_role")

        detected_intent = intent_analysis.get("detected_intent")
        detected_category = category_analysis.get("detected_category")
        primary_state = state_analysis.get("primary_state")
        secondary_states = state_analysis.get("secondary_states", []) or []

        selected_strategy = decision_payload.get("selected_strategy")
        selected_microaction = decision_payload.get("selected_microaction")
        selected_routine_type = decision_payload.get("selected_routine_type")

        curated_response_text = str(llm_curated_payload.get("curated_response_text") or "").strip()
        quality_score = float(llm_curated_payload.get("quality_score", 0.0) or 0.0)

        approved_for_reuse = bool(
            llm_curated_payload.get(
                "approved_for_reuse",
                quality_score >= self.MIN_QUALITY_TO_REUSE,
            )
        )
        should_store = bool(
            llm_curated_payload.get(
                "should_store_in_response_memory",
                quality_score >= self.MIN_QUALITY_TO_LEARN,
            )
        )

        pattern_id = self._build_pattern_id(
            domain=domain,
            goal=goal,
            phase=phase,
            speaker_role=speaker_role,
            detected_intent=detected_intent,
            detected_category=detected_category,
            primary_state=primary_state,
        )

        enriched_tags = self._build_tags(
            base_tags=tags,
            domain=domain,
            phase=phase,
            speaker_role=speaker_role,
            detected_category=detected_category,
            primary_state=primary_state,
            conditions=active_profile.get("conditions", []) or [],
        )

        return LearningPattern(
            pattern_id=pattern_id,
            conversation_domain=domain,
            support_goal=goal,
            conversation_phase=phase,
            speaker_role=speaker_role,
            detected_intent=detected_intent,
            detected_category=detected_category,
            primary_state=primary_state,
            secondary_states=list(secondary_states),
            selected_strategy=selected_strategy,
            selected_microaction=selected_microaction,
            selected_routine_type=selected_routine_type,
            curated_response_text=curated_response_text,
            quality_score=round(quality_score, 4),
            approved_for_reuse=approved_for_reuse,
            should_store_in_memory=should_store,
            tags=enriched_tags,
            notes="learned_from_curated_llm",
        )

    def _build_pattern_id(
        self,
        domain: Optional[str],
        goal: Optional[str],
        phase: Optional[str],
        speaker_role: Optional[str],
        detected_intent: Optional[str],
        detected_category: Optional[str],
        primary_state: Optional[str],
    ) -> str:
        parts = [
            domain or "no_domain",
            goal or "no_goal",
            phase or "no_phase",
            speaker_role or "no_role",
            detected_intent or "no_intent",
            detected_category or "no_category",
            primary_state or "no_state",
        ]
        return "|".join(parts)

    def _build_tags(
        self,
        base_tags: List[str],
        domain: Optional[str],
        phase: Optional[str],
        speaker_role: Optional[str],
        detected_category: Optional[str],
        primary_state: Optional[str],
        conditions: List[str],
    ) -> List[str]:
        tag_list = list(base_tags)
        tag_list.extend(
            [
                domain or "",
                phase or "",
                speaker_role or "",
                detected_category or "",
                primary_state or "",
                "llm_learned",
            ]
        )
        tag_list.extend([str(c).strip() for c in conditions if str(c).strip()])
        return self._deduplicate([t for t in tag_list if t])

    # =========================================================
    # PAYLOAD PARA RESPONSE MEMORY
    # =========================================================
    def _build_response_memory_payload(
        self,
        pattern: LearningPattern,
        llm_curated_payload: Dict[str, Any],
        active_profile: Dict[str, Any],
        family_id: Optional[str],
        stage_result: Dict[str, Any],
        case_id: Optional[str],
    ) -> Dict[str, Any]:
        structure = llm_curated_payload.get("curated_response_structure", {}) or {}

        return {
            "response_text": pattern.curated_response_text,
            "detected_intent": pattern.detected_intent,
            "detected_category": pattern.detected_category,
            "primary_state": pattern.primary_state,
            "conversation_stage": stage_result.get("stage"),
            "profile_id": active_profile.get("profile_id"),
            "family_id": active_profile.get("family_id") or family_id,
            "conditions_signature": active_profile.get("conditions", []) or [],
            "complexity_signature": active_profile.get("complexity_level"),
            "response_structure_json": {
                **structure,
                "pattern_id": pattern.pattern_id,
                "conversation_domain": pattern.conversation_domain,
                "support_goal": pattern.support_goal,
                "conversation_phase": pattern.conversation_phase,
                "speaker_role": pattern.speaker_role,
                "selected_strategy": pattern.selected_strategy,
                "selected_microaction": pattern.selected_microaction,
                "selected_routine_type": pattern.selected_routine_type,
            },
            "confidence_score": pattern.quality_score,
            "approved_for_reuse": pattern.approved_for_reuse,
            "tags": pattern.tags,
            "origin_case_id": case_id,
            "notes": pattern.notes,
        }

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