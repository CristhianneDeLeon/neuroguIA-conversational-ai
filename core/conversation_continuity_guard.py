# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
import re
import unicodedata
from typing import Any, Dict, List, Optional

from core.llm_gateway import LLMGateway
from core.routine_builder_v2 import RoutineBuilderV2, render_routine_payload


class ConversationContinuityGuard:
    """Capa final de continuidad conversacional.

    La lógica determinista conserva seguridad, categoría y estructura de rutina.
    Cuando la API de OpenAI está habilitada, el modelo se usa únicamente como
    redactor conversacional para responder al turno actual sin reiniciar el tema.
    """

    ROUTINE_AUDIENCE_QUESTIONS = (
        "esta rutina es para ti",
        "para tu hijo o para toda la familia",
        "para ti para tu hijo o para toda la familia",
        "para quien es esta rutina",
        "para quién es esta rutina",
    )

    GENERIC_RESTART_MARKERS = (
        "estoy contigo. primero baja una sola señal del cuerpo",
        "estoy contigo primero baja una sola señal del cuerpo",
        "primero baja una sola señal del cuerpo",
        "apoya ambos pies y suelta el aire lento una vez",
    )

    CRISIS_MARKERS = (
        "se puede lastimar",
        "puede lastimarse",
        "riesgo inmediato",
        "riesgo fisico",
        "riesgo físico",
        "se esta golpeando",
        "se está golpeando",
        "esta golpeando",
        "está golpeando",
        "amenaza con",
        "arma",
        "suicid",
    )

    def __init__(self) -> None:
        self.builder = RoutineBuilderV2()
        self.llm_gateway = LLMGateway()

    def ensure(
        self,
        *,
        message: str,
        result: Optional[Dict[str, Any]],
        chat_history: Optional[List[Dict[str, Any]]] = None,
        previous_result: Optional[Dict[str, Any]] = None,
        active_profile: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        output = copy.deepcopy(dict(result or {}))
        history = [item for item in list(chat_history or []) if isinstance(item, dict)]
        previous_result = dict(previous_result or {})
        active_profile = dict(active_profile or output.get("active_profile") or {})

        current_message = str(message or "").strip()
        if not current_message:
            return output

        pending = self._infer_pending_context(history=history, previous_result=previous_result)
        targets = self._resolve_routine_targets(current_message)

        if pending.get("kind") == "routine_audience" and targets:
            output = self._answer_routine_audience_followup(
                message=current_message,
                output=output,
                history=history,
                previous_result=previous_result,
                active_profile=active_profile,
                pending=pending,
                targets=targets,
            )

        response_package = dict(output.get("response_package") or {})
        base_response = str(
            response_package.get("response")
            or response_package.get("text")
            or ""
        ).strip()

        if self._contains_real_crisis(current_message, output):
            return output

        should_rewrite = self._should_use_conversational_writer(
            message=current_message,
            history=history,
            pending=pending,
            base_response=base_response,
            output=output,
        )
        if not should_rewrite:
            return output

        writer_plan = {
            "message": current_message,
            "recent_turns": self._compact_history(history),
            "base_response": base_response,
            "pending_context": pending,
            "conversation_frame": output.get("conversation_frame") or {},
            "conversation_control": output.get("conversation_control") or {},
            "functional_analysis": output.get("functional_analysis") or {},
            "routine_payload": output.get("routine_payload")
            or response_package.get("routine_payload")
            or {},
            "active_profile": {
                "alias": active_profile.get("alias"),
                "role": active_profile.get("role"),
                "age": active_profile.get("age"),
            },
            "must_preserve": self._must_preserve(output),
        }
        llm_result = self.llm_gateway.rewrite_conversational_followup(writer_plan)
        rewritten = str((llm_result or {}).get("response_text") or "").strip()

        if bool((llm_result or {}).get("used_llm")) and rewritten:
            response_package["response"] = rewritten
            response_package["text"] = rewritten
            metadata = dict(response_package.get("response_metadata") or {})
            metadata.update(
                {
                    "conversation_continuity_guard": True,
                    "conversation_writer_used": True,
                    "conversation_writer_provider": (llm_result or {}).get("provider"),
                    "conversation_writer_model": (llm_result or {}).get("model"),
                    "conversation_writer_reason": "contextual_rewrite",
                }
            )
            response_package["response_metadata"] = metadata
            output["response_package"] = response_package
            output["conversation_writer_result"] = llm_result
        else:
            metadata = dict(response_package.get("response_metadata") or {})
            metadata.update(
                {
                    "conversation_continuity_guard": True,
                    "conversation_writer_used": False,
                    "conversation_writer_reason": (llm_result or {}).get("fallback_reason")
                    or "writer_not_available",
                }
            )
            response_package["response_metadata"] = metadata
            output["response_package"] = response_package
            output["conversation_writer_result"] = llm_result

        return output

    def _infer_pending_context(
        self,
        *,
        history: List[Dict[str, Any]],
        previous_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        last_assistant = ""
        last_user = ""
        if history:
            last_turn = history[-1]
            last_assistant = str(last_turn.get("assistant") or "").strip()
            last_user = str(last_turn.get("user") or "").strip()

        normalized_assistant = self._normalize(last_assistant)
        previous_routine = dict(
            previous_result.get("routine_payload")
            or (previous_result.get("response_package") or {}).get("routine_payload")
            or {}
        )

        kind = ""
        if any(marker in normalized_assistant for marker in self.ROUTINE_AUDIENCE_QUESTIONS):
            kind = "routine_audience"

        routine_type = str(previous_routine.get("routine_type") or "").strip()
        if not routine_type:
            routine_type = self._infer_routine_type_from_text(
                f"{last_user}\n{last_assistant}"
            )

        return {
            "kind": kind,
            "last_user": last_user,
            "last_assistant": last_assistant,
            "routine_type": routine_type,
            "routine_payload": previous_routine,
            "question_pending": bool(kind),
        }

    def _answer_routine_audience_followup(
        self,
        *,
        message: str,
        output: Dict[str, Any],
        history: List[Dict[str, Any]],
        previous_result: Dict[str, Any],
        active_profile: Dict[str, Any],
        pending: Dict[str, Any],
        targets: List[str],
    ) -> Dict[str, Any]:
        routine_type = str(pending.get("routine_type") or "morning_organization")
        functional = dict(output.get("functional_analysis") or {})
        if not functional:
            functional = {
                "functional_category": "rutinas_habitos",
                "functional_category_label": "Rutinas y hábitos",
                "functional_category_purpose": (
                    "Organización de actividades cotidianas y seguimiento de objetivos"
                ),
            }

        routines: List[Dict[str, Any]] = []
        for target in targets:
            routine = self.builder.build_routine(
                profile=active_profile,
                state_analysis=dict(output.get("state_analysis") or {}),
                stage_result=dict(output.get("stage_result") or {}),
                memory_payload=dict(output.get("memory_payload") or {}),
                routine_type=routine_type,
                caregiver_capacity=output.get("caregiver_capacity"),
                emotional_intensity=output.get("emotional_intensity"),
                context={
                    "functional_category": functional.get("functional_category")
                    or "rutinas_habitos",
                    "functional_category_label": functional.get("functional_category_label")
                    or "Rutinas y hábitos",
                    "functional_category_purpose": functional.get("functional_category_purpose"),
                    "text_hint": f"{pending.get('last_user', '')}\n{message}",
                    "routine_target": target,
                    "display_mode": "full",
                    "activation_reason": "answer_to_routine_audience_question",
                },
            )
            routine = self._adapt_routine_target(routine, target)
            routines.append(routine)

        intro = self._audience_intro(targets)
        rendered = [render_routine_payload(item, display_mode="full") for item in routines]
        rendered = [item for item in rendered if item]
        final_text = f"{intro}\n\n" + "\n\n".join(rendered)
        final_text = final_text.strip()

        response_package = dict(output.get("response_package") or {})
        response_package["response"] = final_text
        response_package["text"] = final_text
        response_package["routine_generated"] = True
        response_package["routine_payload"] = routines[0] if len(routines) == 1 else {
            "routine_type": routine_type,
            "routine_name": "Rutinas adaptadas por persona",
            "routines": routines,
            "targets": targets,
            "generated_by": "conversation_continuity_guard",
        }
        metadata = dict(response_package.get("response_metadata") or {})
        metadata.update(
            {
                "conversation_continuity_guard": True,
                "answered_pending_question": "routine_audience",
                "routine_targets": targets,
                "routine_generated": True,
                "routine_type": routine_type,
            }
        )
        response_package["response_metadata"] = metadata

        output["response_package"] = response_package
        output["routine_payload"] = response_package["routine_payload"]
        output["functional_analysis"] = functional
        frame = dict(output.get("conversation_frame") or {})
        frame.update(
            {
                "conversation_domain": "rutinas_habitos",
                "support_goal": "adaptar_rutina_por_persona",
                "pending_question": None,
                "routine_targets": targets,
                "last_routine_type": routine_type,
                "last_routine_generated": True,
            }
        )
        output["conversation_frame"] = frame
        return output

    def _adapt_routine_target(self, routine: Dict[str, Any], target: str) -> Dict[str, Any]:
        payload = copy.deepcopy(dict(routine or {}))
        routine_type = str(payload.get("routine_type") or "")

        if routine_type == "morning_organization":
            if target == "self":
                payload["routine_name"] = "Rutina de mañana para ti"
                payload["goal"] = (
                    "hacer tu mañana más predecible y reducir decisiones antes de salir"
                )
                payload["steps"] = [
                    "dejar desde la noche anterior tu ropa, bolso o mochila y lo indispensable",
                    "usar una señal de inicio estable, como una alarma suave o una frase breve",
                    "seguir cuatro bloques visibles: levantarte, asearte, vestirte y desayunar",
                    "concentrarte en un solo bloque a la vez y marcarlo al terminar",
                    "reservar un pequeño margen antes de salir para absorber retrasos sin castigarte",
                ]
            elif target == "child":
                payload["routine_name"] = "Rutina de mañana para tu hijo"
                payload["goal"] = (
                    "acompañar la mañana de tu hijo con menos instrucciones, decisiones y tensión"
                )
                payload["steps"] = [
                    "dejar desde la noche anterior su ropa, mochila y materiales indispensables",
                    "acordar una señal de inicio predecible y amable",
                    "mostrarle una secuencia visual de cuatro bloques: levantarse, asearse, vestirse y desayunar",
                    "darle una sola indicación a la vez y reconocer cada bloque completado",
                    "conservar un margen antes de salir y reducir ruido, luz o cambios de último momento si lo necesita",
                ]
            elif target == "family":
                payload["routine_name"] = "Rutina de mañana familiar"
                payload["goal"] = (
                    "coordinar la salida de casa sin concentrar todas las tareas en una sola persona"
                )
                payload["steps"] = [
                    "preparar desde la noche anterior lo indispensable de cada integrante",
                    "definir una señal común de inicio y un orden estable",
                    "asignar responsabilidades concretas y visibles para cada persona",
                    "usar una sola indicación a la vez y evitar recordatorios simultáneos",
                    "reservar un margen común antes de salir para absorber retrasos",
                ]
        else:
            suffix = {
                "self": " para ti",
                "child": " para tu hijo",
                "family": " familiar",
            }.get(target, "")
            name = str(payload.get("routine_name") or "Rutina sugerida").strip()
            if suffix and suffix.strip().lower() not in name.lower():
                payload["routine_name"] = f"{name}{suffix}"

        payload["routine_target"] = target
        payload["followup_question"] = ""
        payload["generated_by"] = "conversation_continuity_guard"
        return payload

    def _resolve_routine_targets(self, message: str) -> List[str]:
        text = self._normalize(message)
        self_markers = (
            "para mi", "es para mi", "para mí", "yo", "para conmigo", "la necesito yo"
        )
        child_markers = (
            "para mi hijo", "para mi hija", "mi hijo", "mi hija", "para el", "para ella",
            "para mi niño", "para mi nina", "para mi niña",
        )
        family_markers = (
            "para toda la familia", "para la familia", "para todos", "familiar"
        )

        has_self = any(marker in text for marker in map(self._normalize, self_markers))
        has_child = any(marker in text for marker in map(self._normalize, child_markers))
        has_family = any(marker in text for marker in map(self._normalize, family_markers))

        targets: List[str] = []
        if has_self:
            targets.append("self")
        if has_child:
            targets.append("child")
        if has_family:
            targets.append("family")
        return targets

    def _should_use_conversational_writer(
        self,
        *,
        message: str,
        history: List[Dict[str, Any]],
        pending: Dict[str, Any],
        base_response: str,
        output: Dict[str, Any],
    ) -> bool:
        status = self.llm_gateway.get_openai_writer_status()
        if not status.get("enabled"):
            return False

        if pending.get("question_pending"):
            return True

        normalized_response = self._normalize(base_response)
        if any(self._normalize(marker) in normalized_response for marker in self.GENERIC_RESTART_MARKERS):
            return True

        normalized_message = self._normalize(message)
        contextual_markers = (
            "tambien", "también", "igual", "ademas", "además", "los dos", "ambos",
            "para mi", "para mi hijo", "para ella", "para el", "eso", "esa", "lo mismo",
            "si", "sí", "no", "mejor", "entonces", "y ahora",
        )
        is_short = len(normalized_message.split()) <= 24
        if history and is_short and any(self._normalize(marker) in normalized_message for marker in contextual_markers):
            return True

        return False

    def _contains_real_crisis(self, message: str, output: Dict[str, Any]) -> bool:
        text = self._normalize(message)
        functional = dict(output.get("functional_analysis") or {})
        if functional.get("crisis_present"):
            return True
        return any(self._normalize(marker) in text for marker in self.CRISIS_MARKERS)

    def _must_preserve(self, output: Dict[str, Any]) -> Dict[str, Any]:
        response_package = dict(output.get("response_package") or {})
        routine = output.get("routine_payload") or response_package.get("routine_payload") or {}
        return {
            "routine": routine,
            "detected_category": output.get("detected_category"),
            "primary_state": output.get("primary_state"),
            "safety_flags": output.get("safety_flags") or {},
        }

    def _compact_history(self, history: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        result: List[Dict[str, str]] = []
        for item in history[-6:]:
            result.append(
                {
                    "user": str(item.get("user") or "")[:800],
                    "assistant": str(item.get("assistant") or "")[:1400],
                }
            )
        return result

    def _infer_routine_type_from_text(self, text: str) -> str:
        normalized = self._normalize(text)
        if any(token in normalized for token in ("manana", "mañana", "antes de salir", "levantarse")):
            return "morning_organization"
        if any(token in normalized for token in ("escuela", "tarea", "estudio")):
            return "school_support"
        if any(token in normalized for token in ("familia", "responsabilidades", "hogar")):
            return "family_organization"
        if any(token in normalized for token in ("sueno", "sueño", "dormir", "noche")):
            return "sleep"
        return "daily_habits"

    def _audience_intro(self, targets: List[str]) -> str:
        if targets == ["self"]:
            return "Claro. La adapto para ti y la dejamos sencilla de sostener."
        if targets == ["child"]:
            return "Claro. La adapto para tu hijo, con menos instrucciones y más apoyos visibles."
        if targets == ["family"]:
            return "Claro. La convierto en una rutina familiar para repartir la carga."
        if "self" in targets and "child" in targets:
            return (
                "Claro. Te dejo dos versiones: una para ti y otra para tu hijo. "
                "Comparten la misma estructura, pero cambia la forma de acompañar cada paso."
            )
        return "Claro. La adapto según lo que acabas de precisar."

    def _normalize(self, value: Any) -> str:
        text = unicodedata.normalize("NFKD", str(value or "").strip().lower())
        text = "".join(char for char in text if not unicodedata.combining(char))
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        return re.sub(r"\s+", " ", text).strip()
