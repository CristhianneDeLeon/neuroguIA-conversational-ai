# -*- coding: utf-8 -*-
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Literal, Optional, Tuple

from core.support_playbooks import (
    Domain,
    OutcomePolarity,
    ResponsePlan,
    TurnFamily,
    UserSignal,
    build_response_plan,
    get_playbook_spec,
    infer_basic_signal,
    is_deterministic_support_route,
    render_deterministic_support_response,
)


def normalize_input(text: str) -> str:
    """Normaliza solo para matching interno; la respuesta visible conserva UTF-8."""

    normalized = unicodedata.normalize("NFKD", str(text or "").strip().lower())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    return " ".join(normalized.split())


GuidanceMode = Literal["advance", "hold", "close", "switch", "direct"]


@dataclass
class SupportFlowResult:
    handled: bool
    route_id: Domain
    conversation_domain: str
    turn_family: TurnFamily
    guidance_mode: GuidanceMode
    continuity_score: float
    continuity_reason: Optional[str]
    outcome: OutcomePolarity
    response_plan: Optional[ResponsePlan] = None
    signal: Optional[UserSignal] = None
    support_flow_state: Dict[str, Any] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "handled": self.handled,
            "route_id": self.route_id,
            "conversation_domain": self.conversation_domain,
            "turn_family": self.turn_family,
            "guidance_mode": self.guidance_mode,
            "continuity_score": self.continuity_score,
            "continuity_reason": self.continuity_reason,
            "outcome": self.outcome,
            "response_plan": self.response_plan,
            "signal": self.signal,
            "support_flow_state": dict(self.support_flow_state),
            "notes": list(self.notes),
        }


class SupportFlowEngine:
    """
    Minimal behavioral flow layer.

    Role:
    - decide the active support route
    - preserve continuity across follow-ups
    - translate the turn into a deterministic playbook call
    - optionally build a synthetic payload compatible with the orchestrator
    """

    ROUTE_TO_CONVERSATION_DOMAIN: Dict[Domain, str] = {
        "crisis": "crisis_activa",
        "ansiedad": "ansiedad_cognitiva",
        "bloqueo_ejecutivo": "disfuncion_ejecutiva",
        "sueno": "sueno_regulacion",
        "apoyo_infancia_neurodivergente": "apoyo_infancia_neurodivergente",
        "sobrecarga_cuidador": "sobrecarga_cuidador",
        "pregunta_simple": "apoyo_general",
        "meta_question": "apoyo_general",
        "validacion_emocional": "apoyo_general",
        "rechazo_estrategia": "apoyo_general",
        "depresion_baja_energia": "apoyo_general",
        "meditacion_guiada": "apoyo_general",
        "clarificacion": "apoyo_general",
        "cierre": "apoyo_general",
        "general": "apoyo_general",
    }

    ROUTE_TO_PHASE: Dict[Domain, str] = {
        "crisis": "containment",
        "ansiedad": "cognitive_unloading",
        "bloqueo_ejecutivo": "micro_start",
        "sueno": "wind_down",
        "apoyo_infancia_neurodivergente": "co_regulation",
        "sobrecarga_cuidador": "relief",
        "pregunta_simple": "clarification",
        "meta_question": "clarification",
        "validacion_emocional": "clarification",
        "rechazo_estrategia": "clarification",
        "depresion_baja_energia": "clarification",
        "meditacion_guiada": "clarification",
        "clarificacion": "clarification",
        "cierre": "clarification",
        "general": "clarification",
    }

    ROUTE_TO_GOAL: Dict[Domain, str] = {
        "crisis": "contain_and_protect",
        "ansiedad": "reduce_mental_overload",
        "bloqueo_ejecutivo": "enable_first_step",
        "sueno": "stabilize_sleep_transition",
        "apoyo_infancia_neurodivergente": "support_neurodivergent_child",
        "sobrecarga_cuidador": "reduce_caregiver_burden",
        "pregunta_simple": "answer_directly",
        "meta_question": "answer_directly",
        "validacion_emocional": "validate_and_stay_present",
        "rechazo_estrategia": "change_without_reset",
        "depresion_baja_energia": "lower_demand",
        "meditacion_guiada": "guide_short_regulation",
        "clarificacion": "clarify_without_reset",
        "cierre": "close_softly",
        "general": "clarify_and_support",
    }

    CATEGORY_TO_ROUTE: Dict[str, Domain] = {
        "crisis_activa": "crisis",
        "escalada_emocional": "crisis",
        "prevencion_escalada": "crisis",
        "regulacion_post_evento": "crisis",
        "ansiedad_cognitiva": "ansiedad",
        "disfuncion_ejecutiva": "bloqueo_ejecutivo",
        "sueno_regulacion": "sueno",
        "apoyo_infancia_neurodivergente": "apoyo_infancia_neurodivergente",
        "sobrecarga_cuidador": "sobrecarga_cuidador",
        "apoyo_general": "general",
    }

    STATE_TO_ROUTE: Dict[str, Domain] = {
        "meltdown": "crisis",
        "shutdown": "crisis",
        "emotional_dysregulation": "crisis",
        "cognitive_anxiety": "ansiedad",
        "general_distress": "ansiedad",
        "executive_dysfunction": "bloqueo_ejecutivo",
        "sleep_disruption": "sueno",
        "burnout": "sobrecarga_cuidador",
        "parental_fatigue": "sobrecarga_cuidador",
    }

    FOLLOWUP_FAMILIES = {
        "followup_acceptance",
        "clarification_request",
        "blocked_followup",
        "specific_action_request",
        "literal_phrase_request",
        "post_action_followup",
        "strategy_rejection",
        "outcome_report",
        "closure_or_pause",
    }
    DOMAIN_LOCKABLE_ROUTES = {
        "crisis",
        "ansiedad",
        "bloqueo_ejecutivo",
        "sueno",
        "apoyo_infancia_neurodivergente",
        "sobrecarga_cuidador",
    }
    DOMAIN_LOCK_FAMILIES = {
        "followup_acceptance",
        "post_action_followup",
        "clarification_request",
        "literal_phrase_request",
        "blocked_followup",
        "specific_action_request",
        "strategy_rejection",
        "outcome_report",
    }

    DIRECT_FAMILIES = {"meta_question", "simple_question"}

    META_MARKERS = [
        "quien eres",
        "quien sos",
        "cual es tu nombre",
        "tu nombre",
        "como puedo llamarte",
        "puedo hablar contigo",
        "puedo platicar contigo",
        "que puedes hacer",
    ]
    CLOSURE_MARKERS = [
        "ya estuvo",
        "aqui paro",
        "aqui paramos",
        "por ahora ya",
        "quiero parar",
        "vamos a parar",
        "ya no quiero seguir",
    ]
    REJECTION_MARKERS = [
        "no me sirve",
        "no me ayuda",
        "no sirves",
        "no ayudas",
        "eso no funciona",
        "otra cosa",
        "no quiero seguir por ahi",
        "eso no es",
        "eso no era",
        "no es lo que pregunte",
        "no es lo que pregunté",
        "eso no es lo que pregunte",
        "eso no es lo que pregunté",
        "eso no fue",
        "pero eso no",
        "yo la del problema",
        "yo el del problema",
        "la del problema es",
        "el del problema es",
    ]
    BLOCKED_MARKERS = [
        "no se",
        "no lo se",
        "no se como",
        "no tengo idea",
        "no tengo una idea clara",
        "no puedo",
        "no me sale",
        "no logro",
        "me gana",
        "todo se me junta",
    ]
    CLARIFICATION_MARKERS = [
        "no entiendo",
        "no te entiendo",
        "explicamelo",
        "explicame",
        "mas simple",
        "como",
        "cual",
    ]
    ACTION_CLARIFICATION_MARKERS = [
        "que frase",
        "que digo",
        "que le digo",
        "cual frase",
        "cual paso",
        "linea de que",
        "que linea",
        "que tipo",
        "por donde",
        "dime como",
        "dime cómo",
        "como",
        "cual",
    ]
    DIRECT_ACTION_QUESTION_MARKERS = [
        "que",
        "como",
        "cual",
        "por donde",
        "que hago",
        "que sigue",
        "que tipo",
        "que frase",
        "dime como",
        "dime cómo",
        "dime que hago",
        "dime qué hago",
        "linea de que",
    ]
    POST_ACTION_MARKERS = [
        "ya",
        "ya esta",
        "ya estuvo",
        "ya lo hice",
        "listo",
        "hecho",
        "y despues",
        "y luego",
        "que sigue",
        "que mas",
        "y ahora que",
        "ahora que",
    ]
    NEXT_STEP_MARKERS = [
        "y luego",
        "que sigue",
        "que mas",
        "dime",
        "dime como",
        "dime cómo",
        "tu dime",
        "tú dime",
        "ayudame",
        "ayúdame",
        "y despues",
        "y ahora que",
        "seguimos",
        "continua",
        "continuemos",
        "dale",
        "ok dime",
        "ok ayudame",
        "ok ayúdame",
    ]
    CONFIRMATION_MARKERS = [
        "ok",
        "si",
        "si ayudame",
        "si ayudame por favor",
        "ya",
        "listo",
        "aja",
        "vale",
        "ayudame",
        "ayudame por favor",
        "si por favor",
        "por favor",
        "va",
        "dale",
    ]
    LOOP_CUT_MARKERS = [
        "eso ya lo dijiste",
        "ya lo dijiste",
        "ya dijiste eso",
        "ya me dijiste eso",
        "eso ya me lo dijiste",
        "eso ya me lo dijiste antes",
        "me acabas de decir eso",
        "sigues repitiendo",
        "estas repitiendo",
        "estás repitiendo",
        "repites lo mismo",
    ]
    CRISIS_OTHER_REFERENCE_MARKERS = [
        "mi hijo",
        "mi hija",
        "alguien mas",
        "otra persona",
        "el esta",
        "ella esta",
        "el esta en crisis",
        "ella esta en crisis",
    ]
    CRISIS_OTHER_STATE_MARKERS = [
        "esta en crisis",
        "entro en crisis",
        "gritando",
        "golpeando",
        "se esta golpeando",
        "no lo puedo calmar",
        "no la puedo calmar",
        "hay crisis",
    ]
    SPECIFIC_ACTION_MARKERS = [
        "que hago",
        "por donde empiezo",
        "como empiezo",
        "dime el paso",
        "dime que hago",
    ]
    SIMPLE_QUESTION_MARKERS = [
        "me ayudas",
        "puedes ayudarme",
        "que haces",
        "sirves para",
    ]
    OUTCOME_IMPROVED_MARKERS = [
        "ya estoy mejor",
        "ya bajo",
        "ya bajo un poco",
        "me ayudo",
        "me ayudo un poco",
        "aflojo",
        "aflojo un poco",
    ]
    OUTCOME_WORSE_MARKERS = [
        "peor",
        "empeoro",
        "empeoro mas",
        "subio",
    ]
    OUTCOME_NO_CHANGE_MARKERS = [
        "sigo igual",
        "no cambio",
        "no ayudo",
        "no funciono",
        "sigue igual",
    ]
    SLEEP_PRIORITY_MARKERS = [
        "hay problemas de sueño",
        "sueño",
        "dormir",
        "duermo",
        "no duermo",
        "insomnio",
        "no puedo dormir",
        "me cuesta dormir",
        "dormir mal",
        "no descanso",
        "desvelo",
    ]
    CHILD_TARGET_MARKERS = [
        "mi hijo",
        "mi hija",
        "mi niña",
        "mi nino",
        "mi niño",
        "mi adolescente",
        "mis hijos",
    ]
    CHILD_PRONOUN_TARGET_MARKERS = [
        "ella",
        "el",
        "él",
    ]
    CHILD_CONCERN_MARKERS = [
        "sobrepensar",
        "sobre piensa",
        "sobrepiensa",
        "sobrepens",
        "pensamientos intrusivos",
        "pensamiento intrusivo",
        "intrusivos",
        "no pueden dormir",
        "ansiedad",
        "crisis",
        "saturada",
        "saturado",
        "no duerme",
        "no duermen",
        "se altera",
        "se bloquea",
        "bloquea",
        "aacc",
        "altas capacidades",
        "tea",
        "tdah",
        "problema es",
        "la del problema",
        "el del problema",
    ]
    CHILD_SUPPORT_MARKERS = [
        "como ayudo a mi hija",
        "como ayudo a mi hijo",
        "como ayudar a mi hija",
        "como ayudar a mi hijo",
        "ayudar a mi hija",
        "ayudar a mi hijo",
        "como ayudo a mis hijos",
        "como ayudar a mis hijos",
        "como le ayudo",
        "como lo ayudo",
        "como la ayudo",
        "como lo acompano",
        "como la acompano",
        "como le digo",
        "que le digo",
        "mi hija tiene ansiedad",
        "mi hijo tiene ansiedad",
        "mi hija no duerme",
        "mi hijo no duerme",
        "mi niña no duerme",
        "mi niño no duerme",
        "se altera",
        "se bloquea",
        "sobrepiensa",
        "sobrepens",
        "se satura",
        "saturacion",
        "corregulacion",
        "regularse",
        "estimulos",
        "rutina",
        "transicion",
    ]
    CAREGIVER_OVERLOAD_MARKERS = [
        "ya no puedo con esto",
        "ya no puedo",
        "no puedo mas",
        "me rebasa cuidar",
        "me pesa cuidar",
        "estoy agotada de cuidar",
        "estoy agotado de cuidar",
        "todo me toca a mi",
        "todo depende de mi",
        "nadie me ayuda",
        "estoy sola",
        "estoy solo",
    ]
    EXPLICIT_DOMAIN_SHIFT_MARKERS: Dict[Domain, List[str]] = {
        "crisis": [
            "ahora hay crisis",
            "ahora esta en crisis",
            "se esta golpeando",
            "no lo puedo calmar",
            "no la puedo calmar",
        ],
        "ansiedad": [
            "ahora estoy ansiosa",
            "ahora estoy ansioso",
            "me siento ansiosa",
            "me siento ansioso",
            "estoy ansiosa",
            "estoy ansioso",
            "esto me da ansiedad",
            "esto es ansiedad",
        ],
        "bloqueo_ejecutivo": [
            "ahora estoy bloqueada",
            "ahora estoy bloqueado",
            "esto es bloqueo",
            "no puedo empezar ahora",
        ],
        "sueno": [
            "esto es de sueño",
            "ahora no puedo dormir",
            "ahora el problema es dormir",
            "esto es insomnio",
        ],
        "apoyo_infancia_neurodivergente": [
            "como ayudo a mi hija",
            "como ayudo a mi hijo",
            "mi hija sobrepiensa",
            "mi hijo sobrepiensa",
            "mi hija se satura",
            "mi hijo se satura",
            "como le digo",
            "como lo acompano",
            "como la acompano",
        ],
        "sobrecarga_cuidador": [
            "ya no puedo con esto",
            "me rebasa cuidar",
            "nadie me ayuda",
            "estoy agotada de cuidar",
            "estoy agotado de cuidar",
        ],
    }
    ROUTE_TEXT_MARKERS: Dict[Domain, List[str]] = {
        "crisis": [
            "crisis",
            "gritando",
            "golpeando",
            "no la puedo calmar",
            "no lo puedo calmar",
            "hay riesgo",
        ],
        "ansiedad": [
            "ansiedad",
            "ansiosa",
            "ansioso",
            "me siento ansiosa",
            "me siento ansioso",
            "me gana todo",
            "me gana",
            "todo se me junta",
            "muy saturada",
            "muy saturado",
            "muy ansiosa",
            "muy ansioso",
        ],
        "bloqueo_ejecutivo": [
            "no puedo empezar",
            "no puedo arrancar",
            "no puedo organizarme",
            "organizarme",
            "organizar",
            "bloqueada",
            "bloqueado",
            "tarea",
            "archivo",
            "materia",
            "pendiente",
        ],
        "sueno": [
            "no duermo",
            "no puedo dormir",
            "dormir",
            "sueño",
            "desvelo",
            "insomnio",
            "pantalla antes de dormir",
        ],
        "apoyo_infancia_neurodivergente": [
            "como ayudo a mi hija",
            "como ayudo a mi hijo",
            "como ayudo a mis hijos",
            "mi hija sobrepiensa",
            "mi hijo sobrepiensa",
            "mi hija se satura",
            "mi hijo se satura",
            "como le digo",
            "como la acompano",
            "como lo acompano",
            "corregulacion",
            "rutina",
            "transicion",
        ],
        "meditacion_guiada": [
            "meditacion",
            "meditacion breve",
            "respiracion de un minuto",
            "respiracion 1 minuto",
            "grounding",
            "pausa guiada",
        ],
        "sobrecarga_cuidador": [
            "ya no puedo con esto",
            "cuidar",
            "me pesa cuidar",
            "agotada de cuidar",
            "agotado de cuidar",
            "nadie me ayuda",
            "todo me toca a mi",
        ],
    }
    ACTION_FOLLOWUP_FAMILIES = {
        "followup_acceptance",
        "post_action_followup",
        "blocked_followup",
        "clarification_request",
        "literal_phrase_request",
        "outcome_report",
    }
    COUNTED_ACTION_FOLLOWUP_FAMILIES = {
        "followup_acceptance",
        "post_action_followup",
        "blocked_followup",
        "outcome_report",
    }
    FOLLOWUP_EXIT_GOALS = {"close_temporarily", "decide_one_path", "switch_strategy"}
    FOLLOWUP_EXIT_THRESHOLD = 4
    # Disabled: stable demo mode now owns covered-domain progression before this
    # engine runs. Keeping this empty prevents old subroute progressions from
    # crossing ansiedad/crisis/sueno/bloqueo/infancia domains.
    DOMAIN_PROGRESSIONS: Dict[Domain, List[str]] = {}
    PROGRESSION_SUBROUTE_ALIASES: Dict[Domain, Dict[str, str]] = {}
    PROGRESSION_FOLLOWUP_FAMILIES = {
        "followup_acceptance",
        "post_action_followup",
        "specific_action_request",
    }
    PROGRESSION_FOLLOWUP_MARKERS = [
        "ok",
        "y luego",
        "que mas",
        "que sigue",
        "dime",
        "ahora que hago",
        "y ahora que hago",
        "dime que hago",
        "dime que sigue",
        "y despues",
        "despues",
    ]
    NEXT_DISTINCT_SUBROUTES: Dict[Domain, List[str]] = {
        "crisis": [
            "crisis_literal_phrase",
            "crisis_first_step",
            "crisis_check_effect",
            "crisis_close_temporarily",
        ],
        "ansiedad": [
            "anxiety_initial_grounding",
            "anxiety_visible_action",
            "anxiety_binary_decision",
            "anxiety_hold_after_partial_relief",
        ],
        "bloqueo_ejecutivo": [
            "executive_initial",
            "executive_no_se_que_toca",
            "executive_visible_next_step",
            "executive_decide_for_user",
        ],
        "sueno": [
            "sleep_initial",
            "sleep_followup",
            "sleep_mind_racing",
            "sleep_body_activated",
            "sleep_environment",
            "enough_for_now",
        ],
        "apoyo_infancia_neurodivergente": [
            "child_overthinking_support",
            "child_co_regulation",
            "child_clear_communication",
            "child_reduce_stimuli",
            "child_anticipation_routines",
        ],
        "sobrecarga_cuidador": [
            "caregiver_validation",
            "caregiver_reduce_load",
            "caregiver_ask_for_help",
            "caregiver_single_priority",
            "caregiver_self_care_without_guilt",
        ],
    }

    def resolve_turn(
        self,
        source_message: str,
        effective_message: Optional[str] = None,
        previous_frame: Optional[Dict[str, Any]] = None,
        conversation_frame: Optional[Dict[str, Any]] = None,
        conversation_control: Optional[Dict[str, Any]] = None,
        state_analysis: Optional[Dict[str, Any]] = None,
        category_analysis: Optional[Dict[str, Any]] = None,
        intent_analysis: Optional[Dict[str, Any]] = None,
        chat_history: Optional[List[Dict[str, Any]]] = None,
    ) -> SupportFlowResult:
        del conversation_frame, intent_analysis, chat_history

        previous_frame = previous_frame or {}
        conversation_control = conversation_control or {}
        state_analysis = state_analysis or {}
        category_analysis = category_analysis or {}
        text = str(effective_message or source_message or "").strip()

        if not text:
            return SupportFlowResult(
                handled=False,
                route_id="general",
                conversation_domain="apoyo_general",
                turn_family="new_request",
                guidance_mode="direct",
                continuity_score=0.0,
                continuity_reason=None,
                outcome="unknown",
                notes=["empty_message"],
            )

        previous_route = self._resolve_previous_route(previous_frame)
        action_memory = self._extract_action_memory(previous_frame=previous_frame, fallback_route=previous_route)
        turn_family = self._detect_turn_family(text=text, previous_frame=previous_frame)
        route_id = self._resolve_route_id(
            text=text,
            previous_frame=previous_frame,
            previous_route=previous_route,
            turn_family=turn_family,
            state_analysis=state_analysis,
            category_analysis=category_analysis,
            conversation_control=conversation_control,
        )
        continuity_score, continuity_reason = self._detect_continuity(
            previous_route=previous_route,
            route_id=route_id,
            turn_family=turn_family,
            previous_frame=previous_frame,
        )
        handled = self._is_covered(
            route_id=route_id,
            previous_route=previous_route,
            turn_family=turn_family,
            continuity_score=continuity_score,
        )

        outcome = self._detect_outcome(text)
        signal = infer_basic_signal(
            user_text=text,
            domain=route_id,
            turn_family=turn_family,
        )
        signal.active_subroute = self._resolve_active_subroute(
            previous_frame=previous_frame,
            route_id=route_id,
        )
        signal.outcome = outcome
        signal.asks_for_phrase = turn_family == "literal_phrase_request"
        signal.asks_for_next_step = turn_family in {"followup_acceptance", "post_action_followup"}
        signal.expresses_confusion = turn_family in {"clarification_request", "literal_phrase_request"}
        signal.expresses_rejection = turn_family == "strategy_rejection"
        signal.expresses_impossibility = turn_family == "blocked_followup"
        signal.wants_to_pause = turn_family == "closure_or_pause"
        signal.wants_to_continue = turn_family in {"followup_acceptance", "post_action_followup"}
        response_plan = (
            self._build_contextual_response_plan(
                signal=signal,
                route_id=route_id,
                previous_frame=previous_frame,
                action_memory=action_memory,
            )
            if handled
            else None
        )
        guidance_mode = self._resolve_guidance_mode(
            turn_family=turn_family,
            outcome=outcome,
            response_plan=response_plan,
        )

        spec = get_playbook_spec(route_id)
        previous_state = dict(previous_frame.get("support_flow_state") or {})
        step_index = self._next_step_index(
            previous_state=previous_state,
            route_id=route_id,
            guidance_mode=guidance_mode,
            continuity_score=continuity_score,
            max_steps=spec.max_steps if spec else 1,
        )
        conversation_domain = self.ROUTE_TO_CONVERSATION_DOMAIN.get(route_id, "apoyo_general")
        intercept_state = self._resolve_safety_intercept_state(
            previous_state=previous_state,
            route_id=route_id,
            conversation_domain=conversation_domain,
            response_plan=response_plan,
            turn_family=turn_family,
        )
        action_state = self._resolve_action_state(
            response_plan=response_plan,
            route_id=route_id,
            conversation_domain=conversation_domain,
            previous_action=action_memory,
        )
        followup_trace = self._resolve_followup_trace(
            previous_state=previous_state,
            turn_family=turn_family,
            route_id=route_id,
            continuity_score=continuity_score,
            action_memory=action_memory,
            response_plan=response_plan,
            outcome=outcome,
            guidance_mode=guidance_mode,
        )
        active_subroute_id = (
            (
                str(response_plan.state_subroute_id or response_plan.subroute_id or "").strip()
                if response_plan
                else ""
            )
            or signal.active_subroute
            or None
        )
        previous_subroute = signal.active_subroute
        recent_subroutes = self._resolve_recent_subroutes(
            previous_state=previous_state,
            route_id=route_id,
            active_subroute_id=active_subroute_id,
            previous_subroute=previous_subroute,
            continuity_score=continuity_score,
        )
        if response_plan and is_deterministic_support_route(route_id):
            response_plan = self._apply_deterministic_demo_response_plan(
                response_plan=response_plan,
                route_id=route_id,
                user_message=text,
                recent_subroutes=recent_subroutes,
            )
            normalized_active_subroute = (
                str(response_plan.state_subroute_id or response_plan.subroute_id or "").strip()
                or active_subroute_id
            )
            if normalized_active_subroute and normalized_active_subroute != active_subroute_id:
                active_subroute_id = normalized_active_subroute
                recent_subroutes = self._resolve_recent_subroutes(
                    previous_state=previous_state,
                    route_id=route_id,
                    active_subroute_id=active_subroute_id,
                    previous_subroute=previous_subroute,
                    continuity_score=continuity_score,
                )
            guidance_mode = self._resolve_guidance_mode(
                turn_family=turn_family,
                outcome=outcome,
                response_plan=response_plan,
            )
            step_index = self._next_step_index(
                previous_state=previous_state,
                route_id=route_id,
                guidance_mode=guidance_mode,
                continuity_score=continuity_score,
                max_steps=spec.max_steps if spec else 1,
            )
            action_state = self._resolve_action_state(
                response_plan=response_plan,
                route_id=route_id,
                conversation_domain=conversation_domain,
                previous_action=action_memory,
            )
        support_flow_state = {
            "active": handled,
            "handled_by": "support_flow_engine",
            "route_id": route_id,
            "active_route_id": route_id if handled and route_id in self.DOMAIN_LOCKABLE_ROUTES else None,
            "subroute_id": response_plan.subroute_id if response_plan else None,
            "active_subroute": active_subroute_id,
            "active_subroute_id": active_subroute_id,
            "previous_subroute": previous_subroute,
            "recent_subroutes": recent_subroutes,
            "conversation_domain": conversation_domain,
            "active_domain_lock": (
                route_id if handled and route_id in self.DOMAIN_LOCKABLE_ROUTES else None
            ),
            "turn_family": turn_family,
            "guidance_mode": guidance_mode,
            "continuity_score": continuity_score,
            "continuity_reason": continuity_reason,
            "step_index": step_index,
            "max_steps": spec.max_steps if spec else 1,
            "goal": response_plan.goal if response_plan else None,
            "humanization_required": bool(response_plan.humanization_required) if response_plan else False,
            "close_softly": bool(response_plan.close_softly) if response_plan else False,
            "playbook_tags": list(response_plan.tags) if response_plan else [],
            "last_action_instruction": action_state.get("last_action_instruction"),
            "last_action_type": action_state.get("last_action_type"),
            "last_action_goal": action_state.get("last_action_goal"),
            "last_action_domain": action_state.get("last_action_domain"),
            "action_followup_count": followup_trace.get("action_followup_count", 0),
            "recent_followup_modes": list(followup_trace.get("recent_followup_modes", [])),
            "followup_exit": followup_trace.get("followup_exit"),
            "last_safety_intercept_type": intercept_state.get("last_safety_intercept_type"),
            "pre_intercept_route": intercept_state.get("pre_intercept_route"),
            "pre_intercept_domain": intercept_state.get("pre_intercept_domain"),
            "pre_intercept_subroute": intercept_state.get("pre_intercept_subroute"),
            "awaiting_post_intercept_resume": intercept_state.get("awaiting_post_intercept_resume", False),
        }

        notes: List[str] = []
        if previous_route:
            notes.append(f"previous_route:{previous_route}")
        if active_subroute_id:
            notes.append(f"active_subroute:{active_subroute_id}")
        if previous_subroute and previous_subroute != active_subroute_id:
            notes.append(f"previous_subroute:{previous_subroute}")
        if continuity_reason:
            notes.append(f"continuity:{continuity_reason}")
        if followup_trace.get("followup_exit"):
            notes.append(f"followup_exit:{followup_trace['followup_exit']}")

        return SupportFlowResult(
            handled=handled,
            route_id=route_id,
            conversation_domain=conversation_domain,
            turn_family=turn_family,
            guidance_mode=guidance_mode,
            continuity_score=continuity_score,
            continuity_reason=continuity_reason,
            outcome=outcome,
            response_plan=response_plan,
            signal=signal,
            support_flow_state=support_flow_state,
            notes=notes,
        )

    def build_orchestrator_payloads(self, result: SupportFlowResult) -> Dict[str, Any]:
        if not result.handled or not result.response_plan:
            return {}

        response_text = self.render_response_text(result.response_plan)
        response_plan_payload = self._serialize_response_plan(result.response_plan)
        selected_subroute = result.response_plan.subroute_id or result.response_plan.goal
        selected_microaction = self._selected_microaction(result.response_plan)
        response_shape = self._response_shape(result)
        stage_name = "guided_support_flow"
        phase = self.ROUTE_TO_PHASE.get(result.route_id, "clarification")
        intervention_level = self._intervention_level(result)
        should_close = result.guidance_mode == "close" or bool(result.response_plan.close_softly)

        response_goal = {
            "goal": result.response_plan.goal,
            "strategy_signature": f"support_flow:{result.route_id}:{selected_subroute}:{result.response_plan.goal}",
            "response_shape": response_shape,
            "form_variant": result.guidance_mode,
            "intervention_level": intervention_level,
            "candidate_actions": self._candidate_actions(result.response_plan),
            "literal_phrase_candidates": [result.response_plan.literal_phrase] if result.response_plan.literal_phrase else [],
            "possible_questions": [],
            "should_offer_question": False,
            "followup_policy": "avoid",
            "selected_microaction": selected_microaction,
            "selected_strategy": selected_subroute,
            "selected_subroute": selected_subroute,
            "selected_routine_type": None,
            "suggested_content": [result.response_plan.main_response],
            "priority_order": [result.route_id, result.guidance_mode],
            "intervention_type": "guided_support_flow",
            "keep_minimal": should_close,
            "domain_focus": list(result.response_plan.tags),
            "humanization_required": bool(result.response_plan.humanization_required),
        }

        decision_payload = {
            "decision_mode": "support_flow_engine",
            "intervention_type": "guided_support_flow",
            "selected_strategy": selected_subroute,
            "selected_subroute": selected_subroute,
            "selected_microaction": selected_microaction,
            "selected_routine_type": None,
            "priority_order": response_goal["priority_order"],
            "avoid": [],
            "decision_flags": {
                "handled_by_support_flow_engine": True,
                "guidance_mode": result.guidance_mode,
                "turn_family": result.turn_family,
                "use_support_flow_plan": True,
                "requires_support_flow_humanization": bool(result.response_plan.humanization_required),
            },
            "response_goal": response_goal,
            "response_plan": response_goal,
            "support_flow_response_plan": response_plan_payload,
            "reuse_response_candidate": None,
        }

        stage_result = {
            "stage": stage_name,
            "conversation_domain": result.conversation_domain,
            "conversation_phase": phase,
            "continuity_phase": phase,
            "phase_changed": result.continuity_score >= 0.8,
            "phase_progression_reason": result.guidance_mode,
            "turn_type": result.turn_family,
            "turn_family": result.turn_family,
            "clarification_mode": (
                "support_flow" if result.turn_family in {"clarification_request", "literal_phrase_request"} else None
            ),
            "crisis_guided_mode": result.route_id == "crisis",
            "domain_shift": {"detected": False, "target_domain": result.conversation_domain},
            "intervention_level": intervention_level,
            "stuck_followup_count": int(result.support_flow_state.get("action_followup_count", 0) or 0),
            "progression_signals": {
                "guidance_mode": result.guidance_mode,
                "continuity_score": result.continuity_score,
                "action_followup_count": int(result.support_flow_state.get("action_followup_count", 0) or 0),
                "recent_followup_modes": list(result.support_flow_state.get("recent_followup_modes", [])),
            },
            "should_close_with_followup": not should_close,
        }

        confidence_payload = {
            "overall_confidence": 0.93 if result.continuity_score >= 0.8 else 0.88,
            "confidence_level": "high",
            "source": "support_flow_engine",
            "reason": "deterministic_playbook_flow",
        }

        fallback_payload = {
            "use_llm": bool(result.response_plan.humanization_required),
            "fallback_reason": "support_flow_humanization",
            "prompt_mode": "support_flow_humanization",
            "should_learn_if_good": False,
            "prefer_support_flow_local_humanizer": True,
        }

        llm_policy = {
            "should_use_llm": bool(result.response_plan.humanization_required),
            "reason": "support_flow_humanization",
            "prompt_mode": "support_flow_humanization",
            "domain": result.conversation_domain,
            "phase": phase,
            "category": result.conversation_domain,
            "intent": "guided_support",
        }

        conversational_intent = {
            "rhythm": "steady",
            "pressure": "low",
            "permissiveness": "high" if result.turn_family in {"blocked_followup", "closure_or_pause"} else "moderate",
            "closing_style": "soft_close" if should_close else "none",
        }

        response_package = {
            "response": response_text,
            "text": response_text,
            "mode": "guided_support_flow",
            "is_flow_engine_response": True,
            "suggested_strategy": decision_payload["selected_strategy"],
            "suggested_subroute": selected_subroute,
            "suggested_microaction": selected_microaction,
            "suggested_question": None,
            "response_metadata": {
                "source": "support_flow_engine",
                "is_flow_engine_response": True,
                "route_id": result.route_id,
                "subroute_id": selected_subroute,
                "turn_family": result.turn_family,
                "guidance_mode": result.guidance_mode,
                "requires_humanization": bool(result.response_plan.humanization_required),
                "response_plan": response_plan_payload,
                "support_flow_state": dict(result.support_flow_state),
            },
        }

        stage_hints = {
            "source": "support_flow_engine",
            "route_id": result.route_id,
            "subroute_id": selected_subroute,
            "turn_family": result.turn_family,
            "guidance_mode": result.guidance_mode,
        }

        conversation_control_updates = {
            "turn_type": result.turn_family,
            "turn_family": result.turn_family,
            "phase": phase,
            "domain": result.conversation_domain,
            "phase_progression_reason": result.guidance_mode,
            "last_action_instruction": result.support_flow_state.get("last_action_instruction"),
            "last_action_type": result.support_flow_state.get("last_action_type"),
            "last_action_goal": result.support_flow_state.get("last_action_goal"),
            "last_action_domain": result.support_flow_state.get("last_action_domain"),
            "subroute_id": selected_subroute,
            "support_flow_state": dict(result.support_flow_state),
        }

        conversation_frame_updates = {
            "conversation_domain": result.conversation_domain,
            "support_goal": self.ROUTE_TO_GOAL.get(result.route_id, "clarify_and_support"),
            "conversation_phase": phase,
            "turn_type": result.turn_family,
            "turn_family": result.turn_family,
            "continuity_score": result.continuity_score,
            "phase_progression_reason": result.guidance_mode,
            "last_action_instruction": result.support_flow_state.get("last_action_instruction"),
            "last_action_type": result.support_flow_state.get("last_action_type"),
            "last_action_goal": result.support_flow_state.get("last_action_goal"),
            "last_action_domain": result.support_flow_state.get("last_action_domain"),
            "subroute_id": selected_subroute,
            "support_flow_state": dict(result.support_flow_state),
        }

        return {
            "stage_result": stage_result,
            "stage_hints": stage_hints,
            "confidence_payload": confidence_payload,
            "decision_payload": decision_payload,
            "fallback_payload": fallback_payload,
            "llm_policy": llm_policy,
            "conversational_intent": conversational_intent,
            "response_package": response_package,
            "conversation_control_updates": conversation_control_updates,
            "conversation_frame_updates": conversation_frame_updates,
            "support_flow_response_plan": response_plan_payload,
        }

    def render_response_text(self, response_plan: ResponsePlan) -> str:
        parts: List[str] = []
        if response_plan.validation:
            parts.append(response_plan.validation.strip())
        if response_plan.main_response:
            parts.append(response_plan.main_response.strip())
        if response_plan.literal_phrase:
            parts.append(f'"{response_plan.literal_phrase.strip()}"')
        if response_plan.optional_followup:
            parts.append(response_plan.optional_followup.strip())
        return " ".join(part for part in parts if part).strip()

    def _apply_deterministic_demo_response_plan(
        self,
        response_plan: ResponsePlan,
        route_id: Domain,
        user_message: str,
        recent_subroutes: List[str],
    ) -> ResponsePlan:
        subroute_id = response_plan.subroute_id or response_plan.state_subroute_id
        progression_subroute = None
        if (
            route_id in self.DOMAIN_PROGRESSIONS
            and response_plan.goal not in {"safe_medication_boundary", "high_risk_redirect"}
        ):
            if (
                route_id == "apoyo_infancia_neurodivergente"
                and str(subroute_id or "").strip() == "child_co_regulation"
                and len([item for item in recent_subroutes if str(item or "").strip()]) <= 1
            ):
                progression_subroute = "child_initial_support"
            else:
                progression_subroute = self._enforce_domain_progression_subroute(route_id, subroute_id)

        deterministic_text = ""
        if progression_subroute:
            deterministic_text = self._domain_progression_response_text(
                route_id=route_id,
                subroute_id=progression_subroute,
            ).strip()
        if not deterministic_text:
            deterministic_text = render_deterministic_support_response(
                route_id=route_id,
                subroute_id=subroute_id,
                user_message=user_message,
                recent_subroutes=recent_subroutes,
            ).strip()
        if not deterministic_text:
            return response_plan

        tags = list(response_plan.tags)
        if "deterministic_demo" not in tags:
            tags.append("deterministic_demo")
        return replace(
            response_plan,
            validation="",
            main_response=deterministic_text,
            optional_followup=None,
            next_step=None,
            literal_phrase=None,
            micro_practice=None,
            safety_note=None,
            subroute_id=progression_subroute or response_plan.subroute_id,
            state_subroute_id=progression_subroute or response_plan.state_subroute_id,
            humanization_required=False,
            tags=tags,
        )

    def _make_engine_plan(
        self,
        route_id: Domain,
        subroute_id: Optional[str],
        *,
        goal: str,
        tone: str,
        validation: str,
        main_response: str,
        optional_followup: Optional[str] = None,
        next_step: Optional[str] = None,
        literal_phrase: Optional[str] = None,
        micro_practice: Optional[str] = None,
        safety_note: Optional[str] = None,
        close_softly: bool = False,
        needs_professional_redirect: bool = False,
        state_subroute_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> ResponsePlan:
        merged_tags: List[str] = []
        for candidate in [route_id, subroute_id or "", *(tags or [])]:
            cleaned = str(candidate or "").strip()
            if cleaned and cleaned not in merged_tags:
                merged_tags.append(cleaned)
        return ResponsePlan(
            goal=goal,
            tone=tone,
            validation=validation,
            main_response=main_response,
            optional_followup=optional_followup,
            next_step=next_step,
            literal_phrase=literal_phrase,
            micro_practice=micro_practice,
            safety_note=safety_note,
            close_softly=close_softly,
            needs_professional_redirect=needs_professional_redirect,
            route_id=route_id,
            subroute_id=subroute_id,
            state_subroute_id=state_subroute_id or subroute_id,
            humanization_required=True,
            tags=merged_tags,
        )

    def _serialize_response_plan(self, response_plan: ResponsePlan) -> Dict[str, Any]:
        return {
            "goal": response_plan.goal,
            "tone": response_plan.tone,
            "validation": response_plan.validation,
            "main_response": response_plan.main_response,
            "optional_followup": response_plan.optional_followup,
            "next_step": response_plan.next_step,
            "literal_phrase": response_plan.literal_phrase,
            "micro_practice": response_plan.micro_practice,
            "safety_note": response_plan.safety_note,
            "close_softly": bool(response_plan.close_softly),
            "needs_professional_redirect": bool(response_plan.needs_professional_redirect),
            "route_id": response_plan.route_id,
            "subroute_id": response_plan.subroute_id,
            "state_subroute_id": response_plan.state_subroute_id,
            "humanization_required": bool(response_plan.humanization_required),
            "tags": list(response_plan.tags),
        }

    def _resolve_recent_subroutes(
        self,
        previous_state: Dict[str, Any],
        route_id: Domain,
        active_subroute_id: Optional[str],
        previous_subroute: Optional[str],
        continuity_score: float,
    ) -> List[str]:
        same_route = previous_state.get("route_id") == route_id and continuity_score >= 0.7
        recent = list(previous_state.get("recent_subroutes") or []) if same_route else []
        for candidate in [previous_subroute, active_subroute_id]:
            cleaned = str(candidate or "").strip()
            if cleaned and (not recent or recent[-1] != cleaned):
                recent.append(cleaned)
        return recent[-6:]

    def _resolve_active_subroute(
        self,
        previous_frame: Dict[str, Any],
        route_id: Domain,
    ) -> Optional[str]:
        support_state = dict(previous_frame.get("support_flow_state") or {})
        related_route = (
            self._coerce_route(
                support_state.get("route_id")
                or support_state.get("active_domain_lock")
                or support_state.get("active_route_id")
                or support_state.get("active_route")
                or previous_frame.get("active_route_id")
                or previous_frame.get("active_route")
                or support_state.get("pre_intercept_route")
                or previous_frame.get("conversation_domain")
            )
        )
        if related_route and related_route != route_id:
            return None

        for candidate in [
            support_state.get("active_subroute"),
            support_state.get("active_subroute_id"),
            support_state.get("state_subroute_id"),
            support_state.get("subroute_id"),
            support_state.get("pre_intercept_subroute"),
        ]:
            subroute_id = str(candidate or "").strip()
            if subroute_id:
                return subroute_id
        return None

    def _resolve_previous_route(self, previous_frame: Dict[str, Any]) -> Optional[Domain]:
        support_state = previous_frame.get("support_flow_state") or {}
        for candidate in [
            support_state.get("active_domain_lock"),
            support_state.get("pre_intercept_route"),
            support_state.get("active_route_id"),
            support_state.get("active_route"),
            support_state.get("route_id"),
            previous_frame.get("active_route_id"),
            previous_frame.get("active_route"),
            previous_frame.get("last_action_domain"),
            support_state.get("last_action_domain"),
            previous_frame.get("pre_intercept_domain"),
            support_state.get("pre_intercept_domain"),
            previous_frame.get("conversation_domain"),
            support_state.get("conversation_domain"),
        ]:
            route_id = self._coerce_route(candidate)
            if route_id:
                return route_id
        return None

    def _resolve_route_id(
        self,
        text: str,
        previous_frame: Dict[str, Any],
        previous_route: Optional[Domain],
        turn_family: TurnFamily,
        state_analysis: Dict[str, Any],
        category_analysis: Dict[str, Any],
        conversation_control: Optional[Dict[str, Any]] = None,
    ) -> Domain:
        conversation_control = conversation_control or {}
        normalized = self._normalize(text)
        previous_state = dict(previous_frame.get("support_flow_state") or {})
        locked_route = self._resolve_active_domain_lock(previous_frame=previous_frame)
        control_route = self._coerce_route(
            conversation_control.get("active_route_id")
            or conversation_control.get("active_route")
            or conversation_control.get("route_id")
        )
        effective_previous_route = locked_route or control_route or previous_route

        if turn_family == "meta_question":
            return "meta_question"
        if (
            effective_previous_route in self.DOMAIN_PROGRESSIONS
            and self._is_progression_followup_text(normalized=normalized, turn_family=turn_family)
        ):
            return effective_previous_route
        if self._should_keep_crisis_domain(
            previous_route=effective_previous_route,
            normalized=normalized,
            turn_family=turn_family,
            conversation_control=conversation_control,
        ):
            return "crisis"
        if self._is_external_crisis_request(normalized):
            return "crisis"
        explicit_shift_route = self._resolve_explicit_domain_shift_route(
            normalized=normalized,
            conversation_control=conversation_control,
        )
        if explicit_shift_route:
            return explicit_shift_route
        if self._has_child_support_signal(normalized):
            return "apoyo_infancia_neurodivergente"

        if self._should_keep_active_domain_lock(
            locked_route=effective_previous_route,
            turn_family=turn_family,
            conversation_control=conversation_control,
        ):
            return effective_previous_route or "general"

        if turn_family == "simple_question" and not effective_previous_route:
            return "pregunta_simple"
        if turn_family == "closure_or_pause" and not effective_previous_route:
            return "cierre"
        if turn_family == "clarification_request" and not effective_previous_route:
            return "clarificacion"
        if turn_family == "strategy_rejection" and not effective_previous_route:
            return "rechazo_estrategia"

        resume_route = self._resume_pre_intercept_route(
            previous_state=previous_state,
            previous_route=effective_previous_route,
            turn_family=turn_family,
        )
        if resume_route:
            return resume_route

        if effective_previous_route and turn_family in self.FOLLOWUP_FAMILIES:
            return effective_previous_route

        if self._is_external_crisis_request(normalized):
            return "crisis"
        if self._has_child_support_signal(normalized):
            return "apoyo_infancia_neurodivergente"
        if self._contains_any(normalized, self.ROUTE_TEXT_MARKERS.get("crisis", [])):
            return "crisis"
        if self._has_strong_caregiver_signal(normalized):
            return "sobrecarga_cuidador"
        if self._has_strong_sleep_signal(normalized):
            return "sueno"

        route_from_category = self.CATEGORY_TO_ROUTE.get(str(category_analysis.get("detected_category") or "").strip())
        if route_from_category and route_from_category != "general":
            return route_from_category

        route_from_state = self.STATE_TO_ROUTE.get(str(state_analysis.get("primary_state") or "").strip())
        if route_from_state and route_from_state != "general":
            return route_from_state

        for route_id, markers in self.ROUTE_TEXT_MARKERS.items():
            if route_id == "crisis":
                continue
            if self._contains_any(normalized, markers):
                return route_id

        if turn_family == "blocked_followup":
            previous_domain = str(previous_frame.get("conversation_domain") or "").strip()
            return self.CATEGORY_TO_ROUTE.get(previous_domain, effective_previous_route or "general")

        return effective_previous_route or "general"

    def _detect_turn_family(self, text: str, previous_frame: Dict[str, Any]) -> TurnFamily:
        normalized = self._normalize(text)
        compact = self._compact_text(normalized)
        action_memory = self._extract_action_memory(previous_frame=previous_frame, fallback_route=self._resolve_previous_route(previous_frame))
        has_active_action = self._has_active_action(action_memory)

        if self._contains_any(normalized, self.META_MARKERS):
            return "meta_question"
        if self._contains_any(normalized, self.CLOSURE_MARKERS):
            return "closure_or_pause"
        if self._looks_like_outcome_report(normalized):
            return "outcome_report"
        if self._contains_any(normalized, self.BLOCKED_MARKERS):
            return "blocked_followup"
        if has_active_action and self._looks_like_current_action_clarification(normalized):
            if self._wants_literal_phrase(normalized=normalized, action_memory=action_memory):
                return "literal_phrase_request"
            return "clarification_request"
        if self._is_loop_cut_request(normalized):
            if self._has_recent_active_route(previous_frame):
                return "post_action_followup"
            return "strategy_rejection"
        if self._contains_any(normalized, self.REJECTION_MARKERS):
            return "strategy_rejection"
        if has_active_action and self._is_post_action_followup(compact):
            return "post_action_followup"
        if self._contains_any(normalized, self.CLARIFICATION_MARKERS):
            return "clarification_request"
        if self._is_simple_confirmation(compact=compact, previous_frame=previous_frame):
            return "followup_acceptance"
        if self._contains_any(normalized, self.NEXT_STEP_MARKERS):
            if has_active_action:
                return "post_action_followup"
            return "followup_acceptance"
        if self._contains_any(normalized, self.SPECIFIC_ACTION_MARKERS):
            return "specific_action_request"
        if has_active_action and normalized.endswith("?") and self._looks_like_direct_action_question(normalized):
            if self._wants_literal_phrase(normalized=normalized, action_memory=action_memory):
                return "literal_phrase_request"
            return "clarification_request"
        if self._contains_any(normalized, self.SIMPLE_QUESTION_MARKERS) or normalized.endswith("?"):
            return "simple_question"
        return "new_request"

    def _detect_outcome(self, text: str) -> OutcomePolarity:
        normalized = self._normalize(text)
        if self._contains_any(normalized, self.OUTCOME_WORSE_MARKERS):
            return "worse"
        if self._contains_any(normalized, self.OUTCOME_NO_CHANGE_MARKERS):
            return "no_change"
        if self._contains_any(normalized, self.OUTCOME_IMPROVED_MARKERS):
            if "un poco" in normalized:
                return "partial_relief"
            return "improved"
        return "unknown"

    def _detect_continuity(
        self,
        previous_route: Optional[Domain],
        route_id: Domain,
        turn_family: TurnFamily,
        previous_frame: Dict[str, Any],
    ) -> Tuple[float, Optional[str]]:
        if not previous_route:
            return 0.0, None

        if turn_family in self.FOLLOWUP_FAMILIES:
            return 0.96, "followup_on_active_route"

        if previous_route == route_id:
            return 0.82, "same_route_repeated"

        previous_domain = str(previous_frame.get("conversation_domain") or "").strip()
        current_domain = self.ROUTE_TO_CONVERSATION_DOMAIN.get(route_id)
        if previous_domain and previous_domain == current_domain:
            return 0.74, "same_conversation_domain"

        return 0.22, "new_route"

    def _is_covered(
        self,
        route_id: Domain,
        previous_route: Optional[Domain],
        turn_family: TurnFamily,
        continuity_score: float,
    ) -> bool:
        if route_id in {
            "crisis",
            "ansiedad",
            "bloqueo_ejecutivo",
            "sueno",
            "apoyo_infancia_neurodivergente",
            "sobrecarga_cuidador",
            "meta_question",
            "meditacion_guiada",
        }:
            return True
        if route_id in {"clarificacion", "rechazo_estrategia", "cierre", "pregunta_simple"}:
            return True
        if previous_route and continuity_score >= 0.7 and turn_family in self.FOLLOWUP_FAMILIES:
            return True
        return False

    def _resolve_guidance_mode(
        self,
        turn_family: TurnFamily,
        outcome: OutcomePolarity,
        response_plan: Optional[ResponsePlan],
    ) -> GuidanceMode:
        if response_plan and response_plan.goal == "close_temporarily":
            return "close"
        if response_plan and response_plan.goal == "switch_strategy":
            return "switch"
        if response_plan and response_plan.goal == "decide_one_path":
            return "hold"
        if turn_family in self.DIRECT_FAMILIES:
            return "direct"
        if turn_family == "closure_or_pause":
            return "close"
        if turn_family == "strategy_rejection" or outcome in {"no_change", "worse"}:
            return "switch"
        if turn_family in {"clarification_request", "blocked_followup", "literal_phrase_request"}:
            return "hold"
        if turn_family in {"followup_acceptance", "specific_action_request", "post_action_followup"}:
            return "advance"
        if outcome in {"partial_relief", "improved"} or (response_plan and response_plan.close_softly):
            return "hold"
        return "direct"

    def _next_step_index(
        self,
        previous_state: Dict[str, Any],
        route_id: Domain,
        guidance_mode: GuidanceMode,
        continuity_score: float,
        max_steps: int,
    ) -> int:
        previous_route = previous_state.get("route_id")
        previous_step = int(previous_state.get("step_index", 0) or 0)

        if previous_route != route_id or continuity_score < 0.7:
            return 0
        if guidance_mode == "advance":
            return min(previous_step + 1, max(max_steps - 1, 0))
        return previous_step

    def _response_shape(self, result: SupportFlowResult) -> str:
        plan = result.response_plan
        if not plan:
            return "simple_answer"
        if plan.literal_phrase:
            return "literal_phrase"
        if result.turn_family == "meta_question":
            return "meta_answer"
        if result.turn_family == "simple_question":
            return "simple_answer"
        if result.guidance_mode == "close":
            return "closure_pause"
        if result.guidance_mode == "switch":
            return "strategy_switch"
        if result.turn_family == "clarification_request":
            return "clarify_simple"
        if result.turn_family == "outcome_report":
            return "hold_line" if result.outcome in {"partial_relief", "improved"} else "check_effect"
        if plan.micro_practice:
            return "grounding"
        return "single_action"

    def _selected_microaction(self, response_plan: ResponsePlan) -> Optional[str]:
        if response_plan.literal_phrase:
            return None
        if response_plan.next_step:
            return response_plan.next_step.strip()
        if response_plan.micro_practice:
            return response_plan.micro_practice.strip()
        if response_plan.main_response:
            return response_plan.main_response.strip()
        return None

    def _candidate_actions(self, response_plan: ResponsePlan) -> List[str]:
        candidates: List[str] = []
        if response_plan.next_step:
            candidates.append(response_plan.next_step.strip())
        if response_plan.micro_practice:
            candidates.append(response_plan.micro_practice.strip())
        if response_plan.main_response:
            candidates.append(response_plan.main_response.strip())
        seen: List[str] = []
        for candidate in candidates:
            if candidate and candidate not in seen:
                seen.append(candidate)
        return seen

    def _intervention_level(self, result: SupportFlowResult) -> str:
        if result.route_id == "crisis":
            return "high"
        if result.guidance_mode in {"switch", "advance"}:
            return "medium"
        return "low"

    def _looks_like_outcome_report(self, normalized: str) -> bool:
        return (
            self._contains_any(normalized, self.OUTCOME_IMPROVED_MARKERS)
            or self._contains_any(normalized, self.OUTCOME_WORSE_MARKERS)
            or self._contains_any(normalized, self.OUTCOME_NO_CHANGE_MARKERS)
        )

    def _build_contextual_response_plan(
        self,
        signal: UserSignal,
        route_id: Domain,
        previous_frame: Dict[str, Any],
        action_memory: Dict[str, Any],
    ) -> ResponsePlan:
        normalized = self._normalize(signal.user_text)
        intercept_resume_plan = self._build_resume_after_medication_intercept_plan(
            route_id=route_id,
            turn_family=signal.turn_family,
            previous_frame=previous_frame,
        )
        if intercept_resume_plan:
            return intercept_resume_plan

        if route_id == "crisis" and self._is_external_crisis_request(normalized):
            return self._build_external_crisis_plan(normalized=normalized)

        if self._should_clarify_current_action(
            turn_family=signal.turn_family,
            normalized=normalized,
            action_memory=action_memory,
        ):
            return self._build_current_action_clarification_plan(
                route_id=route_id,
                normalized=normalized,
                action_memory=action_memory,
            )

        if self._should_cut_loop(
            route_id=route_id,
            normalized=normalized,
            previous_frame=previous_frame,
        ):
            return self._build_loop_cut_plan(
                route_id=route_id,
                normalized=normalized,
                previous_frame=previous_frame,
                action_memory=action_memory,
                outcome=signal.outcome,
            )

        if self._should_advance_domain_progression(
            route_id=route_id,
            normalized=normalized,
            turn_family=signal.turn_family,
            previous_frame=previous_frame,
        ):
            return self._build_domain_progression_plan(
                route_id=route_id,
                previous_frame=previous_frame,
                action_memory=action_memory,
            )

        if route_id == "bloqueo_ejecutivo" and self._contains_any(
            normalized,
            [
                "dame opciones",
                "dame tres opciones",
                "quiero opciones",
                "que opciones",
                "qué opciones",
                "como empiezo",
                "cómo empiezo",
                "como comienzo",
                "por donde empiezo",
                "que mas hago",
                "qué mas hago",
            ],
        ):
            return self._build_executive_distinct_plan(
                subroute_id="strategy_switch",
                prefix="",
            )

        if signal.turn_family == "specific_action_request" and self._has_recent_active_route(previous_frame):
            next_subroute = self._select_next_distinct_subroute(
                route_id=route_id,
                normalized=normalized,
                previous_state=dict(previous_frame.get("support_flow_state") or {}),
                force_distinct=False,
            )
            return self._build_distinct_subroute_plan(
                route_id=route_id,
                subroute_id=next_subroute,
                loop_cut=False,
            )

        if signal.turn_family == "blocked_followup":
            blocked_plan = self._build_blocked_followup_plan(
                route_id=route_id,
                normalized=normalized,
                action_memory=action_memory,
            )
            if blocked_plan:
                return blocked_plan

        if signal.turn_family in {"followup_acceptance", "post_action_followup"}:
            post_action_plan = self._build_post_action_followup_plan(
                route_id=route_id,
                normalized=normalized,
                previous_frame=previous_frame,
                action_memory=action_memory,
                outcome=signal.outcome,
            )
            if post_action_plan:
                return post_action_plan

        return build_response_plan(signal)

    def _extract_action_memory(
        self,
        previous_frame: Dict[str, Any],
        fallback_route: Optional[Domain],
    ) -> Dict[str, Any]:
        support_state = dict(previous_frame.get("support_flow_state") or {})
        last_action_domain = (
            previous_frame.get("last_action_domain")
            or support_state.get("last_action_domain")
            or previous_frame.get("active_route_id")
            or support_state.get("active_route_id")
            or previous_frame.get("active_route")
            or support_state.get("active_route")
            or previous_frame.get("conversation_domain")
            or support_state.get("conversation_domain")
            or self.ROUTE_TO_CONVERSATION_DOMAIN.get(fallback_route or "general", "apoyo_general")
        )
        return {
            "last_action_instruction": str(
                previous_frame.get("last_action_instruction")
                or support_state.get("last_action_instruction")
                or ""
            ).strip(),
            "last_action_type": str(
                previous_frame.get("last_action_type")
                or support_state.get("last_action_type")
                or ""
            ).strip(),
            "last_action_goal": str(
                previous_frame.get("last_action_goal")
                or support_state.get("last_action_goal")
                or ""
            ).strip(),
            "active_subroute_id": str(
                support_state.get("active_subroute")
                or support_state.get("active_subroute_id")
                or support_state.get("state_subroute_id")
                or support_state.get("subroute_id")
                or ""
            ).strip(),
            "previous_subroute": str(support_state.get("previous_subroute") or "").strip(),
            "recent_subroutes": list(support_state.get("recent_subroutes") or []),
            "last_action_domain": str(last_action_domain or "").strip(),
            "action_followup_count": int(support_state.get("action_followup_count", 0) or 0),
            "recent_followup_modes": list(support_state.get("recent_followup_modes") or []),
        }

    def _has_active_action(self, action_memory: Dict[str, Any]) -> bool:
        return any(
            str(action_memory.get(key) or "").strip()
            for key in ("last_action_instruction", "last_action_type", "last_action_goal")
        )

    def _looks_like_current_action_clarification(self, normalized: str) -> bool:
        if normalized in {"que", "como", "cual", "por donde"}:
            return True
        return self._contains_any(normalized, self.ACTION_CLARIFICATION_MARKERS)

    def _looks_like_direct_action_question(self, normalized: str) -> bool:
        if normalized in {"que", "como", "cual", "por donde"}:
            return True
        return self._contains_any(normalized, self.DIRECT_ACTION_QUESTION_MARKERS)

    def _compact_text(self, normalized: str) -> str:
        collapsed = re.sub(r"[^\w\s]", " ", normalized)
        return " ".join(collapsed.split())

    def _has_recent_active_route(self, previous_frame: Dict[str, Any]) -> bool:
        previous_state = dict(previous_frame.get("support_flow_state") or {})
        if previous_state.get("active") and self._resolve_active_domain_lock(previous_frame):
            return True
        if self._resolve_active_domain_lock(previous_frame):
            return True
        return self._resolve_previous_route(previous_frame) is not None

    def _is_simple_confirmation(self, compact: str, previous_frame: Dict[str, Any]) -> bool:
        if not compact:
            return False
        if compact not in self.CONFIRMATION_MARKERS:
            return False
        return self._has_recent_active_route(previous_frame)

    def _wants_literal_phrase(self, normalized: str, action_memory: Dict[str, Any]) -> bool:
        if self._contains_any(normalized, ["que frase", "que digo", "que le digo", "cual frase"]):
            return True
        return str(action_memory.get("last_action_type") or "").strip() == "literal_phrase"

    def _is_post_action_followup(self, compact: str) -> bool:
        if compact in {"ya", "listo", "hecho"}:
            return True
        return self._contains_any(compact, self.POST_ACTION_MARKERS)

    def _has_strong_sleep_signal(self, normalized: str) -> bool:
        return self._contains_any(normalized, self.SLEEP_PRIORITY_MARKERS)

    def _has_child_support_signal(self, normalized: str) -> bool:
        has_child_target = self._contains_any(normalized, self.CHILD_TARGET_MARKERS)
        has_pronoun_target = any(re.search(rf"\b{re.escape(normalize_input(marker))}\b", normalized) for marker in self.CHILD_PRONOUN_TARGET_MARKERS)
        has_child_concern = self._contains_any(normalized, self.CHILD_CONCERN_MARKERS)
        if has_pronoun_target and has_child_concern:
            has_child_target = True
        if not has_child_target:
            return False
        if self._has_strong_caregiver_signal(normalized):
            return False
        if has_child_concern:
            return True
        if self._contains_any(normalized, self.CHILD_SUPPORT_MARKERS):
            return True
        return any(token in normalized for token in {"como ayudo", "que le digo", "que hago con"})

    def _has_strong_caregiver_signal(self, normalized: str) -> bool:
        return self._contains_any(normalized, self.CAREGIVER_OVERLOAD_MARKERS)

    def _is_external_crisis_request(self, normalized: str) -> bool:
        return (
            self._contains_any(normalized, self.CRISIS_OTHER_REFERENCE_MARKERS)
            and self._contains_any(normalized, self.CRISIS_OTHER_STATE_MARKERS)
        )

    def _is_loop_cut_request(self, normalized: str) -> bool:
        return self._contains_any(normalized, self.LOOP_CUT_MARKERS)

    def _coerce_route(self, value: Any) -> Optional[Domain]:
        route = str(value or "").strip()
        if route in self.ROUTE_TO_CONVERSATION_DOMAIN:
            return route  # type: ignore[return-value]
        mapped = self.CATEGORY_TO_ROUTE.get(route)
        if mapped:
            return mapped
        return None

    def _resolve_active_domain_lock(self, previous_frame: Dict[str, Any]) -> Optional[Domain]:
        support_state = dict(previous_frame.get("support_flow_state") or {})
        for candidate in [
            support_state.get("active_domain_lock"),
            support_state.get("pre_intercept_route"),
            support_state.get("active_route_id"),
            support_state.get("active_route"),
            support_state.get("route_id"),
            previous_frame.get("active_route_id"),
            previous_frame.get("active_route"),
            previous_frame.get("last_action_domain"),
            support_state.get("last_action_domain"),
            previous_frame.get("pre_intercept_domain"),
            support_state.get("pre_intercept_domain"),
        ]:
            route = self._coerce_route(candidate)
            if route and route in self.DOMAIN_LOCKABLE_ROUTES:
                return route
        return None

    def _resolve_explicit_domain_shift_route(
        self,
        normalized: str,
        conversation_control: Dict[str, Any],
    ) -> Optional[Domain]:
        if self._has_child_support_signal(normalized):
            return "apoyo_infancia_neurodivergente"

        if self._is_external_crisis_request(normalized):
            return "crisis"

        domain_shift = dict(conversation_control.get("domain_shift", {}) or {})
        if domain_shift.get("detected"):
            shifted_route = self._coerce_route(domain_shift.get("shift_domain"))
            if shifted_route:
                return shifted_route

        context_override = dict(conversation_control.get("context_override", {}) or {})
        if context_override.get("active") and context_override.get("type") == "override_hard":
            override_route = self._coerce_route(context_override.get("target"))
            if override_route:
                return override_route

        if self._contains_any(normalized, self.ROUTE_TEXT_MARKERS.get("crisis", [])):
            return "crisis"

        if self._has_child_support_signal(normalized):
            return "apoyo_infancia_neurodivergente"

        if self._has_strong_caregiver_signal(normalized):
            return "sobrecarga_cuidador"

        for route_id, markers in self.EXPLICIT_DOMAIN_SHIFT_MARKERS.items():
            if self._contains_any(normalized, markers):
                return route_id
        return None

    def _should_keep_crisis_domain(
        self,
        previous_route: Optional[Domain],
        normalized: str,
        turn_family: TurnFamily,
        conversation_control: Dict[str, Any],
    ) -> bool:
        if previous_route != "crisis":
            return False
        if self._is_external_crisis_request(normalized):
            return True
        if self._has_strong_non_crisis_context_shift(
            normalized=normalized,
            conversation_control=conversation_control,
        ):
            return False
        return turn_family in self.FOLLOWUP_FAMILIES or self._is_ambiguous_followup_text(normalized)

    def _has_strong_non_crisis_context_shift(
        self,
        normalized: str,
        conversation_control: Dict[str, Any],
    ) -> bool:
        context_override = dict(conversation_control.get("context_override", {}) or {})
        if context_override.get("active") and context_override.get("type") == "override_hard":
            override_route = self._coerce_route(context_override.get("target"))
            if override_route and override_route != "crisis":
                return True

        for route_id, markers in self.EXPLICIT_DOMAIN_SHIFT_MARKERS.items():
            if route_id != "crisis" and self._contains_any(normalized, markers):
                return True

        domain_shift = dict(conversation_control.get("domain_shift", {}) or {})
        if domain_shift.get("detected"):
            shifted_route = self._coerce_route(domain_shift.get("shift_domain"))
            if shifted_route and shifted_route != "crisis" and not self._is_ambiguous_followup_text(normalized):
                return True
        return False

    def _is_ambiguous_followup_text(self, normalized: str) -> bool:
        compact = self._compact_text(normalized)
        if compact in self.CONFIRMATION_MARKERS:
            return True
        if self._is_loop_cut_request(normalized):
            return True
        if self._contains_any(normalized, self.ACTION_CLARIFICATION_MARKERS):
            return True
        if self._contains_any(normalized, self.NEXT_STEP_MARKERS):
            return True
        return compact in {"no puedo", "no se", "no lo se", "ayuda", "ayudame"}

    def _should_keep_active_domain_lock(
        self,
        locked_route: Optional[Domain],
        turn_family: TurnFamily,
        conversation_control: Dict[str, Any],
    ) -> bool:
        if not locked_route:
            return False
        if locked_route not in self.DOMAIN_LOCKABLE_ROUTES:
            return False
        turn_type = str(conversation_control.get("turn_type") or "").strip()
        if turn_family in self.DOMAIN_LOCK_FAMILIES:
            return True
        return turn_type in {"followup_acceptance", "followup_request", "clarification", "continuation"}

    def _resume_pre_intercept_route(
        self,
        previous_state: Dict[str, Any],
        previous_route: Optional[Domain],
        turn_family: TurnFamily,
    ) -> Optional[Domain]:
        if turn_family != "followup_acceptance":
            return None
        if str(previous_state.get("last_safety_intercept_type") or "").strip() != "medication_boundary":
            return None
        pre_intercept_route = self._coerce_route(previous_state.get("pre_intercept_route"))
        return pre_intercept_route or previous_route

    def _resolve_safety_intercept_state(
        self,
        previous_state: Dict[str, Any],
        route_id: Domain,
        conversation_domain: str,
        response_plan: Optional[ResponsePlan],
        turn_family: TurnFamily,
    ) -> Dict[str, Any]:
        current_type = str(previous_state.get("last_safety_intercept_type") or "").strip() or None
        current_route = self._coerce_route(previous_state.get("pre_intercept_route"))
        current_domain = str(previous_state.get("pre_intercept_domain") or "").strip() or None
        current_subroute = str(previous_state.get("pre_intercept_subroute") or "").strip() or None
        awaiting_resume = bool(previous_state.get("awaiting_post_intercept_resume"))

        if response_plan and response_plan.goal == "safe_medication_boundary":
            preserved_route = (
                (current_route if current_type == "medication_boundary" and awaiting_resume else None)
                or self._coerce_route(previous_state.get("route_id"))
                or route_id
            )
            preserved_domain = (
                (current_domain if current_type == "medication_boundary" and awaiting_resume else None)
                or str(previous_state.get("conversation_domain") or "").strip()
                or self.ROUTE_TO_CONVERSATION_DOMAIN.get(preserved_route, conversation_domain)
            )
            preserved_subroute = (
                (current_subroute if current_type == "medication_boundary" and awaiting_resume else None)
                or str(previous_state.get("active_subroute_id") or previous_state.get("state_subroute_id") or previous_state.get("subroute_id") or "").strip()
                or None
            )
            return {
                "last_safety_intercept_type": "medication_boundary",
                "pre_intercept_route": preserved_route,
                "pre_intercept_domain": preserved_domain,
                "pre_intercept_subroute": preserved_subroute,
                "awaiting_post_intercept_resume": True,
            }

        if current_type == "medication_boundary" and turn_family == "followup_acceptance":
            return {
                "last_safety_intercept_type": None,
                "pre_intercept_route": current_route or route_id,
                "pre_intercept_domain": current_domain or self.ROUTE_TO_CONVERSATION_DOMAIN.get(current_route or route_id, conversation_domain),
                "pre_intercept_subroute": current_subroute,
                "awaiting_post_intercept_resume": False,
            }

        if current_type == "medication_boundary" and awaiting_resume:
            return {
                "last_safety_intercept_type": current_type,
                "pre_intercept_route": current_route or route_id,
                "pre_intercept_domain": current_domain or self.ROUTE_TO_CONVERSATION_DOMAIN.get(current_route or route_id, conversation_domain),
                "pre_intercept_subroute": current_subroute,
                "awaiting_post_intercept_resume": True,
            }

        return {
            "last_safety_intercept_type": None,
            "pre_intercept_route": None,
            "pre_intercept_domain": None,
            "pre_intercept_subroute": None,
            "awaiting_post_intercept_resume": False,
        }

    def _build_resume_after_medication_intercept_plan(
        self,
        route_id: Domain,
        turn_family: TurnFamily,
        previous_frame: Dict[str, Any],
    ) -> Optional[ResponsePlan]:
        if turn_family != "followup_acceptance":
            return None

        previous_state = dict(previous_frame.get("support_flow_state") or {})
        if str(previous_state.get("last_safety_intercept_type") or "").strip() != "medication_boundary":
            return None

        resumed_route = (
            self._coerce_route(previous_state.get("pre_intercept_route"))
            or route_id
        )
        resumed_subroute = str(previous_state.get("pre_intercept_subroute") or "").strip() or None
        if resumed_route == "sueno":
            return self._make_engine_plan(
                route_id="sueno",
                subroute_id="sleep_initial",
                goal="resume_sleep_after_medication_boundary",
                tone="calido_directo",
                validation="Va.",
                main_response=(
                    "Entonces vamos con algo no farmacologico para esta noche: "
                    "baja una sola fuente de estimulo como pantalla, luz o ruido durante 10 minutos antes de acostarte."
                ),
                optional_followup="Si quieres, luego vemos si lo que mas pesa es la mente, el cuerpo o el entorno.",
                state_subroute_id=resumed_subroute or "sleep_initial",
                tags=["resume_after_medication_boundary", "non_pharmacological_step"],
            )

        resumed_signal = UserSignal(
            domain=resumed_route,
            turn_family="followup_acceptance",
            user_text="",
            asks_for_next_step=True,
            wants_to_continue=True,
            active_subroute=resumed_subroute,
        )
        return build_response_plan(resumed_signal)

    def _should_clarify_current_action(
        self,
        turn_family: TurnFamily,
        normalized: str,
        action_memory: Dict[str, Any],
    ) -> bool:
        if not self._has_active_action(action_memory):
            return False
        if turn_family in {"clarification_request", "literal_phrase_request"}:
            return True
        if turn_family == "simple_question" and self._looks_like_direct_action_question(normalized):
            return True
        return False

    def _build_external_crisis_plan(self, normalized: str) -> ResponsePlan:
        del normalized
        return self._make_engine_plan(
            route_id="crisis",
            subroute_id="crisis_external_coregulation",
            goal="external_crisis_coregulation",
            tone="firme_calmo",
            validation="Estoy contigo.",
            main_response=(
                "Si tu hija o hijo está en crisis, lo primero es bajar carga alrededor: baja tu tono, "
                "usa frases muy breves, no discutas, no expliques demasiado y baja estímulos alrededor."
            ),
            next_step="Baja tono, frases breves, no discutir y menos estimulos",
            optional_followup="Si hay riesgo de golpearse o hacer daño, prioriza distancia segura y ayuda presencial.",
            state_subroute_id="crisis_first_step",
            tags=["external_crisis", "co_regulation", "reduce_stimuli"],
        )

    def _should_cut_loop(
        self,
        route_id: Domain,
        normalized: str,
        previous_frame: Dict[str, Any],
    ) -> bool:
        if not self._is_loop_cut_request(normalized):
            return False
        previous_state = dict(previous_frame.get("support_flow_state") or {})
        previous_route = self._coerce_route(
            previous_state.get("route_id")
            or previous_state.get("active_route_id")
            or previous_frame.get("active_route_id")
            or previous_state.get("active_domain_lock")
            or previous_frame.get("conversation_domain")
        )
        if previous_route and previous_route != route_id:
            return False
        return self._has_recent_active_route(previous_frame) or bool(
            previous_state.get("active_subroute")
            or previous_state.get("active_subroute_id")
            or previous_state.get("subroute_id")
            or previous_state.get("recent_subroutes")
        )

    def _build_loop_cut_plan(
        self,
        route_id: Domain,
        normalized: str,
        previous_frame: Dict[str, Any],
        action_memory: Dict[str, Any],
        outcome: OutcomePolarity,
    ) -> ResponsePlan:
        previous_state = dict(previous_frame.get("support_flow_state") or {})
        if self._should_force_followup_exit_for_current(
            previous_state=previous_state,
            action_memory=action_memory,
        ):
            return self._build_followup_exit_plan(
                route_id=route_id,
                normalized=normalized,
                outcome=outcome,
            )

        next_subroute = self._select_next_distinct_subroute(
            route_id=route_id,
            normalized=normalized,
            previous_state=previous_state,
            force_distinct=True,
        )
        return self._build_distinct_subroute_plan(
            route_id=route_id,
            subroute_id=next_subroute,
            loop_cut=True,
        )

    def get_next_subroute(self, current_subroute: Optional[str], route_id: Domain) -> Optional[str]:
        progression = self.DOMAIN_PROGRESSIONS.get(route_id)
        if not progression:
            return current_subroute

        normalized_current = str(current_subroute or "").strip()
        normalized_current = self.PROGRESSION_SUBROUTE_ALIASES.get(route_id, {}).get(
            normalized_current,
            normalized_current,
        )
        if normalized_current not in progression:
            return progression[0]

        index = progression.index(normalized_current)
        if index < len(progression) - 1:
            return progression[index + 1]

        return progression[-1]

    def _is_progression_followup_text(self, normalized: str, turn_family: TurnFamily) -> bool:
        if turn_family not in self.PROGRESSION_FOLLOWUP_FAMILIES:
            return False
        compact = self._compact_text(normalized)
        if compact in self.CONFIRMATION_MARKERS:
            return True
        return self._contains_any(normalized, self.PROGRESSION_FOLLOWUP_MARKERS)

    def _should_advance_domain_progression(
        self,
        route_id: Domain,
        normalized: str,
        turn_family: TurnFamily,
        previous_frame: Dict[str, Any],
    ) -> bool:
        if route_id not in self.DOMAIN_PROGRESSIONS:
            return False
        if not self._has_recent_active_route(previous_frame):
            return False
        return self._is_progression_followup_text(normalized=normalized, turn_family=turn_family)

    def _build_domain_progression_plan(
        self,
        route_id: Domain,
        previous_frame: Dict[str, Any],
        action_memory: Dict[str, Any],
    ) -> ResponsePlan:
        previous_state = dict(previous_frame.get("support_flow_state") or {})
        current_subroute = (
            self._current_subroute_from_state(previous_state)
            or str(action_memory.get("active_subroute_id") or "").strip()
            or None
        )
        next_subroute = self.get_next_subroute(current_subroute=current_subroute, route_id=route_id)
        next_subroute = self._enforce_domain_progression_subroute(route_id, next_subroute)
        return self._build_progression_subroute_plan(route_id=route_id, subroute_id=next_subroute)

    def _enforce_domain_progression_subroute(
        self,
        route_id: Domain,
        subroute_id: Optional[str],
    ) -> str:
        progression = self.DOMAIN_PROGRESSIONS.get(route_id) or []
        fallback = progression[0] if progression else str(subroute_id or "").strip()
        candidate = str(subroute_id or "").strip()
        candidate = self.PROGRESSION_SUBROUTE_ALIASES.get(route_id, {}).get(candidate, candidate)
        if not candidate:
            return fallback
        if candidate in progression:
            return candidate

        forbidden_prefixes = {
            "ansiedad": ("crisis_", "sleep_", "executive_", "child_"),
            "sueno": ("anxiety_", "crisis_", "executive_", "child_"),
            "crisis": ("anxiety_", "sleep_", "executive_", "child_"),
            "bloqueo_ejecutivo": ("anxiety_", "crisis_", "sleep_", "child_"),
            "apoyo_infancia_neurodivergente": ("anxiety_", "crisis_", "sleep_", "executive_"),
        }.get(route_id, ())
        if forbidden_prefixes and candidate.startswith(forbidden_prefixes):
            return fallback
        return fallback

    def _block_cross_domain_subroute(self, route_id: Domain, subroute_id: Optional[str]) -> str:
        candidate = str(subroute_id or "").strip()
        if not candidate:
            return candidate
        forbidden_prefixes = {
            "ansiedad": ("crisis_", "sleep_", "executive_", "child_"),
            "sueno": ("anxiety_", "crisis_", "executive_", "child_"),
            "crisis": ("anxiety_", "sleep_", "executive_", "child_"),
        }.get(route_id, ())
        if forbidden_prefixes and candidate.startswith(forbidden_prefixes):
            progression = self.DOMAIN_PROGRESSIONS.get(route_id) or []
            return progression[0] if progression else candidate
        return candidate

    def _build_progression_subroute_plan(self, route_id: Domain, subroute_id: Optional[str]) -> ResponsePlan:
        safe_subroute = self._enforce_domain_progression_subroute(route_id, subroute_id)
        close_subroutes = {
            "anxiety_hold_after_partial_relief",
            "crisis_close_temporarily",
            "sleep_followup",
            "executive_close",
            "child_close",
        }
        return self._make_engine_plan(
            route_id=route_id,
            subroute_id=safe_subroute,
            goal="domain_progression_step",
            tone="claro_directo",
            validation="",
            main_response=self._domain_progression_response_text(route_id, safe_subroute),
            close_softly=safe_subroute in close_subroutes,
            state_subroute_id=safe_subroute,
            tags=["domain_progression", safe_subroute],
        )

    def _domain_progression_response_text(self, route_id: Domain, subroute_id: Optional[str]) -> str:
        responses: Dict[Domain, Dict[str, str]] = {
            "ansiedad": {
                "anxiety_initial_grounding": "Estoy contigo. Primero baja una sola señal del cuerpo: apoya ambos pies y suelta el aire lento una vez.",
                "anxiety_visible_action": "Ahora saca una preocupación de la cabeza: escribe una sola línea con lo que más pesa. No la resuelvas todavía.",
                "anxiety_binary_decision": "Ahora ciérralo en una decisión simple: si requiere acción hoy, atiende solo eso; si no requiere acción hoy, queda quieto por ahora.",
                "anxiety_hold_after_partial_relief": "Por ahora basta. No abras otra técnica ni otro frente; deja quieto lo demás y sostén lo que ya bajó.",
            },
            "crisis": {
                "crisis_first_step": "Estoy contigo. Primero bajemos una sola demanda: ruido, preguntas, gente o luz. Solo una.",
                "crisis_literal_phrase": "Ahora usa pocas palabras. Puedes decir: 'Estoy aquí. No tienes que explicar nada. Vamos a bajar esto.' Mantén distancia segura y no discutas.",
                "crisis_environment_adjustment": "Ahora cambia una sola cosa del entorno: menos gente, menos ruido o más espacio físico. No agregues explicación ni debate.",
                "crisis_close_temporarily": "Por ahora no agregues otra demanda. Sostén pocas palabras, distancia segura y el entorno lo más bajo posible.",
            },
            "sueno": {
                "sleep_initial": "Sí, el sueño puede mover todo lo demás. Vamos a ubicar qué parte pesa más: mente acelerada, cuerpo activado o entorno.",
                "sleep_environment": "Para esta noche: baja luz o pantalla durante 10 minutos. No intentes resolver todo el sueño de golpe.",
                "sleep_mind_racing": "Si la mente sigue acelerada, escribe una sola preocupación en una nota y ciérrala. Solo una.",
                "sleep_followup": "Por ahora basta con esa bajada. Mantén luz baja o pantalla fuera y no agregues otra medida esta noche.",
            },
            "bloqueo_ejecutivo": {
                "executive_initial": "No empecemos por organizar todo. Elige una de estas tres: abrir el archivo, escribir el título o poner un temporizador de 2 minutos.",
                "executive_visible_next_step": "Entonces lo hago más concreto: abre el archivo o cuaderno que tengas más cerca. No escribas nada todavía. Solo abrirlo.",
                "executive_expand_action": "Ahora escribe solo el título o una primera frase fea. No tiene que quedar bien; solo tiene que existir.",
                "executive_close": "Por ahora basta. Deja eso abierto o escrito y no intentes ordenar todo lo demás en este mismo paso.",
            },
            "apoyo_infancia_neurodivergente": {
                "child_initial_support": "Claro. Aquí el foco son tus hijos: baja estímulos, usa frases cortas y saca una sola preocupación a papel o voz.",
                "child_single_concern": "Pídele que elija una sola preocupación. Una. La escriben o la dicen en voz alta, y no abren las demás todavía.",
                "child_co_regulation": "Ahora acompaña con presencia calmada, voz baja y una frase corta. No agregues varias explicaciones.",
                "child_close": "Por ahora basta con una sola ayuda sostenida. Observa si baja un poco antes de meter otra indicación.",
            },
        }
        return responses.get(route_id, {}).get(str(subroute_id or "").strip(), "")

    def _select_next_distinct_subroute(
        self,
        route_id: Domain,
        normalized: str,
        previous_state: Dict[str, Any],
        force_distinct: bool = False,
    ) -> str:
        sequence = self.NEXT_DISTINCT_SUBROUTES.get(route_id) or []
        if not sequence:
            return "strategy_switch" if force_distinct else "i_dont_understand"

        active_subroute = self._current_subroute_from_state(previous_state)
        recent_subroutes = [
            str(item or "").strip()
            for item in list(previous_state.get("recent_subroutes") or [])
            if str(item or "").strip()
        ]

        if force_distinct and not active_subroute:
            forced_by_route = {
                "crisis": "crisis_literal_phrase",
                "ansiedad": "strategy_switch",
                "bloqueo_ejecutivo": "strategy_switch",
                "sueno": "sleep_followup",
            }.get(route_id)
            if forced_by_route:
                return forced_by_route
        if not active_subroute and route_id == "ansiedad":
            return "anxiety_visible_action"

        if route_id == "sueno":
            sleep_branch = self._sleep_branch_from_text(normalized)
            if sleep_branch and sleep_branch != active_subroute:
                if not force_distinct or sleep_branch not in recent_subroutes:
                    return sleep_branch
        if route_id == "bloqueo_ejecutivo":
            executive_alias_next = {
                "executive_no_puedo_empezar": "executive_visible_next_step",
                "executive_linea_de_que": "executive_visible_next_step",
                "executive_no_entiendo": "executive_no_se_que_toca",
            }.get(active_subroute or "")
            if executive_alias_next:
                return executive_alias_next
        if (
            route_id == "apoyo_infancia_neurodivergente"
            and active_subroute == "child_overthinking_support"
            and not force_distinct
            and self._contains_any(normalized, ["sobrepiensa", "sobrepensar", "preocupacion", "preocupaciones"])
        ):
            return "child_overthinking_support"

        if active_subroute in sequence:
            start_index = sequence.index(active_subroute) + 1
        else:
            start_index = 0

        ordered = sequence[start_index:] + sequence[:start_index]
        has_fresh_candidate = any(
            candidate != active_subroute and candidate not in recent_subroutes
            for candidate in ordered
        )
        if force_distinct and not has_fresh_candidate:
            return "strategy_switch"
        for candidate in ordered:
            if candidate == active_subroute:
                continue
            if force_distinct and has_fresh_candidate and candidate in recent_subroutes:
                continue
            return candidate
        return active_subroute or sequence[0]

    def _current_subroute_from_state(self, previous_state: Dict[str, Any]) -> Optional[str]:
        for candidate in [
            previous_state.get("active_subroute"),
            previous_state.get("active_subroute_id"),
            previous_state.get("state_subroute_id"),
            previous_state.get("subroute_id"),
        ]:
            cleaned = str(candidate or "").strip()
            if cleaned:
                return cleaned
        return None

    def _sleep_branch_from_text(self, normalized: str) -> Optional[str]:
        if self._contains_any(normalized, ["mente", "pensamiento", "pensamientos", "no para", "no puedo apagar"]):
            return "sleep_mind_racing"
        if self._contains_any(normalized, ["cuerpo", "tension", "inquiet", "activado", "activada", "palpit"]):
            return "sleep_body_activated"
        if self._contains_any(normalized, ["luz", "ruido", "pantalla", "temperatura", "entorno", "ambiente"]):
            return "sleep_environment"
        return None

    def _build_distinct_subroute_plan(
        self,
        route_id: Domain,
        subroute_id: str,
        loop_cut: bool = False,
    ) -> ResponsePlan:
        subroute_id = self._block_cross_domain_subroute(route_id, subroute_id)
        prefix = "Tienes razón. No repito eso. " if loop_cut else ""
        if route_id == "crisis":
            return self._build_crisis_distinct_plan(subroute_id=subroute_id, prefix=prefix)
        if route_id == "ansiedad":
            return self._build_anxiety_distinct_plan(subroute_id=subroute_id, prefix=prefix)
        if route_id == "bloqueo_ejecutivo":
            return self._build_executive_distinct_plan(subroute_id=subroute_id, prefix=prefix)
        if route_id == "sueno":
            return self._build_sleep_distinct_plan(subroute_id=subroute_id, prefix=prefix)
        if route_id == "apoyo_infancia_neurodivergente":
            return self._build_child_distinct_plan(subroute_id=subroute_id, prefix=prefix)
        if route_id == "sobrecarga_cuidador":
            return self._build_caregiver_distinct_plan(subroute_id=subroute_id, prefix=prefix)
        return self._make_engine_plan(
            route_id=route_id,
            subroute_id="strategy_switch",
            goal="switch_strategy",
            tone="claro_directo",
            validation="",
            main_response=f"{prefix}Cambiemos a una sola via distinta, sin abrir mas de un frente.",
            state_subroute_id="strategy_switch",
            tags=["loop_cut" if loop_cut else "next_step", "switch"],
        )

    def _build_crisis_distinct_plan(self, subroute_id: str, prefix: str) -> ResponsePlan:
        if subroute_id == "strategy_switch":
            subroute_id = "crisis_literal_phrase"
        if subroute_id == "crisis_first_step":
            return self._make_engine_plan(
                route_id="crisis",
                subroute_id=subroute_id,
                goal="next_distinct_step",
                tone="firme_claro",
                validation="",
                main_response=f"{prefix}Cambia el entorno inmediato: baja ruido, corta preguntas o aleja gente de alrededor.",
                next_step="Baja ruido, corta preguntas o aleja gente",
                optional_followup="No expliques de mas ni metas varias indicaciones juntas.",
                tags=["next_step", "crisis_progression"],
            )
        if subroute_id == "crisis_check_effect":
            return self._make_engine_plan(
                route_id="crisis",
                subroute_id=subroute_id,
                goal="next_distinct_step",
                tone="firme_claro",
                validation="",
                main_response=f"{prefix}Ahora mira solo si bajo algo: menos ruido, menos tension o mas espacio seguro.",
                optional_followup="Si no bajo nada, quitamos una sola demanda mas del entorno.",
                tags=["next_step", "check_effect"],
            )
        if subroute_id == "crisis_literal_phrase":
            return self._make_engine_plan(
                route_id="crisis",
                subroute_id=subroute_id,
                goal="next_distinct_step",
                tone="firme_claro",
                validation="",
                main_response=f"{prefix}Ahora usa una frase breve y mantén distancia segura:",
                literal_phrase="Estoy aquí. No tienes que explicar nada. Vamos a bajar esto.",
                optional_followup="Repitela igual, sin agregar explicaciones ni acercarte si no es seguro.",
                tags=["next_step", "literal_phrase"],
            )
        return self._make_engine_plan(
            route_id="crisis",
            subroute_id="crisis_close_temporarily",
            goal="close_temporarily",
            tone="firme_claro",
            validation="",
            main_response=f"{prefix}{self._close_temporarily_message('crisis')}",
            close_softly=True,
            tags=["followup_exit", "close"],
        )

    def _build_anxiety_distinct_plan(self, subroute_id: str, prefix: str) -> ResponsePlan:
        if subroute_id == "strategy_switch":
            return self._make_engine_plan(
                route_id="ansiedad",
                subroute_id="anxiety_change_modality",
                goal="switch_strategy",
                tone="claro_directo",
                validation="",
                main_response=f"{prefix}Cambiamos de modalidad: ya no respiración. Ahora escribe una sola frase:",
                literal_phrase="Lo que más me aprieta ahora es...",
                optional_followup="No lo resuelvas todavía; solo déjalo escrito.",
                state_subroute_id="anxiety_change_modality",
                tags=["switch", "anxiety_progression"],
            )
        if subroute_id == "anxiety_initial_grounding":
            return self._make_engine_plan(
                route_id="ansiedad",
                subroute_id=subroute_id,
                goal="next_distinct_step",
                tone="claro_directo",
                validation="",
                main_response=f"{prefix}Vuelve a una señal física mínima: apoya ambos pies y suelta el aire lento una vez.",
                next_step="Apoya ambos pies y suelta el aire lento una vez",
                micro_practice="grounding_exhale",
                tags=["next_step", "grounding"],
            )
        if subroute_id == "anxiety_visible_action":
            return self._make_engine_plan(
                route_id="ansiedad",
                subroute_id=subroute_id,
                goal="next_distinct_step",
                tone="claro_directo",
                validation="",
                main_response=f"{prefix}Pon la preocupación en una marca concreta: escribe una sola línea con lo que más pesa ahora.",
                next_step="Escribe una sola línea con lo que más pesa ahora",
                optional_followup="No la resuelvas todavía; solo déjala fuera de la cabeza.",
                tags=["next_step", "visible_action"],
            )
        if subroute_id == "anxiety_binary_decision":
            return self._make_engine_plan(
                route_id="ansiedad",
                subroute_id=subroute_id,
                goal="next_distinct_step",
                tone="claro_directo",
                validation="",
                main_response=f"{prefix}Ahora cierralo en una decision corta: o eso vence hoy, o no lo vas a mover por ahora.",
                optional_followup="No abras otro frente todavia.",
                tags=["next_step", "binary_decision"],
            )
        return self._make_engine_plan(
            route_id="ansiedad",
            subroute_id="anxiety_hold_after_partial_relief",
            goal="hold_line",
            tone="claro_directo",
            validation="",
            main_response=f"{prefix}Si bajó aunque sea un poco, no abras otra técnica. Deja quieto lo demás por este momento.",
            close_softly=True,
            tags=["hold", "enough_for_now"],
        )

    def _build_executive_distinct_plan(self, subroute_id: str, prefix: str) -> ResponsePlan:
        if subroute_id == "strategy_switch":
            return self._make_engine_plan(
                route_id="bloqueo_ejecutivo",
                subroute_id="executive_visible_next_step",
                goal="switch_strategy",
                tone="claro_directo",
                validation="",
                main_response=f"{prefix}Te doy tres opciones: abrir el archivo, escribir el título o poner un temporizador de 2 minutos.",
                optional_followup="Elige una; si no puedes elegir, empieza por abrir el archivo.",
                state_subroute_id="executive_visible_next_step",
                tags=["switch", "executive_options"],
            )
        if subroute_id == "executive_initial":
            return self._make_engine_plan(
                route_id="bloqueo_ejecutivo",
                subroute_id=subroute_id,
                goal="next_distinct_step",
                tone="claro_directo",
                validation="",
                main_response=f"{prefix}Empieza con una sola entrada visible: abre el archivo, cuaderno o material que toca.",
                next_step="Abre el archivo, cuaderno o material que toca",
                optional_followup="No intentes terminar; solo dejar la entrada abierta.",
                tags=["next_step", "initial"],
            )
        if subroute_id == "executive_no_se_que_toca":
            return self._make_engine_plan(
                route_id="bloqueo_ejecutivo",
                subroute_id=subroute_id,
                goal="next_distinct_step",
                tone="claro_directo",
                validation="",
                main_response=f"{prefix}Ahora define que toca sin pensarlo mucho: abre lo que vence primero o la tarea mas corta.",
                next_step="Abre lo que vence primero o la tarea mas corta",
                optional_followup="Si no sabes cual es, dime una materia y yo la cierro contigo.",
                tags=["next_step", "choose_task"],
            )
        if subroute_id == "executive_visible_next_step":
            return self._make_engine_plan(
                route_id="bloqueo_ejecutivo",
                subroute_id=subroute_id,
                goal="next_distinct_step",
                tone="claro_directo",
                validation="",
                main_response=f"{prefix}Ahora deja una salida visible: escribe solo el titulo, una vieta o una primera linea minima.",
                next_step="Escribe solo el titulo, una vieta o una primera linea minima",
                optional_followup="No tiene que quedar bien; solo visible.",
                tags=["next_step", "visible_output"],
            )
        return self._make_engine_plan(
            route_id="bloqueo_ejecutivo",
            subroute_id="executive_decide_for_user",
            goal="next_distinct_step",
            tone="claro_directo",
            validation="",
            main_response=f"{prefix}Lo decido yo por ahora: abre la tarea mas corta o la que vence primero y escribe solo el titulo.",
            next_step="Abre la tarea mas corta o la que vence primero y escribe solo el titulo",
            optional_followup="Con eso basta por este tramo.",
            tags=["next_step", "decide_for_user"],
        )

    def _build_sleep_distinct_plan(self, subroute_id: str, prefix: str) -> ResponsePlan:
        if subroute_id == "sleep_initial":
            subroute_id = "sleep_followup"
        if subroute_id == "strategy_switch":
            return self._make_engine_plan(
                route_id="sueno",
                subroute_id="sleep_followup",
                goal="switch_strategy",
                tone="claro_suave",
                validation="",
                main_response=f"{prefix}Entonces vamos a una rutina de bajada: baja luz o pantalla 10 minutos.",
                optional_followup="Si tu mente sigue acelerada, escribe una sola preocupación y ciérrala.",
                state_subroute_id="sleep_followup",
                tags=["switch", "sleep_progression"],
            )
        if subroute_id == "sleep_followup":
            return self._make_engine_plan(
                route_id="sueno",
                subroute_id=subroute_id,
                goal="next_distinct_step",
                tone="claro_suave",
                validation="",
                main_response=f"{prefix}Ahora sostén una rutina de bajada: baja pantalla o luz por 10 minutos.",
                optional_followup="Si tu mente sigue acelerada, escribe una sola preocupación y ciérrala.",
                tags=["next_step", "hold_sleep_step"],
            )
        if subroute_id == "sleep_mind_racing":
            return self._make_engine_plan(
                route_id="sueno",
                subroute_id=subroute_id,
                goal="next_distinct_step",
                tone="claro_suave",
                validation="",
                main_response=f"{prefix}Si la mente sigue corriendo, saca tres pendientes a una hoja y cierra la hoja.",
                next_step="Escribe tres pendientes y cierra la hoja",
                literal_phrase="Eso lo veo mañana. Ahorita no tengo que resolverlo.",
                tags=["next_step", "mind_racing"],
            )
        if subroute_id == "sleep_body_activated":
            return self._make_engine_plan(
                route_id="sueno",
                subroute_id=subroute_id,
                goal="next_distinct_step",
                tone="claro_suave",
                validation="",
                main_response=f"{prefix}Si el cuerpo está activado, baja cuerpo sin forzar sueño: afloja mandíbula, hombros y tres exhalaciones largas.",
                next_step="Afloja mandíbula, hombros y deja tres exhalaciones largas",
                micro_practice="body_settle_exhale",
                tags=["next_step", "body_activated"],
            )
        if subroute_id == "sleep_environment":
            return self._make_engine_plan(
                route_id="sueno",
                subroute_id=subroute_id,
                goal="next_distinct_step",
                tone="claro_suave",
                validation="",
                main_response=f"{prefix}Cambia una sola cosa del entorno: luz, ruido, pantalla o temperatura.",
                next_step="Ajusta una sola cosa del entorno",
                tags=["next_step", "environment"],
            )
        return self._make_engine_plan(
            route_id="sueno",
            subroute_id="enough_for_now",
            goal="close_temporarily",
            tone="claro_suave",
            validation="",
            main_response=f"{prefix}Ya no agregues otra medida. Sostén lo más bajo y simple por ahora.",
            close_softly=True,
            tags=["followup_exit", "close"],
        )

    def _build_child_distinct_plan(self, subroute_id: str, prefix: str) -> ResponsePlan:
        if subroute_id == "strategy_switch":
            return self._make_engine_plan(
                route_id="apoyo_infancia_neurodivergente",
                subroute_id="child_co_regulation",
                goal="switch_strategy",
                tone="claro_directo",
                validation="",
                main_response=f"{prefix}No insistamos con la misma ayuda. Cambia solo una cosa para tu hija o hijo: menos palabras, menos estímulos o una frase corta.",
                optional_followup="Elige una sola para no sumarle más carga.",
                state_subroute_id="child_co_regulation",
                tags=["switch", "child_support"],
            )
        if subroute_id == "child_overthinking_support":
            return self._make_engine_plan(
                route_id="apoyo_infancia_neurodivergente",
                subroute_id=subroute_id,
                goal="next_distinct_step",
                tone="claro_directo",
                validation="",
                main_response=(
                    f"{prefix}Si quien está sobrepensando es tu hija o hijo, baja velocidad: "
                    "saquen una sola preocupación, en voz o en papel, y miren solo esa."
                ),
                next_step="Sacar una sola preocupación, en voz o en papel",
                optional_followup="No abran todas las demás preocupaciones al mismo tiempo.",
                tags=["next_step", "child_overthinking"],
            )
        if subroute_id == "child_clear_communication":
            return self._make_engine_plan(
                route_id="apoyo_infancia_neurodivergente",
                subroute_id=subroute_id,
                goal="next_distinct_step",
                tone="claro_directo",
                validation="",
                main_response=f"{prefix}Ahora usa una frase corta, sin explicar de mas:",
                literal_phrase="Vamos con una sola parte. Estoy aqui.",
                optional_followup="Dila con voz baja y no agregues otra demanda.",
                tags=["next_step", "literal_phrase"],
            )
        if subroute_id == "child_reduce_stimuli":
            return self._make_engine_plan(
                route_id="apoyo_infancia_neurodivergente",
                subroute_id=subroute_id,
                goal="next_distinct_step",
                tone="claro_directo",
                validation="",
                main_response=f"{prefix}Baja una sola cosa del entorno para tu hija/o: luz, ruido, gente o preguntas.",
                next_step="Baja una sola cosa del entorno",
                tags=["next_step", "reduce_stimuli"],
            )
        if subroute_id == "child_co_regulation":
            return self._make_engine_plan(
                route_id="apoyo_infancia_neurodivergente",
                subroute_id=subroute_id,
                goal="next_distinct_step",
                tone="claro_directo",
                validation="",
                main_response=f"{prefix}Quédate en una ayuda para tu hija o hijo: presencia calmada, voz baja y una frase corta.",
                literal_phrase="Estoy aquí. Vamos con una sola cosa.",
                tags=["next_step", "co_regulation"],
            )
        return self._make_engine_plan(
            route_id="apoyo_infancia_neurodivergente",
            subroute_id="child_anticipation_routines",
            goal="next_distinct_step",
            tone="claro_directo",
            validation="",
            main_response=f"{prefix}Deja una anticipacion simple: ahora una parte, luego descanso o cierre.",
            literal_phrase="Ahora una parte; luego descansamos.",
            tags=["next_step", "anticipation"],
        )

    def _build_caregiver_distinct_plan(self, subroute_id: str, prefix: str) -> ResponsePlan:
        if subroute_id == "caregiver_ask_for_help":
            return self._make_engine_plan(
                route_id="sobrecarga_cuidador",
                subroute_id=subroute_id,
                goal="next_distinct_step",
                tone="calido_practico",
                validation="",
                main_response=f"{prefix}Pide una ayuda cerrada, no ayuda en general: una hora, una tarea o una decisión concreta.",
                literal_phrase="Hoy necesito que tomes esta parte concreta para que yo pueda bajar un poco.",
                tags=["next_step", "ask_for_help"],
            )
        if subroute_id == "caregiver_single_priority":
            return self._make_engine_plan(
                route_id="sobrecarga_cuidador",
                subroute_id=subroute_id,
                goal="next_distinct_step",
                tone="calido_practico",
                validation="",
                main_response=f"{prefix}Cierra una sola prioridad para hoy: seguridad, descanso o lo que vence hoy.",
                optional_followup="Lo demás no se resuelve en este minuto.",
                tags=["next_step", "single_priority"],
            )
        if subroute_id == "caregiver_self_care_without_guilt":
            return self._make_engine_plan(
                route_id="sobrecarga_cuidador",
                subroute_id=subroute_id,
                goal="hold_line",
                tone="calido_practico",
                validation="",
                main_response=f"{prefix}Deja una pausa mínima sin culpa: agua, baño, sentarte cinco minutos o respirar fuera.",
                close_softly=True,
                tags=["hold", "self_care"],
            )
        if subroute_id == "strategy_switch":
            return self._make_engine_plan(
                route_id="sobrecarga_cuidador",
                subroute_id="caregiver_single_priority",
                goal="switch_strategy",
                tone="calido_practico",
                validation="",
                main_response=f"{prefix}No intentemos sostener todo. Elige solo entre seguridad, descanso o una tarea urgente.",
                state_subroute_id="caregiver_single_priority",
                tags=["switch", "caregiver"],
            )
        return self._make_engine_plan(
            route_id="sobrecarga_cuidador",
            subroute_id="caregiver_reduce_load",
            goal="next_distinct_step",
            tone="calido_practico",
            validation="",
            main_response=f"{prefix}Suelta una carga que pueda esperar: una decisión, una tarea o una exigencia que no sea de seguridad.",
            optional_followup="No estás fallando por bajar una parte.",
            state_subroute_id="caregiver_reduce_load",
            tags=["next_step", "reduce_load"],
        )

    def _build_current_action_clarification_plan(
        self,
        route_id: Domain,
        normalized: str,
        action_memory: Dict[str, Any],
    ) -> ResponsePlan:
        last_action_type = str(action_memory.get("last_action_type") or "").strip()
        instruction = str(action_memory.get("last_action_instruction") or "").strip()
        active_subroute = str(action_memory.get("active_subroute_id") or "").strip() or None

        if self._wants_literal_phrase(normalized=normalized, action_memory=action_memory):
            if last_action_type == "external_coregulation_step":
                literal_phrase = "Estoy aqui. No voy a discutir contigo. Vamos a bajar esto juntos."
            else:
                literal_phrase = instruction if last_action_type == "literal_phrase" and instruction else self._default_literal_phrase(route_id)
            subroute_id = (
                "crisis_literal_phrase"
                if route_id == "crisis"
                else "child_clear_communication"
                if route_id == "apoyo_infancia_neurodivergente"
                else "what_phrase"
            )
            return self._make_engine_plan(
                route_id=route_id,
                subroute_id=subroute_id,
                goal="clarify_current_action",
                tone="claro_directo",
                validation="",
                main_response="La frase es esta:",
                literal_phrase=literal_phrase,
                optional_followup=(
                    "Dila tal cual y no agregues otra instruccion al mismo tiempo."
                    if route_id == "crisis"
                    else "Usa esa frase tal cual, sin hacerla mas larga."
                ),
                state_subroute_id=active_subroute or subroute_id,
                tags=["clarify_current_action", "literal_phrase"],
            )

        if last_action_type == "external_coregulation_step":
            return self._make_engine_plan(
                route_id=route_id,
                subroute_id="crisis_external_coregulation",
                goal="clarify_current_action",
                tone="claro_directo",
                validation="",
                main_response=(
                    "La accion actual es externa: baja tu tono, usa pocas palabras, no discutas, "
                    "no expliques de mas y baja un estimulo como ruido, luz, gente o preguntas."
                ),
                optional_followup="Haz solo una de esas cosas primero.",
                state_subroute_id=active_subroute or "crisis_first_step",
                tags=["clarify_current_action", "external_crisis", "co_regulation"],
            )

        if last_action_type == "environment_step":
            subroute_id = (
                "crisis_demand_examples"
                if route_id == "crisis"
                else "sleep_environment"
                if route_id == "sueno"
                else "child_reduce_stimuli"
                if route_id == "apoyo_infancia_neurodivergente"
                else "what_type"
            )
            return self._make_engine_plan(
                route_id=route_id,
                subroute_id=subroute_id,
                goal="clarify_current_action",
                tone="claro_directo",
                validation="",
                main_response=self._environment_examples_response(route_id),
                optional_followup="Elige solo una y cambia esa primero.",
                state_subroute_id=active_subroute or subroute_id,
                tags=["clarify_current_action", "environment_examples"],
            )

        if last_action_type == "grounding_step":
            subroute_id = "anxiety_initial_grounding" if route_id == "ansiedad" else "what_type"
            if route_id != "ansiedad":
                return self._make_engine_plan(
                    route_id=route_id,
                    subroute_id=subroute_id,
                    goal="clarify_current_action",
                    tone="claro_directo",
                    validation="",
                    main_response=self._starting_point_response(route_id),
                    state_subroute_id=active_subroute or subroute_id,
                    tags=["clarify_current_action", "route_reset"],
                )
            return self._make_engine_plan(
                route_id=route_id,
                subroute_id=subroute_id,
                goal="clarify_current_action",
                tone="claro_directo",
                validation="",
                main_response=(
                    "Hazlo literal: pies en el piso, suelta el aire más largo una vez y mira tres cosas alrededor."
                ),
                state_subroute_id=active_subroute or subroute_id,
                tags=["clarify_current_action", "grounding"],
            )

        if last_action_type == "sleep_step":
            subroute_id = active_subroute or "sleep_followup"
            return self._make_engine_plan(
                route_id=route_id,
                subroute_id=subroute_id,
                goal="clarify_current_action",
                tone="claro_directo",
                validation="",
                main_response=(
                    "Haz una sola acción real de sueño: baja la luz o la pantalla y deja 5 a 10 minutos sin exigencia."
                ),
                state_subroute_id=active_subroute or subroute_id,
                tags=["clarify_current_action", "sleep"],
            )

        if route_id == "bloqueo_ejecutivo" and self._contains_any(normalized, ["dime como", "dime cómo", "como lo hago", "cómo lo hago"]):
            return self._make_engine_plan(
                route_id=route_id,
                subroute_id="executive_visible_next_step",
                goal="clarify_current_action",
                tone="claro_directo",
                validation="",
                main_response=(
                    "Hazlo así: abre el material más cercano, ponle un título mínimo y deja una primera línea aunque sea fea."
                ),
                optional_followup="No ordenes todo todavía; solo deja esa entrada visible.",
                state_subroute_id=active_subroute or "executive_visible_next_step",
                tags=["clarify_current_action", "executive_step"],
            )

        if last_action_type in {"executive_step", "action_step"} and "linea de que" in normalized:
            return self._make_engine_plan(
                route_id=route_id,
                subroute_id="executive_linea_de_que",
                goal="clarify_current_action",
                tone="claro_directo",
                validation="",
                main_response=(
                    "De una linea minima para abrir la tarea: puede ser el titulo del tema, la consigna o una primera frase obvia."
                ),
                optional_followup=(
                    "Si no sabes cual, escribe solo el nombre de la materia o dime el nombre y partimos desde ahi."
                ),
                state_subroute_id=active_subroute or "executive_linea_de_que",
                tags=["clarify_current_action", "line_start"],
            )

        if last_action_type in {"executive_step", "action_step"} and "por donde" in normalized:
            subroute_id = "executive_no_se_que_toca" if route_id == "bloqueo_ejecutivo" else "where_do_i_start"
            return self._make_engine_plan(
                route_id=route_id,
                subroute_id=subroute_id,
                goal="clarify_current_action",
                tone="claro_directo",
                validation="",
                main_response=self._starting_point_response(route_id),
                state_subroute_id=active_subroute or subroute_id,
                tags=["clarify_current_action", "starting_point"],
            )

        if last_action_type in {"executive_step", "action_step"}:
            subroute_id = "executive_visible_next_step" if route_id == "bloqueo_ejecutivo" else "what_type"
            return self._make_engine_plan(
                route_id=route_id,
                subroute_id=subroute_id,
                goal="clarify_current_action",
                tone="claro_directo",
                validation="",
                main_response=self._simple_action_explanation(route_id, instruction),
                optional_followup="Haz solo eso primero.",
                state_subroute_id=active_subroute or subroute_id,
                tags=["clarify_current_action", "action_step"],
            )

        fallback_subroute = active_subroute or "i_dont_understand"
        return self._make_engine_plan(
            route_id=route_id,
            subroute_id=fallback_subroute,
            goal="clarify_current_action",
            tone="claro_directo",
            validation="",
            main_response=self._simple_action_explanation(route_id, instruction),
            optional_followup="Haz solo eso y luego vemos si hace falta algo mas.",
            state_subroute_id=active_subroute or fallback_subroute,
            tags=["clarify_current_action"],
        )

    def _build_blocked_followup_plan(
        self,
        route_id: Domain,
        normalized: str,
        action_memory: Dict[str, Any],
    ) -> Optional[ResponsePlan]:
        active_subroute = str(action_memory.get("active_subroute_id") or "").strip() or None

        if route_id == "bloqueo_ejecutivo":
            if "no se que toca" in normalized or "no se que sigue" in normalized or "no se que hacer" in normalized:
                return self._make_engine_plan(
                    route_id=route_id,
                    subroute_id="executive_no_se_que_toca",
                    goal="lower_demand_for_block",
                    tone="claro_directo",
                    validation="",
                    main_response="Haz solo esto: abre la materia o tarea que mas urge hoy.",
                    optional_followup="Si no sabes cual, dime el nombre de una materia y partimos desde ahi.",
                    state_subroute_id="executive_no_se_que_toca",
                    tags=["lower_demand", "direct_answer"],
                )
            if "no puedo empezar" in normalized or active_subroute == "executive_no_puedo_empezar":
                return self._make_engine_plan(
                route_id=route_id,
                subroute_id="executive_no_puedo_empezar",
                goal="lower_demand_for_block",
                tone="claro_directo",
                validation="No tienes que poder con toda la tarea para empezar.",
                main_response="Abre el archivo o cuaderno y escribe solo el titulo.",
                optional_followup="Con eso ya no esta en cero.",
                state_subroute_id="executive_no_puedo_empezar",
                tags=["lower_demand", "direct_answer"],
                )
            if "decide tu" in normalized or "elige tu" in normalized or active_subroute == "executive_decide_for_user":
                return self._make_engine_plan(
                    route_id=route_id,
                    subroute_id="executive_decide_for_user",
                    goal="lower_demand_for_block",
                    tone="claro_directo",
                    validation="",
                    main_response="No decidas mas. Abre la tarea mas corta o la que vence primero y escribe solo el titulo.",
                    optional_followup="Si quieres, despues te doy la siguiente linea.",
                    state_subroute_id="executive_decide_for_user",
                    tags=["lower_demand", "direct_answer"],
                )
            return self._make_engine_plan(
                route_id=route_id,
                subroute_id="executive_initial",
                goal="lower_demand_for_block",
                tone="claro_directo",
                validation="",
                main_response=(
                    "Entonces no empieces por organizar. Haz esto: abre el cuaderno, archivo o material "
                    "que tengas más cerca."
                ),
                optional_followup="Si no sabes cuál, dime las opciones y elegimos una.",
                state_subroute_id=active_subroute or "executive_initial",
                tags=["lower_demand", "direct_answer"],
            )

        if route_id == "sueno":
            sleep_subroute = (
                "sleep_insomnia"
                if self._contains_any(normalized, ["no puedo dormir", "insomnio", "desvelo"])
                else self._sleep_branch_from_text(normalized)
                or active_subroute
                or "sleep_initial"
            )
            sleep_text = {
                "sleep_mind_racing": "Saca a una hoja tres pendientes o preocupaciones y luego cierra la hoja.",
                "sleep_body_activated": "Afloja mandíbula, hombros y deja tres exhalaciones largas sin forzar sueño.",
                "sleep_environment": "Baja una sola fuente de estímulo: luz, ruido, pantalla o temperatura.",
                "sleep_insomnia": "Sal un momento de la pelea con dormir: poca luz, sin pantalla y sin exigencia.",
            }.get(sleep_subroute, "Baja la luz o apaga la pantalla y deja 5 a 10 minutos sin exigencia.")
            return self._make_engine_plan(
                route_id=route_id,
                subroute_id=sleep_subroute,
                goal="one_sleep_step",
                tone="claro_directo",
                validation="",
                main_response=sleep_text,
                state_subroute_id=sleep_subroute,
                tags=["one_step", "direct_answer"],
            )

        return None

    def _build_post_action_followup_plan(
        self,
        route_id: Domain,
        normalized: str,
        previous_frame: Dict[str, Any],
        action_memory: Dict[str, Any],
        outcome: OutcomePolarity,
    ) -> Optional[ResponsePlan]:
        previous_state = dict(previous_frame.get("support_flow_state") or {})
        previous_count = int(previous_state.get("action_followup_count", 0) or 0)
        if self._should_force_followup_exit_for_current(
            previous_state=previous_state,
            action_memory=action_memory,
        ):
            return self._build_followup_exit_plan(
                route_id=route_id,
                normalized=normalized,
                outcome=outcome,
            )

        if outcome in {"no_change", "worse"}:
            return self._build_followup_exit_plan(
                route_id=route_id,
                normalized=normalized,
                outcome=outcome,
            )

        if outcome in {"partial_relief", "improved"}:
            return self._build_hold_after_effect_plan(route_id=route_id, previous_state=previous_state)

        if route_id == "crisis" and previous_count >= 1 and normalized in {"ya", "listo", "hecho"}:
            return self._make_engine_plan(
                route_id=route_id,
                subroute_id="crisis_close_temporarily",
                goal="hold_line",
                tone="claro_directo",
                validation="",
                main_response="Bien. Por ahora no agregues otra indicacion: sosten la frase breve y el entorno mas bajo un momento.",
                optional_followup="Si vuelve a subir o no baja nada, cambiamos una sola cosa o cerramos por ahora.",
                close_softly=True,
                state_subroute_id="crisis_close_temporarily",
                tags=["hold", "post_action_followup"],
            )

        next_subroute = self._select_next_distinct_subroute(
            route_id=route_id,
            normalized=normalized,
            previous_state=previous_state,
            force_distinct=False,
        )
        return self._build_distinct_subroute_plan(
            route_id=route_id,
            subroute_id=next_subroute,
            loop_cut=False,
        )

    def _build_hold_after_effect_plan(
        self,
        route_id: Domain,
        previous_state: Dict[str, Any],
    ) -> ResponsePlan:
        active_subroute = self._current_subroute_from_state(previous_state)
        if route_id == "ansiedad":
            return self._make_engine_plan(
                route_id=route_id,
                subroute_id="anxiety_hold_after_partial_relief",
                goal="hold_line",
                tone="claro_directo",
                validation="Bien, algo cedio.",
                main_response="No metas otra tecnica ahora. Deja quieto lo demás y mantén solo lo que ya aflojó.",
                close_softly=True,
                state_subroute_id="anxiety_hold_after_partial_relief",
                tags=["hold", "post_action_followup"],
            )
        if route_id == "bloqueo_ejecutivo":
            return self._make_engine_plan(
                route_id=route_id,
                subroute_id=active_subroute or "executive_visible_next_step",
                goal="hold_line",
                tone="claro_directo",
                validation="Bien, eso ya abrió la entrada.",
                main_response="No intentes terminar ahora. Deja visible lo que abriste y para en ese punto si hace falta.",
                close_softly=True,
                state_subroute_id=active_subroute or "executive_visible_next_step",
                tags=["hold", "post_action_followup"],
            )
        if route_id == "sueno":
            return self._make_engine_plan(
                route_id=route_id,
                subroute_id=active_subroute or "sleep_followup",
                goal="hold_line",
                tone="claro_suave",
                validation="Bien, eso ya da una pista.",
                main_response="Sostén solo lo que bajó el estímulo. No agregues otra medida esta noche.",
                close_softly=True,
                state_subroute_id=active_subroute or "sleep_followup",
                tags=["hold", "post_action_followup"],
            )
        if route_id == "apoyo_infancia_neurodivergente":
            return self._make_engine_plan(
                route_id=route_id,
                subroute_id=active_subroute or "child_co_regulation",
                goal="hold_line",
                tone="claro_directo",
                validation="Bien, eso ya es una señal.",
                main_response="Sostén esa misma ayuda para tu hija o hijo y no agregues otra indicación encima.",
                close_softly=True,
                state_subroute_id=active_subroute or "child_co_regulation",
                tags=["hold", "post_action_followup"],
            )
        if route_id == "sobrecarga_cuidador":
            return self._make_engine_plan(
                route_id=route_id,
                subroute_id=active_subroute or "caregiver_reduce_load",
                goal="hold_line",
                tone="calido_practico",
                validation="Bien, eso ya baja una parte.",
                main_response="No llenes ese espacio con otra carga. Deja esa parte suelta por ahora.",
                close_softly=True,
                state_subroute_id=active_subroute or "caregiver_reduce_load",
                tags=["hold", "post_action_followup"],
            )
        return self._make_engine_plan(
            route_id=route_id,
            subroute_id=active_subroute or "pause_here",
            goal="hold_line",
            tone="claro_directo",
            validation="Bien.",
            main_response="Sostén solo lo que ya ayudó y no abras otro frente por ahora.",
            close_softly=True,
            state_subroute_id=active_subroute or "pause_here",
            tags=["hold", "post_action_followup"],
        )

    def _should_force_followup_exit(
        self,
        previous_state: Dict[str, Any],
        action_memory: Dict[str, Any],
    ) -> bool:
        if not self._has_active_action(action_memory):
            return False
        action_followup_count = int(previous_state.get("action_followup_count", 0) or 0)
        recent_modes = list(previous_state.get("recent_followup_modes") or [])
        if action_followup_count >= self.FOLLOWUP_EXIT_THRESHOLD:
            return True
        return recent_modes[-3:] == ["check_effect", "hold_line", "adjustment"]

    def _should_force_followup_exit_for_current(
        self,
        previous_state: Dict[str, Any],
        action_memory: Dict[str, Any],
    ) -> bool:
        if self._should_force_followup_exit(previous_state=previous_state, action_memory=action_memory):
            return True
        if not self._has_active_action(action_memory):
            return False
        action_followup_count = int(previous_state.get("action_followup_count", 0) or 0)
        return action_followup_count >= max(self.FOLLOWUP_EXIT_THRESHOLD - 1, 1)

    def _build_followup_exit_plan(
        self,
        route_id: Domain,
        normalized: str,
        outcome: OutcomePolarity,
    ) -> ResponsePlan:
        if outcome in {"no_change", "worse"}:
            return self._make_engine_plan(
                route_id=route_id,
                subroute_id="strategy_switch",
                goal="switch_strategy",
                tone="claro_directo",
                validation="",
                main_response=self._switch_strategy_message(route_id),
                state_subroute_id="strategy_switch",
                tags=["followup_exit", "switch"],
            )

        if normalized == "ya" or route_id in {"crisis", "sueno"}:
            subroute_id = (
                "crisis_close_temporarily"
                if route_id == "crisis"
                else "enough_for_now"
                if route_id == "sueno"
                else "pause_here"
            )
            return self._make_engine_plan(
                route_id=route_id,
                subroute_id=subroute_id,
                goal="close_temporarily",
                tone="claro_directo",
                validation="",
                main_response=self._close_temporarily_message(route_id),
                close_softly=True,
                state_subroute_id=subroute_id,
                tags=["followup_exit", "close"],
            )

        subroute_id = (
            "anxiety_binary_decision"
            if route_id == "ansiedad"
            else "executive_decide_for_user"
            if route_id == "bloqueo_ejecutivo"
            else "enough_for_now"
        )
        return self._make_engine_plan(
            route_id=route_id,
            subroute_id=subroute_id,
            goal="decide_one_path",
            tone="claro_directo",
            validation="",
            main_response=self._decide_one_path_message(route_id),
            state_subroute_id=subroute_id,
            tags=["followup_exit", "decide"],
        )

    def _resolve_action_state(
        self,
        response_plan: Optional[ResponsePlan],
        route_id: Domain,
        conversation_domain: str,
        previous_action: Dict[str, Any],
    ) -> Dict[str, Optional[str]]:
        if route_id in {"meta_question", "pregunta_simple"} and self._has_active_action(previous_action):
            return {
                "last_action_instruction": previous_action.get("last_action_instruction") or None,
                "last_action_type": previous_action.get("last_action_type") or None,
                "last_action_goal": previous_action.get("last_action_goal") or None,
                "last_action_domain": previous_action.get("last_action_domain") or None,
            }
        if not response_plan:
            return {
                "last_action_instruction": previous_action.get("last_action_instruction") or None,
                "last_action_type": previous_action.get("last_action_type") or None,
                "last_action_goal": previous_action.get("last_action_goal") or None,
                "last_action_domain": previous_action.get("last_action_domain") or conversation_domain,
            }

        instruction = self._extract_action_instruction_from_plan(
            response_plan=response_plan,
            previous_action=previous_action,
        )
        action_type = self._infer_action_type_from_plan(
            response_plan=response_plan,
            route_id=route_id,
            instruction=instruction,
            previous_action=previous_action,
        )

        return {
            "last_action_instruction": instruction or previous_action.get("last_action_instruction") or None,
            "last_action_type": action_type or previous_action.get("last_action_type") or None,
            "last_action_goal": response_plan.goal or previous_action.get("last_action_goal") or None,
            "last_action_domain": conversation_domain or previous_action.get("last_action_domain") or None,
        }

    def _extract_action_instruction_from_plan(
        self,
        response_plan: ResponsePlan,
        previous_action: Dict[str, Any],
    ) -> str:
        if response_plan.literal_phrase:
            return response_plan.literal_phrase.strip().rstrip(".")
        if response_plan.next_step:
            return response_plan.next_step.strip().rstrip(".")
        if response_plan.micro_practice and not response_plan.main_response:
            return response_plan.micro_practice.strip().rstrip(".")

        main_response = str(response_plan.main_response or "").strip()
        normalized_main = self._normalize(main_response)
        if not main_response:
            return str(previous_action.get("last_action_instruction") or "").strip()
        if main_response.endswith("?"):
            return str(previous_action.get("last_action_instruction") or "").strip()
        if normalized_main.startswith("ahora mira solo esto"):
            return str(previous_action.get("last_action_instruction") or "").strip()
        return main_response.rstrip(".")

    def _infer_action_type_from_plan(
        self,
        response_plan: ResponsePlan,
        route_id: Domain,
        instruction: str,
        previous_action: Dict[str, Any],
    ) -> Optional[str]:
        text = self._normalize(
            " ".join(
                part
                for part in [
                    response_plan.main_response,
                    response_plan.next_step,
                    response_plan.literal_phrase,
                    response_plan.micro_practice,
                    instruction,
                ]
                if part
            )
        )
        if response_plan.literal_phrase:
            return "literal_phrase"
        if route_id == "crisis" and self._contains_any(
            text,
            ["baja tu tono", "frases breves", "no discutas", "no discutir", "no expliques demasiado"],
        ):
            return "external_coregulation_step"
        if route_id == "sueno":
            return "sleep_step"
        if route_id == "bloqueo_ejecutivo":
            return "executive_step"
        if route_id == "ansiedad" and (
            response_plan.micro_practice
            or self._contains_any(text, ["pies en el piso", "suelta el aire", "mira tres cosas", "nombra tres cosas"])
        ):
            return "grounding_step"
        if self._contains_any(
            text,
            [
                "ruido",
                "gente",
                "exigencia",
                "exigencias",
                "preguntas",
                "luces",
                "contacto",
                "pantalla",
                "estimulo",
                "estimulos",
                "entorno",
            ],
        ):
            return "environment_step"
        return str(previous_action.get("last_action_type") or "").strip() or "action_step"

    def _resolve_followup_trace(
        self,
        previous_state: Dict[str, Any],
        turn_family: TurnFamily,
        route_id: Domain,
        continuity_score: float,
        action_memory: Dict[str, Any],
        response_plan: Optional[ResponsePlan],
        outcome: OutcomePolarity,
        guidance_mode: GuidanceMode,
    ) -> Dict[str, Any]:
        same_route = previous_state.get("route_id") == route_id and continuity_score >= 0.7
        if not same_route:
            previous_count = 0
            previous_modes: List[str] = []
        else:
            previous_count = int(previous_state.get("action_followup_count", 0) or 0)
            previous_modes = list(previous_state.get("recent_followup_modes") or [])

        has_action = self._has_active_action(action_memory)
        mode = self._resolve_followup_mode(
            turn_family=turn_family,
            response_plan=response_plan,
            outcome=outcome,
            guidance_mode=guidance_mode,
        )

        if has_action and turn_family in self.COUNTED_ACTION_FOLLOWUP_FAMILIES:
            action_followup_count = previous_count + 1 if same_route else 1
        elif not same_route:
            action_followup_count = 0
        else:
            action_followup_count = previous_count

        if has_action and turn_family in self.ACTION_FOLLOWUP_FAMILIES and mode:
            recent_followup_modes = (previous_modes + [mode])[-4:]
        elif not same_route:
            recent_followup_modes = []
        else:
            recent_followup_modes = previous_modes[-4:]

        followup_exit = response_plan.goal if response_plan and response_plan.goal in self.FOLLOWUP_EXIT_GOALS else None
        return {
            "action_followup_count": action_followup_count,
            "recent_followup_modes": recent_followup_modes,
            "followup_exit": followup_exit,
        }

    def _resolve_followup_mode(
        self,
        turn_family: TurnFamily,
        response_plan: Optional[ResponsePlan],
        outcome: OutcomePolarity,
        guidance_mode: GuidanceMode,
    ) -> str:
        if response_plan and response_plan.goal in self.FOLLOWUP_EXIT_GOALS:
            return response_plan.goal
        if response_plan and response_plan.goal in {"clarify_current_action", "hold_line", "next_distinct_step"}:
            return response_plan.goal
        if turn_family in {"clarification_request", "literal_phrase_request"}:
            return "clarify_current_action"
        if turn_family == "blocked_followup":
            return "adjustment"
        if outcome in {"partial_relief", "improved"} or (response_plan and response_plan.close_softly):
            return "hold_line"
        if turn_family == "post_action_followup":
            return "check_effect"
        if turn_family == "followup_acceptance":
            return "next_distinct_step"
        if guidance_mode == "switch":
            return "switch_strategy"
        return guidance_mode

    def _environment_examples_response(self, route_id: Domain) -> str:
        if route_id == "crisis":
            return "Baja una sola demanda concreta: ruido, gente cerca, preguntas o exigencias, luces o contacto"
        if route_id == "sueno":
            return "Ajusta solo una cosa del entorno: luz, ruido o pantalla"
        if route_id == "apoyo_infancia_neurodivergente":
            return "Ajusta solo una cosa del entorno para tu hija/o: luz, ruido, gente o demandas"
        return "Ajusta solo una cosa del entorno: ruido, gente o exigencia"

    def _starting_point_response(self, route_id: Domain) -> str:
        if route_id == "bloqueo_ejecutivo":
            return "Empieza por la materia o tarea que mas urge hoy. Si no sabes cual, dime el nombre de una y partimos desde ahi."
        if route_id == "sueno":
            return "Empieza por una condición de sueño: baja luz, pantalla o ruido durante unos minutos."
        if route_id == "crisis":
            return "Empieza por el entorno: menos ruido, menos preguntas o más espacio seguro."
        if route_id == "apoyo_infancia_neurodivergente":
            return "Empieza por una ayuda para tu hija o hijo: menos palabras, menos estímulos o una frase corta."
        if route_id == "sobrecarga_cuidador":
            return "Empieza por una carga que pueda esperar: una decisión, una tarea o una exigencia no urgente."
        return "Empieza por una sola parte concreta del tema que traías."

    def _simple_action_explanation(self, route_id: Domain, instruction: str) -> str:
        if route_id == "bloqueo_ejecutivo" and not instruction:
            return "Haz una sola cosa: abre la materia o tarea mas urgente de hoy."
        if route_id == "ansiedad" and not instruction:
            return "Haz una sola cosa: pies en el piso y una exhalación larga."
        if route_id == "apoyo_infancia_neurodivergente" and not instruction:
            return "Haz una sola cosa por tu hija/o: o menos palabras, o menos estimulos, o una frase breve."
        if instruction:
            return f"La accion actual es esta: {instruction}"
        return "La accion actual es hacer una sola cosa pequeña y literal."

    def _default_literal_phrase(self, route_id: Domain) -> str:
        if route_id == "crisis":
            return "Estoy aqui contigo. No hace falta hablar mucho ahora. Vamos a bajar esto juntos."
        if route_id == "ansiedad":
            return "Solo una cosa a la vez. Ahora no tengo que resolver todo."
        if route_id == "apoyo_infancia_neurodivergente":
            return "No tienes que resolverlo todo ahorita. Vamos con una sola parte."
        return "Vamos paso a paso. Solo una cosa ahora."

    def _switch_strategy_message(self, route_id: Domain) -> str:
        if route_id == "crisis":
            return "No vamos a repetir lo mismo. Cambia una sola via: menos palabras y mas espacio seguro, o menos gente y ruido."
        if route_id == "ansiedad":
            return "No seguimos con el mismo carril. Cambiamos a una sola via distinta: cuerpo, entorno o una frase breve."
        if route_id == "bloqueo_ejecutivo":
            return "No vamos a empujar mas el mismo paso. Dime la materia y te doy una sola linea de arranque."
        if route_id == "sueno":
            return "No seguimos intentando lo mismo. Cambia a una sola medida real: menos pantalla o menos luz por unos minutos."
        if route_id == "apoyo_infancia_neurodivergente":
            return "No vamos a insistir por la misma via. Cambiemos a una sola ayuda distinta para tu hija/o: frase corta, presencia calmada o menos estimulos."
        return "Cambiemos a una sola via distinta, sin abrir mas de un frente."

    def _close_temporarily_message(self, route_id: Domain) -> str:
        if route_id == "crisis":
            return "Por ahora no metas otro paso. Sosten la frase breve y el entorno mas bajo un momento, y cerramos ahi por ahora."
        if route_id == "sueno":
            return "Ya no sumes otra medida. Sosten luz baja o pantalla fuera 5 a 10 minutos y por ahora cerramos ahi."
        if route_id == "apoyo_infancia_neurodivergente":
            return "Por ahora basta con una sola ayuda para tu hija/o. Sostenla un momento y cerramos ahi temporalmente."
        return "Por ahora no hace falta meter otro paso. Sosten esta accion un momento y cerramos aqui temporalmente."

    def _decide_one_path_message(self, route_id: Domain) -> str:
        if route_id == "ansiedad":
            return "No vamos a abrir mas pasos ahorita. O sostienes esto un minuto y cerramos por ahora, o me dices la preocupacion principal y vemos solo esa."
        if route_id == "bloqueo_ejecutivo":
            return "No metas otro paso ahorita. O dejas solo la materia abierta y cerramos por ahora, o me dices la materia y te doy una sola linea."
        if route_id == "apoyo_infancia_neurodivergente":
            return "No metas varias ayudas al mismo tiempo. O sostienes una sola ayuda y observas, o cambiamos a una sola via distinta."
        return "Ahora toca una sola decision: o sostener esto por ahora, o cambiar a una sola via distinta."

    def _contains_any(self, normalized_text: str, phrases: List[str]) -> bool:
        return any(normalize_input(phrase) in normalized_text for phrase in phrases)

    def _normalize(self, text: str) -> str:
        return normalize_input(text)


if __name__ == "__main__":
    engine = SupportFlowEngine()
    samples = [
        ("Esta ocurriendo una crisis y necesito ayuda", {}),
        ("que le digo", {"last_action_instruction": "Estoy aqui contigo", "last_action_type": "literal_phrase", "conversation_domain": "crisis_activa"}),
        ("no me sirve", {"support_flow_state": {"route_id": "ansiedad"}, "conversation_domain": "ansiedad_cognitiva"}),
        ("y luego", {"support_flow_state": {"route_id": "bloqueo_ejecutivo", "step_index": 0}, "conversation_domain": "disfuncion_ejecutiva"}),
    ]
    for message, previous in samples:
        result = engine.resolve_turn(
            source_message=message,
            previous_frame=previous,
        )
        print("-" * 72)
        print(message)
        print(result.to_dict())
