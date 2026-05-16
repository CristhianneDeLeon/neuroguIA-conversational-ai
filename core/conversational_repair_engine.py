# -*- coding: utf-8 -*-
from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Optional


DOMAIN_TO_ROUTE = {
    "crisis_activa": "crisis",
    "ansiedad_cognitiva": "ansiedad",
    "sueno_regulacion": "sueno",
    "disfuncion_ejecutiva": "bloqueo_ejecutivo",
    "apoyo_infancia_neurodivergente": "apoyo_infancia_neurodivergente",
    "sobrecarga_cuidador": "sobrecarga_cuidador",
    "apoyo_general": "meta",
}


def _normalize(text: Optional[str]) -> str:
    normalized = unicodedata.normalize("NFKD", str(text or "").strip().lower())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    return " ".join(normalized.split())


def _has(normalized: str, phrases: List[str]) -> bool:
    return any(_normalize(phrase) in normalized for phrase in phrases)


def _previous_route(previous_frame: Optional[Dict[str, Any]]) -> Optional[str]:
    frame = previous_frame or {}
    support_state = dict(frame.get("support_flow_state") or {})
    for candidate in [
        frame.get("stable_demo_route_id"),
        frame.get("route_id"),
        support_state.get("route_id"),
        support_state.get("active_route_id"),
        frame.get("active_route_id"),
        DOMAIN_TO_ROUTE.get(str(frame.get("conversation_domain") or "").strip()),
    ]:
        route = str(candidate or "").strip()
        if route:
            return route
    return None


def _previous_subject(previous_frame: Optional[Dict[str, Any]]) -> Optional[str]:
    frame = previous_frame or {}
    support_state = dict(frame.get("support_flow_state") or {})
    care_context = dict(frame.get("care_context") or {})
    for candidate in [
        frame.get("support_subject"),
        support_state.get("support_subject"),
        care_context.get("support_subject"),
    ]:
        subject = str(candidate or "").strip()
        if subject:
            return subject
    return None


def _previous_intervention(previous_frame: Optional[Dict[str, Any]]) -> Optional[str]:
    frame = previous_frame or {}
    support_state = dict(frame.get("support_flow_state") or {})
    for candidate in [
        frame.get("last_intervention_id"),
        frame.get("stable_demo_intervention_id"),
        support_state.get("last_intervention_id"),
    ]:
        intervention = str(candidate or "").strip()
        if intervention:
            return intervention
    return None


def _empty(notes: Optional[List[str]] = None) -> Dict[str, Any]:
    return {
        "handled": False,
        "repair_type": "",
        "response_text": "",
        "route_id": None,
        "support_subject": None,
        "do_not_advance_step": True,
        "mark_strategy_exhausted": None,
        "notes": notes or [],
    }


def _handled(
    *,
    repair_type: str,
    response_text: str,
    route_id: Optional[str],
    support_subject: Optional[str],
    mark_strategy_exhausted: Optional[str] = None,
    notes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return {
        "handled": True,
        "repair_type": repair_type,
        "response_text": response_text,
        "route_id": route_id,
        "support_subject": support_subject,
        "do_not_advance_step": True,
        "mark_strategy_exhausted": mark_strategy_exhausted,
        "notes": notes or [],
    }


def resolve_conversational_repair(
    message: str,
    previous_frame: Optional[Dict[str, Any]],
    recent_messages: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    del recent_messages

    normalized = _normalize(message)
    if not normalized:
        return _empty(["empty_message"])

    route_id = _previous_route(previous_frame)
    support_subject = _previous_subject(previous_frame)
    previous_intervention = _previous_intervention(previous_frame)
    notes: List[str] = []

    child_context = _has(
        normalized,
        [
            "mi hijo",
            "mi hija",
            "mis hijos",
            "mis hijas",
            "hijo",
            "hija",
            "adolescente",
            "adolescentes",
        ],
    )

    if _has(normalized, ["no es sobrepensamiento"]) and _has(normalized, ["sueno", "sue o", "dormir"]):
        return _handled(
            repair_type="context_correction",
            response_text=(
                "Tienes razon. Me centro en sueno. No vamos a trabajar pensamientos ahora; "
                "vamos con una medida concreta para bajar el cuerpo y el entorno."
            ),
            route_id="sueno",
            support_subject=support_subject or ("teen_child" if child_context else "self"),
            notes=["overthinking_negated", "route_corrected_to_sleep"],
        )

    if _has(normalized, ["no soy yo es mi hijo", "no soy yo es mi hija", "no es mio es mi hijo", "no es mio es mi hija"]):
        corrected_route = "crisis" if "crisis" in normalized else "apoyo_infancia_neurodivergente"
        return _handled(
            repair_type="context_correction",
            response_text=(
                "Tienes razon, me centro en tu hijo. No lo llevo a ti: dime solo si ahora hay riesgo fisico "
                "o si lo que necesita es bajar estimulos y palabras."
            ),
            route_id=corrected_route,
            support_subject="child",
            notes=["subject_corrected_to_child"],
        )

    if _has(normalized, ["la crisis es mia", "la crisis es mía", "es mi crisis", "la crisis soy yo"]):
        return _handled(
            repair_type="context_correction",
            response_text=(
                "Gracias por aclararlo. Entonces me centro en ti: baja una sola demanda alrededor y quedate con pocas palabras. "
                "Si hay riesgo para ti, busca apoyo presencial ahora."
            ),
            route_id="crisis",
            support_subject="self",
            notes=["subject_corrected_to_self_crisis"],
        )

    if _has(normalized, ["la crisis es de mi hijo", "la crisis es de mi hija", "crisis de mi hijo", "crisis de mi hija"]):
        return _handled(
            repair_type="context_correction",
            response_text=(
                "Gracias por aclararlo. Me centro en tu hijo: ahora la prioridad es seguridad y baja demanda, no razonar mucho. "
                "Baja ruido o gente cerca, manten distancia segura y usa pocas palabras."
            ),
            route_id="crisis",
            support_subject="child",
            notes=["subject_corrected_to_child_crisis"],
        )

    if _has(normalized, ["lo escribo aqui", "la escribo aqui", "las escribo aqui", "escribo aqui"]):
        return _handled(
            repair_type="clarification_request",
            response_text="Si, puedes escribirlo aqui conmigo. No tiene que estar perfecto; una sola frase basta.",
            route_id=route_id,
            support_subject=support_subject,
            notes=["write_here_question"],
        )

    if _has(normalized, ["a quien le digo eso", "a quien se lo digo", "a quien le digo", "a quien digo eso"]):
        return _handled(
            repair_type="clarification_request",
            response_text=(
                "No tienes que decirselo a otra persona si no aplica. Era una frase para bajar el momento. "
                "Quedate conmigo: dime si ahora estas en un lugar seguro."
            ),
            route_id=route_id,
            support_subject=support_subject,
            notes=["recipient_question"],
        )

    if _has(normalized, ["en donde", "donde lo", "donde la", "donde las", "donde escribo", "en que lo escribo"]):
        return _handled(
            repair_type="clarification_request",
            response_text="Puede ser aqui mismo, o en una nota cualquiera. Si no tienes donde escribir, dilo en voz baja y con eso basta.",
            route_id=route_id,
            support_subject=support_subject,
            notes=["where_question"],
        )

    if _has(normalized, ["no tengo nada donde escribir", "no tengo donde escribir", "no tengo en que escribir", "no tengo nada que abrir"]):
        return _handled(
            repair_type="clarification_request",
            response_text="Entonces no dependemos de escribir. Di en voz baja el nombre de la tarea o del peso de ahora, y elegimos solo el primer movimiento.",
            route_id=route_id,
            support_subject=support_subject,
            notes=["no_materials"],
        )

    if _has(normalized, ["como hago eso", "como lo hago", "como hago", "dime como", "explicamelo mejor", "explicame mejor", "paso a paso"]) and not _has(
        normalized, ["meditar", "meditacion"]
    ):
        return _handled(
            repair_type="guidance_request",
            response_text=(
                "Si, lo hacemos paso a paso. Primero: nombra solo que toca. Segundo: elige una accion minima. "
                "Tercero: hazla durante un minuto, sin revisar si quedo bien."
            ),
            route_id=route_id,
            support_subject=support_subject,
            notes=["step_by_step_requested"],
        )

    if _has(normalized, ["no se meditar", "no se como meditar", "dime como meditar"]) or (
        _has(normalized, ["dime como"]) and _has(normalized, ["meditar", "meditacion"])
    ):
        return _handled(
            repair_type="guidance_request",
            response_text=(
                "No tienes que saber meditar. Hagamoslo muy simple: mira un punto fijo, suelta el aire lento una vez "
                "y repite por dentro: 'ahora solo estoy aqui'. Con eso basta para empezar."
            ),
            route_id=route_id or "ansiedad",
            support_subject=support_subject,
            notes=["meditation_guidance_requested"],
        )

    if _has(normalized, ["me puedes ayudar tu", "me ayudas tu", "puedes ayudarme tu", "quedate conmigo", "no tengo a nadie"]):
        return _handled(
            repair_type="direct_containment_request",
            response_text="Si. Me quedo contigo aqui. No tienes que resolver todo en este minuto; vamos paso a paso.",
            route_id=route_id,
            support_subject=support_subject,
            notes=["direct_containment_requested"],
        )

    if _has(normalized, ["sigues repitiendo", "estas repitiendo", "repites", "eso ya me lo dijiste", "ya me lo dijiste", "no me estas ayudando", "no me ayudas"]):
        return _handled(
            repair_type="frustration_or_repetition",
            response_text=(
                "Tienes razon. No te esta ayudando que repita lo mismo. Cambio de forma: dime si quieres "
                "una opcion corporal, una opcion de entorno o una opcion de decision."
            ),
            route_id=route_id,
            support_subject=support_subject,
            mark_strategy_exhausted=previous_intervention,
            notes=["repetition_or_frustration_detected"],
        )

    if _has(normalized, ["eso no me sirve", "no me sirve", "eso no funciono", "eso no funciona", "eso ya no funciono", "ya lo intente", "ya lo hice y no"]):
        if route_id == "sueno":
            response = (
                "Tienes razon, no insistimos con lo mismo. Cambio de forma sin salirnos de sueno: "
                "elige una sola cosa del entorno, como pantalla fuera, luz baja o menos conversacion intensa."
            )
        elif route_id == "crisis":
            response = (
                "Tienes razon, si eso no ayudo y sigue subiendo, ahora no toca explicar mas: "
                "mas distancia, menos palabras, objetos fuera y apoyo presencial si hay riesgo."
            )
        else:
            response = "Tienes razon, no insistimos con lo mismo. Cambio de forma: bajamos la exigencia y elegimos una accion mas pequena."
        return _handled(
            repair_type="strategy_rejection",
            response_text=response,
            route_id=route_id,
            support_subject=support_subject,
            mark_strategy_exhausted=previous_intervention,
            notes=["strategy_rejected"],
        )

    return _empty(["no_repair_match"])
