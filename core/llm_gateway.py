# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import re
import unicodedata
from typing import Any, Dict, List, Optional

from core.support_playbooks import is_deterministic_support_route

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


def normalize_input(text: Optional[str]) -> str:
    """Normaliza solo para matching interno; la salida visible conserva acentos."""

    normalized = " ".join((text or "").strip().lower().split())
    normalized = unicodedata.normalize("NFKD", normalized)
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    return " ".join(normalized.split())


class LLMGateway:
    ALLOWED_PROMPT_MODES = {
        "controlled_support_generation",
        "controlled_crisis_support",
        "controlled_low_demand_support",
        "controlled_explanatory_support",
        "controlled_structured_support",
        "controlled_reflective_feedback",
        "controlled_adaptive_support",
        "controlled_calm_support",
            "support_flow_humanization",
            "stable_demo_behavioral_writer",
        }

    DEFAULT_OPENAI_MODEL = "gpt-5-mini"
    DEFAULT_TIMEOUT_SECONDS = 20.0

    def build_request(
        self,
        message: str,
        fallback_payload: Optional[Dict[str, Any]] = None,
        decision_payload: Optional[Dict[str, Any]] = None,
        confidence_payload: Optional[Dict[str, Any]] = None,
        intent_analysis: Optional[Dict[str, Any]] = None,
        category_analysis: Optional[Dict[str, Any]] = None,
        state_analysis: Optional[Dict[str, Any]] = None,
        stage_result: Optional[Dict[str, Any]] = None,
        support_plan: Optional[Dict[str, Any]] = None,
        active_profile: Optional[Dict[str, Any]] = None,
        routine_payload: Optional[Dict[str, Any]] = None,
        memory_payload: Optional[Dict[str, Any]] = None,
        response_memory_payload: Optional[Dict[str, Any]] = None,
        case_context: Optional[Dict[str, Any]] = None,
        chat_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        fallback_payload = fallback_payload or {}
        decision_payload = decision_payload or {}
        confidence_payload = confidence_payload or {}
        intent_analysis = intent_analysis or {}
        category_analysis = category_analysis or {}
        state_analysis = state_analysis or {}
        stage_result = stage_result or {}
        support_plan = support_plan or {}
        active_profile = active_profile or {}
        routine_payload = routine_payload or {}
        memory_payload = memory_payload or {}
        response_memory_payload = response_memory_payload or {}
        case_context = case_context or {}
        chat_history = chat_history or []

        if not bool(fallback_payload.get("use_llm", False)):
            return {"allowed": False, "reason": "llm_not_authorized", "request_payload": None}

        prompt_mode = str(fallback_payload.get("prompt_mode") or "controlled_adaptive_support").strip()
        if prompt_mode not in self.ALLOWED_PROMPT_MODES:
            prompt_mode = "controlled_adaptive_support"

        conversation_frame = case_context.get("conversation_frame", {}) or {}
        conversation_control = case_context.get("conversation_control", {}) or {}
        conversational_intent = case_context.get("conversational_intent", {}) or {}
        user_context_memory = case_context.get("user_context_memory", {}) or {}
        expert_adaptation_plan = case_context.get("expert_adaptation_plan", {}) or {}
        support_flow_response_plan = (
            case_context.get("support_flow_response_plan")
            or decision_payload.get("support_flow_response_plan")
            or {}
        )
        if support_flow_response_plan and is_deterministic_support_route(
            support_flow_response_plan.get("route_id")
        ):
            return {
                "allowed": False,
                "reason": "deterministic_support_route_llm_blocked",
                "request_payload": None,
            }
        response_goal = decision_payload.get("response_goal", {}) or {}
        constraints = fallback_payload.get("constraints", {}) or {}

        prompt_package = {
            "message": message,
            "prompt_mode": prompt_mode,
            "intent": intent_analysis.get("detected_intent"),
            "category": category_analysis.get("detected_category"),
            "primary_state": state_analysis.get("primary_state"),
            "conversation_frame": {
                "conversation_domain": conversation_frame.get("conversation_domain"),
                "support_goal": conversation_frame.get("support_goal"),
                "conversation_phase": conversation_frame.get("conversation_phase"),
                "turn_family": conversation_frame.get("turn_family"),
                "speaker_role": conversation_frame.get("speaker_role"),
                "continuity_score": conversation_frame.get("continuity_score"),
                "last_guided_action": conversation_frame.get("last_guided_action"),
                "phase_progression_reason": conversation_frame.get("phase_progression_reason"),
                "intervention_level": conversation_frame.get("intervention_level"),
                "stuck_followup_count": conversation_frame.get("stuck_followup_count"),
                "last_response_shape": conversation_frame.get("last_response_shape"),
                "response_form_variant": conversation_frame.get("response_form_variant"),
            },
            "conversation_control": {
                "turn_type": conversation_control.get("turn_type"),
                "turn_family": conversation_control.get("turn_family"),
                "domain": conversation_control.get("domain"),
                "phase": conversation_control.get("phase"),
                "previous_domain": conversation_control.get("previous_domain"),
                "previous_phase": conversation_control.get("previous_phase"),
                "clarification_mode": conversation_control.get("clarification_mode"),
                "crisis_guided_mode": conversation_control.get("crisis_guided_mode"),
                "last_guided_action": conversation_control.get("last_guided_action"),
                "domain_shift": conversation_control.get("domain_shift", {}),
                "intervention_level": conversation_control.get("intervention_level"),
                "previous_intervention_level": conversation_control.get("previous_intervention_level"),
                "stuck_followup_count": conversation_control.get("stuck_followup_count"),
                "progression_signals": conversation_control.get("progression_signals", {}),
                "previous_strategy_signature": conversation_control.get("previous_strategy_signature"),
                "previous_response_shape": conversation_control.get("previous_response_shape"),
                "previous_form_variant": conversation_control.get("previous_form_variant"),
                "strategy_repeat_count": conversation_control.get("strategy_repeat_count"),
            },
            "stage_summary": {
                "stage": stage_result.get("stage"),
                "phase_changed": stage_result.get("phase_changed"),
                "phase_progression_reason": stage_result.get("phase_progression_reason"),
                "should_close_with_followup": stage_result.get("should_close_with_followup"),
                "config": stage_result.get("config", {}),
            },
            "profile_summary": self._build_profile_summary(active_profile),
            "case_summary": self._build_case_summary(message, state_analysis, category_analysis, intent_analysis, case_context),
            "guidance_summary": self._build_guidance_summary(decision_payload, routine_payload, memory_payload, response_memory_payload, support_plan),
            "response_goal": response_goal,
            "support_flow_response_plan": support_flow_response_plan,
            "conversational_intent": conversational_intent,
            "recent_turns": self._build_recent_turns(chat_history),
            "confidence_summary": {
                "overall_confidence": confidence_payload.get("overall_confidence"),
                "confidence_level": confidence_payload.get("confidence_level"),
                "weak_points": confidence_payload.get("weak_points", []),
            },
            "user_context_memory": {
                "inferred_user_role": user_context_memory.get("inferred_user_role"),
                "conversation_preferences": user_context_memory.get("conversation_preferences", {}),
                "recurrent_topics": user_context_memory.get("recurrent_topics", []),
                "recurrent_signals": user_context_memory.get("recurrent_signals", []),
                "helpful_strategies": user_context_memory.get("helpful_strategies", []),
                "helpful_routines": user_context_memory.get("helpful_routines", []),
                "last_useful_domain": user_context_memory.get("last_useful_domain"),
                "last_useful_phase": user_context_memory.get("last_useful_phase"),
                "summary_snapshot": user_context_memory.get("summary_snapshot", {}),
            },
            "expert_adaptation_plan": {
                "tone_profile": expert_adaptation_plan.get("tone_profile", {}),
                "structure_profile": expert_adaptation_plan.get("structure_profile", {}),
                "language_profile": expert_adaptation_plan.get("language_profile", {}),
                "followup_policy": expert_adaptation_plan.get("followup_policy", {}),
            },
            "constraints": constraints,
        }
        prompt_package["system_rules"] = self._build_system_rules(prompt_mode, stage_result, category_analysis.get("detected_category"), state_analysis.get("primary_state"), constraints, response_goal, conversational_intent, conversation_control)
        return {"allowed": True, "reason": fallback_payload.get("fallback_reason", "authorized_llm_support"), "request_payload": prompt_package}

    def run(self, request_payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        request_payload = request_payload or {}
        if not request_payload:
            return self._build_stub_fallback_result(request_payload=request_payload, reason="empty_request_payload")
        if not self._is_openai_llm_enabled():
            return self._build_stub_fallback_result(request_payload=request_payload, reason="llm_disabled_by_env", llm_enabled=False)

        client, client_error = self._get_openai_client()
        if client is None:
            return self._build_stub_fallback_result(request_payload=request_payload, reason=client_error or "openai_client_unavailable", llm_enabled=True)

        try:
            response = client.responses.create(
                model=self._get_openai_model(),
                instructions=self._build_openai_instructions(request_payload),
                input=self._build_openai_input(request_payload),
                max_output_tokens=420,
            )
        except Exception as exc:
            return self._build_stub_fallback_result(request_payload=request_payload, reason=f"openai_request_failed:{type(exc).__name__}", llm_enabled=True)

        response_text = self._extract_openai_response_text(response)
        if not response_text:
            return self._build_stub_fallback_result(request_payload=request_payload, reason="empty_openai_response", llm_enabled=True)
        return self._normalize_openai_response(response_text=response_text, request_payload=request_payload, llm_enabled=True)

    def _is_openai_llm_enabled(self) -> bool:
        value = str(os.getenv("USE_OPENAI_LLM", "false") or "false").strip().lower()
        return value in {"1", "true", "yes", "y", "on", "si", "sí", "enabled"}

    def _get_openai_model(self) -> str:
        model = str(os.getenv("OPENAI_MODEL", self.DEFAULT_OPENAI_MODEL) or self.DEFAULT_OPENAI_MODEL).strip()
        return model or self.DEFAULT_OPENAI_MODEL

    def _get_openai_timeout_seconds(self) -> float:
        raw_value = str(os.getenv("OPENAI_TIMEOUT_SECONDS", str(self.DEFAULT_TIMEOUT_SECONDS)) or self.DEFAULT_TIMEOUT_SECONDS)
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            value = self.DEFAULT_TIMEOUT_SECONDS
        return max(5.0, value)

    def _get_openai_client(self) -> tuple[Optional[Any], Optional[str]]:
        if OpenAI is None:
            return None, "openai_sdk_not_installed"
        api_key = str(os.getenv("OPENAI_API_KEY", "") or "").strip()
        if not api_key:
            return None, "missing_openai_api_key"
        try:
            client = OpenAI(api_key=api_key, timeout=self._get_openai_timeout_seconds())
        except Exception as exc:
            return None, f"openai_client_init_failed:{type(exc).__name__}"
        if not hasattr(client, "responses"):
            return None, "responses_api_not_available"
        return client, None

    def is_openai_writer_enabled(self) -> bool:
        return self._is_openai_llm_enabled() and bool(str(os.getenv("OPENAI_API_KEY", "") or "").strip())

    def get_openai_writer_status(self) -> Dict[str, Any]:
        env_enabled = self._is_openai_llm_enabled()
        raw_enabled = str(os.getenv("USE_OPENAI_LLM", "") or "").strip()
        has_api_key = bool(str(os.getenv("OPENAI_API_KEY", "") or "").strip())
        enabled = env_enabled and has_api_key
        block_reason = None if enabled else "missing_openai_key_or_disabled"
        return {
            "enabled": enabled,
            "provider": "openai",
            "model": self._get_openai_model(),
            "block_reason": block_reason,
            "env_enabled": env_enabled,
            "use_openai_llm_raw": raw_enabled,
            "has_api_key": has_api_key,
        }

    def rewrite_from_behavioral_plan(self, plan: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        plan = dict(plan or {})
        request_payload = {
            "prompt_mode": "stable_demo_behavioral_writer",
            "message": str(plan.get("recent_user_message") or "").strip(),
            "behavioral_plan": plan,
        }
        if not plan:
            return self._build_behavioral_writer_fallback_result(
                request_payload=request_payload,
                reason="empty_behavioral_plan",
                llm_enabled=self._is_openai_llm_enabled(),
            )
        if not self._is_openai_llm_enabled():
            return self._build_behavioral_writer_fallback_result(
                request_payload=request_payload,
                reason="llm_disabled_by_env",
                llm_enabled=False,
            )

        client, client_error = self._get_openai_client()
        if client is None:
            return self._build_behavioral_writer_fallback_result(
                request_payload=request_payload,
                reason=client_error or "openai_client_unavailable",
                llm_enabled=True,
            )

        try:
            response = client.responses.create(
                model=self._get_openai_model(),
                instructions=self._build_behavioral_writer_instructions(plan),
                input=self._build_behavioral_writer_input(plan),
                max_output_tokens=260,
            )
        except Exception as exc:
            return self._build_behavioral_writer_fallback_result(
                request_payload=request_payload,
                reason=f"openai_request_failed:{type(exc).__name__}",
                llm_enabled=True,
            )

        response_text = self._extract_openai_response_text(response)
        if not response_text:
            return self._build_behavioral_writer_fallback_result(
                request_payload=request_payload,
                reason="empty_openai_response",
                llm_enabled=True,
            )
        normalized = self._normalize_openai_response(
            response_text=response_text,
            request_payload=request_payload,
            llm_enabled=True,
        )
        normalized["generation_metadata"] = {
            **dict(normalized.get("generation_metadata") or {}),
            "behavioral_writer": True,
            "route_id": plan.get("route_id"),
            "support_subject": plan.get("support_subject"),
            "support_mode": plan.get("support_mode"),
            "intervention_id": plan.get("intervention_id"),
        }
        return normalized

    def _build_behavioral_writer_instructions(self, plan: Dict[str, Any]) -> str:
        allowed_actions = ", ".join(map(str, (plan.get("allowed_actions") or [])[:10]))
        forbidden_actions = ", ".join(map(str, (plan.get("forbidden_actions") or [])[:10]))
        route_id = str(plan.get("route_id") or "").strip()
        support_subject = str(plan.get("support_subject") or "").strip()
        support_mode = str(plan.get("support_mode") or "").strip()

        rules = [
            "Eres la voz de neuroGuIA.",
            "No decides el dominio ni la intervencion.",
            "Solo redactas una respuesta humana y util basada en el plan.",
            "Debes responder directamente al ultimo mensaje del usuario.",
            "Si el usuario hizo una pregunta concreta o corrigio el dominio, esa respuesta va primero y no avanzas a otro paso.",
            "Si el plan dice do_not_advance_intervention, no anadas una nueva intervencion ni cambies de plantilla.",
            f"Debes mantener route_id={route_id}, support_subject={support_subject} y support_mode={support_mode}.",
            "Usa base_guidance como intencion central, no como texto obligatorio.",
            "Suena calida, clara, contenedora, casi maternal, sin infantilizar.",
            "Evita listas largas salvo que ayuden de verdad.",
            "Evita repetir frases usadas recientemente.",
            "No suenes como plantilla.",
            "No digas que eres un modelo.",
            "No des diagnostico.",
            "No recomiendes medicamentos ni dosis.",
            "Si hay riesgo fisico, prioriza seguridad.",
            "No cambies a otro dominio.",
            "No introduzcas ansiedad si el dominio es sueno, crisis o bloqueo.",
            "No introduzcas crisis si el dominio es sueno preventivo.",
            "No uses sobrepensamiento si el plan lo bloquea o si el usuario dijo que no era sobrepensamiento.",
            "No uses frases rigidas como 'primero baja una senal del cuerpo' todo el tiempo.",
            "Longitud: 2 a 5 frases maximo.",
            "Devuelve solo el texto final.",
        ]
        if allowed_actions:
            rules.append(f"Acciones permitidas: {allowed_actions}.")
        if forbidden_actions:
            rules.append(f"Acciones prohibidas: {forbidden_actions}.")
        if plan.get("safety_boundary"):
            rules.append(f"Limite de seguridad: {plan.get('safety_boundary')}.")
        if plan.get("conversation_priority"):
            rules.append(f"Prioridad conversacional: {plan.get('conversation_priority')}.")
        if plan.get("current_turn_task"):
            rules.append(f"Tarea exacta del turno: {plan.get('current_turn_task')}.")
        if plan.get("blocked_interventions"):
            rules.append(f"Intervenciones bloqueadas temporalmente: {plan.get('blocked_interventions')}.")
        if route_id == "medicacion":
            rules.append("En medicacion, puedes rechazar recomendar medicamentos o dosis; no nombres farmacos concretos.")
        if route_id == "crisis" and support_subject in {"child", "teen_child"} and support_mode == "acute":
            rules.append("Crisis de hijo/hija en modo agudo: prioriza seguridad fisica, distancia, retirar objetos peligrosos, pocas palabras y ayuda presencial si hay riesgo.")
        if route_id == "sueno":
            rules.append("Ruta sueno: no metas sobrepensamiento, preocupaciones por escrito ni ansiedad salvo que el usuario lo haya mencionado de forma explicita.")
        return "\n".join(f"- {rule}" for rule in rules)

    def _build_behavioral_writer_input(self, plan: Dict[str, Any]) -> str:
        compact_plan = {
            "route_id": plan.get("route_id"),
            "support_subject": plan.get("support_subject"),
            "support_mode": plan.get("support_mode"),
            "intervention_id": plan.get("intervention_id"),
            "objective": plan.get("objective"),
            "base_guidance": plan.get("base_guidance"),
            "recent_user_message": plan.get("recent_user_message"),
            "recent_context": (plan.get("recent_context") or [])[-5:],
            "allowed_actions": plan.get("allowed_actions") or [],
            "forbidden_actions": plan.get("forbidden_actions") or [],
            "safety_boundary": plan.get("safety_boundary"),
            "tone": plan.get("tone"),
            "turn_family": plan.get("turn_family"),
            "repair_type": plan.get("repair_type"),
            "current_turn_task": plan.get("current_turn_task"),
            "conversation_priority": plan.get("conversation_priority"),
            "must_answer_current_question_first": plan.get("must_answer_current_question_first"),
            "do_not_advance_intervention": plan.get("do_not_advance_intervention"),
            "blocked_interventions": plan.get("blocked_interventions") or {},
        }
        return (
            "PLAN CONDUCTUAL YA DECIDIDO POR EL SISTEMA LOCAL:\n"
            f"{json.dumps(compact_plan, ensure_ascii=False, indent=2)}\n\n"
            "Redacta la respuesta final para el turno actual sin cambiar ese plan."
        )

    def _build_behavioral_writer_fallback_result(
        self,
        request_payload: Dict[str, Any],
        reason: str,
        llm_enabled: bool = False,
    ) -> Dict[str, Any]:
        return {
            "response_text": "",
            "response_structure": {},
            "llm_confidence_hint": 0.0,
            "provider": "openai",
            "model": self._get_openai_model(),
            "used_stub_fallback": True,
            "fallback_reason": reason,
            "llm_enabled": llm_enabled,
            "generation_metadata": {
                "provider": "openai",
                "model": self._get_openai_model(),
                "used_stub_fallback": True,
                "fallback_reason": reason,
                "llm_enabled": llm_enabled,
                "behavioral_writer": True,
                "prompt_mode": request_payload.get("prompt_mode"),
            },
        }

    def _build_openai_instructions(self, request_payload: Dict[str, Any]) -> str:
        system_rules = request_payload.get("system_rules", []) or []
        conversation_frame = request_payload.get("conversation_frame", {}) or {}
        conversation_control = request_payload.get("conversation_control", {}) or {}
        conversational_intent = request_payload.get("conversational_intent", {}) or {}
        response_goal = request_payload.get("response_goal", {}) or {}
        support_flow_response_plan = request_payload.get("support_flow_response_plan", {}) or {}
        stage_summary = request_payload.get("stage_summary", {}) or {}
        constraints = request_payload.get("constraints", {}) or {}
        recent_turns = request_payload.get("recent_turns", []) or []

        rules = [
            "Eres NeuroGuIA y solo redactas la respuesta final para la persona usuaria.",
            "La clasificacion, la seguridad, el dominio y la fase ya fueron decididos por el sistema local.",
            "Si recibes un support_flow_response_plan, tu trabajo es redactarlo mejor, no cambiarlo.",
            "Responde en espanol claro, calido, cercano, suave, paciente y contenedor; evita sonar tecnico, clinico o rigido.",
            "Haz sentir presencia real: puedes sonar casi maternal si el momento lo pide, sin infantilizar.",
            "No menciones taxonomias internas, nombres tecnicos ni etiquetas del sistema.",
            "No diagnostiques ni sustituyas atencion profesional.",
            "No cambies de dominio por tu cuenta.",
            "No cambies el problema central ni metas estrategias nuevas si no vienen ya implicitas en el plan base.",
            "Orden sugerido: responde primero al mensaje real del usuario y usa el response_goal solo como direccion de fondo.",
            "Si conversational_intent contradice, suaviza o desvanece el dominio o el response_goal, ignoralo.",
            "Respeta el objetivo del turno, no una forma exacta prefabricada.",
            "Haz que el contenido especifico del dominio sea visible en la respuesta; la direccion conversacional solo modula ritmo, presion, permisividad y cierre.",
            "Prioriza presencia humana y continuidad real por encima de sonar perfectamente estructurado.",
            "Puedes validar, acompanar, pausar o solo estar presente si eso encaja mejor con el momento.",
            "Si la persona pregunta algo concreto, responde eso primero de forma concreta.",
            "No estas obligada a dejar una accion, una pregunta, una lista o una estructura fija en cada turno.",
            "No repitas la misma idea del turno anterior con otras palabras.",
            "Si la persona pregunta algo concreto como donde escribir, que decir, como conseguir ayuda o aclara que no tiene materiales, responde esa pregunta antes de cualquier paso.",
            "Si la persona niega sobrepensamiento, no uses sobrepensamiento durante ese turno; permanece en el dominio corregido.",
            "Si habla de hijo/hija gritando, agresion o querer golpear, prioriza seguridad fisica, distancia, retirar objetos peligrosos y pedir ayuda si hay riesgo inmediato.",
            "Evita caer en formulas repetidas como 'Vamos paso a paso', 'Haz solo esto ahora' o 'Que parte te serviria mas ordenar primero?'.",
            "Evita arranques tipo 'La respuesta mas util aqui es', 'Lo mas util suele ser' o 'En este caso'.",
            "Si el sistema ya subio el nivel de intervencion, haz que tambien cambie la forma visible: apertura, cadencia, estructura o cierre.",
            "No mantengas la misma apertura y la misma cadencia en follow-ups bloqueados.",
            "Devuelve solo el texto final.",
        ]

        if conversation_frame.get("conversation_phase"):
            rules.append(f"Mantente alineado con la fase actual: {conversation_frame.get('conversation_phase')}.")
        if conversation_control.get("turn_family"):
            rules.append(f"Familia real del turno: {conversation_control.get('turn_family')}.")
        if stage_summary.get("phase_changed"):
            rules.append("Haz perceptible el avance de fase de forma natural.")
        if conversation_control.get("clarification_mode") not in {None, "", "none"}:
            rules.append("Estas en modo de aclaracion: reformula lo ultimo mas simple, sin abrir temas nuevos.")
        if conversation_control.get("crisis_guided_mode") == "guided_steps":
            rules.append("Estas en crisis guiada: pasa a pasos breves, concretos y seguros.")
        if response_goal.get("goal"):
            rules.append(f"Objetivo del turno: {response_goal.get('goal')}.")
        if response_goal.get("domain_focus"):
            rules.append(f"Foco especifico del dominio: {response_goal.get('domain_focus')}.")
        if response_goal.get("response_shape"):
            rules.append(f"Forma preferida si ayuda: {response_goal.get('response_shape')}.")
        if response_goal.get("intervention_level"):
            rules.append(f"Nivel de intervencion actual: {response_goal.get('intervention_level')}.")
        if response_goal.get("form_variant"):
            rules.append(f"Variante visible sugerida: {response_goal.get('form_variant')}.")
        if conversational_intent:
            rules.append(
                "Modulacion conversacional disponible: "
                f"ritmo={conversational_intent.get('rhythm')}, "
                f"presion={conversational_intent.get('pressure')}, "
                f"permisividad={conversational_intent.get('permissiveness')}, "
                f"cierre={conversational_intent.get('closing_style')}."
            )
        if conversational_intent.get("permissiveness") == "high":
            rules.append("No es obligatorio cerrar con tarea si la respuesta funciona mejor bajando exigencia o pausando.")
        if response_goal.get("response_shape") == "literal_phrase":
            rules.append("Entrega primero una frase literal usable, no solo una estrategia general.")
        if support_flow_response_plan:
            rules.append("Conserva la validacion, la accion central, la frase literal y el tipo de cierre del support_flow_response_plan.")
            rules.append("Puedes corregir ortografia, tildes, naturalidad y calidez, pero no debes mover la ruta conductual.")
            rules.append("No cambies route_id, subroute_id, objetivo, seguridad, dominio ni tipo de accion. Solo redacta mejor el plan recibido.")
            rules.append("La respuesta final debe conservar palabras-ancla de la accion central del plan; si el plan habla de sueño, infancia, crisis, tarea o cuidador, ese dominio debe verse en el texto final.")
            rules.append("No agregues grounding, validacion emocional generica ni tecnicas de ansiedad si no aparecen en el plan.")
            rules.append("No uses plantillas recicladas, mecánica interna, ni mensajes donde la persona deba escoger dominio cuando ya hay ruta activa.")
            rules.append("Bloquea estas frases salvo subruta ansiedad_grounding: 'Tiene sentido que esto te este pesando', 'Vamos primero a bajar la activacion', 'pies en el piso', 'exhalacion mas larga'.")
            route_id = normalize_input(str(support_flow_response_plan.get("route_id") or ""))
            subroute_id = normalize_input(str(support_flow_response_plan.get("subroute_id") or ""))
            if route_id == "crisis":
                rules.append("Ruta crisis: usa solo entorno, bajar demanda, distancia segura, frase breve, no discutir y no explicar demasiado. Prohibido: pies en el piso, exhalacion, abrir notas o escribir preocupaciones.")
            if route_id == "sueno":
                rules.append("Ruta sueño: usa luz, pantalla, ruido, rutina de bajada, mente acelerada, cuerpo activado o entorno. Prohibido: presion real, decision de tareas y grounding de ansiedad.")
                if subroute_id != "sleep mind racing":
                    rules.append("En sueño, no uses nota de preocupacion salvo si la subruta es sleep_mind_racing o el plan menciona mente acelerada.")
            if route_id == "bloqueo ejecutivo":
                rules.append("Ruta bloqueo ejecutivo: da paso visible, abrir material, elegir materia urgente, escribir titulo o dividir tarea. Prohibido responder con ansiedad generica.")
            if route_id == "apoyo infancia neurodivergente":
                rules.append("Ruta infancia: centra la respuesta en la hija/hijo, corregulacion, frases cortas, bajar estimulos o anticipar. Usa sobrepensamiento solo si el usuario lo menciono explicitamente.")
            if subroute_id:
                rules.append(f"Subruta bloqueada por el flow_engine: {support_flow_response_plan.get('subroute_id')}.")
        if conversation_control.get("turn_family") == "post_action_followup":
            rules.append("Esto es seguimiento post-accion: no repitas el protocolo anterior; verifica efecto, decide si parar o da un paso distinto.")
        if (conversation_control.get("progression_signals", {}) or {}).get("repeated_post_action_followup"):
            rules.append("Ya hubo accion, seguimiento y ajuste: ahora cierra, deja una pausa guiada o toma una decision concreta. No sigas abriendo pasos.")
        if conversation_control.get("turn_family") == "specific_action_request":
            rules.append("Esto es una peticion de accion concreta: responde con una accion clara primero, no con estrategia general.")
        if conversation_control.get("turn_family") == "literal_phrase_request":
            rules.append("Esto es una peticion de frase literal: entrega la frase usable antes de cualquier explicacion.")
        if conversation_control.get("turn_family") == "simple_question":
            rules.append("Esto es una consulta simple: responde breve y directa, sin entrar en intervencion prolongada.")
        if conversation_control.get("turn_family") == "meta_question":
            rules.append("Esto es una pregunta meta o relacional: responde directo, breve y humano, sin logica terapeutica.")
        if conversation_control.get("turn_family") == "validation_request":
            rules.append("Esto es una peticion de validacion: responde si es esperable o no de forma clara y breve.")
        if conversation_control.get("turn_family") == "closure_or_pause":
            rules.append("Esto es cierre o pausa: no empujes otra accion ni otra pregunta.")
        if response_goal.get("response_shape") in {"single_action", "grounding", "sleep_settle", "concrete_action", "guided_decision", "direct_instruction"}:
            rules.append("Si el turno pide direccion clara y ayuda mas decidir que preguntar, puedes elegir una accion concreta por la persona.")
        if int(conversation_control.get("stuck_followup_count", 0) or 0) >= 1:
            rules.append("La persona sigue bloqueada: sube claridad o direccion y no repitas la misma microaccion ni el mismo arranque.")
        if int(conversation_control.get("strategy_repeat_count", 0) or 0) >= 1:
            rules.append("Evita repetir el mismo esqueleto del turno anterior.")
        if recent_turns:
            rules.append("Usa la transcripcion reciente para sonar continuo, sin repetir ni reiniciar.")
        avoid = constraints.get("avoid", []) or []
        if avoid:
            rules.append(f"Evita explicitamente: {', '.join(map(str, avoid[:8]))}.")
        return "\n".join(f"- {rule}" for rule in rules + [str(rule) for rule in system_rules if str(rule).strip()])

    def _build_openai_input(self, request_payload: Dict[str, Any]) -> str:
        case_summary = request_payload.get("case_summary", {}) or {}
        conversation_frame = request_payload.get("conversation_frame", {}) or {}
        conversation_control = request_payload.get("conversation_control", {}) or {}
        profile_summary = request_payload.get("profile_summary", {}) or {}
        guidance_summary = request_payload.get("guidance_summary", {}) or {}
        response_goal = request_payload.get("response_goal", {}) or {}
        support_flow_response_plan = request_payload.get("support_flow_response_plan", {}) or {}
        conversational_intent = request_payload.get("conversational_intent", {}) or {}
        user_context_memory = request_payload.get("user_context_memory", {}) or {}
        constraints = request_payload.get("constraints", {}) or {}
        recent_turns = request_payload.get("recent_turns", []) or []

        transcript_lines: List[str] = []
        for turn in recent_turns:
            user_text = str(turn.get("user") or "").strip()
            assistant_text = str(turn.get("assistant") or "").strip()
            if user_text:
                transcript_lines.append(f"USUARIO: {user_text}")
            if assistant_text:
                transcript_lines.append(f"NEUROGUIA: {assistant_text}")
        transcript = "\n".join(transcript_lines).strip() or "(sin turnos previos relevantes)"

        compact_context = {
            "conversation_domain": conversation_frame.get("conversation_domain"),
            "conversation_phase": conversation_frame.get("conversation_phase"),
            "support_goal": conversation_frame.get("support_goal"),
            "speaker_role": conversation_frame.get("speaker_role"),
            "turn_type": conversation_control.get("turn_type"),
            "turn_family": conversation_control.get("turn_family"),
            "clarification_mode": conversation_control.get("clarification_mode"),
            "crisis_guided_mode": conversation_control.get("crisis_guided_mode"),
            "last_guided_action": conversation_control.get("last_guided_action"),
            "domain_shift": conversation_control.get("domain_shift", {}),
            "detected_category": case_summary.get("detected_category"),
            "detected_intent": case_summary.get("detected_intent"),
            "primary_state": case_summary.get("primary_state"),
            "secondary_states": case_summary.get("secondary_states", []),
            "caregiver_capacity": case_summary.get("caregiver_capacity"),
            "emotional_intensity": case_summary.get("emotional_intensity"),
            "profile_alias": profile_summary.get("alias"),
            "profile_role": profile_summary.get("role"),
            "profile_conditions": profile_summary.get("conditions", []),
            "response_goal": response_goal,
            "support_flow_response_plan": support_flow_response_plan,
            "conversational_intent": conversational_intent,
            "memory_snapshot": user_context_memory.get("summary_snapshot", {}),
            "helpful_memory": {
                "helpful_strategies": user_context_memory.get("helpful_strategies", [])[:4],
                "helpful_routines": user_context_memory.get("helpful_routines", [])[:3],
                "last_useful_domain": user_context_memory.get("last_useful_domain"),
                "last_useful_phase": user_context_memory.get("last_useful_phase"),
            },
            "guidance_summary": guidance_summary,
            "constraints": {
                "avoid": constraints.get("avoid", []),
                "must_include": constraints.get("must_include", []),
                "should_close_with_followup": constraints.get("should_close_with_followup"),
            },
        }
        support_flow_base = ""
        if support_flow_response_plan:
            support_flow_base = (
                "\n\nPLAN CONDUCTUAL YA DECIDIDO:\n"
                f"{json.dumps(support_flow_response_plan, ensure_ascii=False, indent=2)}"
            )

        return (
            "TRANSCRIPCION RECIENTE:\n"
            f"{transcript}\n\n"
            "MENSAJE DEL USUARIO:\n"
            f"{request_payload.get('message') or ''}\n\n"
            "CONTEXTO ESTRUCTURADO DEL SISTEMA:\n"
            f"{json.dumps(compact_context, ensure_ascii=False, indent=2)}"
            f"{support_flow_base}"
        )

    def _build_recent_turns(self, chat_history: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        recent_turns: List[Dict[str, str]] = []
        for item in (chat_history or [])[-4:]:
            if not isinstance(item, dict):
                continue
            user_text = str(item.get("user") or "").strip()
            assistant_text = str(item.get("assistant") or "").strip()
            if not user_text and not assistant_text:
                continue
            recent_turns.append({"user": user_text[:500], "assistant": assistant_text[:700]})
        return recent_turns

    def _extract_openai_response_text(self, response: Any) -> str:
        text = str(getattr(response, "output_text", "") or "").strip()
        if text:
            return text
        output_items = getattr(response, "output", None) or []
        fragments: List[str] = []
        for item in output_items:
            content_items = getattr(item, "content", None)
            if content_items is None and isinstance(item, dict):
                content_items = item.get("content", [])
            for block in content_items or []:
                candidate = getattr(block, "text", None)
                if candidate is None and isinstance(block, dict):
                    candidate = block.get("text")
                if isinstance(candidate, str) and candidate.strip():
                    fragments.append(candidate.strip())
                else:
                    value = getattr(candidate, "value", None)
                    if isinstance(value, str) and value.strip():
                        fragments.append(value.strip())
        return " ".join(fragments).strip()

    def _normalize_openai_response(self, response_text: str, request_payload: Dict[str, Any], llm_enabled: bool) -> Dict[str, Any]:
        clean_text = str(response_text or "").strip()
        clean_text = re.sub(r"\s+\n", "\n", clean_text)
        clean_text = re.sub(r"\n{3,}", "\n\n", clean_text)
        clean_text = re.sub(r"^\s*(neuroguia|respuesta)\s*:\s*", "", clean_text, flags=re.IGNORECASE)
        clean_text = self._strip_robotic_openings(clean_text)
        return {
            "response_text": clean_text,
            "response_structure": self._extract_structure(clean_text),
            "llm_confidence_hint": 0.76,
            "provider": "openai",
            "model": self._get_openai_model(),
            "used_stub_fallback": False,
            "fallback_reason": None,
            "llm_enabled": llm_enabled,
            "generation_metadata": self._build_generation_metadata(request_payload, "openai", self._get_openai_model(), False, None, llm_enabled),
        }

    def _extract_structure(self, text: str) -> Dict[str, Any]:
        clean_text = str(text or "").strip()
        if not clean_text:
            return {"opening_validation": None, "main_guidance": None, "microaction": None, "followup_bridge": None, "full_text": ""}
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", clean_text) if part.strip()]
        opening = paragraphs[0] if paragraphs else clean_text
        main_guidance = paragraphs[1] if len(paragraphs) > 1 else clean_text
        followup = paragraphs[-1] if len(paragraphs) > 2 else None
        return {"opening_validation": opening, "main_guidance": main_guidance, "microaction": None, "followup_bridge": followup, "full_text": clean_text}

    def _build_stub_fallback_result(self, request_payload: Dict[str, Any], reason: str, llm_enabled: bool = False) -> Dict[str, Any]:
        stub_result = self.build_local_stub_response(request_payload)
        stub_result["provider"] = "stub_local"
        stub_result["model"] = "local_stub"
        stub_result["used_stub_fallback"] = True
        stub_result["fallback_reason"] = reason
        stub_result["llm_enabled"] = llm_enabled
        stub_result["generation_metadata"] = self._build_generation_metadata(request_payload, "stub_local", "local_stub", True, reason, llm_enabled)
        return stub_result

    def _build_generation_metadata(self, request_payload: Dict[str, Any], provider: str, model: str, used_stub_fallback: bool, fallback_reason: Optional[str], llm_enabled: bool) -> Dict[str, Any]:
        case_summary = request_payload.get("case_summary", {}) or {}
        conversation_frame = request_payload.get("conversation_frame", {}) or {}
        conversation_control = request_payload.get("conversation_control", {}) or {}
        conversational_intent = request_payload.get("conversational_intent", {}) or {}
        user_context_memory = request_payload.get("user_context_memory", {}) or {}
        return {
            "provider": provider,
            "model": model,
            "used_stub_fallback": used_stub_fallback,
            "fallback_reason": fallback_reason,
            "llm_enabled": llm_enabled,
            "context_summary": {
                "prompt_mode": request_payload.get("prompt_mode"),
                "conversation_domain": conversation_frame.get("conversation_domain"),
                "conversation_phase": conversation_frame.get("conversation_phase"),
                "turn_type": conversation_control.get("turn_type"),
                "clarification_mode": conversation_control.get("clarification_mode"),
                "crisis_guided_mode": conversation_control.get("crisis_guided_mode"),
                "conversational_rhythm": conversational_intent.get("rhythm"),
                "conversational_pressure": conversational_intent.get("pressure"),
                "conversational_permissiveness": conversational_intent.get("permissiveness"),
                "conversational_closing_style": conversational_intent.get("closing_style"),
                "detected_category": case_summary.get("detected_category"),
                "detected_intent": case_summary.get("detected_intent"),
                "primary_state": case_summary.get("primary_state"),
                "user_context_available": bool(user_context_memory),
            },
        }
    def _build_profile_summary(self, active_profile: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "profile_id": active_profile.get("profile_id"),
            "alias": active_profile.get("alias"),
            "role": active_profile.get("role"),
            "age": active_profile.get("age"),
            "conditions": active_profile.get("conditions", []),
            "sensory_needs": active_profile.get("sensory_needs", []),
            "emotional_needs": active_profile.get("emotional_needs", []),
            "helpful_strategies": active_profile.get("helpful_strategies", []),
            "harmful_strategies": active_profile.get("harmful_strategies", []),
            "sleep_profile": active_profile.get("sleep_profile"),
            "school_profile": active_profile.get("school_profile"),
            "executive_profile": active_profile.get("executive_profile"),
        }

    def _build_case_summary(self, message: str, state_analysis: Dict[str, Any], category_analysis: Dict[str, Any], intent_analysis: Dict[str, Any], case_context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "user_message": message,
            "detected_intent": intent_analysis.get("detected_intent"),
            "intent_confidence": intent_analysis.get("confidence"),
            "detected_category": category_analysis.get("detected_category"),
            "category_confidence": category_analysis.get("confidence"),
            "primary_state": state_analysis.get("primary_state"),
            "secondary_states": state_analysis.get("secondary_states", []),
            "caregiver_capacity": case_context.get("caregiver_capacity"),
            "emotional_intensity": case_context.get("emotional_intensity"),
            "followup_needed": case_context.get("followup_needed"),
            "conversation_domain": case_context.get("conversation_domain"),
            "conversation_phase": case_context.get("conversation_phase"),
            "speaker_role": case_context.get("speaker_role"),
        }

    def _build_guidance_summary(self, decision_payload: Dict[str, Any], routine_payload: Dict[str, Any], memory_payload: Dict[str, Any], response_memory_payload: Dict[str, Any], support_plan: Dict[str, Any]) -> Dict[str, Any]:
        best_response = response_memory_payload.get("best_response") or {}
        response_goal = decision_payload.get("response_goal", {}) or {}
        return {
            "selected_strategy": decision_payload.get("selected_strategy"),
            "selected_microaction": decision_payload.get("selected_microaction"),
            "selected_routine_type": decision_payload.get("selected_routine_type"),
            "intervention_type": decision_payload.get("intervention_type"),
            "response_goal": response_goal.get("goal"),
            "candidate_actions": response_goal.get("candidate_actions", [])[:3],
            "possible_questions": response_goal.get("possible_questions", [])[:2],
            "support_priorities": support_plan.get("support_priorities", [])[:5],
            "response_alerts": support_plan.get("response_alerts", [])[:5],
            "memory_recommended_strategies": memory_payload.get("recommended_strategies", [])[:4],
            "memory_recommended_microactions": memory_payload.get("recommended_microactions", [])[:4],
            "routine_name": routine_payload.get("routine_name"),
            "routine_short_version": routine_payload.get("short_version", [])[:3],
            "routine_steps": routine_payload.get("steps", [])[:4],
            "reuse_candidate_exists": bool(best_response),
            "reuse_candidate_text": best_response.get("response_text"),
        }

    def _build_system_rules(self, prompt_mode: str, stage_result: Dict[str, Any], category: Optional[str], primary_state: Optional[str], constraints: Dict[str, Any], response_goal: Dict[str, Any], conversational_intent: Dict[str, Any], conversation_control: Dict[str, Any]) -> List[str]:
        rules = [
            "No diagnostiques.",
            "No sustituyas atencion profesional.",
            "No moralices ni culpabilices.",
            "Manten la respuesta proporcional al estado del caso.",
            "No contradigas las restricciones locales de seguridad.",
            "Prioriza una salida clara, calida, cercana y humana.",
            "Usa espanol claro y natural, sin tecnicismos ni tono de manual.",
            "No reinicies la conversacion si ya existe un dominio claro.",
            "Haz visible primero el problema concreto del usuario y el contenido del dominio; usa conversational_intent solo para modular ritmo, presion, permisividad y cierre.",
            "Puedes responder solo con acompanamiento si eso sirve mejor que dejar una accion o una pregunta.",
            "Evita frases como 'La respuesta mas util aqui es', 'Lo mas util suele ser' y 'En este caso'.",
        ]
        if prompt_mode == "controlled_crisis_support":
            rules.extend(["Prioriza seguridad, baja demanda y contencion.", "Usa frases breves y concretas.", "No hagas analisis extenso."])
        if prompt_mode == "controlled_low_demand_support":
            rules.extend(["Reduce carga cognitiva.", "No conviertas la respuesta en una lista larga."])
        if prompt_mode == "controlled_explanatory_support":
            rules.extend(["Explica de forma clara y breve.", "No uses jerga innecesaria."])
        if prompt_mode == "controlled_reflective_feedback":
            rules.append("Ayuda a reflexionar sin sonar evaluativo.")
        if prompt_mode == "support_flow_humanization":
            rules.extend(
                [
                    "Redacta desde el plan conductual ya decidido sin cambiar la ruta.",
                    "Tu trabajo principal aqui es humanizar, corregir ortografia, mejorar fluidez y sonar mas cercano.",
                    "Si el plan trae una frase literal, conservala o solo suavizala sin cambiar su sentido.",
                ]
            )
        if primary_state in {"meltdown", "shutdown"}:
            rules.append("Reduce aun mas la exigencia verbal.")
        if category == "ansiedad_cognitiva":
            rules.append("Favorece descarga mental, priorizacion y reduccion de saturacion.")
        if category == "disfuncion_ejecutiva":
            rules.append("Favorece microacciones y primer paso visible.")
        if response_goal.get("domain_focus"):
            rules.append(f"Manten visible este foco: {response_goal.get('domain_focus')}.")
        if response_goal.get("response_shape"):
            rules.append(f"Usa esta forma solo como guia flexible: {response_goal.get('response_shape')}.")
        if response_goal.get("intervention_level"):
            rules.append(f"Sube o baja la direccion segun este nivel: {response_goal.get('intervention_level')}.")
        if response_goal.get("form_variant"):
            rules.append(f"No uses una forma generica: apunta a esta variante visible {response_goal.get('form_variant')}.")
        if conversation_control.get("turn_family"):
            rules.append(f"Responde segun esta familia de turno: {conversation_control.get('turn_family')}.")
        if conversation_control.get("clarification_mode") not in {None, "", "none"}:
            rules.append("Reformula de manera mas simple lo ultimo sin repetir exactamente la misma idea.")
        if conversation_control.get("crisis_guided_mode") == "guided_steps":
            rules.append("Pasa a guia concreta y breve; no te quedes en contencion general.")
        if int(conversation_control.get("stuck_followup_count", 0) or 0) >= 1:
            rules.append("La persona sigue bloqueada: cambia tambien la apertura, el ritmo o el cierre; no solo la accion.")
        if conversation_control.get("turn_family") == "post_action_followup":
            rules.append("No recicles la misma lista: mira efecto, decide si basta o da un paso distinto.")
        if (conversation_control.get("progression_signals", {}) or {}).get("repeated_post_action_followup"):
            rules.append("Ya hubo accion, seguimiento y ajuste: ahora toca cierre temporal, pausa guiada o decision concreta.")
        if conversation_control.get("turn_family") == "simple_question":
            rules.append("Evita sonar como intervencion larga; responde de forma puntual.")
        if conversation_control.get("turn_family") == "meta_question":
            rules.append("Responde directo y humano; no la conviertas en acompanamiento terapeutico.")
        if conversation_control.get("turn_family") == "closure_or_pause":
            rules.append("Permite cerrar o pausar sin reabrir la intervencion.")
        if conversational_intent:
            rules.append(
                "Modula solo estos ejes: "
                f"ritmo={conversational_intent.get('rhythm')}, "
                f"presion={conversational_intent.get('pressure')}, "
                f"permisividad={conversational_intent.get('permissiveness')}, "
                f"cierre={conversational_intent.get('closing_style')}."
            )
        if conversational_intent.get("permissiveness") == "high":
            rules.append("Puede ser suficiente validar o acompanar sin dejar tarea.")
        if response_goal.get("response_shape") == "literal_phrase":
            rules.append("Da una frase literal usable antes de cualquier explicacion.")
        if response_goal.get("response_shape") in {"single_action", "grounding", "sleep_settle", "concrete_action", "guided_decision", "direct_instruction"}:
            rules.append("Si la persona esta saturada y ayuda mas direccion que exploracion, puedes decidir una accion concreta por ella.")
        if response_goal.get("safety_constraints"):
            rules.append(f"Restricciones estrategicas: {', '.join(map(str, response_goal.get('safety_constraints', [])[:6]))}.")
        avoid = constraints.get("avoid", []) or []
        if avoid:
            rules.append(f"Evitar explicitamente: {', '.join(map(str, avoid[:8]))}.")
        must_include = constraints.get("must_include", []) or []
        if must_include:
            rules.append(f"Incluir, si es natural: {', '.join(map(str, must_include[:5]))}.")
        return rules

    def build_local_stub_response(self, request_payload: Dict[str, Any]) -> Dict[str, Any]:
        if not request_payload:
            return {"response_text": "", "response_structure": {}, "llm_confidence_hint": 0.0}
        response_goal = request_payload.get("response_goal", {}) or {}
        conversational_intent = request_payload.get("conversational_intent", {}) or {}
        case_summary = request_payload.get("case_summary", {}) or {}
        conversation_control = request_payload.get("conversation_control", {}) or {}
        conversation_frame = request_payload.get("conversation_frame", {}) or {}
        constraints = request_payload.get("constraints", {}) or {}
        response_goal_for_render = dict(response_goal)
        if not constraints.get("should_close_with_followup", False):
            response_goal_for_render["should_offer_question"] = False
            if response_goal_for_render.get("followup_policy") == "brief_check":
                response_goal_for_render["followup_policy"] = "avoid"

        from core.response_builder import ResponseBuilder

        renderer = ResponseBuilder()
        render_frame = {
            **conversation_frame,
            "conversation_domain": conversation_frame.get("conversation_domain") or case_summary.get("detected_category"),
            "conversation_phase": conversation_frame.get("conversation_phase") or request_payload.get("conversation_phase"),
            "turn_type": conversation_control.get("turn_type"),
            "turn_family": conversation_control.get("turn_family"),
            "clarification_mode": conversation_control.get("clarification_mode"),
            "crisis_guided_mode": conversation_control.get("crisis_guided_mode"),
        }
        full_text = renderer._render_fallback(
            response_goal=response_goal_for_render,
            conversational_intent=conversational_intent,
            conversation_frame=render_frame,
            state_analysis={"primary_state": case_summary.get("primary_state")},
            category_analysis={"detected_category": case_summary.get("detected_category")},
        )
        return {
            "response_text": full_text,
            "response_structure": self._extract_structure(full_text),
            "llm_confidence_hint": self._estimate_stub_confidence(case_summary, response_goal),
            "provider": "stub_local",
            "model": "local_stub",
            "used_stub_fallback": True,
            "fallback_reason": "manual_stub",
            "llm_enabled": False,
        }

    def _estimate_stub_confidence(self, case_summary: Dict[str, Any], response_goal: Dict[str, Any]) -> float:
        score = 0.56
        if case_summary.get("detected_category"):
            score += 0.10
        if case_summary.get("primary_state"):
            score += 0.10
        if response_goal.get("suggested_content"):
            score += 0.08
        if response_goal.get("candidate_actions"):
            score += 0.07
        return min(score, 0.89)

    def _strip_robotic_openings(self, text: str) -> str:
        clean_text = str(text or "").strip()
        patterns = [
            r"^\s*la respuesta mas util aqui es[:\s,]*",
            r"^\s*la respuesta mas util es[:\s,]*",
            r"^\s*lo mas util suele ser[:\s,]*",
            r"^\s*lo mas util aqui es[:\s,]*",
            r"^\s*en este caso[:\s,]*",
        ]
        for pattern in patterns:
            clean_text = re.sub(pattern, "", clean_text, flags=re.IGNORECASE)
        return clean_text.strip()


def build_llm_request(
    message: str,
    fallback_payload: Optional[Dict[str, Any]] = None,
    decision_payload: Optional[Dict[str, Any]] = None,
    confidence_payload: Optional[Dict[str, Any]] = None,
    intent_analysis: Optional[Dict[str, Any]] = None,
    category_analysis: Optional[Dict[str, Any]] = None,
    state_analysis: Optional[Dict[str, Any]] = None,
    stage_result: Optional[Dict[str, Any]] = None,
    support_plan: Optional[Dict[str, Any]] = None,
    active_profile: Optional[Dict[str, Any]] = None,
    routine_payload: Optional[Dict[str, Any]] = None,
    memory_payload: Optional[Dict[str, Any]] = None,
    response_memory_payload: Optional[Dict[str, Any]] = None,
    case_context: Optional[Dict[str, Any]] = None,
    chat_history: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    gateway = LLMGateway()
    return gateway.build_request(
        message=message,
        fallback_payload=fallback_payload,
        decision_payload=decision_payload,
        confidence_payload=confidence_payload,
        intent_analysis=intent_analysis,
        category_analysis=category_analysis,
        state_analysis=state_analysis,
        stage_result=stage_result,
        support_plan=support_plan,
        active_profile=active_profile,
        routine_payload=routine_payload,
        memory_payload=memory_payload,
        response_memory_payload=response_memory_payload,
        case_context=case_context,
        chat_history=chat_history,
    )
