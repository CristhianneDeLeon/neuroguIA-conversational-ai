from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Optional

from core.intent_router import IntentRouter
from core.category_router import CategoryRouter
from core.state_guardian import StateGuardian
from core.decision_engine import DecisionEngine
from core.confidence_engine import ConfidenceEngine
from core.fallback_manager import FallbackManager
from core.response_builder import ResponseBuilder
from core.response_curator import ResponseCurator
from core.routine_builder import RoutineBuilder
from core.conversation_stages import ConversationStages
from core.conversational_intent import ConversationalIntentBuilder
from core.conversational_repair_engine import resolve_conversational_repair
from core.exceptionality_mapper import ExceptionalityMapper
from core.support_playbooks import INTERVENTION_BANK
from core.support_flow_engine import SupportFlowEngine
from core.llm_gateway import LLMGateway
from core.learning_engine import LearningEngine
from core.expert_mode_adapter import ExpertModeAdapter

from memory.case_memory import CaseMemory
from memory.conversation_curation import ConversationCuration
from memory.response_memory import ResponseMemory
from memory.profile_manager import ProfileManager
from memory.user_context_memory import UserContextMemory


STABLE_DEMO_STEPS: Dict[str, List[str]] = {
    route_id: list(interventions.values())
    for route_id, interventions in INTERVENTION_BANK.items()
}

STABLE_DEMO_ROUTE_TO_DOMAIN: Dict[str, str] = {
    "crisis": "crisis_activa",
    "ansiedad": "ansiedad_cognitiva",
    "sueno": "sueno_regulacion",
    "bloqueo_ejecutivo": "disfuncion_ejecutiva",
    "apoyo_infancia_neurodivergente": "apoyo_infancia_neurodivergente",
    "sobrecarga_cuidador": "sobrecarga_cuidador",
    "medicacion": "apoyo_general",
    "meta": "apoyo_general",
}

STABLE_DEMO_DOMAIN_TO_ROUTE: Dict[str, str] = {
    value: key for key, value in STABLE_DEMO_ROUTE_TO_DOMAIN.items()
}

STABLE_DEMO_GOALS: Dict[str, str] = {
    "crisis": "contain_and_protect",
    "ansiedad": "reduce_mental_overload",
    "sueno": "stabilize_sleep_transition",
    "bloqueo_ejecutivo": "enable_first_step",
    "apoyo_infancia_neurodivergente": "support_neurodivergent_child",
    "sobrecarga_cuidador": "support_caregiver_capacity",
    "medicacion": "safe_medication_boundary",
    "meta": "answer_directly",
}

STABLE_DEMO_PHASES: Dict[str, str] = {
    "crisis": "stable_demo_crisis",
    "ansiedad": "stable_demo_ansiedad",
    "sueno": "stable_demo_sueno",
    "bloqueo_ejecutivo": "stable_demo_bloqueo",
    "apoyo_infancia_neurodivergente": "stable_demo_infancia",
    "sobrecarga_cuidador": "stable_demo_cuidador",
    "medicacion": "stable_demo_medicacion",
    "meta": "stable_demo_meta",
}

STABLE_DEMO_RECENT_WINDOW = 10
STABLE_DEMO_RECENT_AVOID_WINDOW = 8


def _stable_demo_normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(text or "").strip().lower())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    return " ".join(normalized.split())


def _stable_demo_has(normalized: str, phrases: List[str]) -> bool:
    return any(_stable_demo_normalize(phrase) in normalized for phrase in phrases)


STABLE_DEMO_OVERTHINKING_BLOCK_TURNS = 5


def _stable_demo_explicit_overthinking_marker(normalized: str) -> bool:
    return _stable_demo_has(
        normalized,
        [
            "sobrepensar",
            "sobrepensamiento",
            "sobrepiensa",
            "pensamientos intrusivos",
            "pensamiento intrusivo",
            "pensamientos repetitivos",
            "pensamiento repetitivo",
            "rumiacion",
            "rumiando",
            "le da vueltas",
            "le da muchas vueltas",
            "mente no para",
            "la mente no para",
            "mente no se apaga",
            "la mente no se apaga",
        ],
    )


def _stable_demo_negates_overthinking(normalized: str) -> bool:
    return _stable_demo_has(
        normalized,
        [
            "no es sobrepensamiento",
            "no es sobrepensar",
            "no tiene que ver con sobrepensamiento",
            "no tiene que ver con sobrepensar",
            "no es una crisis de sobrepensamiento",
        ],
    )


def _stable_demo_overthinking_block_remaining(previous_frame: Optional[Dict[str, Any]]) -> int:
    frame = previous_frame or {}
    support_state = dict(frame.get("support_flow_state") or {})
    care_context = dict(frame.get("care_context") or {})
    for source in (frame, support_state, care_context):
        try:
            return max(int(source.get("overthinking_block_turns", 0) or 0), 0)
        except (TypeError, ValueError):
            continue
    return 0


def _stable_demo_recent_context(chat_history: Optional[List[Dict[str, Any]]]) -> List[Dict[str, str]]:
    recent_context: List[Dict[str, str]] = []
    for turn in (chat_history or [])[-5:]:
        if not isinstance(turn, dict):
            continue
        user_text = str(turn.get("user") or "").strip()
        assistant_text = str(turn.get("assistant") or "").strip()
        if not user_text and not assistant_text:
            continue
        recent_context.append(
            {
                "user": user_text[:500],
                "assistant": assistant_text[:700],
            }
        )
    return recent_context


def _stable_demo_variant_offset(seed_text: str, modulo: int) -> int:
    if modulo <= 1:
        return 0
    weighted = sum((index + 1) * ord(char) for index, char in enumerate(str(seed_text or "")))
    return weighted % modulo


def _stable_demo_quick_button_message(normalized: str) -> bool:
    return _stable_demo_has(
        normalized,
        [
            "me siento muy ansiosa o y no se como calmarme",
            "me siento muy ansiosa y no se como calmarme",
            "me siento muy ansioso y no se como calmarme",
            "esta ocurriendo una crisis y necesito ayuda para manejarla",
            "hay problemas de sueno y eso esta afectando mucho",
            "hay problemas de sue o y eso esta afectando mucho",
            "no puedo organizarme ni empezar lo que tengo pendiente",
        ],
    )


def _stable_demo_anxiety_crisis_marker(normalized: str) -> bool:
    return _stable_demo_has(
        normalized,
        [
            "crisis de ansiedad",
            "ataque de ansiedad",
            "ansiedad fuerte",
            "ansiedad muy fuerte",
            "ataque de panico",
            "crisis ansiosa",
        ],
    )


def _stable_demo_timer_done_marker(normalized: str) -> bool:
    return _stable_demo_has(
        normalized,
        [
            "ya termino el timer",
            "ya termin el timer",
            "ya termino el temporizador",
            "ya termin el temporizador",
            "ya termino",
            "ya termin",
            "ya termino el tiempo",
            "ya termin el tiempo",
            "ya paso el tiempo",
            "ya pasaron los dos minutos",
            "ya pasaron 2 minutos",
            "se acabo el timer",
            "se acabo el temporizador",
        ],
    )


def _stable_demo_llm_block_reason(
    llm_result: Optional[Dict[str, Any]],
    llm_curated_payload: Optional[Dict[str, Any]],
    default_reason: Optional[str] = None,
) -> Optional[str]:
    if llm_result and llm_result.get("fallback_reason"):
        return str(llm_result.get("fallback_reason") or "").strip() or default_reason
    notes = list((llm_curated_payload or {}).get("curation_notes", []) or [])
    for note in notes:
        text = str(note or "").strip()
        if text.startswith("rejected="):
            return text.split("=", 1)[1].strip() or default_reason
    if llm_curated_payload and not bool(llm_curated_payload.get("approved")):
        return "curator_rejected"
    return default_reason


def _stable_demo_is_child_sleep_plan(
    route_id: str,
    support_subject: str,
    intervention_id: Optional[str],
    normalized: str,
) -> bool:
    child_sleep_interventions = {
        "sueno_infancia",
        "teen_sueno_activacion_cognitiva",
        "teen_rutina_baja_demanda",
        "teen_descompresion_sensorial",
        "teen_ansiedad_anticipatoria",
    }
    return (
        route_id == "apoyo_infancia_neurodivergente"
        and support_subject in {"child", "teen_child"}
        and (
            _stable_demo_has_sleep_marker(normalized)
            or str(intervention_id or "").strip() in child_sleep_interventions
        )
    )


def _stable_demo_behavioral_contract(
    route_id: str,
    support_subject: str,
    support_mode: str,
    intervention_id: Optional[str],
    normalized: str,
) -> Dict[str, Any]:
    support_mode = str(support_mode or "").strip()

    objective = STABLE_DEMO_GOALS.get(route_id, "clarify_and_support")
    allowed_actions: List[str] = []
    forbidden_actions: List[str] = []
    safety_boundary = "Mantener la ruta local ya decidida; no diagnosticar ni abrir dominios nuevos."

    if route_id == "ansiedad":
        objective = "responder al turno concreto mientras baja la carga mental"
        allowed_actions = [
            "respiraci\u00f3n",
            "grounding",
            "descarga mental",
            "decisi\u00f3n simple",
        ]
        forbidden_actions = [
            "crisis de hijo",
            "sue\u00f1o",
            "medicaci\u00f3n",
            "diagn\u00f3stico",
        ]
        safety_boundary = "No convertir ansiedad en crisis, sue\u00f1o o medicaci\u00f3n; responder primero a la pregunta concreta."
        if support_mode == "acute" or _stable_demo_anxiety_crisis_marker(normalized):
            objective = "contener una crisis de ansiedad como ansiedad aguda, sin convertirla en crisis externa"
            allowed_actions = [
                "respiraci\u00f3n simple",
                "orientaci\u00f3n al presente",
                "bajar demanda",
                "acompa\u00f1amiento directo",
            ]
            forbidden_actions.extend(
                [
                    "distancia segura",
                    "retirar objetos",
                    "no invadir espacio",
                    "crisis externa",
                    "crisis de hijo",
                ]
            )
            safety_boundary = "Crisis de ansiedad = ansiedad aguda; no usar guion de crisis externa ni agresion."
    elif route_id == "crisis":
        objective = "contener y proteger con acciones inmediatas y pocas palabras"
        allowed_actions = [
            "seguridad",
            "bajar est\u00edmulos",
            "frase breve",
            "distancia segura",
            "retirar objetos",
            "pedir ayuda si hay riesgo",
        ]
        forbidden_actions = [
            "sobrepensamiento",
            "tarea",
            "sue\u00f1o",
            "meditaci\u00f3n larga",
            "grounding de ansiedad",
        ]
        safety_boundary = "Si hay riesgo f\u00edsico, priorizar seguridad del entorno, distancia segura y ayuda real."
    elif route_id == "sueno" or _stable_demo_is_child_sleep_plan(
        route_id=route_id,
        support_subject=support_subject,
        intervention_id=intervention_id,
        normalized=normalized,
    ):
        objective = "preparar el cuerpo para dormir sin pelea ni sobreexplicaci\u00f3n"
        allowed_actions = [
            "rutina de bajada",
            "baja demanda",
            "pantallas",
            "luz",
            "pensamientos intrusivos",
            "acuerdo breve",
        ]
        forbidden_actions = [
            "crisis",
            "distancia segura",
            "no discutir",
            "grounding de ansiedad de la madre",
            "tarea",
            "sobrepensamiento",
            "escribir preocupaciones por defecto",
        ]
        safety_boundary = "Mantener sue\u00f1o preventivo o regulaci\u00f3n de sue\u00f1o; no meter crisis ni ansiedad como dominio."
    elif route_id == "bloqueo_ejecutivo":
        objective = "hacer posible el primer movimiento sin exigir claridad total"
        allowed_actions = [
            "nombrar la tarea",
            "abrir material si existe",
            "hoja o nota",
            "t\u00edtulo feo",
            "temporizador breve",
            "primer pedacito",
        ]
        forbidden_actions = [
            "crisis",
            "sue\u00f1o",
            "medicaci\u00f3n",
            "grounding de ansiedad",
            "diagn\u00f3stico",
        ]
        safety_boundary = "No insistir en un archivo si la persona dice que no hay archivo; bajar la tarea a una entrada visible."
    elif route_id == "apoyo_infancia_neurodivergente":
        objective = "acompa\u00f1ar al hijo o hija neurodivergente sin centrar el problema en la madre"
        allowed_actions = [
            "corregulaci\u00f3n",
            "bajar est\u00edmulos",
            "frases cortas",
            "rutina visual",
            "una preocupaci\u00f3n",
            "anticipaci\u00f3n breve",
        ]
        forbidden_actions = [
            "grounding de ansiedad de la madre",
            "tarea",
            "medicaci\u00f3n",
            "diagn\u00f3stico",
            "sue\u00f1o si el turno no lo pide",
        ]
        safety_boundary = "Centrar la ayuda en el ni\u00f1o, ni\u00f1a o adolescente; si aparece riesgo f\u00edsico, la ruta local debe ser crisis."
    elif route_id == "sobrecarga_cuidador":
        objective = "bajar carga del cuidador con una acci\u00f3n posible y compasiva"
        allowed_actions = [
            "validaci\u00f3n",
            "bajar carga",
            "pedir ayuda concreta",
            "una prioridad",
            "pausa sin culpa",
        ]
        forbidden_actions = [
            "grounding de ansiedad",
            "tarea acad\u00e9mica",
            "sue\u00f1o",
            "medicaci\u00f3n",
            "diagn\u00f3stico",
        ]
        safety_boundary = "No convertir sobrecarga de cuidado en tarea, sue\u00f1o o medicaci\u00f3n."
    elif route_id == "medicacion":
        objective = "poner un l\u00edmite seguro sobre medicamentos y ofrecer alternativa no farmacol\u00f3gica"
        allowed_actions = [
            "l\u00edmite m\u00e9dico",
            "consulta profesional",
            "medida no farmacol\u00f3gica",
            "seguridad",
        ]
        forbidden_actions = [
            "recomendar medicamentos",
            "dosis",
            "nombres de f\u00e1rmacos",
            "diagn\u00f3stico",
        ]
        safety_boundary = "Nunca recomendar medicamentos, dosis ni f\u00e1rmacos; redirigir a profesional de salud."
    elif route_id == "meta":
        objective = "responder la pregunta sobre NeuroGuIA de forma directa y humana"
        allowed_actions = ["respuesta directa", "presencia", "claridad"]
        forbidden_actions = ["diagn\u00f3stico", "medicaci\u00f3n", "cambiar a crisis sin se\u00f1al local"]
        safety_boundary = "Responder solo la pregunta meta sin abrir intervenci\u00f3n cl\u00ednica innecesaria."

    return {
        "objective": objective,
        "allowed_actions": allowed_actions,
        "forbidden_actions": forbidden_actions,
        "safety_boundary": safety_boundary,
    }


def _stable_demo_build_behavioral_plan(
    *,
    route_id: str,
    support_subject: str,
    support_mode: str,
    intervention_id: Optional[str],
    response_text: str,
    message: str,
    previous_frame: Optional[Dict[str, Any]],
    chat_history: Optional[List[Dict[str, Any]]],
    turn_family: str,
    step_index: int,
) -> Dict[str, Any]:
    normalized = _stable_demo_normalize(message)
    contract = _stable_demo_behavioral_contract(
        route_id=route_id,
        support_subject=support_subject,
        support_mode=support_mode,
        intervention_id=intervention_id,
        normalized=normalized,
    )
    previous_assistant = ""
    if previous_frame:
        previous_assistant = str(
            previous_frame.get("last_guided_action")
            or previous_frame.get("last_action_instruction")
            or ""
        ).strip()

    return {
        "route_id": route_id,
        "support_subject": support_subject,
        "support_mode": support_mode,
        "intervention_id": intervention_id,
        "objective": contract.get("objective"),
        "base_guidance": response_text,
        "recent_user_message": message,
        "recent_context": _stable_demo_recent_context(chat_history),
        "allowed_actions": list(contract.get("allowed_actions") or []),
        "forbidden_actions": list(contract.get("forbidden_actions") or []),
        "safety_boundary": contract.get("safety_boundary"),
        "tone": "c\u00e1lido, claro, contenedor, casi maternal",
        "turn_family": turn_family,
        "step_index": step_index,
        "current_turn_task": "Responder al ultimo mensaje real del usuario antes de cualquier guia de fondo.",
        "previous_assistant_guidance": previous_assistant,
    }


def _stable_demo_previous_route(previous_frame: Optional[Dict[str, Any]]) -> Optional[str]:
    frame = previous_frame or {}
    support_state = dict(frame.get("support_flow_state") or {})
    candidates = [
        frame.get("stable_demo_route_id"),
        frame.get("route_id"),
        support_state.get("route_id"),
        support_state.get("active_route_id"),
        frame.get("active_route_id"),
        STABLE_DEMO_DOMAIN_TO_ROUTE.get(str(frame.get("conversation_domain") or "").strip()),
    ]
    for candidate in candidates:
        route = str(candidate or "").strip()
        if route in STABLE_DEMO_ROUTE_TO_DOMAIN:
            return route
    return None


def _stable_demo_previous_step(previous_frame: Optional[Dict[str, Any]]) -> int:
    frame = previous_frame or {}
    support_state = dict(frame.get("support_flow_state") or {})
    for key_source, key in [
        (frame, "stable_demo_step_index"),
        (frame, "step_index"),
        (support_state, "step_index"),
    ]:
        try:
            return max(int(key_source.get(key, 0) or 0), 0)
        except (TypeError, ValueError):
            continue
    return 0


def _stable_demo_used_interventions(previous_frame: Optional[Dict[str, Any]]) -> Dict[str, List[str]]:
    frame = previous_frame or {}
    support_state = dict(frame.get("support_flow_state") or {})
    raw = frame.get("used_interventions")
    if not isinstance(raw, dict):
        raw = support_state.get("used_interventions")
    if not isinstance(raw, dict):
        return {}

    used: Dict[str, List[str]] = {}
    for route_id, interventions in raw.items():
        route = str(route_id or "").strip()
        if route not in INTERVENTION_BANK:
            continue
        seen: List[str] = []
        for intervention_id in interventions or []:
            key = str(intervention_id or "").strip()
            if key in INTERVENTION_BANK[route] and key not in seen:
                seen.append(key)
        if seen:
            used[route] = seen
    return used


def _stable_demo_recent_interventions(previous_frame: Optional[Dict[str, Any]]) -> Dict[str, List[str]]:
    frame = previous_frame or {}
    support_state = dict(frame.get("support_flow_state") or {})
    raw = frame.get("used_interventions_last_10")
    if not isinstance(raw, dict):
        raw = support_state.get("used_interventions_last_10")
    if not isinstance(raw, dict):
        raw = frame.get("used_interventions")
    if not isinstance(raw, dict):
        raw = support_state.get("used_interventions")
    if not isinstance(raw, dict):
        return {}

    recent: Dict[str, List[str]] = {}
    for route_id, interventions in raw.items():
        route = str(route_id or "").strip()
        if route not in INTERVENTION_BANK:
            continue
        cleaned: List[str] = []
        for intervention_id in interventions or []:
            key = str(intervention_id or "").strip()
            if key in INTERVENTION_BANK[route]:
                cleaned.append(key)
        if cleaned:
            recent[route] = cleaned[-STABLE_DEMO_RECENT_WINDOW:]
    return recent


def _stable_demo_exhausted_strategies(previous_frame: Optional[Dict[str, Any]]) -> Dict[str, List[str]]:
    frame = previous_frame or {}
    support_state = dict(frame.get("support_flow_state") or {})
    raw = frame.get("exhausted_strategies")
    if not isinstance(raw, dict):
        raw = support_state.get("exhausted_strategies")
    if not isinstance(raw, dict):
        return {}

    exhausted: Dict[str, List[str]] = {}
    for route_id, strategies in raw.items():
        route = str(route_id or "").strip()
        if not route:
            continue
        cleaned: List[str] = []
        for strategy in strategies or []:
            key = str(strategy or "").strip()
            if key and key not in cleaned:
                cleaned.append(key)
        if cleaned:
            exhausted[route] = cleaned
    return exhausted


def _stable_demo_add_exhausted_strategy(
    previous_frame: Optional[Dict[str, Any]],
    route_id: Optional[str],
    strategy_id: Optional[str],
) -> Dict[str, List[str]]:
    exhausted = _stable_demo_exhausted_strategies(previous_frame)
    route = str(route_id or "").strip()
    strategy = str(strategy_id or "").strip()
    if not route or not strategy:
        return exhausted
    route_exhausted = list(exhausted.get(route, []) or [])
    if strategy not in route_exhausted:
        route_exhausted.append(strategy)
    exhausted[route] = route_exhausted
    return exhausted


def _stable_demo_update_recent_interventions(
    recent_interventions: Dict[str, List[str]],
    route_id: str,
    intervention_id: Optional[str],
) -> Dict[str, List[str]]:
    next_recent: Dict[str, List[str]] = {}
    for route, interventions in (recent_interventions or {}).items():
        route_key = str(route or "").strip()
        if route_key not in INTERVENTION_BANK:
            continue
        cleaned = [
            str(item or "").strip()
            for item in (interventions or [])
            if str(item or "").strip() in INTERVENTION_BANK[route_key]
        ]
        if cleaned:
            next_recent[route_key] = cleaned[-STABLE_DEMO_RECENT_WINDOW:]

    route = str(route_id or "").strip()
    selected = str(intervention_id or "").strip()
    if route in INTERVENTION_BANK and selected in INTERVENTION_BANK[route]:
        route_recent = list(next_recent.get(route, []) or [])
        route_recent.append(selected)
        next_recent[route] = route_recent[-STABLE_DEMO_RECENT_WINDOW:]

    return next_recent


def _stable_demo_previous_intervention(previous_frame: Optional[Dict[str, Any]]) -> Optional[str]:
    frame = previous_frame or {}
    support_state = dict(frame.get("support_flow_state") or {})
    for candidate in [
        frame.get("last_intervention_id"),
        frame.get("stable_demo_intervention_id"),
        support_state.get("last_intervention_id"),
    ]:
        key = str(candidate or "").strip()
        if key:
            return key
    return None


def _stable_demo_previous_subject(previous_frame: Optional[Dict[str, Any]]) -> str:
    frame = previous_frame or {}
    support_state = dict(frame.get("support_flow_state") or {})
    care_context = dict(frame.get("care_context") or {})
    for candidate in [
        frame.get("support_subject"),
        support_state.get("support_subject"),
        care_context.get("support_subject"),
    ]:
        subject = str(candidate or "").strip()
        if subject in {"self", "child", "teen_child", "caregiver", "partner", "family", "unknown"}:
            return subject
    return "unknown"


def _stable_demo_previous_mode(previous_frame: Optional[Dict[str, Any]]) -> str:
    frame = previous_frame or {}
    support_state = dict(frame.get("support_flow_state") or {})
    care_context = dict(frame.get("care_context") or {})
    for candidate in [
        frame.get("support_mode"),
        support_state.get("support_mode"),
        care_context.get("support_mode"),
    ]:
        mode = str(candidate or "").strip()
        if mode in {"acute", "preventive", "supportive", "co_regulation", "reflection"}:
            return mode
    return "supportive"


def _stable_demo_repeat_complaint(normalized: str) -> bool:
    return _stable_demo_has(
        normalized,
        [
            "eso ya me lo dijiste",
            "eso ya lo dijiste",
            "ya me lo dijiste",
            "sigues repitiendo",
            "estas repitiendo",
            "estás repitiendo",
            "repites",
            "otra vez",
        ],
    )


def _stable_demo_wants_another(normalized: str) -> bool:
    return _stable_demo_has(
        normalized,
        [
            "que mas",
            "qué más",
            "y luego",
            "despues",
            "despues que",
            "otra cosa",
            "no me sirve",
            "eso no me sirve",
            "que sigue",
            "qué sigue",
            "ahora que",
            "ahora qué",
            "dame opciones",
            "no se como",
            "no sé cómo",
        ],
    )


def _stable_demo_wants_pause(normalized: str) -> bool:
    return _stable_demo_has(
        normalized,
        [
            "paramos aqui",
            "paremos aqui",
            "hasta aqui",
            "aqui paro",
            "ya estuvo",
            "por ahora ya",
            "quiero parar",
            "quiero pausar",
            "dejemoslo aqui",
            "dejemoslo por ahora",
        ],
    )


def _stable_demo_has_sleep_marker(normalized: str) -> bool:
    return _stable_demo_has(
        normalized,
        [
            "sueno",
            "sue o",
            "dormir",
            "duermo",
            "duerme",
            "duermen",
            "desvelo",
            "insomnio",
            "no descanso",
            "acostarse",
            "hora de dormir",
        ],
    )


def _stable_demo_has_executive_marker(normalized: str) -> bool:
    return _stable_demo_has(
        normalized,
        [
            "bloqueo",
            "bloqueada",
            "bloqueado",
            "no puedo organizarme",
            "organizarme",
            "no puedo empezar",
            "me cuesta arrancar",
            "abrir archivo",
            "temporizador",
            "tarea",
            "pendiente",
            "no se por donde empezar",
        ],
    )


def _stable_demo_has_child_marker(normalized: str) -> bool:
    return _stable_demo_has(
        normalized,
        [
            "mi hijo",
            "mi hija",
            "mis hijos",
            "mis hijas",
            "mi nino",
            "mi nina",
            "mi ni o",
            "mi ni a",
            "hijo",
            "hija",
            "nino",
            "nina",
            "ni o",
            "ni a",
            "menor",
            "pequeno",
            "pequena",
        ],
    )


def _stable_demo_has_teen_marker(normalized: str) -> bool:
    return _stable_demo_has(
        normalized,
        [
            "adolescente",
            "mi adolescente",
            "hijo adolescente",
            "hija adolescente",
            "teen",
            "secundaria",
            "prepa",
            "bachillerato",
            "15 anos",
            "16 anos",
            "17 anos",
        ],
    )


def _stable_demo_has_caregiver_marker(normalized: str) -> bool:
    direct = _stable_demo_has(
        normalized,
        [
            "cuidador",
            "cuidadora",
            "como mama",
            "como madre",
            "como papa",
            "como padre",
            "soy mama",
            "soy madre",
            "soy papa",
            "soy padre",
            "cuidando",
            "nadie me ayuda",
            "me toca sostener",
        ],
    )
    overload_with_child = _stable_demo_has(
        normalized,
        [
            "ya no puedo",
            "no puedo mas",
            "me rebasa",
            "estoy agotada",
            "estoy agotado",
            "no doy mas",
        ],
    ) and _stable_demo_has_child_marker(normalized)
    return direct or overload_with_child


def _stable_demo_has_partner_marker(normalized: str) -> bool:
    return _stable_demo_has(
        normalized,
        [
            "mi pareja",
            "mi esposo",
            "mi esposa",
            "mi marido",
            "mi novia",
            "mi novio",
        ],
    )


def _stable_demo_has_family_marker(normalized: str) -> bool:
    return _stable_demo_has(
        normalized,
        [
            "mi familia",
            "familia",
            "todos en casa",
            "en casa todos",
            "mis hijos y yo",
        ],
    )


def _stable_demo_child_aggression_marker(normalized: str) -> bool:
    return _stable_demo_has(
        normalized,
        [
            "grita",
            "gritando",
            "esta gritando",
            "quiere golpear",
            "quiere pegar",
            "golpear a su papa",
            "golpear a su padre",
            "golpear a su mama",
            "golpear a su madre",
            "agresivo",
            "agresiva",
            "se esta lastimando",
            "se lastima",
            "quiere lastimar",
            "quiere lastimarse",
            "quiere lastimarlo",
            "quiere lastimarla",
        ],
    )


def _stable_demo_explicit_escalation(normalized: str) -> bool:
    return _stable_demo_has(
        normalized,
        [
            "esta ocurriendo una crisis",
            "hay una crisis",
            "hay crisis",
            "en crisis",
            "meltdown",
            "hay riesgo",
            "peligro",
            "emergencia",
            "gritando",
            "esta gritando",
            "quiere golpear",
            "quiere pegar",
            "golpear a su papa",
            "golpear a su padre",
            "agresivo",
            "agresiva",
            "se esta golpeando",
            "esta golpeando",
            "se golpea",
            "se quiere golpear",
            "se esta lastimando",
            "quiere lastimar",
            "lastimarse",
            "lastimarme",
            "lastimarlo",
            "lastimarla",
            "no puedo mantenerlo seguro",
            "no puedo mantenerla segura",
            "no puedo mantenerme seguro",
            "no puedo mantenerme segura",
            "se quiere morir",
            "me quiero morir",
            "suicid",
        ],
    )


def _stable_demo_detect_subject(
    message: str,
    previous_frame: Optional[Dict[str, Any]],
    route_id: Optional[str] = None,
) -> str:
    normalized = _stable_demo_normalize(message)
    previous_subject = _stable_demo_previous_subject(previous_frame)

    if _stable_demo_has_partner_marker(normalized):
        return "partner"
    if _stable_demo_has_teen_marker(normalized):
        return "teen_child"
    if _stable_demo_has_family_marker(normalized) and not _stable_demo_has_child_marker(normalized):
        return "family"
    if _stable_demo_explicit_escalation(normalized) and _stable_demo_has_child_marker(normalized):
        return "child"
    if _stable_demo_has_caregiver_marker(normalized) and not _stable_demo_has_sleep_marker(normalized):
        return "caregiver"
    if _stable_demo_has_child_marker(normalized):
        return "child"
    if _stable_demo_has_caregiver_marker(normalized):
        return "caregiver"
    if _stable_demo_has(
        normalized,
        [
            "yo",
            "me siento",
            "me da",
            "mi ansiedad",
            "no puedo dormir",
            "estoy bloqueada",
            "estoy bloqueado",
        ],
    ):
        return "self"
    if previous_subject != "unknown":
        return previous_subject
    if route_id == "apoyo_infancia_neurodivergente":
        return "child"
    if route_id == "sobrecarga_cuidador":
        return "caregiver"
    if route_id in {"ansiedad", "sueno", "bloqueo_ejecutivo", "crisis"}:
        return "self"
    return "unknown"


def _stable_demo_detect_mode(
    message: str,
    previous_frame: Optional[Dict[str, Any]],
    route_id: Optional[str],
    support_subject: str,
) -> str:
    normalized = _stable_demo_normalize(message)
    if route_id == "ansiedad" and _stable_demo_anxiety_crisis_marker(normalized):
        return "acute"
    if _stable_demo_explicit_escalation(normalized):
        return "acute"
    if _stable_demo_has(
        normalized,
        [
            "prevenir",
            "prevencion",
            "preventivo",
            "para que no",
            "antes de que",
            "anticipar",
            "anticipacion",
            "plan",
            "rutina",
            "senales tempranas",
        ],
    ):
        return "preventive"
    if support_subject in {"child", "teen_child"} and _stable_demo_has(
        normalized,
        [
            "calmarlo",
            "calmarla",
            "regularlo",
            "regularla",
            "coregular",
            "corregular",
            "acompanarlo",
            "acompanarla",
            "se desregula",
            "se satura",
        ],
    ):
        return "co_regulation"
    if _stable_demo_has(
        normalized,
        [
            "entender",
            "por que",
            "reflexionar",
            "pensar esto",
            "no se que me pasa",
            "quiero ordenar",
        ],
    ):
        return "reflection"

    previous_mode = _stable_demo_previous_mode(previous_frame)
    if previous_mode in {"acute", "preventive", "co_regulation", "reflection"} and _stable_demo_wants_another(normalized):
        return previous_mode
    if route_id == "crisis":
        return "acute"
    return "supportive"


def _stable_demo_reports_relief(normalized: str) -> bool:
    return _stable_demo_has(
        normalized,
        [
            "bajo un poco",
            "bajÃ³ un poco",
            "aflojo un poco",
            "aflojÃ³ un poco",
            "me ayudo",
            "me ayudÃ³",
            "ya estoy mejor",
            "me siento mejor",
            "ya bajo",
            "ya bajÃ³",
            "se calmo",
            "se calmÃ³",
        ],
    )


def _stable_demo_shared_heavy_load(normalized: str) -> bool:
    return _stable_demo_has(
        normalized,
        [
            "no puedo",
            "me rebasa",
            "me gana",
            "no puedo con todo",
            "sola con esto",
            "solo con esto",
            "muy ansiosa",
            "muy ansioso",
            "bloqueada",
            "bloqueado",
            "crisis",
        ],
    )


def _stable_demo_emotional_close(
    route_id: str,
    normalized: str,
    turn_family: str,
    step_index: int,
    support_subject: str = "unknown",
    support_mode: str = "supportive",
) -> Optional[str]:
    if route_id in {"meta", "medicacion"}:
        return None
    if _stable_demo_wants_pause(normalized):
        return "Aquí podemos pausar. Si necesitas seguir, seguimos desde aquí."
    if _stable_demo_reports_relief(normalized):
        if route_id == "sueno":
            return "Si bajo un poco la activacion, sosten solo eso y no agregues mas pasos."
        if route_id == "bloqueo_ejecutivo":
            return "Si ya hubo un primer movimiento, eso cuenta; el siguiente puede seguir igual de pequeno."
        if support_subject in {"child", "teen_child"}:
            return "Si bajo un poco, manten la misma ayuda sin sumar demandas nuevas."
        if support_mode == "preventive":
            return "Para prevenir, basta con dejar visible un paso pequeno y repetible."
    return None


def _stable_demo_apply_emotional_close(
    response_text: str,
    route_id: str,
    normalized: str,
    turn_family: str,
    step_index: int,
    support_subject: str = "unknown",
    support_mode: str = "supportive",
) -> str:
    close = _stable_demo_emotional_close(
        route_id=route_id,
        normalized=normalized,
        turn_family=turn_family,
        step_index=step_index,
        support_subject=support_subject,
        support_mode=support_mode,
    )
    if not close or close in response_text:
        return response_text
    return f"{response_text}\n\n{close}"


def _stable_demo_preferred_interventions(
    route_id: str,
    normalized: str,
    support_subject: str = "unknown",
    support_mode: str = "supportive",
) -> List[str]:
    if route_id == "crisis":
        if support_subject in {"child", "teen_child"}:
            if support_mode == "acute" or _stable_demo_explicit_escalation(normalized):
                return ["crisis_hijo_coregulacion", "seguridad_entorno", "bajar_estimulos", "distancia_segura"]
            return ["crisis_hijo_coregulacion", "bajar_estimulos"]
        if support_subject == "self":
            return ["crisis_self_bajar_estimulos", "crisis_self_contacto_apoyo", "bajar_estimulos", "distancia_segura"]

    if route_id == "apoyo_infancia_neurodivergente":
        if support_subject == "teen_child" and _stable_demo_has_sleep_marker(normalized):
            return [
                "teen_rutina_baja_demanda",
                "teen_descompresion_sensorial",
                "teen_ansiedad_anticipatoria",
                "teen_sueno_activacion_cognitiva",
            ]
        if support_subject == "child" and _stable_demo_has_sleep_marker(normalized):
            return ["sueno_infancia", "rutina_visual", "reduccion_sensorial"]
        if support_mode == "preventive":
            return ["rutina_visual", "reduccion_sensorial", "comunicacion_concreta"]
        if support_mode == "co_regulation":
            return ["corregulacion", "reduccion_sensorial", "comunicacion_concreta"]

    if route_id == "sobrecarga_cuidador":
        if support_mode == "preventive":
            return ["prioridad_cuidador", "pedir_ayuda_concreta", "bajar_carga"]
        return ["validacion_cuidador", "bajar_carga", "prioridad_cuidador", "pausa_sin_culpa"]
    if _stable_demo_has(normalized, ["medita", "meditar", "meditacion", "meditación"]):
        if route_id == "sueno":
            return ["meditacion_sueno", "rutina_bajada"]
        if route_id == "ansiedad":
            return ["meditacion_ansiedad", "meditacion_1_minuto", "respiracion_1_min"]
        return ["corregulacion"]

    if route_id == "ansiedad":
        if support_mode == "acute" or _stable_demo_anxiety_crisis_marker(normalized):
            return ["respiracion_1_min", "grounding_pies", "meditacion_1_minuto"]
        if _stable_demo_has(normalized, ["respira", "respiracion", "respiración", "aire"]):
            return ["respiracion_1_min", "grounding_pies"]
        if _stable_demo_has(normalized, ["5 4 3", "54321", "cinco sentidos", "sentidos"]):
            return ["grounding_54321"]
        if _stable_demo_has(normalized, ["preocupacion", "preocupación", "preocupa", "mente"]):
            return ["descarga_mental", "decision_hoy_no_hoy"]
        return []

    if route_id == "crisis":
        if _stable_demo_has(normalized, ["que digo", "qué digo", "frase", "que le digo", "qué le digo"]):
            return ["frase_literal"]
        if _stable_demo_has(normalized, ["distancia", "espacio", "seguro", "segura"]):
            return ["distancia_segura", "seguridad_entorno"]
        if _stable_demo_has(normalized, ["discute", "discutir", "no entiende"]):
            return ["no_discutir"]
        if _stable_demo_has(normalized, ["mi hijo", "mi hija", "hijo", "hija"]):
            return ["crisis_hijo_coregulacion", "bajar_estimulos"]
        return []

    if route_id == "sueno":
        if _stable_demo_has(normalized, ["pensamientos intrusivos", "pensamiento intrusivo", "intrusivos"]):
            return ["pensamientos_intrusivos", "mente_acelerada"]
        if _stable_demo_has(normalized, ["mente acelerada", "preocupacion", "preocupación", "no se apaga"]):
            return ["mente_acelerada"]
        if _stable_demo_has(normalized, ["cuerpo activado", "inquieto", "palpitaciones", "tension", "tensión"]):
            return ["cuerpo_activado"]
        if _stable_demo_has(normalized, ["luz", "ruido", "pantalla", "entorno"]):
            return ["entorno", "rutina_bajada"]
        if _stable_demo_has(normalized, ["no puedo dormir", "insomnio", "desvelo"]):
            return ["si_no_puede_dormir", "rutina_bajada"]
        return []

    if route_id == "bloqueo_ejecutivo":
        if _stable_demo_has(normalized, ["opciones", "dame opciones", "tres opciones"]):
            return ["tres_opciones"]
        if _stable_demo_has(normalized, ["temporizador", "timer", "2 minutos", "dos minutos"]):
            return ["temporizador"]
        if _stable_demo_has(normalized, ["titulo", "título", "frase"]):
            return ["titulo_feo"]
        if _stable_demo_has(normalized, ["no se como", "no sé cómo", "no se que toca", "no sé qué toca"]):
            return ["si_no_sabe_que_toca", "tres_opciones"]
        return []

    if route_id == "apoyo_infancia_neurodivergente":
        if _stable_demo_has(normalized, ["dormir", "duerman", "duerme", "sueno", "sue o"]):
            return ["sueno_infancia", "rutina_visual", "reduccion_sensorial"]
        if _stable_demo_explicit_overthinking_marker(normalized):
            return ["sobrepensamiento"]
        if _stable_demo_has(normalized, ["intrusivos", "pensamiento intrusivo", "pensamientos intrusivos"]):
            return ["pensamientos_intrusivos"]
        if _stable_demo_has(normalized, ["que les digo", "qué les digo", "como les digo", "cómo les digo", "frase"]):
            return ["comunicacion_concreta"]
        if _stable_demo_has(normalized, ["rutina", "visual", "anticipacion", "anticipación"]):
            return ["rutina_visual"]
        if _stable_demo_has(normalized, ["estimulos", "estímulos", "ruido", "luz", "sensorial"]):
            return ["reduccion_sensorial"]
        return []

    return []


def _stable_demo_explicit_intervention_requests(route_id: str, normalized: str) -> List[str]:
    requested: List[str] = []

    def add(*keys: str) -> None:
        for key in keys:
            if key in INTERVENTION_BANK.get(route_id, {}) and key not in requested:
                requested.append(key)

    if _stable_demo_has(normalized, ["medita", "meditar", "meditacion", "meditaciÃ³n"]):
        add("meditacion_sueno", "meditacion_ansiedad", "meditacion_1_minuto")
    if _stable_demo_has(normalized, ["respira", "respiracion", "respiraciÃ³n"]):
        add("respiracion_1_min")
    if route_id == "ansiedad" and _stable_demo_has(
        normalized,
        [
            "las escribo",
            "lo escribo",
            "la escribo",
            "escribo aqui",
            "escribir aqui",
        ],
    ):
        add("descarga_mental")
    if _stable_demo_has(normalized, ["5 4 3", "54321", "cinco sentidos", "grounding"]):
        add("grounding_54321")
    if _stable_demo_has(normalized, ["temporizador", "timer", "2 minutos", "dos minutos"]):
        add("temporizador")
    if _stable_demo_has(normalized, ["que digo", "quÃ© digo", "frase", "que le digo", "quÃ© le digo"]):
        add("frase_literal", "comunicacion_concreta", "titulo_feo")
    if _stable_demo_has(normalized, ["rutina visual", "visual"]):
        add("rutina_visual")
    if _stable_demo_has(normalized, ["estimulos", "estÃ­mulos", "ruido", "luz", "sensorial"]):
        add("reduccion_sensorial", "bajar_estimulos", "entorno")
    if _stable_demo_has(normalized, ["distancia", "espacio seguro", "segura", "seguro"]):
        add("distancia_segura", "seguridad_entorno")
    if _stable_demo_has(normalized, ["opciones", "tres opciones"]):
        add("tres_opciones")
    if _stable_demo_has(normalized, ["abrir archivo", "abre el archivo", "abrir material"]):
        add("abrir_material")
    if route_id == "bloqueo_ejecutivo" and _stable_demo_has(
        normalized,
        [
            "no tengo archivo",
            "no hay archivo",
            "sin archivo",
            "archivo que abrir",
        ],
    ):
        add("titulo_feo", "primer_movimiento")

    return requested


def _stable_demo_select_intervention(
    route_id: str,
    normalized: str,
    step_index: int,
    used_interventions: Dict[str, List[str]],
    recent_interventions: Dict[str, List[str]],
    previous_intervention: Optional[str],
    exhausted_strategies: Optional[Dict[str, List[str]]] = None,
    support_subject: str = "unknown",
    support_mode: str = "supportive",
    explicit_intervention_ids: Optional[List[str]] = None,
    overthinking_blocked: bool = False,
    variant_seed: Optional[str] = None,
) -> Dict[str, Any]:
    bank = INTERVENTION_BANK.get(route_id) or {}
    if not bank:
        return {
            "intervention_id": None,
            "response_text": "",
            "used_interventions": used_interventions,
            "used_interventions_last_10": recent_interventions,
        }

    order = list(bank.keys())
    preferred = [
        key
        for key in _stable_demo_preferred_interventions(
            route_id,
            normalized,
            support_subject=support_subject,
            support_mode=support_mode,
        )
        if key in bank
    ]
    explicit_preferred = [
        key
        for key in (explicit_intervention_ids or [])
        if key in bank
    ]
    candidates = (
        explicit_preferred
        + [key for key in preferred if key not in explicit_preferred]
        + [key for key in order if key not in preferred and key not in explicit_preferred]
    )
    if route_id == "apoyo_infancia_neurodivergente" and (
        overthinking_blocked or not _stable_demo_explicit_overthinking_marker(normalized)
    ):
        overthinking_only = {"sobrepensamiento", "pensamientos_intrusivos"}
        filtered_candidates = [key for key in candidates if key not in overthinking_only]
        if filtered_candidates:
            candidates = filtered_candidates
    if route_id == "sueno" and overthinking_blocked:
        overthinking_sleep = {"mente_acelerada", "pensamientos_intrusivos"}
        filtered_candidates = [key for key in candidates if key not in overthinking_sleep]
        if filtered_candidates:
            candidates = filtered_candidates
    exhausted_for_route = {
        str(item or "").strip()
        for item in (exhausted_strategies or {}).get(route_id, []) or []
        if str(item or "").strip()
    }
    if exhausted_for_route:
        non_exhausted_candidates = [key for key in candidates if key not in exhausted_for_route]
        if non_exhausted_candidates:
            candidates = non_exhausted_candidates
    if (
        step_index == 0
        and _stable_demo_quick_button_message(normalized)
        and not explicit_preferred
        and len(candidates) > 1
    ):
        rotation_window = min(len(candidates), 3)
        offset = _stable_demo_variant_offset(
            f"{variant_seed or ''}:{route_id}:{normalized}",
            rotation_window,
        )
        if offset:
            candidates = candidates[offset:] + candidates[:offset]

    used_for_route = list(used_interventions.get(route_id, []) or [])
    exhausted = bool(order) and all(key in used_for_route for key in order)
    effective_used = [] if exhausted else used_for_route
    recent_for_route = list(recent_interventions.get(route_id, []) or [])[-STABLE_DEMO_RECENT_WINDOW:]
    recent_to_avoid = set(recent_for_route[-STABLE_DEMO_RECENT_AVOID_WINDOW:])
    explicit_requested = set(explicit_preferred)

    selected = None
    for key in candidates:
        if (
            (key != previous_intervention or key in explicit_requested)
            and (key not in recent_to_avoid or key in explicit_requested)
            and (key not in effective_used or key in explicit_requested)
        ):
            selected = key
            break

    if selected is None:
        selected = next(
            (
                key
                for key in candidates
                if key != previous_intervention and key not in recent_to_avoid
            ),
            None,
        )

    if selected is None:
        selected = next((key for key in candidates if key != previous_intervention), None)

    if selected is None:
        rotated = candidates[step_index % len(candidates)] if candidates else None
        selected = rotated or order[0]

    next_used_for_route = [] if exhausted else used_for_route
    if selected not in next_used_for_route:
        next_used_for_route.append(selected)

    next_used = dict(used_interventions)
    next_used[route_id] = next_used_for_route
    next_recent = _stable_demo_update_recent_interventions(
        recent_interventions=recent_interventions,
        route_id=route_id,
        intervention_id=selected,
    )

    return {
        "intervention_id": selected,
        "response_text": bank[selected],
        "used_interventions": next_used,
        "used_interventions_last_10": next_recent,
    }


def _stable_demo_detect_route(message: str, previous_frame: Optional[Dict[str, Any]]) -> Optional[str]:
    normalized = _stable_demo_normalize(message)
    previous_route = _stable_demo_previous_route(previous_frame)
    support_subject = _stable_demo_detect_subject(message, previous_frame, previous_route)
    explicit_escalation = _stable_demo_explicit_escalation(normalized)
    overthinking_block_active = _stable_demo_overthinking_block_remaining(previous_frame) > 0
    preventive_request = _stable_demo_has(
        normalized,
        [
            "prevenir",
            "prevencion",
            "preventivo",
            "para que no",
            "antes de que",
            "anticipar",
            "anticipacion",
            "plan",
            "senales tempranas",
        ],
    )
    previous_pre_medication_route = str((previous_frame or {}).get("pre_medication_route_id") or "").strip()

    non_pharmacological = _stable_demo_has(
        normalized,
        [
            "medida no farmacologica",
            "no farmacologico",
            "no farmacologica",
            "sin medicamento",
            "sin pastilla",
            "sin farmaco",
        ],
    )
    asks_medication = _stable_demo_has(
        normalized,
        [
            "medicamento",
            "medicamentos",
            "medicina",
            "pastilla",
            "pastillas",
            "dosis",
            "que tomo",
            "que me tomo",
            "que pastilla",
            "que le doy",
            "recetame",
            "algo para dormir",
            "algo para calmarme",
            "algo para la ansiedad",
        ],
    )
    if asks_medication and not non_pharmacological:
        return "medicacion"
    if non_pharmacological and previous_pre_medication_route in STABLE_DEMO_STEPS:
        return previous_pre_medication_route

    if _stable_demo_has(
        normalized,
        [
            "quien eres",
            "quien sos",
            "como te llamo",
            "como puedo llamarte",
            "tu nombre",
            "que puedes hacer",
            "para que sirves",
            "puedo hablar contigo",
            "puedo platicar contigo",
        ],
    ):
        return "meta"

    if _stable_demo_anxiety_crisis_marker(normalized):
        return "ansiedad"

    if _stable_demo_has_child_marker(normalized) and _stable_demo_has(
        normalized,
        [
            "crisis es de mi hijo",
            "crisis es de mi hija",
            "la crisis es de mi hijo",
            "la crisis es de mi hija",
            "crisis de mi hijo",
            "crisis de mi hija",
            "crisis de mis hijos",
            "crisis de mis hijas",
            "mi hijo esta en crisis",
            "mi hija esta en crisis",
            "mi hijo esta en una crisis",
            "mi hija esta en una crisis",
        ],
    ):
        return "crisis"

    if support_subject in {"child", "teen_child"} and _stable_demo_child_aggression_marker(normalized):
        return "crisis"

    if _stable_demo_has(
        normalized,
        [
            "no es sobrepensamiento es sueno",
            "no es sobrepensamiento es sue o",
            "no es sobrepensamiento es dormir",
        ],
    ):
        return "sueno"

    if _stable_demo_has(
        normalized,
        [
            "no es sobrepensamiento es crisis",
            "no es una crisis de sobrepensamiento",
            "no es sobrepensamiento la crisis",
        ],
    ):
        return "crisis"

    if _stable_demo_has(normalized, ["no es ansiedad es sueno", "no es ansiedad es sue o", "no es ansiedad es dormir", "el problema es dormir", "el problema es sueno", "el problema es sue o"]):
        return "sueno"
    if _stable_demo_has(normalized, ["no es crisis es ansiedad", "no es sueno es ansiedad", "el problema es ansiedad"]):
        return "ansiedad"
    if _stable_demo_has(normalized, ["no es ansiedad es crisis", "hay crisis", "esta ocurriendo una crisis"]):
        return "crisis"
    if _stable_demo_has(
        normalized,
        [
            "el problema es mi hija",
            "el problema es mi hijo",
            "el problema son mis hijos",
            "el problema son mis hijas",
            "no soy yo es mi hija",
            "no soy yo es mi hijo",
            "no es mio es mi hija",
            "no es mio es mi hijo",
        ],
    ):
        return "apoyo_infancia_neurodivergente"

    if preventive_request and not explicit_escalation:
        if support_subject in {"child", "teen_child", "family"}:
            return "apoyo_infancia_neurodivergente"
        if support_subject == "caregiver":
            return "sobrecarga_cuidador"
        if _stable_demo_has_sleep_marker(normalized):
            return "sueno"
        if _stable_demo_has_executive_marker(normalized):
            return "bloqueo_ejecutivo"
        if previous_route and previous_route != "crisis":
            return previous_route
        return "ansiedad"

    if support_subject in {"child", "teen_child"} and _stable_demo_has_sleep_marker(normalized) and not explicit_escalation:
        return "apoyo_infancia_neurodivergente"

    if support_subject in {"child", "teen_child"} and previous_route == "sueno" and not explicit_escalation:
        return "sueno"

    if support_subject == "caregiver" and not _stable_demo_has_sleep_marker(normalized) and not explicit_escalation:
        return "sobrecarga_cuidador"

    if _stable_demo_has_executive_marker(normalized) and not explicit_escalation:
        return "bloqueo_ejecutivo"

    if _stable_demo_has_sleep_marker(normalized) and not explicit_escalation:
        if support_subject in {"child", "teen_child"}:
            return "apoyo_infancia_neurodivergente"
        return "sueno"

    behavioral_escalation = _stable_demo_has(
        normalized,
        [
            "esta gritando",
            "no lo puedo calmar",
            "no la puedo calmar",
            "esta fuera de control",
            "no se puede controlar",
        ],
    ) and not _stable_demo_has_sleep_marker(normalized)

    if explicit_escalation or behavioral_escalation:
        return "crisis"
    if _stable_demo_has(
        normalized,
        [
            "mi hijo",
            "mi hija",
            "mis hijos",
            "mis hijas",
            "mi nino",
            "mi nina",
            "mi niño",
            "mi niña",
            "triple excepcionalidad",
            "doble excepcionalidad",
            "altas capacidades",
            "aacc",
            "tea",
            "tdah",
            *([] if overthinking_block_active else ["sobrepensamiento", "sobrepiensa"]),
        ],
    ):
        return "apoyo_infancia_neurodivergente"
    if previous_route == "apoyo_infancia_neurodivergente" and _stable_demo_has(
        normalized,
        [
            "dormir",
            "duerman",
            "duerme",
            "los ayudo",
            "las ayudo",
            "ayudarlos",
            "ayudarlas",
            "como los ayudo",
            "cómo los ayudo",
        ],
    ):
        return "apoyo_infancia_neurodivergente"
    if _stable_demo_has(
        normalized,
        [
            "sueno",
            "sue o",
            "dormir",
            "duermo",
            "duerme",
            "insomnio",
            "desvelo",
            "no descanso",
            "problemas de sueno",
            "problemas de sue o",
        ],
    ):
        return "sueno"
    if _stable_demo_has(
        normalized,
        [
            "bloqueo",
            "bloqueada",
            "bloqueado",
            "no puedo organizarme",
            "organizarme",
            "no puedo empezar",
            "me cuesta arrancar",
            "abrir archivo",
            "temporizador",
            "tarea",
        ],
    ):
        return "bloqueo_ejecutivo"
    if previous_route in {"sueno", "crisis", "bloqueo_ejecutivo", "apoyo_infancia_neurodivergente", "sobrecarga_cuidador"} and _stable_demo_has(
        normalized,
        [
            "ansiedad",
            "ansiosa",
            "ansioso",
            "me siento ansiosa",
            "me siento ansioso",
            "preocupacion",
            "preocupa",
            "mente acelerada",
        ],
    ):
        return previous_route
    if _stable_demo_has(
        normalized,
        [
            "ansiedad",
            "ansiosa",
            "ansioso",
            "me siento ansiosa",
            "me siento ansioso",
            "preocupacion",
            "preocupa",
            "mente acelerada",
        ],
    ):
        return "ansiedad"
    if previous_route in STABLE_DEMO_ROUTE_TO_DOMAIN:
        return previous_route
    return None


def _stable_demo_write_here_question(normalized: str) -> bool:
    return _stable_demo_has(
        normalized,
        [
            "lo escribo aqui",
            "la escribo aqui",
            "las escribo aqui",
            "escribo aqui",
            "lo puedo escribir aqui",
            "las puedo escribir aqui",
            "aqui lo escribo",
            "aqui las escribo",
        ],
    )


def _stable_demo_where_to_write_question(normalized: str) -> bool:
    return _stable_demo_has(
        normalized,
        [
            "donde lo escribo",
            "en donde lo escribo",
            "donde la escribo",
            "donde las escribo",
            "en que lo escribo",
            "en que las escribo",
            "donde escribo",
        ],
    )


def _stable_demo_no_materials_marker(normalized: str) -> bool:
    return _stable_demo_has(
        normalized,
        [
            "no tengo archivo",
            "no hay archivo",
            "no tengo archivo que abrir",
            "no tengo nada que abrir",
            "no tengo nada cerca para abrir",
            "no tengo cuaderno",
            "no tengo hoja",
            "no tengo papel",
            "no tengo en que escribir",
            "no tengo donde escribir",
            "no tengo nada que abrir ni donde escribir",
            "no tengo nada que abrir ni en que escribir",
            "no tengo en donde escribir",
        ],
    )


def _stable_demo_no_writing_marker(normalized: str) -> bool:
    return _stable_demo_has(
        normalized,
        [
            "no tengo ganas de escribir",
            "no quiero escribir",
            "no puedo escribir",
            "no me sale escribir",
            "no escribimos",
        ],
    )


def _stable_demo_failed_previous_marker(normalized: str) -> bool:
    return _stable_demo_has(
        normalized,
        [
            "eso no ha funcionado",
            "eso no funciono",
            "eso no funciona",
            "no ha funcionado",
            "no funciono",
            "no funciona",
            "sigue igual",
        ],
    )


def _stable_demo_phrase_question(normalized: str) -> bool:
    return _stable_demo_has(
        normalized,
        [
            "que le digo",
            "que les digo",
            "que digo",
            "como le digo",
            "como les digo",
            "que frase",
            "cual frase",
        ],
    )


def _stable_demo_build_direct_turn_response(
    *,
    route_id: str,
    normalized: str,
    support_subject: str,
    support_mode: str,
    previous_frame: Optional[Dict[str, Any]],
) -> Optional[Dict[str, str]]:
    previous_intervention = _stable_demo_previous_intervention(previous_frame)

    child_crisis_correction = _stable_demo_has(
        normalized,
        [
            "la crisis es de mi hijo",
            "la crisis es de mi hija",
            "crisis de mi hijo",
            "crisis de mi hija",
        ],
    )
    child_aggression = _stable_demo_child_aggression_marker(normalized)
    if support_subject in {"child", "teen_child"} and child_crisis_correction and not child_aggression:
        return {
            "turn_family": "safety_clarification",
            "response_text": (
                "Gracias por aclararlo. Me centro en tu hijo: ahora la prioridad es seguridad y baja demanda, no razonar mucho. "
                "Baja ruido o gente cerca, manten distancia segura y usa pocas palabras. Si aparece riesgo de golpearse o lastimar a alguien, retira objetos peligrosos y pide apoyo presencial."
            ),
        }

    if support_subject in {"child", "teen_child"} and child_aggression:
        return {
            "turn_family": "safety_clarification",
            "response_text": (
                "Gracias por aclararlo. Si tu hijo esta gritando o quiere golpear, ahora la prioridad es seguridad fisica: "
                "separa a su papa si puedes, retira objetos que puedan lastimar y no intentes razonar con el en este momento. "
                "Usa pocas palabras: 'Estoy aqui. Vamos a darte espacio'. Si hay riesgo inmediato de dano, pide apoyo presencial o servicios de emergencia."
            ),
        }

    if route_id == "bloqueo_ejecutivo" and (
        _stable_demo_timer_done_marker(normalized)
        or (
            previous_intervention == "temporizador"
            and _stable_demo_has(normalized, ["ya lo hice", "listo", "hecho"])
        )
    ):
        return {
            "turn_family": "post_action_followup",
            "response_text": "Bien. Ahora el siguiente paso es elegir una sola linea de inicio: titulo, fecha o primera frase minima.",
        }

    if (
        route_id in {"sueno", "apoyo_infancia_neurodivergente"}
        and _stable_demo_has_sleep_marker(normalized)
        and _stable_demo_has(
            normalized,
            [
                "dame una actividad",
                "actividad para dormir",
                "que actividad",
                "una actividad",
                "algo tranquilo para dormir",
            ],
        )
    ):
        return {
            "turn_family": "direct_question",
            "response_text": (
                "Prueba una actividad baja en demanda durante 10 a 15 minutos: musica tranquila, lectura ligera o ducha tibia, con luz baja y sin conversaciones intensas. "
                "El objetivo no es dormir a la fuerza; es bajar el cuerpo un poco."
            ),
        }

    if _stable_demo_negates_overthinking(normalized) and _stable_demo_has_sleep_marker(normalized):
        if support_subject in {"child", "teen_child"}:
            return {
                "turn_family": "domain_correction",
                "response_text": (
                    "Tienes razon, me centro en sueno. Con adolescentes suele funcionar mejor negociar antes, no en plena noche: "
                    "pantalla cargando fuera del cuarto, luz baja y una actividad tranquila de 10 a 15 minutos, como musica suave, lectura ligera o ducha tibia. "
                    "Si no aceptan todo, empieza por una sola cosa: pantalla fuera de la cama."
                ),
            }
        return {
            "turn_family": "domain_correction",
            "response_text": (
                "Tienes razon, me centro en sueno. Si bajar luz no alcanzo, prueba una medida mas concreta: pantalla lejos de la cama, poca luz y una actividad baja en demanda durante 10 a 15 minutos. "
                "El objetivo no es forzar dormir, es bajar activacion."
            ),
        }

    if _stable_demo_negates_overthinking(normalized) and route_id == "crisis":
        return {
            "turn_family": "domain_correction",
            "response_text": (
                "Tienes razon, no lo trato como sobrepensamiento. Si es crisis, ahora va seguridad primero: baja demandas alrededor, usa pocas palabras y manten distancia segura. "
                "Si hay riesgo de dano, retira objetos peligrosos y pide apoyo presencial."
            ),
        }

    if _stable_demo_write_here_question(normalized):
        return {
            "turn_family": "direct_question",
            "response_text": "Si, puedes escribirlo aqui si quieres. Puede ser solo una linea; no tiene que estar completa.",
        }

    if _stable_demo_where_to_write_question(normalized):
        return {
            "turn_family": "direct_question",
            "response_text": "Puede ser aqui mismo. Si prefieres no ponerlo en el chat, puede ser una nota cualquiera; basta una sola linea.",
        }

    if _stable_demo_no_writing_marker(normalized):
        if route_id == "bloqueo_ejecutivo":
            return {
                "turn_family": "materials_blocked",
                "response_text": "Entonces no escribimos todavia. Di en voz alta el nombre de la tarea y elige solo el primer verbo: leer, buscar, escribir o revisar.",
            }
        return {
            "turn_family": "materials_blocked",
            "response_text": "Entonces no escribimos. Dilo en voz baja o nombralo mentalmente: 'lo que mas pesa es...'. Con eso basta por ahora.",
        }

    if _stable_demo_no_materials_marker(normalized):
        if _stable_demo_has(normalized, ["abrir"]) and _stable_demo_has(normalized, ["escribir"]):
            text = (
                "Entonces el primer paso no sera abrir ni escribir. Hazlo fisico: sientate en el lugar donde trabajarias "
                "o di en voz alta: 'voy a empezar por tesis'."
            )
        elif _stable_demo_has(normalized, ["escribir", "hoja", "cuaderno", "papel"]):
            if route_id == "bloqueo_ejecutivo":
                text = "No necesitas escribir todavia. Di en voz alta el nombre de la tarea y elige solo el primer verbo: leer, buscar, escribir o revisar."
            else:
                text = "Entonces no escribimos. Dilo en voz baja o nombralo mentalmente: 'lo que mas pesa es...'. Con eso basta por ahora."
        else:
            text = (
                "No necesitas tener archivo abierto. Empieza por una accion sin material: di en voz alta 'tengo que iniciar tesis' "
                "y elige solo el primer verbo: leer, buscar, escribir o revisar."
            )
        return {
            "turn_family": "materials_blocked",
            "response_text": text,
        }

    if _stable_demo_phrase_question(normalized):
        if route_id == "crisis" and support_subject in {"child", "teen_child"}:
            return {
                "turn_family": "literal_phrase_request",
                "response_text": (
                    "Dile una frase corta, sin explicar demasiado: 'Estoy aqui. Vamos a darte espacio. No voy a discutir ahora'. "
                    "Despues vuelve a seguridad: distancia, objetos fuera y menos gente cerca."
                ),
            }
        if route_id == "crisis":
            return {
                "turn_family": "literal_phrase_request",
                "response_text": "Puedes decir solo esto: 'Estoy aqui. No tenemos que resolverlo ahora. Vamos a bajar esto'. Luego guarda silencio unos segundos.",
            }
        if support_subject in {"child", "teen_child"}:
            return {
                "turn_family": "literal_phrase_request",
                "response_text": "Puedes decirle: 'Vamos con una sola cosa ahora. No tenemos que resolver todo en este momento'. Dilo bajo y sin agregar otra instruccion.",
            }
        return {
            "turn_family": "literal_phrase_request",
            "response_text": "Puedes decirlo asi: 'Ahora solo necesito empezar por una cosa pequena'. No hace falta explicarlo perfecto.",
        }

    if _stable_demo_has(normalized, ["como consigo eso", "como consigo ayuda", "como consigo apoyo"]):
        return {
            "turn_family": "direct_question",
            "response_text": (
                "Consiguelo por la via mas cercana, no la perfecta: alguien en casa, un familiar, una vecina, seguridad del lugar o servicios de emergencia si hay riesgo inmediato. "
                "El mensaje puede ser: 'Necesito apoyo presencial ahora; hay riesgo de que alguien salga lastimado'."
            ),
        }

    if _stable_demo_failed_previous_marker(normalized):
        if route_id == "sueno" or (
            route_id == "apoyo_infancia_neurodivergente"
            and support_subject in {"child", "teen_child"}
            and support_mode != "acute"
        ):
            return {
                "turn_family": "strategy_rejection",
                "response_text": (
                    "Tienes razon, entonces cambiamos sin salirnos de sueno. No lo negocies en plena noche: manana pacta algo concreto, "
                    "pantalla fuera del cuarto a una hora acordada y una actividad tranquila de 10 a 15 minutos. Si esto se repite mucho, conviene revisarlo con un profesional."
                ),
            }
        if route_id == "crisis":
            return {
                "turn_family": "strategy_rejection",
                "response_text": (
                    "Si eso no funciono y sigue habiendo riesgo, sube la prioridad a seguridad: mas distancia, separa a quien pueda salir lastimado, retira objetos peligrosos "
                    "y pide apoyo presencial. Ahora no toca convencer; toca proteger."
                ),
            }
        if route_id == "bloqueo_ejecutivo":
            return {
                "turn_family": "strategy_rejection",
                "response_text": "Entonces no abrimos archivo ni escribimos. Haz una entrada sin material: di en voz alta el nombre de la tarea y elige solo el primer verbo: leer, buscar, escribir o revisar.",
            }
        if route_id == "ansiedad":
            return {
                "turn_family": "strategy_rejection",
                "response_text": "Entonces no insistimos por ahi. Si escribir no ayudo, bajalo a voz o mente: nombra solo 'lo que mas pesa es...' y no intentes resolverlo todavia.",
            }

    return None


def _stable_demo_turn_family(message: str, previous_route: Optional[str], route_id: str) -> str:
    normalized = _stable_demo_normalize(message)
    if route_id == "meta":
        return "meta_question"
    if route_id == "medicacion":
        return "specific_action_request"
    if previous_route and previous_route != route_id:
        return "domain_shift"
    if _stable_demo_has(normalized, ["ya lo hice", "listo", "hecho"]):
        return "post_action_followup"
    if _stable_demo_has(normalized, ["eso ya me lo dijiste", "eso ya lo dijiste", "repites", "estas repitiendo", "estás repitiendo"]):
        return "post_action_followup"
    if _stable_demo_wants_another(normalized) or _stable_demo_has(
        normalized,
        [
            "dime que hago",
            "que hago",
            "dime una medida",
            "pero dime",
            "ensename a meditar",
            "enseñame a meditar",
        ],
    ):
        return "followup_acceptance"
    if previous_route == route_id:
        return "followup_acceptance"
    return "new_request"


def stable_demo_response(
    message: str,
    previous_frame: Optional[Dict[str, Any]],
    chat_history: Optional[List[Dict[str, Any]]] = None,
    variant_seed: Optional[str] = None,
) -> Dict[str, Any]:
    route_id = _stable_demo_detect_route(message, previous_frame)
    if route_id not in STABLE_DEMO_ROUTE_TO_DOMAIN:
        return {"handled": False}

    normalized = _stable_demo_normalize(message)
    previous_route = _stable_demo_previous_route(previous_frame)
    previous_step = _stable_demo_previous_step(previous_frame)
    previous_intervention = _stable_demo_previous_intervention(previous_frame)
    used_interventions = _stable_demo_used_interventions(previous_frame)
    used_interventions_last_10 = _stable_demo_recent_interventions(previous_frame)
    exhausted_strategies = _stable_demo_exhausted_strategies(previous_frame)
    support_subject = _stable_demo_detect_subject(message, previous_frame, route_id)
    support_mode = _stable_demo_detect_mode(message, previous_frame, route_id, support_subject)
    turn_family = _stable_demo_turn_family(message, previous_route, route_id)
    intervention_id = None
    overthinking_negated = _stable_demo_negates_overthinking(normalized)
    previous_overthinking_block = _stable_demo_overthinking_block_remaining(previous_frame)
    overthinking_blocked = bool(overthinking_negated or previous_overthinking_block > 0)
    next_overthinking_block = (
        STABLE_DEMO_OVERTHINKING_BLOCK_TURNS
        if overthinking_negated
        else max(previous_overthinking_block - 1, 0)
    )
    direct_turn = _stable_demo_build_direct_turn_response(
        route_id=route_id,
        normalized=normalized,
        support_subject=support_subject,
        support_mode=support_mode,
        previous_frame=previous_frame,
    )

    if route_id == "medicacion":
        response_text = (
            "No puedo decirte qué medicamento tomar ni recomendar dosis. "
            "Si el sueño o la ansiedad están afectando mucho, lo más seguro es consultarlo con un profesional de salud. "
            "Sí puedo ayudarte con una medida no farmacológica."
        )
        step_index = 0
    elif route_id == "meta":
        response_text = "Soy NeuroGuIA. Estoy aquí para acompañar, ordenar lo que pasa y ayudarte a encontrar un paso claro."
        if _stable_demo_has(normalized, ["como puedo llamarte", "como te llamo", "tu nombre"]):
            response_text = "Puedes llamarme NeuroGuIA."
        elif _stable_demo_has(normalized, ["que puedes hacer", "para que sirves"]):
            response_text = "Puedo ayudarte a ordenar lo que está pasando y darte un siguiente paso claro, breve y seguro."
        elif _stable_demo_has(normalized, ["puedo hablar contigo", "puedo platicar contigo"]):
            response_text = "Sí. Puedes hablar conmigo aquí; te respondo con pasos claros y cuidado."
        step_index = 0
    elif direct_turn:
        turn_family = str(direct_turn.get("turn_family") or "direct_question")
        response_text = str(direct_turn.get("response_text") or "").strip()
        step_index = previous_step if previous_route == route_id else 0
        intervention_id = previous_intervention if previous_route == route_id else None
    else:
        same_route = previous_route == route_id
        if same_route or (
            previous_route
            and turn_family in {"followup_acceptance", "post_action_followup"}
        ):
            step_index = previous_step + 1
        else:
            step_index = 0

        selection_normalized = normalized
        previous_child_sleep = previous_intervention in {
            "sueno_infancia",
            "teen_sueno_activacion_cognitiva",
            "teen_rutina_baja_demanda",
            "teen_descompresion_sensorial",
            "teen_ansiedad_anticipatoria",
        }
        if (
            route_id == "apoyo_infancia_neurodivergente"
            and support_subject == "teen_child"
            and (previous_route == "sueno" or previous_child_sleep)
            and not _stable_demo_has_sleep_marker(normalized)
        ):
            selection_normalized = f"{normalized} sueno dormir"

        selection = _stable_demo_select_intervention(
            route_id=route_id,
            normalized=selection_normalized,
            step_index=step_index,
            used_interventions=used_interventions,
            recent_interventions=used_interventions_last_10,
            previous_intervention=previous_intervention if same_route else None,
            exhausted_strategies=exhausted_strategies,
            support_subject=support_subject,
            support_mode=support_mode,
            explicit_intervention_ids=_stable_demo_explicit_intervention_requests(route_id, selection_normalized),
            overthinking_blocked=overthinking_blocked,
            variant_seed=variant_seed,
        )
        intervention_id = selection.get("intervention_id")
        response_text = str(selection.get("response_text") or "").strip()
        used_interventions = dict(selection.get("used_interventions") or used_interventions)
        used_interventions_last_10 = dict(
            selection.get("used_interventions_last_10") or used_interventions_last_10
        )
        if same_route and _stable_demo_wants_pause(normalized):
            turn_family = "closure_or_pause"
            intervention_id = None
            response_text = "Aquí podemos pausar. Si necesitas seguir, seguimos desde aquí."
            used_interventions = _stable_demo_used_interventions(previous_frame)
            used_interventions_last_10 = _stable_demo_recent_interventions(previous_frame)

        if _stable_demo_repeat_complaint(normalized):
            response_text = f"Tienes razón. No repito esa vía. Probemos otra. {response_text}"
        elif _stable_demo_has(normalized, ["no me sirve", "eso no me sirve", "otra cosa"]):
            response_text = f"Probemos otra vía. {response_text}"

        response_text = _stable_demo_apply_emotional_close(
            response_text=response_text,
            route_id=route_id,
            normalized=normalized,
            turn_family=turn_family,
            step_index=step_index,
            support_subject=support_subject,
            support_mode=support_mode,
        )

    conversation_domain = STABLE_DEMO_ROUTE_TO_DOMAIN[route_id]
    support_goal = STABLE_DEMO_GOALS.get(route_id, "clarify_and_support")
    conversation_phase = STABLE_DEMO_PHASES.get(route_id, "stable_demo")
    max_steps = len(STABLE_DEMO_STEPS.get(route_id, [""])) or 1
    pre_medication_route_id = None
    pre_medication_step_index = None
    if route_id == "medicacion":
        detected_context_route = None
        if _stable_demo_has(normalized, ["dormir", "sueno", "insomnio", "desvelo"]):
            detected_context_route = "sueno"
        elif _stable_demo_has(normalized, ["ansiedad", "ansiosa", "ansioso", "calmarme"]):
            detected_context_route = "ansiedad"
        pre_medication_route_id = previous_route if previous_route in STABLE_DEMO_STEPS else detected_context_route
        pre_medication_step_index = previous_step if pre_medication_route_id == previous_route else 0

    conversation_frame = {
        "conversation_domain": conversation_domain,
        "support_goal": support_goal,
        "conversation_phase": conversation_phase,
        "speaker_role": (previous_frame or {}).get("speaker_role") or "usuario",
        "care_context": {
            "stable_demo": True,
            "previous_route_id": previous_route,
            "previous_step_index": previous_step,
            "last_intervention_id": intervention_id,
            "support_subject": support_subject,
            "support_mode": support_mode,
            "overthinking_block_turns": next_overthinking_block,
            "overthinking_block_active": overthinking_blocked,
            "exhausted_strategies": exhausted_strategies,
        },
        "continuity_score": 0.96 if previous_route == route_id else 0.62,
        "source_message": message,
        "effective_message": message,
        "turn_type": turn_family,
        "turn_family": turn_family,
        "route_id": route_id,
        "support_subject": support_subject,
        "support_mode": support_mode,
        "stable_demo_routing_key": f"{route_id}:{support_subject}:{support_mode}",
        "stable_demo_route_id": route_id,
        "step_index": step_index,
        "stable_demo_step_index": step_index,
        "stable_demo_intervention_id": intervention_id,
        "last_intervention_id": intervention_id,
        "direct_turn_response": bool(direct_turn),
        "overthinking_block_turns": next_overthinking_block,
        "overthinking_block_active": overthinking_blocked,
        "exhausted_strategies": exhausted_strategies,
        "used_interventions": used_interventions,
        "used_interventions_last_10": used_interventions_last_10,
        "max_steps": max_steps,
        "stable_demo": True,
        "phase_progression_reason": "stable_demo_counter",
        "last_guided_action": response_text,
        "last_action_instruction": response_text,
        "last_action_type": "stable_demo_step",
        "intervention_level": 1,
        "domain_shift_detected": bool(previous_route and previous_route != route_id),
        "domain_shift_analysis": {
            "detected": bool(previous_route and previous_route != route_id),
            "previous_route_id": previous_route,
            "route_id": route_id,
        },
        "support_flow_state": {
            "active": False,
            "handled_by": "stable_demo_response",
            "route_id": route_id,
            "active_route_id": route_id if route_id in STABLE_DEMO_STEPS else None,
            "support_subject": support_subject,
            "support_mode": support_mode,
            "stable_demo_routing_key": f"{route_id}:{support_subject}:{support_mode}",
            "conversation_domain": conversation_domain,
            "step_index": step_index,
            "max_steps": max_steps,
            "last_intervention_id": intervention_id,
            "direct_turn_response": bool(direct_turn),
            "overthinking_block_turns": next_overthinking_block,
            "overthinking_block_active": overthinking_blocked,
            "exhausted_strategies": exhausted_strategies,
            "used_interventions": used_interventions,
            "used_interventions_last_10": used_interventions_last_10,
        },
    }
    if pre_medication_route_id:
        conversation_frame["pre_medication_route_id"] = pre_medication_route_id
        conversation_frame["pre_medication_step_index"] = pre_medication_step_index

    behavioral_plan = _stable_demo_build_behavioral_plan(
        route_id=route_id,
        support_subject=support_subject,
        support_mode=support_mode,
        intervention_id=intervention_id,
        response_text=response_text,
        message=message,
        previous_frame=previous_frame,
        chat_history=chat_history,
        turn_family=turn_family,
        step_index=step_index,
    )
    if direct_turn:
        behavioral_plan["conversation_priority"] = "answer_current_user_turn"
        behavioral_plan["must_answer_current_question_first"] = True
        behavioral_plan["do_not_advance_intervention"] = True
        behavioral_plan["current_turn_task"] = "Responder la pregunta o aclaracion concreta del usuario y no avanzar la plantilla."
    if overthinking_blocked:
        behavioral_plan["blocked_interventions"] = {
            "sobrepensamiento": next_overthinking_block,
        }
    conversation_frame["behavioral_plan"] = behavioral_plan
    conversation_frame["support_flow_state"]["behavioral_plan"] = behavioral_plan

    return {
        "handled": True,
        "response_text": response_text,
        "behavioral_plan": behavioral_plan,
        "route_id": route_id,
        "support_subject": support_subject,
        "support_mode": support_mode,
        "stable_demo_routing_key": f"{route_id}:{support_subject}:{support_mode}",
        "step_index": step_index,
        "intervention_id": intervention_id,
        "used_interventions": used_interventions,
        "used_interventions_last_10": used_interventions_last_10,
        "exhausted_strategies": exhausted_strategies,
        "turn_family": turn_family,
        "direct_turn_response": bool(direct_turn),
        "overthinking_block_turns": next_overthinking_block,
        "overthinking_block_active": overthinking_blocked,
        "conversation_frame": conversation_frame,
    }


def stable_demo_repair_response(
    message: str,
    previous_frame: Optional[Dict[str, Any]],
    repair: Dict[str, Any],
    chat_history: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    if not repair.get("handled"):
        return {"handled": False}

    previous_route = _stable_demo_previous_route(previous_frame)
    repair_route = str(repair.get("route_id") or "").strip()
    route_id = repair_route or previous_route or "meta"
    if route_id not in STABLE_DEMO_ROUTE_TO_DOMAIN:
        route_id = previous_route if previous_route in STABLE_DEMO_ROUTE_TO_DOMAIN else "meta"

    normalized = _stable_demo_normalize(message)
    previous_step = _stable_demo_previous_step(previous_frame)
    previous_intervention = _stable_demo_previous_intervention(previous_frame)
    used_interventions = _stable_demo_used_interventions(previous_frame)
    used_interventions_last_10 = _stable_demo_recent_interventions(previous_frame)
    support_subject = str(repair.get("support_subject") or "").strip()
    if support_subject not in {"self", "child", "teen_child", "caregiver", "partner", "family", "unknown"}:
        support_subject = _stable_demo_previous_subject(previous_frame)
    support_mode = _stable_demo_previous_mode(previous_frame)
    if route_id == "crisis":
        support_mode = "acute"
    if not support_subject or support_subject == "unknown":
        support_subject = _stable_demo_detect_subject(message, previous_frame, route_id)

    do_not_advance_step = bool(repair.get("do_not_advance_step", True))
    step_index = previous_step if do_not_advance_step else previous_step + 1
    intervention_id = previous_intervention if do_not_advance_step else None
    mark_strategy_exhausted = str(repair.get("mark_strategy_exhausted") or "").strip() or None
    exhausted_strategies = _stable_demo_add_exhausted_strategy(
        previous_frame=previous_frame,
        route_id=previous_route or route_id,
        strategy_id=mark_strategy_exhausted,
    )
    overthinking_negated = _stable_demo_negates_overthinking(normalized)
    previous_overthinking_block = _stable_demo_overthinking_block_remaining(previous_frame)
    next_overthinking_block = (
        STABLE_DEMO_OVERTHINKING_BLOCK_TURNS
        if overthinking_negated
        else max(previous_overthinking_block - 1, 0)
    )
    response_text = str(repair.get("response_text") or "").strip()
    repair_type = str(repair.get("repair_type") or "conversational_repair").strip()

    conversation_domain = STABLE_DEMO_ROUTE_TO_DOMAIN[route_id]
    support_goal = STABLE_DEMO_GOALS.get(route_id, "clarify_and_support")
    conversation_phase = STABLE_DEMO_PHASES.get(route_id, "stable_demo")
    max_steps = len(STABLE_DEMO_STEPS.get(route_id, [""])) or 1

    conversation_frame = {
        "conversation_domain": conversation_domain,
        "support_goal": support_goal,
        "conversation_phase": conversation_phase,
        "speaker_role": (previous_frame or {}).get("speaker_role") or "usuario",
        "care_context": {
            "stable_demo": True,
            "conversational_repair": True,
            "repair_type": repair_type,
            "previous_route_id": previous_route,
            "previous_step_index": previous_step,
            "last_intervention_id": intervention_id,
            "support_subject": support_subject,
            "support_mode": support_mode,
            "overthinking_block_turns": next_overthinking_block,
            "overthinking_block_active": bool(next_overthinking_block),
            "exhausted_strategies": exhausted_strategies,
        },
        "continuity_score": 0.98 if previous_route == route_id else 0.7,
        "source_message": message,
        "effective_message": message,
        "turn_type": repair_type,
        "turn_family": repair_type,
        "route_id": route_id,
        "support_subject": support_subject,
        "support_mode": support_mode,
        "stable_demo_routing_key": f"{route_id}:{support_subject}:{support_mode}",
        "stable_demo_route_id": route_id,
        "step_index": step_index,
        "stable_demo_step_index": step_index,
        "stable_demo_intervention_id": intervention_id,
        "last_intervention_id": intervention_id,
        "conversational_repair": True,
        "repair_type": repair_type,
        "repair_notes": list(repair.get("notes") or []),
        "do_not_advance_step": do_not_advance_step,
        "mark_strategy_exhausted": mark_strategy_exhausted,
        "exhausted_strategies": exhausted_strategies,
        "direct_turn_response": True,
        "overthinking_block_turns": next_overthinking_block,
        "overthinking_block_active": bool(next_overthinking_block),
        "used_interventions": used_interventions,
        "used_interventions_last_10": used_interventions_last_10,
        "max_steps": max_steps,
        "stable_demo": True,
        "phase_progression_reason": "conversational_repair_no_step_advance",
        "last_guided_action": response_text,
        "last_action_instruction": response_text,
        "last_action_type": "conversational_repair",
        "intervention_level": 1,
        "domain_shift_detected": bool(previous_route and previous_route != route_id),
        "domain_shift_analysis": {
            "detected": bool(previous_route and previous_route != route_id),
            "previous_route_id": previous_route,
            "route_id": route_id,
            "reason": repair_type,
        },
        "support_flow_state": {
            "active": False,
            "handled_by": "conversational_repair_engine",
            "route_id": route_id,
            "active_route_id": route_id if route_id in STABLE_DEMO_STEPS else None,
            "support_subject": support_subject,
            "support_mode": support_mode,
            "stable_demo_routing_key": f"{route_id}:{support_subject}:{support_mode}",
            "conversation_domain": conversation_domain,
            "step_index": step_index,
            "max_steps": max_steps,
            "last_intervention_id": intervention_id,
            "conversational_repair": True,
            "repair_type": repair_type,
            "do_not_advance_step": do_not_advance_step,
            "mark_strategy_exhausted": mark_strategy_exhausted,
            "exhausted_strategies": exhausted_strategies,
            "direct_turn_response": True,
            "overthinking_block_turns": next_overthinking_block,
            "overthinking_block_active": bool(next_overthinking_block),
            "used_interventions": used_interventions,
            "used_interventions_last_10": used_interventions_last_10,
        },
    }
    behavioral_plan = _stable_demo_build_behavioral_plan(
        route_id=route_id,
        support_subject=support_subject,
        support_mode=support_mode,
        intervention_id=intervention_id,
        response_text=response_text,
        message=message,
        previous_frame=previous_frame,
        chat_history=chat_history,
        turn_family=repair_type,
        step_index=step_index,
    )
    behavioral_plan["conversation_priority"] = "conversational_repair"
    behavioral_plan["must_answer_current_question_first"] = True
    behavioral_plan["do_not_advance_intervention"] = do_not_advance_step
    behavioral_plan["repair_type"] = repair_type
    behavioral_plan["repair_notes"] = list(repair.get("notes") or [])
    behavioral_plan["current_turn_task"] = "Resolver la reparacion conversacional del ultimo mensaje sin avanzar plantilla."
    if next_overthinking_block:
        behavioral_plan["blocked_interventions"] = {
            "sobrepensamiento": next_overthinking_block,
        }
    conversation_frame["behavioral_plan"] = behavioral_plan
    support_state = dict(conversation_frame.get("support_flow_state") or {})
    support_state["behavioral_plan"] = behavioral_plan
    conversation_frame["support_flow_state"] = support_state

    return {
        "handled": True,
        "response_text": response_text,
        "behavioral_plan": behavioral_plan,
        "route_id": route_id,
        "support_subject": support_subject,
        "support_mode": support_mode,
        "stable_demo_routing_key": f"{route_id}:{support_subject}:{support_mode}",
        "step_index": step_index,
        "intervention_id": intervention_id,
        "used_interventions": used_interventions,
        "used_interventions_last_10": used_interventions_last_10,
        "exhausted_strategies": exhausted_strategies,
        "turn_family": repair_type,
        "direct_turn_response": True,
        "overthinking_block_turns": next_overthinking_block,
        "overthinking_block_active": bool(next_overthinking_block),
        "conversational_repair": True,
        "repair_type": repair_type,
        "repair_notes": list(repair.get("notes") or []),
        "conversation_frame": conversation_frame,
    }


class NeuroGuiaOrchestratorV2:
    """
    Orquestador principal de NeuroGuIA.

    Objetivos:
    - mantener dominio y fase conversacional entre turnos
    - expandir follow-ups cortos con continuidad semántica
    - coordinar estado, categoría, intención, memoria, decisiones y respuesta
    - permitir progresión real en conversaciones como:
        bloqueo -> bajar fricción -> rutina
        ansiedad -> priorizar -> frase anti saturación
        prevención -> señal temprana -> respuesta temprana -> plan
    """

    STATE_NAME_MAP = {
        "executive_block": "executive_dysfunction",
        "cognitive_anxiety": "cognitive_anxiety",
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

    SHORT_FOLLOWUPS = {
        "si", "sí", "ok", "okay", "va", "aja", "ajá", "de acuerdo",
        "dale", "claro", "yes", "continua", "continúa", "ayudame", "ayúdame"
    }

    FOLLOWUP_ACCEPTANCE_WORDS = {
        "si", "ok", "okay", "va", "aja", "de", "acuerdo",
        "dale", "claro", "yes", "continua", "continuar",
        "continuemos", "sigue", "seguimos", "ayudame", "ayuda",
        "por", "favor",
    }

    FOLLOWUP_REQUIRED_WORDS = {
        "si", "ok", "okay", "va", "dale", "yes", "continua",
        "continuar", "continuemos", "sigue", "seguimos", "ayudame", "ayuda",
    }

    HISTORY_CONTINUITY_MARKERS = {
        "por donde empiezo",
        "por donde comienzo",
        "con que empiezo",
        "como empiezo",
        "que hago",
        "que hago ahora",
        "que hago ahorita",
        "que le digo",
        "que le digo ahora",
        "que le puedo decir",
        "no lo se",
        "no se que hacer",
        "no se como",
        "no tengo una idea clara",
        "no tengo ninguna",
        "no lo tengo claro",
        "no tengo claro",
        "no entiendo",
        "no comprendo",
        "explicamelo",
        "explicame",
        "dilo mas simple",
        "puedes decirlo mas simple",
        "que sigue",
        "y luego",
        "que mas",
        "y ahora",
    }

    DOMAIN_TO_GOAL = {
        "crisis_activa": "contain_and_protect",
        "escalada_emocional": "deescalate_before_peak",
        "prevencion_escalada": "prevent_recurrence",
        "regulacion_post_evento": "repair_and_learn",
        "ansiedad_cognitiva": "reduce_mental_overload",
        "disfuncion_ejecutiva": "enable_first_step",
        "sobrecarga_sensorial": "reduce_stimulus_load",
        "transicion_rigidez": "increase_predictability",
        "sueno_regulacion": "stabilize_sleep_transition",
        "sobrecarga_cuidador": "reduce_caregiver_burden",
        "apoyo_general": "clarify_and_support",
    }

    DOMAIN_TO_PHASE = {
        "crisis_activa": "containment",
        "escalada_emocional": "early_intervention",
        "prevencion_escalada": "mapping_signals",
        "regulacion_post_evento": "repair",
        "ansiedad_cognitiva": "cognitive_unloading",
        "disfuncion_ejecutiva": "micro_start",
        "sobrecarga_sensorial": "environment_adjustment",
        "transicion_rigidez": "anticipation",
        "sueno_regulacion": "wind_down",
        "sobrecarga_cuidador": "relief",
        "apoyo_general": "clarification",
    }

    DOMAIN_SHIFT_KEYWORDS = {
        "crisis_activa": [
            "esta ocurriendo una crisis",
            "no la puedo calmar",
            "no lo puedo calmar",
            "hay riesgo de golpe",
            "se esta golpeando",
            "esta gritando y golpeando",
        ],
        "sueno_regulacion": [
            "no estoy durmiendo bien",
            "no estoy durmiendo",
            "no duermo bien",
            "no he dormido bien",
            "no ha dormido",
            "no duerme bien",
            "el cansancio me esta pegando mucho",
            "me esta pegando mucho el cansancio",
        ],
        "sobrecarga_cuidador": [
            "me esta pesando cuidar",
            "ya no puedo con esto",
            "me rebasa cuidar",
            "estoy agotada de cuidar",
            "estoy agotado de cuidar",
        ],
        "apoyo_general": [
            "dolor", "me duele", "enfermedad", "enferma", "enfermo",
        ],
    }

    def __init__(self, db_path: str = "neuroguia.db") -> None:
        self.db_path = db_path

        self.profile_manager = ProfileManager(db_path=db_path)
        self.exceptionality_mapper = ExceptionalityMapper()
        self.state_guardian = StateGuardian()
        self.case_memory = CaseMemory(db_path=db_path)
        self.response_memory = ResponseMemory(db_path=db_path)
        self.user_context_memory = UserContextMemory(db_path=db_path)
        self.conversation_curation = ConversationCuration(db_path=db_path)

        self.category_router = CategoryRouter()
        self.intent_router = IntentRouter()
        self.conversation_stages = ConversationStages()
        self.conversational_intent_builder = ConversationalIntentBuilder()
        self.confidence_engine = ConfidenceEngine()
        self.decision_engine = DecisionEngine()
        self.fallback_manager = FallbackManager()
        self.routine_builder = RoutineBuilder()
        self.response_builder = ResponseBuilder()
        self.response_curator = ResponseCurator()
        self.support_flow_engine = SupportFlowEngine()
        self.llm_gateway = LLMGateway()
        self.learning_engine = LearningEngine()
        self.expert_mode_adapter = ExpertModeAdapter()

    # =========================================================
    # API PRINCIPAL
    # =========================================================
    def process_message(
        self,
        message: str,
        family_id: Optional[str] = None,
        profile_id: Optional[str] = None,
        profile_alias: Optional[str] = None,
        caregiver_capacity: Optional[float] = None,
        emotional_intensity: Optional[float] = None,
        tags: Optional[List[str]] = None,
        extra_context: Optional[Dict[str, Any]] = None,
        chat_history: Optional[List[Dict[str, Any]]] = None,
        auto_save_case: bool = True,
        auto_store_system_response: bool = False,
        auto_store_curated_llm_response: bool = True,
        use_llm_stub: bool = False,
    ) -> Dict[str, Any]:
        extra_context = extra_context or {}
        tags = tags or []
        chat_history = chat_history or []
        session_scope_id = str(extra_context.get("session_scope_id") or "").strip() or None
        user_context_payload = self._empty_user_context_payload(session_scope_id=session_scope_id)
        user_context_store_result = {
            "stored": False,
            "reason": "not_attempted",
            "payload": None,
        }
        conversation_curation_result = {
            "stored": False,
            "reason": "not_attempted",
            "curation_id": None,
        }
        unit_context = self._resolve_unit_context(family_id=family_id)

        # -----------------------------------------------------
        # 0) MARCO PREVIO DE CONVERSACIÓN
        # -----------------------------------------------------
        previous_frame = self._infer_previous_conversation_frame(
            chat_history=chat_history,
            extra_context=extra_context,
        )

        context_override = self._detect_context_override(
            message=message,
            chat_history=chat_history,
            previous_frame=previous_frame,
        )
        effective_message = context_override.get("effective_message") or message
        conversational_repair = resolve_conversational_repair(
            message=message,
            previous_frame=previous_frame,
            recent_messages=chat_history,
        )
        if conversational_repair.get("handled"):
            stable_repair = stable_demo_repair_response(
                message=message,
                previous_frame=previous_frame,
                repair=conversational_repair,
                chat_history=chat_history,
            )
            if stable_repair.get("handled"):
                return self._build_stable_demo_process_result(
                    stable_demo=stable_repair,
                    message=message,
                    effective_message=effective_message,
                    previous_frame=previous_frame,
                    context_override=context_override,
                    unit_context=unit_context,
                    user_context_payload=user_context_payload,
                    user_context_store_result=user_context_store_result,
                    conversation_curation_result=conversation_curation_result,
                    session_scope_id=session_scope_id,
                    chat_history=chat_history,
                    chat_history_size=len(chat_history or []),
                )
        stable_demo = stable_demo_response(
            message=message,
            previous_frame=previous_frame,
            chat_history=chat_history,
            variant_seed=session_scope_id,
        )
        if stable_demo.get("handled"):
            return self._build_stable_demo_process_result(
                stable_demo=stable_demo,
                message=message,
                effective_message=effective_message,
                previous_frame=previous_frame,
                context_override=context_override,
                unit_context=unit_context,
                user_context_payload=user_context_payload,
                user_context_store_result=user_context_store_result,
                conversation_curation_result=conversation_curation_result,
                session_scope_id=session_scope_id,
                chat_history=chat_history,
                chat_history_size=len(chat_history or []),
            )

        # -----------------------------------------------------
        # 1) PERFIL ACTIVO
        # -----------------------------------------------------
        active_profile = self.profile_manager.resolve_active_profile(
            family_id=family_id,
            profile_id=profile_id,
            profile_alias=profile_alias or extra_context.get("profile_alias"),
            message=effective_message,
        )

        if active_profile:
            exceptionality_analysis = self.exceptionality_mapper.analyze_profile(active_profile)
            support_plan = self.exceptionality_mapper.map_profile_to_support_plan(active_profile)
        else:
            exceptionality_analysis = self._empty_exceptionality_analysis()
            support_plan = self._empty_support_plan()

        # -----------------------------------------------------
        # 2) ESTADO FUNCIONAL
        # -----------------------------------------------------
        merged_context = dict(unit_context)
        merged_context.update(extra_context)

        state_analysis = self._build_state_analysis(
            message=effective_message,
            extra_context=merged_context,
        )

        derived_emotional_intensity = (
            emotional_intensity
            if emotional_intensity is not None
            else self._estimate_emotional_intensity(state_analysis)
        )

        derived_caregiver_capacity = (
            caregiver_capacity
            if caregiver_capacity is not None
            else self._estimate_caregiver_capacity(state_analysis)
        )

        # -----------------------------------------------------
        # 3) CATEGORÍA + INTENCIÓN
        # -----------------------------------------------------
        category_analysis = self._canonicalize_category_analysis(
            self.category_router.route(
                message=effective_message,
                state_analysis=state_analysis,
                intent_analysis=None,
                history_hint=chat_history,
                profile=active_profile,
                extra_context=merged_context,
            )
        )

        intent_analysis = self.intent_router.route(
            message=effective_message,
            state_analysis=state_analysis,
            category_analysis=category_analysis,
            history_hint=chat_history,
            extra_context=merged_context,
            profile=active_profile,
        )

        conversation_control = self._build_conversation_control(
            source_message=message,
            effective_message=effective_message,
            previous_frame=previous_frame,
            context_override=context_override,
            state_analysis=state_analysis,
            category_analysis=category_analysis,
            intent_analysis=intent_analysis,
            chat_history=chat_history,
            active_profile=active_profile,
            unit_context=unit_context,
            extra_context=extra_context,
        )

        # -----------------------------------------------------
        # 4) MARCO CONVERSACIONAL ACTUAL
        # -----------------------------------------------------
        conversation_frame = self._build_conversation_frame(
            source_message=message,
            effective_message=effective_message,
            chat_history=chat_history,
            previous_frame=previous_frame,
            context_override=context_override,
            state_analysis=state_analysis,
            category_analysis=category_analysis,
            intent_analysis=intent_analysis,
            active_profile=active_profile,
            unit_context=unit_context,
            extra_context=extra_context,
            conversation_control=conversation_control,
        )

        flow_result = self.support_flow_engine.resolve_turn(
            source_message=message,
            effective_message=effective_message,
            previous_frame=previous_frame,
            conversation_frame=conversation_frame,
            conversation_control=conversation_control,
            state_analysis=state_analysis,
            category_analysis=category_analysis,
            intent_analysis=intent_analysis,
            chat_history=chat_history,
        )
        support_flow_payloads = (
            self.support_flow_engine.build_orchestrator_payloads(flow_result)
            if flow_result.handled
            else {}
        )
        if support_flow_payloads:
            conversation_control.update(
                support_flow_payloads.get("conversation_control_updates", {}) or {}
            )
            conversation_frame.update(
                support_flow_payloads.get("conversation_frame_updates", {}) or {}
            )

        effective_family_id = family_id or (active_profile.get("family_id") if active_profile else None)
        effective_profile_id = active_profile.get("profile_id") if active_profile else None

        try:
            user_context_payload = self.user_context_memory.build_live_context_payload(
                profile_id=effective_profile_id,
                family_id=effective_family_id,
                session_scope_id=session_scope_id,
            )
        except Exception as exc:
            user_context_payload = self._empty_user_context_payload(
                session_scope_id=session_scope_id,
                reason=f"user_context_memory_unavailable:{type(exc).__name__}",
            )

        # -----------------------------------------------------
        # 5) CONTEXTO DE CASO BASE
        # -----------------------------------------------------
        case_context = {
            "unit_type": unit_context.get("unit_type", "individual"),
            "caregiver_capacity": derived_caregiver_capacity,
            "emotional_intensity": derived_emotional_intensity,
            "followup_needed": state_analysis.get("followup_needed", False),
            "context_notes": unit_context.get("context_notes", ""),
            "support_network": unit_context.get("support_network", ""),
            "user_extra_context": extra_context.get("user_extra_context", ""),
            "conversation_domain": conversation_frame.get("conversation_domain"),
            "support_goal": conversation_frame.get("support_goal"),
            "conversation_phase": conversation_frame.get("conversation_phase"),
            "speaker_role": conversation_frame.get("speaker_role"),
            "care_context": conversation_frame.get("care_context"),
            "conversation_frame": conversation_frame,
            "conversation_control": conversation_control,
            "support_flow_response_plan": support_flow_payloads.get("support_flow_response_plan", {}),
            "domain_shift_detected": conversation_frame.get("domain_shift_detected", False),
            "is_followup_acceptance": conversation_control.get("turn_type") == "followup_acceptance",
            "context_override": context_override,
            "user_context_memory": user_context_payload,
        }

        # -----------------------------------------------------
        # 6) MODO EXPERTO ADAPTATIVO (PRELIMINAR)
        # -----------------------------------------------------
        expert_adaptation_plan = self.expert_mode_adapter.build_adaptation_plan(
            conversation_frame=conversation_frame,
            state_analysis=state_analysis,
            category_analysis=category_analysis,
            intent_analysis=intent_analysis,
            stage_result={},
            active_profile=active_profile,
            case_context=case_context,
        )
        case_context["expert_adaptation_plan"] = expert_adaptation_plan

        # -----------------------------------------------------
        # 7) MEMORIA
        # -----------------------------------------------------
        memory_summary = self._build_memory_summary(
            family_id=family_id,
            profile_id=active_profile.get("profile_id") if active_profile else None,
            unit_type=unit_context.get("unit_type", "individual"),
        )

        memory_payload = self.case_memory.build_contextual_recommendation_payload(
            profile_id=active_profile.get("profile_id") if active_profile else None,
            family_id=family_id,
            detected_category=category_analysis.get("detected_category"),
            primary_state=state_analysis.get("primary_state"),
            suggested_routine_type=None,
            tags=tags,
            limit=8,
        )
        memory_payload = self._merge_user_context_into_memory_payload(
            memory_payload=memory_payload,
            user_context_payload=user_context_payload,
        )

        conditions_signature = active_profile.get("conditions", []) if active_profile else []
        complexity_signature = support_plan.get("complexity_level")

        response_memory_payload = self.response_memory.build_reuse_payload(
            detected_intent=intent_analysis.get("detected_intent"),
            detected_category=category_analysis.get("detected_category"),
            primary_state=state_analysis.get("primary_state"),
            conversation_stage=conversation_frame.get("conversation_phase"),
            complexity_signature=complexity_signature,
            conditions_signature=conditions_signature,
            profile_id=active_profile.get("profile_id") if active_profile else None,
            family_id=family_id,
            tags=tags,
            min_reuse_score=0.50,
        )

        # -----------------------------------------------------
        # 8) ETAPA CONVERSACIONAL
        # -----------------------------------------------------
        if support_flow_payloads:
            stage_result = dict(support_flow_payloads.get("stage_result", {}))
            stage_result["intervention_level"] = self._coerce_intervention_level(
                stage_result.get("intervention_level")
            )
        else:
            stage_result = self.conversation_stages.determine_stage(
                message=effective_message,
                state_analysis=state_analysis,
                category_analysis=category_analysis,
                intent_analysis=intent_analysis,
                case_context=case_context,
                memory_summary=memory_summary,
                memory_payload=memory_payload,
                response_memory_payload=response_memory_payload,
            )

        # =====================================================
        # AJUSTE CRÍTICO:
        # si conversation_stages devuelve continuity_phase,
        # se impone sobre la fase previa del conversation_frame.
        # =====================================================
        continuity_phase = stage_result.get("continuity_phase")
        if continuity_phase:
            conversation_control["domain"] = stage_result.get("conversation_domain") or conversation_control.get("domain")
            conversation_control["turn_type"] = stage_result.get("turn_type") or conversation_control.get("turn_type")
            conversation_control["turn_family"] = stage_result.get("turn_family") or conversation_control.get("turn_family")
            conversation_control["context_override"] = stage_result.get("context_override") or conversation_control.get("context_override")
            conversation_control["clarification_mode"] = stage_result.get("clarification_mode") or conversation_control.get("clarification_mode")
            conversation_control["crisis_guided_mode"] = stage_result.get("crisis_guided_mode") or conversation_control.get("crisis_guided_mode")
            conversation_control["domain_shift"] = stage_result.get("domain_shift") or conversation_control.get("domain_shift", {})
            conversation_control["phase"] = continuity_phase
            conversation_control["phase_progression_reason"] = stage_result.get("phase_progression_reason")
            conversation_frame["conversation_phase"] = continuity_phase
            conversation_frame["phase_progression_reason"] = stage_result.get("phase_progression_reason")
            if stage_result.get("phase_changed"):
                conversation_frame["continuity_score"] = max(
                    float(conversation_frame.get("continuity_score", 0.0) or 0.0),
                    0.94,
                )

        conversation_frame["turn_type"] = conversation_control.get("turn_type")
        conversation_frame["turn_family"] = conversation_control.get("turn_family")
        conversation_frame["context_override"] = conversation_control.get("context_override") or conversation_frame.get("context_override")
        conversation_frame["clarification_mode"] = conversation_control.get("clarification_mode")
        conversation_frame["crisis_guided_mode"] = conversation_control.get("crisis_guided_mode")
        conversation_frame["domain_shift_analysis"] = conversation_control.get("domain_shift", {})
        conversation_frame["domain_shift_detected"] = bool(
            (conversation_control.get("domain_shift", {}) or {}).get("detected")
        )
        conversation_control["intervention_level"] = (
            self._coerce_intervention_level(stage_result.get("intervention_level"))
            or self._coerce_intervention_level(conversation_control.get("intervention_level"))
        )
        conversation_control["stuck_followup_count"] = stage_result.get("stuck_followup_count") or conversation_control.get("stuck_followup_count", 0)
        conversation_control["progression_signals"] = stage_result.get("progression_signals") or conversation_control.get("progression_signals", {})
        conversation_frame["intervention_level"] = conversation_control.get("intervention_level")
        conversation_frame["stuck_followup_count"] = conversation_control.get("stuck_followup_count", 0)
        conversation_frame["progression_signals"] = conversation_control.get("progression_signals", {})

        case_context["conversation_phase"] = conversation_frame.get("conversation_phase")
        case_context["conversation_frame"] = conversation_frame
        case_context["conversation_control"] = conversation_control

        if support_flow_payloads:
            stage_hints = dict(support_flow_payloads.get("stage_hints", {}))
        else:
            stage_hints = self.conversation_stages.build_stage_prompt_hints(stage_result)

        # -----------------------------------------------------
        # 9) RECONSTRUIR MODO EXPERTO YA CON PHASE FINAL
        # -----------------------------------------------------
        expert_adaptation_plan = self.expert_mode_adapter.build_adaptation_plan(
            conversation_frame=conversation_frame,
            state_analysis=state_analysis,
            category_analysis=category_analysis,
            intent_analysis=intent_analysis,
            stage_result=stage_result,
            active_profile=active_profile,
            case_context=case_context,
        )
        case_context["expert_adaptation_plan"] = expert_adaptation_plan

        # -----------------------------------------------------
        # 10) RUTINA
        # -----------------------------------------------------
        if support_flow_payloads:
            routine_payload = {}
        else:
            routine_payload = self.routine_builder.build_routine(
                profile=active_profile,
                state_analysis=state_analysis,
                stage_result=stage_result,
                memory_payload=memory_payload,
                routine_type=None,
                caregiver_capacity=derived_caregiver_capacity,
                emotional_intensity=derived_emotional_intensity,
                context={
                    "detected_category": category_analysis.get("detected_category"),
                    "sleep_profile": active_profile.get("sleep_profile") if active_profile else None,
                    "support_network": unit_context.get("support_network"),
                    "text_hint": effective_message,
                    "conversation_domain": conversation_frame.get("conversation_domain"),
                    "support_goal": conversation_frame.get("support_goal"),
                    "conversation_phase": conversation_frame.get("conversation_phase"),
                    "expert_adaptation_plan": expert_adaptation_plan,
                    **extra_context,
                },
            )

        # -----------------------------------------------------
        # 11) CONFIANZA
        # -----------------------------------------------------
        if support_flow_payloads:
            confidence_payload = dict(support_flow_payloads.get("confidence_payload", {}))
        else:
            confidence_payload = self.confidence_engine.evaluate(
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

        # -----------------------------------------------------
        # 12) DECISIÓN
        # -----------------------------------------------------
        if support_flow_payloads:
            decision_payload = dict(support_flow_payloads.get("decision_payload", {}))
            response_goal = dict(decision_payload.get("response_goal", {}) or {})
            if response_goal:
                response_goal["intervention_level"] = self._coerce_intervention_level(
                    response_goal.get("intervention_level")
                )
                decision_payload["response_goal"] = response_goal
                decision_payload["response_plan"] = dict(response_goal)
            conversational_intent = dict(
                support_flow_payloads.get("conversational_intent", {})
            )
        else:
            decision_payload = self.decision_engine.decide(
                intent_analysis=intent_analysis,
                category_analysis=category_analysis,
                state_analysis=state_analysis,
                support_plan=support_plan,
                stage_result=stage_result,
                confidence_payload=confidence_payload,
                memory_payload=memory_payload,
                response_memory_payload=response_memory_payload,
                routine_payload=routine_payload,
                case_context=case_context,
            )
            conversational_intent = self.conversational_intent_builder.build(
                stage_result=stage_result,
                decision_payload=decision_payload,
                state_analysis=state_analysis,
                category_analysis=category_analysis,
                intent_analysis=intent_analysis,
                case_context=case_context,
            )
        case_context["conversational_intent"] = conversational_intent

        # -----------------------------------------------------
        # 13) POLÍTICA DE FALLBACK / LLM
        # -----------------------------------------------------
        if support_flow_payloads:
            fallback_payload = dict(support_flow_payloads.get("fallback_payload", {}))
            llm_policy = dict(support_flow_payloads.get("llm_policy", {}))
        else:
            fallback_payload = self.fallback_manager.evaluate(
                decision_payload=decision_payload,
                confidence_payload=confidence_payload,
                response_memory_payload=response_memory_payload,
                state_analysis=state_analysis,
                category_analysis=category_analysis,
                intent_analysis=intent_analysis,
                stage_result=stage_result,
                routine_payload=routine_payload,
                case_context=case_context,
            )

            llm_policy = self._build_llm_policy(
                source_message=message,
                effective_message=effective_message,
                chat_history=chat_history,
                conversation_frame=conversation_frame,
                state_analysis=state_analysis,
                category_analysis=category_analysis,
                intent_analysis=intent_analysis,
                stage_result=stage_result,
                confidence_payload=confidence_payload,
                decision_payload=decision_payload,
                fallback_payload=fallback_payload,
            )

        # -----------------------------------------------------
        # 14) LLM
        # -----------------------------------------------------
        llm_request_payload = None
        llm_result = None
        llm_curated_payload = None
        llm_should_run = False

        llm_should_run = bool(
            fallback_payload.get("use_llm") or llm_policy.get("should_use_llm")
        )

        if llm_should_run:
            llm_request_payload = self.llm_gateway.build_request(
                message=effective_message,
                fallback_payload={
                    **fallback_payload,
                    "use_llm": True,
                    "fallback_reason": llm_policy.get("reason") or fallback_payload.get("fallback_reason"),
                    "prompt_mode": fallback_payload.get("prompt_mode", "controlled_support_generation"),
                    "should_learn_if_good": fallback_payload.get("should_learn_if_good", False),
                },
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
                case_context={
                    **case_context,
                    "conversation_frame": conversation_frame,
                    "conversation_control": conversation_control,
                    "conversational_intent": conversational_intent,
                    "llm_policy": llm_policy,
                    "expert_adaptation_plan": expert_adaptation_plan,
                },
                chat_history=chat_history,
            )

            if llm_request_payload.get("allowed"):
                if support_flow_payloads and use_llm_stub:
                    llm_result = None
                elif use_llm_stub:
                    llm_result = self.llm_gateway.build_local_stub_response(
                        llm_request_payload.get("request_payload") or {}
                    )
                else:
                    if hasattr(self.llm_gateway, "run"):
                        llm_result = self.llm_gateway.run(
                            llm_request_payload.get("request_payload") or {}
                        )
                    else:
                        llm_result = self.llm_gateway.build_local_stub_response(
                            llm_request_payload.get("request_payload") or {}
                        )

                if not support_flow_payloads and llm_result is not None:
                    llm_curated_payload = self.response_curator.curate(
                        llm_result=llm_result,
                        fallback_payload={
                            **fallback_payload,
                            "use_llm": True,
                            "fallback_reason": llm_policy.get("reason") or fallback_payload.get("fallback_reason"),
                            "should_learn_if_good": fallback_payload.get("should_learn_if_good", False),
                        },
                        decision_payload=decision_payload,
                        stage_result=stage_result,
                        state_analysis=state_analysis,
                        category_analysis=category_analysis,
                        intent_analysis=intent_analysis,
                        routine_payload=routine_payload,
                        conversation_control=conversation_control,
                        conversation_frame=conversation_frame,
                        chat_history=chat_history,
                    )

        # -----------------------------------------------------
        # 15) RESPUESTA FINAL
        # -----------------------------------------------------
        if support_flow_payloads:
            response_package = dict(support_flow_payloads.get("response_package", {}))
            llm_curated_payload = self.response_curator.humanize_support_flow_response(
                response_package=response_package,
                support_flow_response_plan=support_flow_payloads.get("support_flow_response_plan", {}),
                llm_result=llm_result,
                conversation_control=conversation_control,
                conversation_frame=conversation_frame,
                chat_history=chat_history,
            )
            humanized_text = str(llm_curated_payload.get("curated_response_text") or "").strip()
            if humanized_text:
                response_package["response"] = humanized_text
                response_package["text"] = humanized_text
            response_metadata = dict(response_package.get("response_metadata", {}) or {})
            response_metadata.update(
                {
                    "humanization_provider": llm_curated_payload.get("source_provider"),
                    "humanization_used_llm": bool(llm_curated_payload.get("used_llm", False)),
                    "humanization_used_local_humanizer": bool(
                        llm_curated_payload.get("used_local_humanizer", False)
                    ),
                    "humanization_notes": list(llm_curated_payload.get("curation_notes", []) or []),
                }
            )
            response_package["response_metadata"] = response_metadata
        else:
            rb_input = self._build_response_builder_input(
                decision_payload=decision_payload,
                stage_result=stage_result,
                response_memory_payload=response_memory_payload,
            )

            response_package = self.response_builder.build(
                decision_payload=decision_payload,
                state_analysis=state_analysis,
                stage_result=rb_input["stage_result"],
                routine_payload=routine_payload,
                response_memory_payload=rb_input["response_memory_payload"],
                fallback_payload={
                    **fallback_payload,
                    "use_llm": llm_should_run,
                    "fallback_reason": llm_policy.get("reason") or fallback_payload.get("fallback_reason"),
                },
                llm_curated_payload=llm_curated_payload,
                category_analysis=category_analysis,
                intent_analysis=intent_analysis,
                source_message=message,
                effective_message=effective_message,
                chat_history=chat_history,
                conversation_frame=conversation_frame,
                llm_policy=llm_policy,
                expert_adaptation_plan=expert_adaptation_plan,
                conversational_intent=conversational_intent,
            )

        conversation_control["last_guided_action"] = (
            response_package.get("suggested_microaction")
            or decision_payload.get("selected_microaction")
            or conversation_control.get("last_guided_action")
        )
        last_action_state = self._resolve_last_action_state(
            response_package=response_package,
            decision_payload=decision_payload,
        )
        response_goal = decision_payload.get("response_goal", {}) or {}
        current_strategy_signature = response_goal.get("strategy_signature") or response_goal.get("goal")
        previous_strategy_signature = previous_frame.get("last_strategy_signature")
        previous_strategy_repeat_count = int(previous_frame.get("strategy_repeat_count", 0) or 0)
        recent_strategy_history = list(previous_frame.get("recent_strategy_history") or [])
        strategy_repeat_count = (
            previous_strategy_repeat_count + 1
            if current_strategy_signature and current_strategy_signature == previous_strategy_signature
            else 0
        )
        current_history_entry = {
            "strategy_signature": current_strategy_signature,
            "response_shape": response_goal.get("response_shape"),
            "response_goal": response_goal.get("goal"),
            "turn_family": conversation_control.get("turn_family"),
            "form_variant": response_goal.get("form_variant"),
        }
        recent_strategy_history = [
            item
            for item in recent_strategy_history
            if isinstance(item, dict)
        ]
        recent_strategy_history.append(current_history_entry)
        recent_strategy_history = recent_strategy_history[-4:]
        conversation_control["intervention_level"] = (
            self._coerce_intervention_level(response_goal.get("intervention_level"))
            or self._coerce_intervention_level(conversation_control.get("intervention_level"))
        )
        conversation_control["last_strategy_signature"] = current_strategy_signature
        conversation_control["last_response_shape"] = response_goal.get("response_shape")
        conversation_control["response_form_variant"] = response_goal.get("form_variant")
        conversation_control["strategy_repeat_count"] = strategy_repeat_count
        conversation_control["recent_strategy_history"] = recent_strategy_history
        conversation_control["last_action_instruction"] = last_action_state.get("last_action_instruction")
        conversation_control["last_action_type"] = last_action_state.get("last_action_type")
        conversation_frame["last_guided_action"] = conversation_control.get("last_guided_action")
        conversation_frame["last_action_instruction"] = conversation_control.get("last_action_instruction")
        conversation_frame["last_action_type"] = conversation_control.get("last_action_type")
        conversation_frame["phase_progression_reason"] = stage_result.get("phase_progression_reason")
        conversation_frame["intervention_level"] = conversation_control.get("intervention_level")
        conversation_frame["last_strategy_signature"] = conversation_control.get("last_strategy_signature")
        conversation_frame["last_response_shape"] = conversation_control.get("last_response_shape")
        conversation_frame["response_form_variant"] = conversation_control.get("response_form_variant")
        conversation_frame["strategy_repeat_count"] = conversation_control.get("strategy_repeat_count")
        conversation_frame["recent_strategy_history"] = conversation_control.get("recent_strategy_history")
        conversation_frame["context_override"] = conversation_control.get("context_override") or conversation_frame.get("context_override")
        case_context["conversation_control"] = conversation_control
        case_context["conversation_frame"] = conversation_frame
        case_context["context_override"] = conversation_control.get("context_override")

        # -----------------------------------------------------
        # 16) GUARDADO DEL CASO
        # -----------------------------------------------------
        saved_case_id = None
        if auto_save_case:
            saved_case_id = self.case_memory.create_case(
                family_id=family_id,
                profile_id=active_profile.get("profile_id") if active_profile else None,
                unit_type=unit_context.get("unit_type", "individual"),
                raw_input=message,
                normalized_summary=self._normalize_summary(effective_message),
                detected_category=category_analysis.get("detected_category"),
                detected_stage=stage_result.get("stage"),
                primary_state=state_analysis.get("primary_state"),
                secondary_states=state_analysis.get("secondary_states", []),
                emotional_intensity=derived_emotional_intensity,
                caregiver_capacity=derived_caregiver_capacity,
                sensory_overload_risk=self._state_score(state_analysis, "sensory_overload"),
                executive_block_risk=self._state_score(state_analysis, "executive_dysfunction"),
                meltdown_risk=self._state_score(state_analysis, "meltdown"),
                shutdown_risk=self._state_score(state_analysis, "shutdown"),
                burnout_risk=self._state_score(state_analysis, "burnout"),
                sleep_disruption_risk=self._state_score(state_analysis, "sleep_disruption"),
                suggested_strategy=decision_payload.get("selected_strategy"),
                suggested_microaction=decision_payload.get("selected_microaction"),
                suggested_routine_type=decision_payload.get("selected_routine_type"),
                response_mode=decision_payload.get("decision_mode"),
                followup_needed=stage_result.get("should_close_with_followup", False),
                tags=self._deduplicate(
                    tags
                    + [conversation_frame.get("conversation_domain") or ""]
                    + [conversation_frame.get("speaker_role") or ""]
                    + [conversation_frame.get("conversation_phase") or ""]
                ),
            )

        # -----------------------------------------------------
        # 17) GUARDADO OPCIONAL DE RESPUESTA LOCAL
        # -----------------------------------------------------
        stored_response_id = None
        if (
            auto_store_system_response
            and response_package.get("mode") == "system_generated"
            and response_package.get("response")
        ):
            stored_response_id = self.response_memory.create_from_system_response(
                response_text=response_package["response"],
                detected_intent=intent_analysis.get("detected_intent"),
                detected_category=category_analysis.get("detected_category"),
                primary_state=state_analysis.get("primary_state"),
                conversation_stage=conversation_frame.get("conversation_phase"),
                profile_id=active_profile.get("profile_id") if active_profile else None,
                family_id=family_id,
                conditions_signature=conditions_signature,
                complexity_signature=complexity_signature,
                response_structure_json={
                    "mode": response_package.get("mode"),
                    "strategy": decision_payload.get("selected_strategy"),
                    "microaction": decision_payload.get("selected_microaction"),
                    "routine_type": decision_payload.get("selected_routine_type"),
                    "conversation_domain": conversation_frame.get("conversation_domain"),
                    "support_goal": conversation_frame.get("support_goal"),
                    "conversation_phase": conversation_frame.get("conversation_phase"),
                    "expert_adaptation_plan": expert_adaptation_plan,
                    "response_metadata": response_package.get("response_metadata", {}),
                },
                confidence_score=confidence_payload.get("overall_confidence"),
                approved_for_reuse=False,
                tags=self._deduplicate(
                    tags
                    + [conversation_frame.get("conversation_domain") or ""]
                    + [conversation_frame.get("conversation_phase") or ""]
                ),
                origin_case_id=saved_case_id,
                notes="system_generated_auto_store",
            )

        # -----------------------------------------------------
        # 18) APRENDIZAJE Y GUARDADO LLM CURADO
        # -----------------------------------------------------
        curated_llm_response_id = None
        learning_payload = None
        learning_store_result = None

        if auto_store_curated_llm_response and llm_curated_payload:
            learning_payload = self.learning_engine.build_learning_payload(
                llm_curated_payload=llm_curated_payload,
                conversation_frame=conversation_frame,
                decision_payload=decision_payload,
                state_analysis=state_analysis,
                category_analysis=category_analysis,
                intent_analysis=intent_analysis,
                stage_result=stage_result,
                active_profile=active_profile,
                case_id=saved_case_id,
                family_id=family_id,
                tags=tags,
            )

            learning_store_result = self.learning_engine.try_store_in_response_memory(
                response_memory=self.response_memory,
                learning_payload=learning_payload,
            )

            if learning_store_result.get("stored"):
                curated_llm_response_id = learning_store_result.get("response_id")

        # -----------------------------------------------------
        # 19) MEMORIA CONTEXTUAL + CURACION SUPERVISADA
        # -----------------------------------------------------
        try:
            user_context_store_result = self.user_context_memory.register_turn_context(
                source_message=message,
                family_id=effective_family_id,
                profile_id=effective_profile_id,
                session_scope_id=session_scope_id,
                extra_context=extra_context,
                conversation_frame=conversation_frame,
                category_analysis=category_analysis,
                intent_analysis=intent_analysis,
                state_analysis=state_analysis,
                confidence_payload=confidence_payload,
                decision_payload=decision_payload,
                memory_payload=memory_payload,
                response_memory_payload=response_memory_payload,
                llm_curated_payload=llm_curated_payload,
                source_case_id=saved_case_id,
            )
        except Exception as exc:
            user_context_store_result = {
                "stored": False,
                "reason": f"user_context_store_failed:{type(exc).__name__}",
                "payload": None,
            }

        try:
            conversation_curation_result = self.conversation_curation.register_curatable_turn(
                source_message=message,
                family_id=effective_family_id,
                profile_id=effective_profile_id,
                session_scope_id=session_scope_id,
                source_case_id=saved_case_id,
                conversation_frame=conversation_frame,
                category_analysis=category_analysis,
                intent_analysis=intent_analysis,
                state_analysis=state_analysis,
                confidence_payload=confidence_payload,
                decision_payload=decision_payload,
                stage_result=stage_result,
                response_package=response_package,
                response_memory_payload=response_memory_payload,
                llm_result=llm_result,
                llm_curated_payload=llm_curated_payload,
            )
        except Exception as exc:
            conversation_curation_result = {
                "stored": False,
                "reason": f"conversation_curation_failed:{type(exc).__name__}",
                "curation_id": None,
            }

        return {
            "case_id": saved_case_id,
            "stored_response_id": stored_response_id,
            "curated_llm_response_id": curated_llm_response_id,
            "learning_payload": learning_payload,
            "learning_store_result": learning_store_result,
            "unit_context": unit_context,
            "active_profile": active_profile,
            "exceptionality_analysis": exceptionality_analysis,
            "support_plan": support_plan,
            "conversation_control": conversation_control,
            "conversation_frame": conversation_frame,
            "conversational_intent": conversational_intent,
            "expert_adaptation_plan": expert_adaptation_plan,
            "state_analysis": state_analysis,
            "category_analysis": category_analysis,
            "intent_analysis": intent_analysis,
            "memory_summary": memory_summary,
            "memory_payload": memory_payload,
            "user_context_payload": user_context_payload,
            "user_context_store_result": user_context_store_result,
            "response_memory_payload": response_memory_payload,
            "stage_result": stage_result,
            "stage_hints": stage_hints,
            "routine_payload": routine_payload,
            "confidence_payload": confidence_payload,
            "decision_payload": decision_payload,
            "fallback_payload": fallback_payload,
            "llm_policy": llm_policy,
            "llm_request_payload": llm_request_payload,
            "llm_result": llm_result,
            "llm_curated_payload": llm_curated_payload,
            "conversation_curation_result": conversation_curation_result,
            "session_scope_id": session_scope_id,
            "response_package": response_package,
        }

    def _build_stable_demo_process_result(
        self,
        stable_demo: Dict[str, Any],
        message: str,
        effective_message: str,
        previous_frame: Dict[str, Any],
        context_override: Dict[str, Any],
        unit_context: Dict[str, Any],
        user_context_payload: Dict[str, Any],
        user_context_store_result: Dict[str, Any],
        conversation_curation_result: Dict[str, Any],
        session_scope_id: Optional[str],
        chat_history: Optional[List[Dict[str, Any]]] = None,
        chat_history_size: int = 0,
    ) -> Dict[str, Any]:
        chat_history = chat_history or []
        base_response_text = str(stable_demo.get("response_text") or "").strip()
        response_text = base_response_text
        route_id = str(stable_demo.get("route_id") or "").strip()
        support_subject = str(stable_demo.get("support_subject") or "unknown").strip()
        support_mode = str(stable_demo.get("support_mode") or "supportive").strip()
        step_index = int(stable_demo.get("step_index", 0) or 0)
        intervention_id = str(stable_demo.get("intervention_id") or "").strip() or None
        used_interventions = dict(stable_demo.get("used_interventions") or {})
        used_interventions_last_10 = dict(stable_demo.get("used_interventions_last_10") or {})
        conversation_frame = dict(stable_demo.get("conversation_frame") or {})
        support_state_from_frame = dict(conversation_frame.get("support_flow_state") or {})
        exhausted_strategies = dict(
            stable_demo.get("exhausted_strategies")
            or conversation_frame.get("exhausted_strategies")
            or support_state_from_frame.get("exhausted_strategies")
            or {}
        )
        behavioral_plan = dict(stable_demo.get("behavioral_plan") or conversation_frame.get("behavioral_plan") or {})
        if behavioral_plan:
            behavioral_plan["base_guidance"] = base_response_text
            behavioral_plan["recent_user_message"] = message
            if not behavioral_plan.get("recent_context"):
                behavioral_plan["recent_context"] = _stable_demo_recent_context(chat_history)
        conversation_frame["context_override"] = dict(
            context_override
            or self._empty_context_override(
                message=message,
                effective_message=effective_message,
            )
        )
        conversation_frame["effective_message"] = effective_message
        conversation_frame = self._normalize_conversation_frame(conversation_frame)
        conversation_frame["route_id"] = route_id
        conversation_frame["support_subject"] = support_subject
        conversation_frame["support_mode"] = support_mode
        conversation_frame["stable_demo_routing_key"] = f"{route_id}:{support_subject}:{support_mode}"
        conversation_frame["stable_demo_route_id"] = route_id
        conversation_frame["step_index"] = step_index
        conversation_frame["stable_demo_step_index"] = step_index
        conversation_frame["stable_demo_intervention_id"] = intervention_id
        conversation_frame["last_intervention_id"] = intervention_id
        conversation_frame["used_interventions"] = used_interventions
        conversation_frame["used_interventions_last_10"] = used_interventions_last_10
        conversation_frame["exhausted_strategies"] = exhausted_strategies
        conversation_frame["direct_turn_response"] = bool(stable_demo.get("direct_turn_response", False))
        conversation_frame["overthinking_block_turns"] = int(stable_demo.get("overthinking_block_turns", 0) or 0)
        conversation_frame["overthinking_block_active"] = bool(stable_demo.get("overthinking_block_active", False))
        conversation_frame["stable_demo"] = True
        if behavioral_plan:
            conversation_frame["behavioral_plan"] = behavioral_plan

        writer_status = self.llm_gateway.get_openai_writer_status()
        llm_writer_requested = bool(behavioral_plan)
        llm_writer_used = False
        llm_provider = str(writer_status.get("provider") or "openai").strip() or "openai"
        llm_block_reason = None
        llm_curator_status = "not_requested" if not llm_writer_requested else "not_run"
        model_used = str(writer_status.get("model") or "").strip() or None
        response_source = "deterministic"

        llm_request_payload = {
            "allowed": False,
            "reason": "stable_demo_no_behavioral_plan" if not behavioral_plan else (
                writer_status.get("block_reason") or "stable_demo_writer_disabled"
            ),
            "request_payload": None,
        }
        llm_result = None
        llm_curated_payload = None
        if llm_writer_requested:
            if bool(writer_status.get("enabled")):
                llm_request_payload = {
                    "allowed": True,
                    "reason": "stable_demo_behavioral_writer",
                    "request_payload": {"behavioral_plan": behavioral_plan},
                }
                llm_result = self.llm_gateway.rewrite_from_behavioral_plan(behavioral_plan)
                llm_provider = str(
                    (llm_result or {}).get("provider")
                    or writer_status.get("provider")
                    or "openai"
                ).strip() or "openai"
                model_used = str(
                    (llm_result or {}).get("model")
                    or writer_status.get("model")
                    or ""
                ).strip() or None
                llm_curated_payload = self.response_curator.curate_behavioral_plan_response(
                    llm_result=llm_result,
                    behavioral_plan=behavioral_plan,
                )
                llm_curator_status = "approved" if bool((llm_curated_payload or {}).get("approved")) else "rejected"
                curated_text = str(
                    (llm_curated_payload or {}).get("curated_response_text")
                    or ""
                ).strip()
                if bool((llm_curated_payload or {}).get("approved")) and curated_text:
                    response_text = curated_text
                    llm_writer_used = True
                    response_source = "llm_writer"
                else:
                    response_source = "fallback_deterministic"
                    llm_block_reason = _stable_demo_llm_block_reason(
                        llm_result=llm_result,
                        llm_curated_payload=llm_curated_payload,
                        default_reason="curator_rejected",
                    )
            else:
                llm_block_reason = str(
                    writer_status.get("block_reason") or "missing_openai_key_or_disabled"
                )
                llm_curator_status = "not_run"

        if behavioral_plan:
            behavioral_plan["final_response_text"] = response_text
            conversation_frame["behavioral_plan"] = behavioral_plan
            support_state = dict(conversation_frame.get("support_flow_state") or {})
            support_state["behavioral_plan"] = behavioral_plan
            conversation_frame["support_flow_state"] = support_state
        conversation_frame["last_guided_action"] = response_text
        conversation_frame["last_action_instruction"] = base_response_text
        conversation_frame["llm_writer_requested"] = llm_writer_requested
        conversation_frame["llm_writer_used"] = llm_writer_used
        conversation_frame["llm_provider"] = llm_provider
        conversation_frame["llm_block_reason"] = llm_block_reason
        conversation_frame["llm_curator_status"] = llm_curator_status
        conversation_frame["model_used"] = model_used
        conversation_frame["response_source"] = response_source

        conversation_control = {
            "domain": conversation_frame.get("conversation_domain"),
            "route_id": route_id,
            "support_subject": support_subject,
            "support_mode": support_mode,
            "stable_demo_routing_key": conversation_frame.get("stable_demo_routing_key"),
            "stable_demo_route_id": route_id,
            "step_index": step_index,
            "intervention_id": intervention_id,
            "used_interventions": used_interventions,
            "used_interventions_last_10": used_interventions_last_10,
            "exhausted_strategies": exhausted_strategies,
            "direct_turn_response": conversation_frame.get("direct_turn_response", False),
            "overthinking_block_turns": conversation_frame.get("overthinking_block_turns", 0),
            "overthinking_block_active": conversation_frame.get("overthinking_block_active", False),
            "stable_demo": True,
            "turn_type": conversation_frame.get("turn_type") or stable_demo.get("turn_family"),
            "turn_family": conversation_frame.get("turn_family") or stable_demo.get("turn_family"),
            "phase": conversation_frame.get("conversation_phase"),
            "speaker_role": conversation_frame.get("speaker_role"),
            "source_message": message,
            "effective_message": effective_message,
            "chat_history_size": chat_history_size,
            "context_override": conversation_frame.get("context_override"),
            "intervention_level": conversation_frame.get("intervention_level", 1),
            "last_guided_action": response_text,
            "last_action_instruction": base_response_text,
            "last_action_type": "stable_demo_step",
            "phase_progression_reason": "stable_demo_counter",
            "domain_shift": conversation_frame.get("domain_shift_analysis", {}),
            "conversational_repair": conversation_frame.get("conversational_repair", False),
            "repair_type": conversation_frame.get("repair_type"),
            "llm_writer_requested": llm_writer_requested,
            "llm_writer_used": llm_writer_used,
            "llm_provider": llm_provider,
            "llm_block_reason": llm_block_reason,
            "llm_curator_status": llm_curator_status,
            "model_used": model_used,
            "response_source": response_source,
        }

        stage_result = {
            "stage": "stable_demo",
            "conversation_domain": conversation_frame.get("conversation_domain"),
            "conversation_phase": conversation_frame.get("conversation_phase"),
            "route_id": route_id,
            "support_subject": support_subject,
            "support_mode": support_mode,
            "stable_demo_routing_key": conversation_frame.get("stable_demo_routing_key"),
            "step_index": step_index,
            "intervention_id": intervention_id,
            "turn_type": conversation_control.get("turn_type"),
            "turn_family": conversation_control.get("turn_family"),
            "intervention_level": 1,
            "phase_progression_reason": "stable_demo_counter",
            "should_close_with_followup": False,
        }
        response_goal = {
            "goal": STABLE_DEMO_GOALS.get(route_id, "stable_demo_support"),
            "route_id": route_id,
            "support_subject": support_subject,
            "support_mode": support_mode,
            "stable_demo_routing_key": conversation_frame.get("stable_demo_routing_key"),
            "step_index": step_index,
            "intervention_id": intervention_id,
            "response_shape": "direct_deterministic_step",
            "intervention_level": 1,
            "strategy_signature": f"stable_demo:{route_id}:{intervention_id or step_index}",
            "selected_microaction": base_response_text,
        }
        decision_payload = {
            "decision_mode": "stable_demo",
            "selected_strategy": route_id,
            "selected_microaction": base_response_text,
            "selected_routine_type": None,
            "response_goal": response_goal,
            "response_plan": dict(response_goal),
        }
        response_package = {
            "mode": "system_generated",
            "response": response_text,
            "text": response_text,
            "suggested_microaction": base_response_text,
            "route_id": route_id,
            "step_index": step_index,
            "intervention_id": intervention_id,
            "stable_demo": True,
            "llm_writer_requested": llm_writer_requested,
            "llm_writer_used": llm_writer_used,
            "llm_provider": llm_provider,
            "llm_block_reason": llm_block_reason,
            "llm_curator_status": llm_curator_status,
            "model_used": model_used,
            "response_source": response_source,
            "response_metadata": {
                "source": "stable_demo_response",
                "response_source": response_source,
                "route_id": route_id,
                "support_subject": support_subject,
                "support_mode": support_mode,
                "stable_demo_routing_key": conversation_frame.get("stable_demo_routing_key"),
                "step_index": step_index,
                "intervention_id": intervention_id,
                "used_interventions": used_interventions,
                "used_interventions_last_10": used_interventions_last_10,
                "exhausted_strategies": exhausted_strategies,
                "conversational_repair": conversation_frame.get("conversational_repair", False),
                "repair_type": conversation_frame.get("repair_type"),
                "repair_notes": list(conversation_frame.get("repair_notes", []) or []),
                "direct_turn_response": conversation_frame.get("direct_turn_response", False),
                "overthinking_block_turns": conversation_frame.get("overthinking_block_turns", 0),
                "overthinking_block_active": conversation_frame.get("overthinking_block_active", False),
                "llm_writer_requested": llm_writer_requested,
                "llm_writer_used": llm_writer_used,
                "llm_provider": llm_provider,
                "llm_block_reason": llm_block_reason,
                "llm_curator_status": llm_curator_status,
                "model_used": model_used,
                "openai_writer_status": {
                    "enabled": bool(writer_status.get("enabled")),
                    "env_enabled": bool(writer_status.get("env_enabled")),
                    "use_openai_llm_raw": writer_status.get("use_openai_llm_raw"),
                    "has_api_key": bool(writer_status.get("has_api_key")),
                    "model": writer_status.get("model"),
                },
                "used_llm": bool((llm_curated_payload or {}).get("used_llm", False)),
                "used_curator": bool(llm_curated_payload),
                "llm_writer_provider": (llm_curated_payload or {}).get("source_provider"),
                "llm_writer_notes": list((llm_curated_payload or {}).get("curation_notes", []) or []),
                "deterministic_base_guidance": base_response_text,
                "behavioral_plan": behavioral_plan,
                "bypassed_support_flow_engine": True,
                "bypassed_response_curator": not bool(llm_curated_payload),
                "bypassed_fallback": True,
            },
        }
        category_analysis = {
            "detected_category": conversation_frame.get("conversation_domain"),
            "confidence": 1.0,
            "route_id": route_id,
            "source": "stable_demo_response",
        }
        state_analysis = {
            "primary_state": route_id,
            "secondary_states": [],
            "detected_states": [],
            "followup_needed": False,
            "source": "stable_demo_response",
        }
        intent_analysis = {
            "detected_intent": conversation_control.get("turn_family") or "stable_demo",
            "confidence": 1.0,
            "source": "stable_demo_response",
        }
        confidence_payload = {
            "overall_confidence": 1.0,
            "source": "stable_demo_response",
        }
        fallback_payload = {
            "use_llm": bool(llm_writer_requested and writer_status.get("enabled")),
            "fallback_reason": "stable_demo_bypass",
            "should_learn_if_good": False,
            "response_source": response_source,
            "llm_writer_requested": llm_writer_requested,
            "llm_writer_used": llm_writer_used,
            "llm_provider": llm_provider,
            "llm_block_reason": llm_block_reason,
            "llm_curator_status": llm_curator_status,
            "model_used": model_used,
        }
        llm_policy = {
            "should_use_llm": bool(llm_writer_requested and writer_status.get("enabled")),
            "reason": "stable_demo_behavioral_writer" if behavioral_plan else "stable_demo_bypass",
            "response_source": response_source,
            "llm_writer_requested": llm_writer_requested,
            "llm_writer_used": llm_writer_used,
            "llm_provider": llm_provider,
            "llm_block_reason": llm_block_reason,
            "llm_curator_status": llm_curator_status,
            "model_used": model_used,
        }
        conversational_intent = {
            "intent": "stable_demo_direct_response",
            "route_id": route_id,
            "step_index": step_index,
        }
        support_plan = self._empty_support_plan()
        exceptionality_analysis = self._empty_exceptionality_analysis()
        user_context_payload = {
            **(user_context_payload or {}),
            "available": False,
            "reason": "stable_demo_bypass",
            "session_scope_id": session_scope_id,
        }
        user_context_store_result = {
            **(user_context_store_result or {}),
            "stored": False,
            "reason": "stable_demo_bypass",
        }
        conversation_curation_result = {
            **(conversation_curation_result or {}),
            "stored": False,
            "reason": "stable_demo_bypass",
            "curation_id": None,
        }

        return {
            "case_id": None,
            "stored_response_id": None,
            "curated_llm_response_id": None,
            "learning_payload": None,
            "learning_store_result": None,
            "unit_context": unit_context,
            "active_profile": None,
            "exceptionality_analysis": exceptionality_analysis,
            "support_plan": support_plan,
            "conversation_control": conversation_control,
            "conversation_frame": conversation_frame,
            "conversational_intent": conversational_intent,
            "expert_adaptation_plan": {},
            "state_analysis": state_analysis,
            "category_analysis": category_analysis,
            "intent_analysis": intent_analysis,
            "memory_summary": {},
            "memory_payload": {},
            "user_context_payload": user_context_payload,
            "user_context_store_result": user_context_store_result,
            "response_memory_payload": {},
            "stage_result": stage_result,
            "stage_hints": {},
            "routine_payload": {},
            "confidence_payload": confidence_payload,
            "decision_payload": decision_payload,
            "fallback_payload": fallback_payload,
            "llm_policy": llm_policy,
            "llm_request_payload": llm_request_payload,
            "llm_result": llm_result,
            "llm_curated_payload": llm_curated_payload,
            "conversation_curation_result": conversation_curation_result,
            "session_scope_id": session_scope_id,
            "response_package": response_package,
            "previous_frame": previous_frame,
        }

    # =========================================================
    # CONVERSATION FRAME
    # =========================================================
    def _infer_previous_conversation_frame(
        self,
        chat_history: Optional[List[Dict[str, Any]]] = None,
        extra_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        chat_history = chat_history or []
        extra_context = extra_context or {}

        if isinstance(extra_context.get("conversation_frame"), dict):
            return self._normalize_conversation_frame(extra_context["conversation_frame"])

        if not chat_history:
            return self._normalize_conversation_frame(
                {
                    "conversation_domain": None,
                    "support_goal": None,
                    "conversation_phase": None,
                    "speaker_role": None,
                    "care_context": {},
                    "continuity_score": 0.0,
                    "last_guided_action": None,
                    "last_action_instruction": None,
                    "last_action_type": None,
                    "phase_progression_reason": None,
                }
            )

        domain: Optional[str] = None
        phase: Optional[str] = None
        continuity_score = 0.0
        followup_depth = 0

        for turn in chat_history:
            if not isinstance(turn, dict):
                continue

            explicit_frame = turn.get("conversation_frame")
            if isinstance(explicit_frame, dict) and explicit_frame.get("conversation_domain"):
                normalized_frame = self._normalize_conversation_frame(explicit_frame)
                domain = normalized_frame.get("conversation_domain")
                phase = normalized_frame.get("conversation_phase")
                continuity_score = max(
                    continuity_score,
                    float(normalized_frame.get("continuity_score", 0.0) or 0.0),
                    0.88,
                )
                followup_depth = 0
                continue

            last_user = str(turn.get("user") or "").strip()
            if not last_user:
                continue

            domain_from_user = self._infer_domain_from_text(last_user)
            if domain_from_user:
                domain = domain_from_user
                phase = self._default_phase_for_domain(domain_from_user)
                continuity_score = 0.78
                followup_depth = 0
                continue

            if domain and self._looks_like_history_followup(last_user):
                phase = self._advance_inferred_phase(
                    domain=domain,
                    current_phase=phase,
                    source_message=last_user,
                )
                followup_depth += 1
                continuity_score = max(continuity_score, 0.92 if followup_depth >= 1 else 0.82)

        return self._normalize_conversation_frame(
            {
                "conversation_domain": domain,
                "support_goal": self.DOMAIN_TO_GOAL.get(domain),
                "conversation_phase": phase or self._default_phase_for_domain(domain),
                "speaker_role": None,
                "care_context": {},
                "continuity_score": continuity_score if domain else 0.0,
                "last_guided_action": None,
                "last_action_instruction": None,
                "last_action_type": None,
                "phase_progression_reason": None,
            }
        )

    def _build_conversation_control(
        self,
        source_message: str,
        effective_message: str,
        previous_frame: Dict[str, Any],
        context_override: Optional[Dict[str, Any]],
        state_analysis: Dict[str, Any],
        category_analysis: Dict[str, Any],
        intent_analysis: Dict[str, Any],
        chat_history: List[Dict[str, Any]],
        active_profile: Optional[Dict[str, Any]],
        unit_context: Dict[str, Any],
        extra_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        control = self.conversation_stages.resolve_conversation_control(
            message=effective_message or source_message,
            previous_frame=previous_frame,
            context_override=context_override,
            state_analysis=state_analysis,
            category_analysis=category_analysis,
            intent_analysis=intent_analysis,
        )
        control["speaker_role"] = self._infer_speaker_role(
            source_message=source_message,
            active_profile=active_profile,
            unit_context=unit_context,
            extra_context=extra_context,
        )
        control["source_message"] = source_message
        control["effective_message"] = effective_message
        control["chat_history_size"] = len(chat_history or [])
        control["context_override"] = dict(context_override or self._empty_context_override(message=source_message, effective_message=effective_message))
        return control

    def _build_conversation_frame(
        self,
        source_message: str,
        effective_message: str,
        chat_history: List[Dict[str, Any]],
        previous_frame: Dict[str, Any],
        context_override: Optional[Dict[str, Any]],
        state_analysis: Dict[str, Any],
        category_analysis: Dict[str, Any],
        intent_analysis: Dict[str, Any],
        active_profile: Optional[Dict[str, Any]],
        unit_context: Dict[str, Any],
        extra_context: Dict[str, Any],
        conversation_control: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        category = self._canonicalize_category(category_analysis.get("detected_category"))
        previous_domain = self._canonicalize_category(previous_frame.get("conversation_domain"))
        previous_phase = previous_frame.get("conversation_phase")
        conversation_control = conversation_control or {}
        domain_shift_analysis = dict(conversation_control.get("domain_shift", {}) or {})
        domain_shift_detected = bool(domain_shift_analysis.get("detected"))
        domain = conversation_control.get("domain") or category or previous_domain or "apoyo_general"
        support_goal = self.DOMAIN_TO_GOAL.get(domain, "clarify_and_support")
        phase = (
            conversation_control.get("phase")
            or previous_phase
            or self.DOMAIN_TO_PHASE.get(domain)
        )
        turn_type = conversation_control.get("turn_type") or "new_request"
        turn_family = conversation_control.get("turn_family") or "new_request"
        speaker_role = (
            conversation_control.get("speaker_role")
            or self._infer_speaker_role(
                source_message=source_message,
                active_profile=active_profile,
                unit_context=unit_context,
                extra_context=extra_context,
            )
        )

        if domain_shift_detected:
            continuity_score = 0.38
        elif turn_type in {"followup_acceptance", "followup_request", "continuation", "clarification", "system_meta"} and previous_domain:
            continuity_score = 0.95
        elif domain and domain == previous_domain:
            continuity_score = 0.84
        else:
            continuity_score = 0.58 if domain else 0.35

        care_context = {
            "unit_type": unit_context.get("unit_type", "individual"),
            "speaker_role": speaker_role,
            "profile_conditions": active_profile.get("conditions", []) if active_profile else [],
            "support_network": unit_context.get("support_network", ""),
            "context_notes": unit_context.get("context_notes", ""),
            "user_extra_context": extra_context.get("user_extra_context", ""),
            "primary_state": state_analysis.get("primary_state"),
            "detected_category": category,
            "detected_intent": intent_analysis.get("detected_intent"),
            "previous_domain": previous_domain,
            "previous_phase": previous_phase,
            "previous_frame": {
                "conversation_domain": previous_domain,
                "support_goal": previous_frame.get("support_goal"),
                "conversation_phase": previous_phase,
                "continuity_score": previous_frame.get("continuity_score"),
                "last_guided_action": previous_frame.get("last_guided_action"),
                "last_action_instruction": previous_frame.get("last_action_instruction"),
                "last_action_type": previous_frame.get("last_action_type"),
            },
            "domain_shift": domain_shift_analysis,
        }

        return self._normalize_conversation_frame({
            "conversation_domain": domain,
            "support_goal": support_goal,
            "conversation_phase": phase,
            "speaker_role": speaker_role,
            "care_context": care_context,
            "continuity_score": continuity_score,
            "source_message": source_message,
            "effective_message": effective_message,
            "domain_shift_detected": domain_shift_detected,
            "domain_shift_analysis": domain_shift_analysis,
            "turn_type": turn_type,
            "turn_family": turn_family,
            "context_override": dict(context_override or conversation_control.get("context_override") or self._empty_context_override(message=source_message, effective_message=effective_message)),
            "clarification_mode": conversation_control.get("clarification_mode"),
            "crisis_guided_mode": conversation_control.get("crisis_guided_mode"),
            "last_guided_action": conversation_control.get("last_guided_action") or previous_frame.get("last_guided_action"),
            "last_action_instruction": conversation_control.get("last_action_instruction") or previous_frame.get("last_action_instruction"),
            "last_action_type": conversation_control.get("last_action_type") or previous_frame.get("last_action_type"),
            "phase_progression_reason": conversation_control.get("phase_progression_reason"),
            "recent_strategy_history": list(previous_frame.get("recent_strategy_history") or []),
        })

    def _detect_clarification_mode(
        self,
        message: str,
        intent_analysis: Dict[str, Any],
    ) -> str:
        normalized = self._normalize_followup_text(message)
        clarification_markers = {
            "no entiendo",
            "no comprendo",
            "explicamelo",
            "explicame",
            "dilo mas simple",
            "puedes decirlo mas simple",
            "aclarame",
        }
        if intent_analysis.get("detected_intent") == "clarification_request":
            return "simplify_last_guidance"
        if normalized in clarification_markers:
            return "simplify_last_guidance"
        if any(marker in normalized for marker in clarification_markers):
            return "simplify_last_guidance"
        return "none"

    def _resolve_turn_type(
        self,
        message: str,
        previous_frame: Dict[str, Any],
        intent_analysis: Dict[str, Any],
        clarification_mode: str,
        domain_shift: Dict[str, Any],
    ) -> str:
        if clarification_mode != "none":
            return "clarification"
        if domain_shift.get("detected"):
            return "domain_shift"

        detected_intent = intent_analysis.get("detected_intent")
        has_previous_domain = bool(previous_frame.get("conversation_domain"))
        is_followup_acceptance = self._is_followup_acceptance(message)

        if is_followup_acceptance and has_previous_domain:
            return "followup_acceptance"
        if detected_intent == "followup" and has_previous_domain:
            return "continuation"
        if detected_intent == "strategy_feedback":
            return "reflection_feedback"
        if detected_intent in {"general_support", "routine_request"} and has_previous_domain:
            if len(self._normalize_followup_text(message).split()) <= 5:
                return "followup_request"
        if detected_intent == "urgent_support" and has_previous_domain:
            return "followup_request"
        return "new_request"

    def _resolve_conversation_domain(
        self,
        previous_domain: Optional[str],
        detected_category: Optional[str],
        category_confidence: float,
        turn_type: str,
        clarification_mode: str,
        domain_shift: Dict[str, Any],
    ) -> str:
        if domain_shift.get("detected"):
            return self._canonicalize_category(domain_shift.get("shift_domain")) or detected_category or previous_domain or "apoyo_general"
        if clarification_mode != "none" and previous_domain:
            return previous_domain
        if turn_type in {"followup_acceptance", "followup_request", "continuation"} and previous_domain:
            if detected_category in {None, "", previous_domain, "apoyo_general"} or category_confidence < 0.72:
                return previous_domain
        return detected_category or previous_domain or "apoyo_general"

    def _resolve_crisis_guided_mode(
        self,
        source_message: str,
        domain: str,
        previous_domain: Optional[str],
        turn_type: str,
    ) -> str:
        normalized = self._normalize_followup_text(source_message)
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
            or any(marker in normalized for marker in guidance_acceptance_markers)
        ):
            return "guided_steps"
        return "none"

    def _resolve_conversation_phase(
        self,
        domain: Optional[str],
        source_message: str,
        previous_frame: Dict[str, Any],
        chat_history: List[Dict[str, Any]],
    ) -> str:
        domain = self._canonicalize_category(domain)
        previous_phase = previous_frame.get("conversation_phase")

        if self._is_followup_acceptance(source_message) and previous_phase:
            transition_map = {
                "mapping_signals": "pattern_detection",
                "pattern_detection": "prepare_early_response",
                "prepare_early_response": "stabilize_plan",
                "cognitive_unloading": "prioritize",
                "prioritize": "anti_overload_phrase",
                "micro_start": "reduce_friction",
                "reduce_friction": "start_ritual",
                "start_ritual": "consolidate",
                "repair": "brief_reflection",
                "brief_reflection": "repair_phrase",
                "environment_adjustment": "identify_main_trigger",
                "anticipation": "make_transition_script",
                "relief": "single_priority",
            }
            return transition_map.get(previous_phase, previous_phase)

        return self.DOMAIN_TO_PHASE.get(domain, "clarification")

    def _default_phase_for_domain(self, domain: Optional[str]) -> Optional[str]:
        domain = self._canonicalize_category(domain)
        if not domain:
            return None
        phase_path = getattr(self.conversation_stages, "PHASE_PATHS", {}).get(domain, [])
        if phase_path:
            return phase_path[0]
        return self.DOMAIN_TO_PHASE.get(domain)

    def _looks_like_history_followup(self, text: str) -> bool:
        normalized = self._normalize_followup_text(text)
        if not normalized:
            return False
        if self._is_followup_acceptance(normalized):
            return True
        if any(self._text_contains_keyword(normalized, marker) for marker in self.HISTORY_CONTINUITY_MARKERS):
            return True
        return len(normalized.split()) <= 5

    def _advance_inferred_phase(
        self,
        domain: str,
        current_phase: Optional[str],
        source_message: str,
    ) -> Optional[str]:
        if not domain:
            return current_phase
        if current_phase:
            return current_phase
        return self._default_phase_for_domain(domain)

    def _infer_speaker_role(
        self,
        source_message: str,
        active_profile: Optional[Dict[str, Any]],
        unit_context: Dict[str, Any],
        extra_context: Dict[str, Any],
    ) -> str:
        explicit_role = str(extra_context.get("speaker_role") or "").strip().lower()
        if explicit_role:
            return explicit_role

        msg = self._normalize_text(source_message)

        if any(token in msg for token in ["mi hijo", "mi hija", "mi alumno", "mi alumna", "mi niño", "mi niña"]):
            if "alumno" in msg or "alumna" in msg:
                return "docente"
            return "cuidador"

        if any(token in msg for token in ["soy docente", "como docente", "en mi aula", "en el salón", "en el salon"]):
            return "docente"

        if active_profile and active_profile.get("profile_type") == "caregiver":
            return "cuidador"

        return "usuario"

    def _detect_domain_shift(
        self,
        message: str,
        previous_frame: Dict[str, Any],
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
        if self._is_followup_acceptance(message) or len(words) <= 3:
            result["reason"] = "short_or_followup_continuity"
            return result

        if (
            detected_category
            and detected_category not in {previous_domain, "apoyo_general"}
            and category_confidence >= 0.58
        ):
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

    def _infer_domain_from_text(self, text: str) -> Optional[str]:
        text = self._normalize_followup_text(text)

        if not text:
            return None

        if any(self._text_contains_keyword(text, token) for token in [
            "esta ocurriendo una crisis",
            "crisis ahora",
            "hay riesgo fisico",
            "hay riesgo de golpe",
            "se esta golpeando",
            "no la puedo calmar",
            "no lo puedo calmar",
        ]):
            return "crisis_activa"

        if any(self._text_contains_keyword(text, token) for token in [
            "evitar que vuelva a pasar",
            "evitar llegar a eso",
            "senales tempranas",
            "senales de escalada",
            "prevenir otra crisis",
        ]):
            return "prevencion_escalada"

        if any(self._text_contains_keyword(text, token) for token in [
            "despues de la crisis",
            "hablarlo despues",
            "reparar despues de la crisis",
            "cuando pase la crisis",
        ]):
            return "regulacion_post_evento"

        if any(self._text_contains_keyword(text, token) for token in [
            "me siento muy ansiosa",
            "me siento muy ansioso",
            "me da ansiedad pensar en todo",
            "tengo demasiados pendientes y me da ansiedad",
            "me abruma pensar en todo",
            "ansiedad por pendientes",
            "saturacion mental",
        ]):
            return "ansiedad_cognitiva"

        if any(self._text_contains_keyword(text, token) for token in [
            "no puedo organizarme",
            "no puedo empezar",
            "me cuesta arrancar",
            "bloqueo para empezar",
            "no puedo organizarme ni empezar",
        ]):
            return "disfuncion_ejecutiva"

        if any(self._text_contains_keyword(text, token) for token in [
            "sobrecarga sensorial",
            "saturacion sensorial",
            "demasiado ruido y luces",
            "demasiados estimulos",
        ]):
            return "sobrecarga_sensorial"

        if any(self._text_contains_keyword(text, token) for token in [
            "cambio de plan",
            "cambios inesperados",
            "no saber que va a pasar",
            "transicion dificil",
        ]):
            return "transicion_rigidez"

        if any(self._text_contains_keyword(text, token) for token in [
            "no estoy durmiendo bien",
            "no duermo bien",
            "no ha dormido",
            "no duerme bien",
            "problemas de sueno",
            "el cansancio me esta pegando mucho",
        ]):
            return "sueno_regulacion"

        if any(self._text_contains_keyword(text, token) for token in [
            "me esta pesando cuidar",
            "me rebasa cuidar",
            "estoy agotada de cuidar",
            "estoy agotado de cuidar",
            "ya no puedo con esto",
        ]):
            return "sobrecarga_cuidador"

        return None

    def _build_llm_policy(
        self,
        source_message: str,
        effective_message: str,
        chat_history: List[Dict[str, Any]],
        conversation_frame: Dict[str, Any],
        state_analysis: Dict[str, Any],
        category_analysis: Dict[str, Any],
        intent_analysis: Dict[str, Any],
        stage_result: Dict[str, Any],
        confidence_payload: Dict[str, Any],
        decision_payload: Dict[str, Any],
        fallback_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        domain = self._canonicalize_category(conversation_frame.get("conversation_domain"))
        phase = conversation_frame.get("conversation_phase")
        confidence = float(confidence_payload.get("overall_confidence", 0.0) or 0.0)
        stage = stage_result.get("stage")
        category = self._canonicalize_category(category_analysis.get("detected_category"))
        intent = intent_analysis.get("detected_intent")

        repetitive_followup = (
            self._is_followup_acceptance(source_message)
            and domain in {
                "crisis_activa",
                "regulacion_post_evento",
                "sobrecarga_sensorial",
                "disfuncion_ejecutiva",
                "ansiedad_cognitiva",
                "transicion_rigidez",
                "prevencion_escalada",
                "sobrecarga_cuidador",
            }
        )

        ambiguous_case = confidence < 0.58
        multi_factor_case = len(state_analysis.get("secondary_states", []) or []) >= 2
        phase_sensitive_case = phase in {
            "repair",
            "brief_reflection",
            "identify_main_trigger",
            "start_ritual",
            "consolidate",
            "reduce_friction",
            "prioritize",
            "prepare_early_response",
            "anti_overload_phrase",
            "stabilize_plan",
        }

        should_use_llm = bool(
            fallback_payload.get("use_llm")
            or ambiguous_case
            or (repetitive_followup and stage in {"adaptive_intervention", "closure_continuity"})
            or (multi_factor_case and category not in {"crisis_activa"})
            or phase_sensitive_case
        )

        reasons = []
        if fallback_payload.get("use_llm"):
            reasons.append("fallback_manager")
        if ambiguous_case:
            reasons.append("low_confidence")
        if repetitive_followup:
            reasons.append("followup_continuity")
        if multi_factor_case:
            reasons.append("multi_factor_case")
        if phase_sensitive_case:
            reasons.append("phase_sensitive_case")

        prompt_mode = fallback_payload.get("prompt_mode", "controlled_support_generation")

        return {
            "should_use_llm": should_use_llm,
            "reason": ",".join(reasons) if reasons else None,
            "prompt_mode": prompt_mode,
            "domain": domain,
            "phase": phase,
            "category": category,
            "intent": intent,
        }

    def _expand_short_followup_message(
        self,
        message: str,
        chat_history: Optional[List[Dict[str, Any]]] = None,
        previous_frame: Optional[Dict[str, Any]] = None,
    ) -> str:
        if not self._is_followup_acceptance(message):
            return message

        previous_frame = previous_frame or {}
        domain = previous_frame.get("conversation_domain")
        phase = previous_frame.get("conversation_phase")

        if domain == "prevencion_escalada":
            if phase in {"mapping_signals", "pattern_detection"}:
                return "Sí, quiero revisar mejor cuál es la primera señal."
            if phase in {"prepare_early_response", "stabilize_plan"}:
                return "Sí, quiero preparar qué hacer apenas aparezca la señal."
            return "Sí, quiero continuar con la prevención y revisar el siguiente paso."

        if domain == "ansiedad_cognitiva":
            if phase == "prioritize":
                return "Sí, quiero elegir una sola prioridad."
            if phase == "anti_overload_phrase":
                return "Sí, quiero una frase breve para no saturarme otra vez."
            return "Sí, quiero continuar ordenando esto para bajar la ansiedad."

        if domain == "disfuncion_ejecutiva":
            if phase == "reduce_friction":
                return "Sí, quiero bajar esto a un paso todavía más pequeño."
            if phase == "start_ritual":
                return "Sí, quiero convertir esto en una mini rutina de arranque."
            if phase == "consolidate":
                return "Sí, quiero dejar esto como una rutina fácil de repetir."
            return "Sí, quiero ayuda para empezar por el primer paso."

        if domain == "regulacion_post_evento":
            if phase == "brief_reflection":
                return "Sí, quiero revisar con calma qué señal apareció antes."
            if phase == "repair_phrase":
                return "Sí, quiero una frase breve para después del episodio."
            return "Sí, quiero saber qué conviene hacer después de la crisis."

        if domain == "sobrecarga_sensorial":
            return "Sí, quiero revisar cómo detectar y bajar la saturación sensorial."

        if domain == "transicion_rigidez":
            return "Sí, quiero revisar cómo anticipar mejor el cambio."

        if domain == "crisis_activa":
            return "Sí, quiero saber qué hacer ahora que esto sigue intenso."

        if domain == "sobrecarga_cuidador":
            return "Sí, quiero bajar esto a una sola prioridad posible."

        return message

    def _empty_context_override(
        self,
        message: str = "",
        effective_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        return {
            "active": False,
            "type": None,
            "reason": None,
            "confidence": 0.0,
            "target": None,
            "source_message": message,
            "effective_message": effective_message or message,
        }

    def _detect_context_override(
        self,
        message: str,
        chat_history: Optional[List[Dict[str, Any]]] = None,
        previous_frame: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        base = self._empty_context_override(message=message, effective_message=message)
        normalized = self._normalize_followup_text(message)
        if not normalized:
            return base

        previous_frame = previous_frame or {}
        previous_domain = self._canonicalize_category(previous_frame.get("conversation_domain"))
        previous_action = self._normalize_followup_text(str(previous_frame.get("last_guided_action") or ""))
        previous_shape = str(previous_frame.get("last_response_shape") or "")
        last_assistant = ""
        if chat_history:
            last_turn = chat_history[-1] if isinstance(chat_history[-1], dict) else {}
            last_assistant = self._normalize_text(str(last_turn.get("assistant") or ""))

        done_markers = {
            "ya lo hice",
            "eso ya lo hice",
            "ya hice eso",
            "ya lo intente",
            "ya lo intenté",
            "ya probe eso",
            "ya probé eso",
            "ya lo probe",
            "ya lo probé",
        }
        invalidation_markers = {
            "eso no aplica",
            "no aplica",
            "eso no sirve",
            "no sirve",
            "eso no me sirve",
            "no me sirve",
            "no me ayuda",
            "eso no funciona",
            "no funciona aqui",
            "no funciona acá",
            "eso no funciona aqui",
            "no otra cosa",
        }
        impossibility_markers = {
            "no puedo",
            "no puedo ni",
            "no me da",
            "no me sale",
            "no logro",
            "no alcanzo",
        }

        if any(self._text_contains_keyword(normalized, marker) for marker in done_markers):
            base.update(
                {
                    "active": True,
                    "type": "override_hard",
                    "reason": "explicit_action_completed",
                    "confidence": 0.97,
                    "target": "action",
                }
            )
            return base

        if (
            any(self._text_contains_keyword(normalized, marker) for marker in invalidation_markers)
            and (previous_domain or previous_action or previous_shape)
        ):
            base.update(
                {
                    "active": True,
                    "type": "override_hard",
                    "reason": "explicit_invalidation",
                    "confidence": 0.94,
                    "target": "action",
                }
            )
            return base

        strong_impossibility = any(
            self._text_contains_keyword(
                normalized,
                marker,
            )
            for marker in {
                "no puedo ni",
                "no puedo levantarme",
                "no puedo moverme",
                "no me da el cuerpo",
                "no me sale ni",
            }
        )
        has_actional_context = bool(previous_domain or previous_action or previous_shape)
        has_explicit_limit_context = any(
            self._text_contains_keyword(normalized, marker)
            for marker in {
                "eso",
                "esta accion",
                "ese paso",
                "asi",
                "asi no",
                "asi tampoco",
                "tampoco puedo",
                "con eso no puedo",
                "no puedo hacer eso",
                "no puedo hacer ese paso",
            }
        )
        if any(self._text_contains_keyword(normalized, marker) for marker in impossibility_markers) and (
            strong_impossibility or (has_actional_context and has_explicit_limit_context)
        ):
            base.update(
                {
                    "active": True,
                    "type": "override_hard",
                    "reason": "explicit_impossibility",
                    "confidence": 0.93,
                    "target": "action",
                }
            )
            return base

        contradiction = self._detect_action_contradiction(
            normalized=normalized,
            previous_domain=previous_domain,
            previous_action=previous_action,
        )
        if contradiction:
            base.update(
                {
                    "active": True,
                    "type": "override_hard",
                    "reason": contradiction,
                    "confidence": 0.9,
                    "target": "action",
                }
            )
            return base

        contextual_override = self._detect_contextual_override(
            message=message,
            normalized=normalized,
            last_assistant=last_assistant,
            previous_domain=previous_domain,
        )
        if contextual_override.get("active"):
            return contextual_override

        return base

    def _detect_action_contradiction(
        self,
        normalized: str,
        previous_domain: Optional[str],
        previous_action: str,
    ) -> Optional[str]:
        if not any(marker in normalized for marker in {"no tengo", "no hay", "ya no hay", "sin "}):
            return None

        domain_terms = {
            "crisis_activa": {"ruido", "estimulo", "estimulos", "gente", "espacio", "luz"},
            "sobrecarga_sensorial": {"ruido", "estimulo", "estimulos", "gente", "luz", "pantalla"},
            "disfuncion_ejecutiva": {"archivo", "cuaderno", "material", "computadora", "escritorio"},
            "ansiedad_cognitiva": {"nota", "papel", "celular", "tiempo"},
            "sueno_regulacion": {"pantalla", "luz", "ruido", "tiempo"},
        }
        candidate_terms = set(domain_terms.get(previous_domain or "", set()))
        candidate_terms.update(
            {
                term
                for term in ["ruido", "estimulo", "estimulos", "gente", "luz", "archivo", "cuaderno", "material", "papel", "pantalla", "tiempo"]
                if term in previous_action
            }
        )

        if not candidate_terms:
            return None

        for term in candidate_terms:
            if self._text_contains_keyword(normalized, term):
                return f"explicit_contradiction_{term}"
        return None

    def _detect_contextual_override(
        self,
        message: str,
        normalized: str,
        last_assistant: str,
        previous_domain: Optional[str],
    ) -> Dict[str, Any]:
        base = self._empty_context_override(message=message, effective_message=message)
        raw_message = " ".join((message or "").strip().split())

        time_fragments = {
            "por la manana",
            "por la tarde",
            "por la noche",
            "en la manana",
            "en la tarde",
            "en la noche",
        }
        location_fragments = {
            "en casa",
            "en el trabajo",
            "en la escuela",
            "en el aula",
            "en el coche",
            "afuera",
        }
        condition_fragments = {
            "estoy acostada",
            "estoy acostado",
            "estoy en cama",
            "estoy con gente",
            "estoy sola",
            "estoy solo",
        }

        expects_time = any(token in last_assistant for token in ["cuando", "qué momento", "que momento", "manana", "tarde", "noche", "hora"])
        expects_location = any(token in last_assistant for token in ["donde", "dónde", "lugar", "casa", "trabajo", "escuela", "aula"])
        expects_numeric = any(token in last_assistant for token in ["del 1 al", "de 1 a", "de 0 a", "numero", "número", "escala", "opcion", "opción"])
        expects_condition = any(token in last_assistant for token in ["sentada", "sentado", "acostada", "acostado", "de pie", "con gente", "solo", "sola"])

        if normalized.isdigit() and expects_numeric:
            value = normalized
            effective = f"La respuesta contextual es {value}."
            if any(token in last_assistant for token in ["del 1 al 10", "de 1 a 10", "de 0 a 10"]):
                effective = f"Mi nivel ahora es {value} de 10."
            elif any(token in last_assistant for token in ["del 1 al 5", "de 1 a 5", "de 0 a 5"]):
                effective = f"Mi nivel ahora es {value} de 5."
            elif "opcion" in last_assistant or "opción" in last_assistant:
                effective = f"Elijo la opcion {value}."
            base.update(
                {
                    "active": True,
                    "type": "override_contextual",
                    "reason": "contextual_numeric_answer",
                    "confidence": 0.84,
                    "target": "context",
                    "effective_message": effective,
                }
            )
            return base

        if normalized in time_fragments and (expects_time or previous_domain == "sueno_regulacion"):
            base.update(
                {
                    "active": True,
                    "type": "override_contextual",
                    "reason": "contextual_time_answer",
                    "confidence": 0.82,
                    "target": "context",
                    "effective_message": f"Esto pasa {normalized}.",
                }
            )
            return base

        if normalized in location_fragments and expects_location:
            base.update(
                {
                    "active": True,
                    "type": "override_contextual",
                    "reason": "contextual_location_answer",
                    "confidence": 0.8,
                    "target": "context",
                    "effective_message": f"Esto pasa {normalized}.",
                }
            )
            return base

        if raw_message and self._normalize_followup_text(raw_message) in condition_fragments and (
            expects_condition or previous_domain in {"disfuncion_ejecutiva", "ansiedad_cognitiva", "sueno_regulacion"}
        ):
            effective = raw_message if raw_message.endswith(".") else f"{raw_message}."
            effective = effective[0].upper() + effective[1:]
            base.update(
                {
                    "active": True,
                    "type": "override_contextual",
                    "reason": "contextual_condition_answer",
                    "confidence": 0.8,
                    "target": "context",
                    "effective_message": effective,
                }
            )
            return base

        return base

    def _build_response_builder_input(
        self,
        decision_payload: Dict[str, Any],
        stage_result: Dict[str, Any],
        response_memory_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        rb_stage_result = dict(stage_result)
        rb_stage_result["emotional_validation"] = self._build_emotional_validation(stage_result)

        rb_response_memory_payload = dict(response_memory_payload)
        reuse_candidate = decision_payload.get("reuse_response_candidate")
        if reuse_candidate:
            rb_response_memory_payload["selected_response"] = reuse_candidate.get("response_text")
            rb_response_memory_payload["can_reuse_directly"] = True

        return {
            "stage_result": rb_stage_result,
            "response_memory_payload": rb_response_memory_payload,
        }

    def _build_emotional_validation(self, stage_result: Dict[str, Any]) -> Optional[str]:
        stage = stage_result.get("stage")
        if stage == "reception_containment":
            return "Estoy contigo. Vamos poco a poco, sin cargar más este momento."
        if stage == "focus_clarification":
            return "Lo que está pasando pesa, y vale la pena ordenar el foco con calma."
        if stage == "adaptive_intervention":
            return "No necesitamos hacerlo perfecto; solo encontrar algo útil y aplicable."
        if stage == "closure_continuity":
            return "Por ahora basta con quedarnos con algo claro y manejable."
        return None

    # =========================================================
    # STATE ANALYSIS
    # =========================================================
    def _build_state_analysis(
        self,
        message: str,
        extra_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        raw = self.state_guardian.analyze(message=message, extra_context=extra_context) or {}
        all_scores = raw.get("all_scores", {}) or {}

        detected_states = []
        for state_name, score in all_scores.items():
            canonical_state = self.STATE_NAME_MAP.get(state_name, state_name)
            if score <= 0:
                continue
            detected_states.append(
                {
                    "state": canonical_state,
                    "score": round(float(score), 3),
                    "severity": self._severity_from_score(float(score)),
                    "response_mode": self._response_mode_for_state(canonical_state),
                    "priority_actions": self._priority_actions_for_state(canonical_state),
                    "avoid": self._avoid_for_state(canonical_state),
                }
            )

        detected_states.sort(key=lambda x: x["score"], reverse=True)

        primary_state = self.STATE_NAME_MAP.get(raw.get("primary_state"), raw.get("primary_state")) or "general_distress"
        secondary_states = [
            item["state"]
            for item in detected_states[1:3]
            if item["state"] != primary_state
        ]

        risk_summary = self._build_risk_summary_from_states(detected_states)
        response_plan = self._build_response_plan_from_states(primary_state, secondary_states, detected_states)
        flags = self._build_flags_from_states(primary_state, secondary_states)
        followup_needed = bool((raw.get("intensity") or 0.0) >= 0.45)

        return {
            "message": message,
            "normalized_message": self._normalize_text(message),
            "detected_states": detected_states,
            "primary_state": primary_state,
            "secondary_states": secondary_states,
            "evidence": {},
            "risk_summary": risk_summary,
            "response_plan": response_plan,
            "flags": flags,
            "followup_needed": followup_needed,
            "raw_guardian_output": raw,
        }

    def _severity_from_score(self, score: float) -> str:
        if score >= 0.75:
            return "high"
        if score >= 0.50:
            return "medium_high"
        if score >= 0.30:
            return "medium"
        return "low"

    def _response_mode_for_state(self, state: str) -> str:
        mapping = {
            "meltdown": "crisis_containment",
            "shutdown": "very_low_demand",
            "burnout": "low_demand_support",
            "parental_fatigue": "caregiver_support",
            "executive_dysfunction": "microstep_guidance",
            "sleep_disruption": "sleep_support",
            "emotional_dysregulation": "emotional_grounding",
            "sensory_overload": "sensory_support",
            "cognitive_anxiety": "cognitive_unloading",
            "general_distress": "general_support",
        }
        return mapping.get(state, "general_support")

    def _priority_actions_for_state(self, state: str) -> List[str]:
        mapping = {
            "meltdown": ["priorizar seguridad", "bajar estímulos", "usar frases cortas"],
            "shutdown": ["bajar demanda verbal", "ofrecer pocas opciones", "permitir silencio"],
            "burnout": ["validar agotamiento", "reducir exigencia", "ofrecer una sola acción viable"],
            "parental_fatigue": ["validar cansancio", "reducir culpa", "hacer una sola cosa posible"],
            "executive_dysfunction": ["dividir en microacciones", "hacer visible el primer paso", "reducir complejidad"],
            "sleep_disruption": ["bajar activación", "reducir estímulos", "priorizar rutina suave"],
            "emotional_dysregulation": ["validar emoción", "reducir presión", "usar anclaje breve"],
            "sensory_overload": ["bajar estímulos", "ajustar entorno", "reducir carga sensorial"],
            "cognitive_anxiety": ["vaciar pendientes", "reducir carga mental", "elegir una sola prioridad"],
            "general_distress": ["validar", "clarificar el foco", "ofrecer una microacción"],
        }
        return mapping.get(state, ["validar", "responder con claridad"])

    def _avoid_for_state(self, state: str) -> List[str]:
        mapping = {
            "meltdown": ["moralizar", "corregir en medio de la crisis", "hacer razonar en el pico"],
            "shutdown": ["presión verbal", "preguntas complejas", "exigir explicación inmediata"],
            "burnout": ["tono productivista", "listas largas", "culpabilizar"],
            "parental_fatigue": ["idealizar crianza perfecta", "dar demasiadas tareas"],
            "executive_dysfunction": ["decir solo organizate", "dar demasiados pasos a la vez"],
            "sleep_disruption": ["correcciones largas antes de dormir", "rigidez excesiva"],
            "emotional_dysregulation": ["minimizar emoción", "subir presión"],
            "sensory_overload": ["aumentar estímulos", "muchas palabras", "contacto inesperado"],
            "cognitive_anxiety": ["decir relajate", "sobrecargar con tareas", "pedir que piense en todo"],
            "general_distress": [],
        }
        return mapping.get(state, [])

    def _build_risk_summary_from_states(self, detected_states: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not detected_states:
            return {
                "risk_level": "low_or_unclear",
                "message": "No se detectaron señales fuertes de un estado funcional específico.",
            }

        top_score = float(detected_states[0]["score"])
        if top_score >= 0.75:
            level = "high"
            msg = "Se detectan señales altas de saturación funcional. Conviene priorizar contención, simplificación y baja demanda."
        elif top_score >= 0.55:
            level = "medium_high"
            msg = "Se observan señales moderadas a altas de desregulación o agotamiento. Conviene responder con estructura breve y foco claro."
        elif top_score >= 0.35:
            level = "medium"
            msg = "Se detectan señales relevantes, aunque no extremas. Puede ayudar una intervención concreta y proporcional."
        else:
            level = "low_or_unclear"
            msg = "Las señales son leves o poco concluyentes. Conviene explorar con suavidad."

        return {"risk_level": level, "message": msg}

    def _build_response_plan_from_states(
        self,
        primary_state: str,
        secondary_states: List[str],
        detected_states: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        priorities = list(self._priority_actions_for_state(primary_state))
        avoid = list(self._avoid_for_state(primary_state))

        for state in secondary_states[:2]:
            priorities.extend(self._priority_actions_for_state(state)[:2])
            avoid.extend(self._avoid_for_state(state)[:2])

        return {
            "mode": self._response_mode_for_state(primary_state),
            "tone": self._tone_for_state(primary_state),
            "length": self._length_for_state(primary_state),
            "priorities": self._deduplicate(priorities),
            "avoid": self._deduplicate(avoid),
        }

    def _build_flags_from_states(self, primary_state: str, secondary_states: List[str]) -> Dict[str, bool]:
        states = {primary_state, *secondary_states}
        return {
            "needs_low_demand_language": bool({"burnout", "shutdown", "meltdown"}.intersection(states)),
            "needs_sensory_reduction": bool({"sensory_overload", "meltdown", "shutdown"}.intersection(states)),
            "needs_microsteps": bool({"executive_dysfunction", "burnout"}.intersection(states)),
            "needs_caregiver_validation": bool({"parental_fatigue", "burnout"}.intersection(states)),
            "needs_sleep_support": bool({"sleep_disruption"}.intersection(states)),
            "needs_predictability": bool({"shutdown", "cognitive_rigidity"}.intersection(states)),
        }

    def _tone_for_state(self, primary_state: str) -> str:
        mapping = {
            "burnout": "warm_gentle",
            "shutdown": "very_soft",
            "meltdown": "calm_containment",
            "executive_dysfunction": "clear_step_by_step",
            "sensory_overload": "calm_low_stimulus",
            "parental_fatigue": "warm_validating",
            "sleep_disruption": "soft_structured",
            "emotional_dysregulation": "warm_grounding",
            "cognitive_anxiety": "warm_structured",
            "general_distress": "warm_clear",
        }
        return mapping.get(primary_state, "warm_clear")

    def _length_for_state(self, primary_state: str) -> str:
        mapping = {
            "burnout": "short",
            "shutdown": "very_short",
            "meltdown": "very_short",
            "executive_dysfunction": "short",
            "sensory_overload": "short",
            "parental_fatigue": "short",
            "sleep_disruption": "medium",
            "emotional_dysregulation": "short",
            "cognitive_anxiety": "medium",
            "general_distress": "medium",
        }
        return mapping.get(primary_state, "medium")

    # =========================================================
    # UNIT / MEMORY HELPERS
    # =========================================================
    def _resolve_unit_context(self, family_id: Optional[str]) -> Dict[str, Any]:
        if not family_id:
            return {
                "family_id": None,
                "unit_type": "individual",
                "caregiver_alias": None,
                "context_notes": "",
                "support_network": "",
                "environmental_factors": "",
                "global_history": "",
            }

        unit = self.profile_manager.get_unit(family_id)
        if unit:
            return unit

        return {
            "family_id": family_id,
            "unit_type": "individual",
            "caregiver_alias": None,
            "context_notes": "",
            "support_network": "",
            "environmental_factors": "",
            "global_history": "",
        }

    def _build_memory_summary(
        self,
        family_id: Optional[str],
        profile_id: Optional[str],
        unit_type: str,
    ) -> Dict[str, Any]:
        if profile_id:
            return self.case_memory.build_profile_memory_summary(profile_id)

        if family_id and unit_type == "family":
            return self.case_memory.build_family_memory_summary(family_id)

        return {
            "total_cases": 0,
            "successful_cases": 0,
            "success_rate": 0.0,
            "average_usefulness": 0.0,
            "frequent_categories": [],
            "frequent_primary_states": [],
            "best_help_patterns": [],
            "main_worsening_patterns": [],
            "pattern_count": 0,
            "followup_cases": 0,
            "latest_case_at": None,
        }

    def _empty_user_context_payload(
        self,
        session_scope_id: Optional[str] = None,
        reason: str = "not_available",
    ) -> Dict[str, Any]:
        return {
            "available": False,
            "reason": reason,
            "scope_key": f"session:{session_scope_id}" if session_scope_id else None,
            "scope_type": "session" if session_scope_id else None,
            "inferred_user_role": "indefinido",
            "role_confidence": 0.0,
            "conversation_preferences": {},
            "recurrent_topics": [],
            "recurrent_signals": [],
            "helpful_strategies": [],
            "helpful_routines": [],
            "last_useful_domain": None,
            "last_useful_phase": None,
            "summary_snapshot": {},
            "updated_at": None,
        }

    def _merge_user_context_into_memory_payload(
        self,
        memory_payload: Dict[str, Any],
        user_context_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        memory_payload = dict(memory_payload or {})
        user_context_payload = user_context_payload or {}

        if not user_context_payload.get("available"):
            memory_payload["user_context_memory"] = user_context_payload
            return memory_payload

        existing_strategies = list(memory_payload.get("recommended_strategies", []) or [])
        existing_routines = list(memory_payload.get("recommended_routine_types", []) or [])

        memory_payload["recommended_strategies"] = self._deduplicate(
            list(user_context_payload.get("helpful_strategies", []) or []) + existing_strategies
        )
        memory_payload["recommended_routine_types"] = self._deduplicate(
            list(user_context_payload.get("helpful_routines", []) or []) + existing_routines
        )
        memory_payload["user_context_memory"] = {
            "inferred_user_role": user_context_payload.get("inferred_user_role"),
            "conversation_preferences": user_context_payload.get("conversation_preferences", {}),
            "recurrent_topics": user_context_payload.get("recurrent_topics", []),
            "recurrent_signals": user_context_payload.get("recurrent_signals", []),
            "last_useful_domain": user_context_payload.get("last_useful_domain"),
            "last_useful_phase": user_context_payload.get("last_useful_phase"),
            "summary_snapshot": user_context_payload.get("summary_snapshot", {}),
        }
        return memory_payload

    def _estimate_emotional_intensity(self, state_analysis: Dict[str, Any]) -> float:
        detected_states = state_analysis.get("detected_states", []) or []
        if not detected_states:
            return 0.35
        top_score = float(detected_states[0].get("score", 0.35))
        return round(min(max(top_score, 0.20), 0.95), 3)

    def _estimate_caregiver_capacity(self, state_analysis: Dict[str, Any]) -> float:
        primary_state = state_analysis.get("primary_state")
        if primary_state in {"burnout", "parental_fatigue"}:
            return 0.25
        if primary_state in {"meltdown", "shutdown"}:
            return 0.30
        if primary_state in {"executive_dysfunction", "sensory_overload"}:
            return 0.45
        if primary_state == "sleep_disruption":
            return 0.40
        return 0.60

    def _state_score(self, state_analysis: Dict[str, Any], state_name: str) -> Optional[float]:
        for item in state_analysis.get("detected_states", []) or []:
            if item.get("state") == state_name:
                try:
                    return float(item.get("score"))
                except (TypeError, ValueError):
                    return None
        return 0.0

    def _normalize_summary(self, message: str) -> str:
        return self._normalize_text(message)[:500]

    def _canonicalize_category(self, category: Optional[str]) -> Optional[str]:
        if not category:
            return category
        return self.LEGACY_CATEGORY_ALIASES.get(category, category)

    def _canonicalize_category_list(self, categories: Optional[List[Any]]) -> List[Any]:
        result: List[Any] = []
        for category in categories or []:
            canonical = self._canonicalize_category(category) if isinstance(category, str) else category
            if canonical not in result:
                result.append(canonical)
        return result

    def _canonicalize_category_analysis(self, category_analysis: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        category_analysis = dict(category_analysis or {})
        detected_category = self._canonicalize_category(category_analysis.get("detected_category"))
        if detected_category:
            category_analysis["detected_category"] = detected_category

        if "alternatives" in category_analysis:
            category_analysis["alternatives"] = self._canonicalize_category_list(category_analysis.get("alternatives"))
        if "alternative_categories" in category_analysis:
            category_analysis["alternative_categories"] = self._canonicalize_category_list(
                category_analysis.get("alternative_categories")
            )

        candidates = []
        seen_candidates = set()
        for candidate in category_analysis.get("candidates", []) or []:
            if not isinstance(candidate, dict):
                continue
            normalized_candidate = dict(candidate)
            normalized_category = self._canonicalize_category(normalized_candidate.get("category"))
            if normalized_category:
                normalized_candidate["category"] = normalized_category
            key = (
                normalized_candidate.get("category"),
                normalized_candidate.get("score"),
            )
            if key in seen_candidates:
                continue
            seen_candidates.add(key)
            candidates.append(normalized_candidate)

        if candidates:
            category_analysis["candidates"] = candidates

        return category_analysis

    def _coerce_intervention_level(self, value: Any) -> int:
        if isinstance(value, (int, float)):
            return max(int(value or 0), 0)

        normalized = str(value or "").strip().lower()
        if normalized in {"low", "bajo"}:
            return 1
        if normalized in {"medium", "medio"}:
            return 2
        if normalized in {"high", "alto"}:
            return 3

        try:
            return max(int(float(normalized)), 0)
        except (TypeError, ValueError):
            return 0

    def _normalize_conversation_frame(self, frame: Dict[str, Any]) -> Dict[str, Any]:
        normalized = dict(frame or {})
        domain = self._canonicalize_category(normalized.get("conversation_domain"))
        normalized["conversation_domain"] = domain
        normalized["support_goal"] = normalized.get("support_goal") or self.DOMAIN_TO_GOAL.get(domain)
        normalized["conversation_phase"] = normalized.get("conversation_phase") or self.DOMAIN_TO_PHASE.get(domain)
        normalized["intervention_level"] = self._coerce_intervention_level(
            normalized.get("intervention_level")
        )
        normalized["last_guided_action"] = normalized.get("last_guided_action")
        normalized["last_action_instruction"] = normalized.get("last_action_instruction")
        normalized["last_action_type"] = normalized.get("last_action_type")
        normalized["phase_progression_reason"] = normalized.get("phase_progression_reason")
        normalized["domain_shift_analysis"] = normalized.get("domain_shift_analysis", {}) or {}
        normalized["turn_family"] = normalized.get("turn_family") or "new_request"
        normalized["recent_strategy_history"] = list(normalized.get("recent_strategy_history") or [])
        normalized["used_interventions_last_10"] = dict(normalized.get("used_interventions_last_10") or {})
        normalized["support_subject"] = normalized.get("support_subject") or "unknown"
        normalized["support_mode"] = normalized.get("support_mode") or "supportive"
        normalized["stable_demo_routing_key"] = normalized.get("stable_demo_routing_key")
        normalized["context_override"] = normalized.get("context_override") or self._empty_context_override(
            message=normalized.get("source_message") or "",
            effective_message=normalized.get("effective_message") or normalized.get("source_message") or "",
        )
        return normalized

    def _resolve_last_action_state(
        self,
        response_package: Optional[Dict[str, Any]],
        decision_payload: Optional[Dict[str, Any]],
    ) -> Dict[str, Optional[str]]:
        response_package = response_package or {}
        decision_payload = decision_payload or {}
        response_goal = decision_payload.get("response_goal", {}) or {}
        response_text = str(
            response_package.get("response")
            or response_package.get("text")
            or ""
        ).strip()
        normalized_response = self._normalize_followup_text(response_text)
        response_shape = str(response_goal.get("response_shape") or "").strip()
        literal_candidates = [
            str(item).strip()
            for item in response_goal.get("literal_phrase_candidates", [])
            if str(item).strip()
        ]
        candidate_actions = [
            str(item).strip()
            for item in response_goal.get("candidate_actions", [])
            if str(item).strip()
        ]
        selected_microaction = str(
            response_package.get("suggested_microaction")
            or decision_payload.get("selected_microaction")
            or response_goal.get("selected_microaction")
            or ""
        ).strip()

        extracted_phrase = self._extract_literal_phrase_from_response(response_text)
        phrase_markers = (
            "puedes decirle",
            "puedes decirte",
            "di solo esto",
            "repite solo esto",
        )
        if extracted_phrase and (
            response_shape in {"literal_phrase", "permission_phrase"}
            or any(marker in normalized_response for marker in phrase_markers)
        ):
            return {
                "last_action_instruction": extracted_phrase,
                "last_action_type": "literal_phrase",
            }

        if literal_candidates:
            return {
                "last_action_instruction": literal_candidates[0].rstrip("."),
                "last_action_type": "literal_phrase",
            }

        if selected_microaction:
            return {
                "last_action_instruction": selected_microaction.rstrip("."),
                "last_action_type": "action_step",
            }

        if candidate_actions:
            return {
                "last_action_instruction": candidate_actions[0].rstrip("."),
                "last_action_type": "action_step",
            }

        return {
            "last_action_instruction": None,
            "last_action_type": None,
        }

    def _extract_literal_phrase_from_response(self, response_text: str) -> Optional[str]:
        if not response_text:
            return None
        match = re.search(r'"([^"\n]{6,})"', response_text)
        if match:
            return match.group(1).strip().rstrip(".")
        return None

    def _normalize_text(self, text: str) -> str:
        return " ".join((text or "").strip().lower().split())

    def _normalize_followup_text(self, text: str) -> str:
        normalized = self._normalize_text(text)
        normalized = unicodedata.normalize("NFKD", normalized)
        normalized = "".join(char for char in normalized if not unicodedata.combining(char))
        normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
        return " ".join(normalized.split())

    def _text_contains_keyword(self, text: str, keyword: str) -> bool:
        text = self._normalize_followup_text(text)
        keyword = self._normalize_followup_text(keyword)
        if not text or not keyword:
            return False
        pattern = r"(?<!\w)" + re.escape(keyword).replace(r"\ ", r"\s+") + r"(?!\w)"
        return bool(re.search(pattern, text))

    def _is_followup_acceptance(self, message: str) -> bool:
        normalized = self._normalize_followup_text(message)
        if not normalized:
            return False

        if normalized in {self._normalize_followup_text(item) for item in self.SHORT_FOLLOWUPS}:
            return True

        words = normalized.split()
        if not words:
            return False

        word_set = set(words)
        if not word_set.intersection(self.FOLLOWUP_REQUIRED_WORDS):
            return False

        return all(word in self.FOLLOWUP_ACCEPTANCE_WORDS for word in words)

    def _empty_exceptionality_analysis(self) -> Dict[str, Any]:
        return {
            "profile_id": None,
            "conditions": [],
            "supports": [],
            "alerts": [],
            "contradictions": [],
            "exceptionality_level": "none",
        }

    def _empty_support_plan(self) -> Dict[str, Any]:
        return {
            "complexity_level": "low_or_single",
            "support_priorities": [],
            "response_alerts": [],
            "functional_contradictions": [],
        }

    def _deduplicate(self, items: List[Any]) -> List[Any]:
        seen = set()
        result = []
        for item in items:
            if item and item not in seen:
                seen.add(item)
                result.append(item)
        return result

    # =========================================================
    # FEEDBACK / CLOSE
    # =========================================================
    def register_case_feedback(
        self,
        case_id: str,
        user_feedback: Optional[str] = None,
        observed_result: Optional[str] = None,
        usefulness_score: Optional[float] = None,
        applied_successfully: Optional[bool] = None,
        helps_patterns: Optional[List[str]] = None,
        worsens_patterns: Optional[List[str]] = None,
        followup_needed: Optional[bool] = None,
    ) -> bool:
        return self.case_memory.register_case_feedback(
            case_id=case_id,
            user_feedback=user_feedback,
            observed_result=observed_result,
            usefulness_score=usefulness_score,
            applied_successfully=applied_successfully,
            helps_patterns=helps_patterns,
            worsens_patterns=worsens_patterns,
            followup_needed=followup_needed,
        )

    def register_response_feedback(
        self,
        response_id: str,
        used: bool = True,
        successful: Optional[bool] = None,
        usefulness_score: Optional[float] = None,
        notes: Optional[str] = None,
    ) -> bool:
        return self.response_memory.register_response_outcome(
            response_id=response_id,
            used=used,
            successful=successful,
            usefulness_score=usefulness_score,
            notes=notes,
        )

    def close(self) -> None:
        for component_name in [
            "profile_manager",
            "case_memory",
            "response_memory",
            "user_context_memory",
            "conversation_curation",
        ]:
            component = getattr(self, component_name, None)
            if component is None:
                continue
            try:
                component.close()
            except Exception:
                pass


def process_neuroguia_message_v2(
    message: str,
    db_path: str = "neuroguia.db",
    family_id: Optional[str] = None,
    profile_id: Optional[str] = None,
    profile_alias: Optional[str] = None,
    caregiver_capacity: Optional[float] = None,
    emotional_intensity: Optional[float] = None,
    tags: Optional[List[str]] = None,
    extra_context: Optional[Dict[str, Any]] = None,
    chat_history: Optional[List[Dict[str, Any]]] = None,
    auto_save_case: bool = True,
    auto_store_system_response: bool = False,
    auto_store_curated_llm_response: bool = True,
    use_llm_stub: bool = False,
) -> Dict[str, Any]:
    orchestrator = NeuroGuiaOrchestratorV2(db_path=db_path)
    try:
        return orchestrator.process_message(
            message=message,
            family_id=family_id,
            profile_id=profile_id,
            profile_alias=profile_alias,
            caregiver_capacity=caregiver_capacity,
            emotional_intensity=emotional_intensity,
            tags=tags,
            extra_context=extra_context,
            chat_history=chat_history,
            auto_save_case=auto_save_case,
            auto_store_system_response=auto_store_system_response,
            auto_store_curated_llm_response=auto_store_curated_llm_response,
            use_llm_stub=use_llm_stub,
        )
    finally:
        orchestrator.close()
