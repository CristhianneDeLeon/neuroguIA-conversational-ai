# -*- coding: utf-8 -*-
"""
support_playbooks.py
Catalogo conductual principal de NeuroGuIA.

Objetivo:
- centralizar rutas y subrutas con nombres explicitos
- mantener respuestas concretas, breves y calidas
- dejar que otra capa humanice el texto sin cambiar la ruta
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Literal, Optional, Sequence, Tuple


# =========================================================
# Tipos base
# =========================================================

Domain = Literal[
    "crisis",
    "ansiedad",
    "bloqueo_ejecutivo",
    "sueno",
    "apoyo_infancia_neurodivergente",
    "sobrecarga_cuidador",
    "pregunta_simple",
    "meta_question",
    "validacion_emocional",
    "rechazo_estrategia",
    "depresion_baja_energia",
    "meditacion_guiada",
    "clarificacion",
    "cierre",
    "general",
]

TurnFamily = Literal[
    "new_request",
    "followup_acceptance",
    "clarification_request",
    "blocked_followup",
    "specific_action_request",
    "literal_phrase_request",
    "post_action_followup",
    "simple_question",
    "validation_request",
    "strategy_rejection",
    "outcome_report",
    "meta_question",
    "closure_or_pause",
]

OutcomePolarity = Literal[
    "no_change",
    "worse",
    "partial_relief",
    "improved",
    "unknown",
]


@dataclass
class UserSignal:
    """Senales detectadas por capas anteriores o inferidas localmente."""

    domain: Domain
    turn_family: TurnFamily
    outcome: OutcomePolarity = "unknown"
    user_text: str = ""
    asks_for_meds: bool = False
    asks_for_phrase: bool = False
    asks_for_next_step: bool = False
    expresses_confusion: bool = False
    expresses_overwhelm: bool = False
    expresses_rejection: bool = False
    expresses_impossibility: bool = False
    wants_to_pause: bool = False
    wants_to_continue: bool = False
    mentions_risk: bool = False
    active_subroute: Optional[str] = None


@dataclass
class ResponsePlan:
    """
    Plan conductual base.
    El renderer o el LLM pueden humanizarlo, pero no cambiar su ruta.
    """

    goal: str
    tone: str
    validation: str
    main_response: str
    optional_followup: Optional[str] = None
    next_step: Optional[str] = None
    literal_phrase: Optional[str] = None
    micro_practice: Optional[str] = None
    safety_note: Optional[str] = None
    close_softly: bool = False
    needs_professional_redirect: bool = False
    route_id: Optional[Domain] = None
    subroute_id: Optional[str] = None
    state_subroute_id: Optional[str] = None
    humanization_required: bool = True
    tags: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class PlaybookSpec:
    route_id: Domain
    tone_objective: str
    validation_base: str
    max_steps: int
    expected_user_responses: List[str]
    if_not_understood: TurnFamily
    if_rejected: TurnFamily
    if_continue: TurnFamily
    if_pause: TurnFamily


# =========================================================
# Catalogo
# =========================================================

PLAYBOOK_CATALOG: Dict[Domain, Tuple[str, ...]] = {
    "crisis": (
        "crisis_initial",
        "crisis_first_step",
        "crisis_demand_examples",
        "crisis_literal_phrase",
        "crisis_check_effect",
        "crisis_close_temporarily",
    ),
    "ansiedad": (
        "anxiety_initial_grounding",
        "anxiety_visible_action",
        "anxiety_binary_decision",
        "anxiety_change_modality",
        "anxiety_hold_after_partial_relief",
        "anxiety_repair_after_rejection",
    ),
    "bloqueo_ejecutivo": (
        "executive_initial",
        "executive_no_se_que_toca",
        "executive_linea_de_que",
        "executive_no_entiendo",
        "executive_no_puedo_empezar",
        "executive_visible_next_step",
        "executive_decide_for_user",
    ),
    "sueno": (
        "sleep_initial",
        "sleep_mind_racing",
        "sleep_body_activated",
        "sleep_environment",
        "sleep_insomnia",
        "sleep_followup",
        "sleep_medication_boundary",
    ),
    "apoyo_infancia_neurodivergente": (
        "child_overthinking_support",
        "child_saturation_support",
        "child_co_regulation",
        "child_clear_communication",
        "child_reduce_stimuli",
        "child_anticipation_routines",
        "child_social_or_family_context",
    ),
    "sobrecarga_cuidador": (
        "caregiver_validation",
        "caregiver_reduce_load",
        "caregiver_ask_for_help",
        "caregiver_single_priority",
        "caregiver_self_care_without_guilt",
    ),
    "meta_question": (
        "who_are_you",
        "how_can_i_call_you",
        "can_i_talk_to_you",
        "what_can_you_do",
    ),
    "meditacion_guiada": (
        "one_minute_breath",
        "grounding_5_senses",
        "pause_guided",
    ),
    "rechazo_estrategia": (
        "strategy_repair",
        "strategy_switch",
    ),
    "clarificacion": (
        "what_phrase",
        "what_type",
        "where_do_i_start",
        "i_dont_understand",
    ),
    "cierre": (
        "pause_here",
        "enough_for_now",
    ),
}


INTERVENTION_BANK: Dict[str, Dict[str, str]] = {
    "ansiedad": {
        "grounding_pies": "Estoy contigo. Primero baja una señal del cuerpo: apoya ambos pies y suelta el aire lento una vez.",
        "respiracion_1_min": "Vamos con una respiración sencilla: inhala normal, exhala más lento. No busques hacerlo perfecto. Hazlo tres veces, como si bajaras el volumen interno.",
        "grounding_54321": "Mira alrededor: nombra 5 cosas que ves, 4 que sientes, 3 que oyes, 2 que hueles y 1 cosa que puedes saborear o imaginar. No expliques nada, solo nómbralas.",
        "descarga_mental": "Saca una preocupación de la cabeza: escribe una sola línea con lo que más pesa. No la resuelvas todavía.",
        "decision_hoy_no_hoy": "Ahora decide solo esto: ¿esa preocupación necesita acción hoy o puede esperar? Si necesita acción hoy, haz solo el primer paso; si puede esperar, déjala fuera por ahora.",
        "meditacion_1_minuto": "Vamos a meditar un minuto. No tienes que dejar la mente en blanco. Solo nota el aire entrar y salir. Si aparece un pensamiento, di por dentro: 'ahí está', y vuelve al aire.",
        "meditacion_ansiedad": "Haz una meditación muy breve para ansiedad: nota los pies, suelta el aire lento y repite por dentro: 'ahora solo una cosa'. Quédate ahí tres respiraciones.",
    },
    "crisis": {
        "crisis_self_bajar_estimulos": "Si la crisis es tuya, baja una sola entrada ahora: menos luz, menos ruido, menos pantalla o menos gente. No intentes resolver el tema en este minuto.",
        "crisis_self_contacto_apoyo": "Si estas en crisis, busca una presencia real o envia un mensaje corto a alguien seguro: 'No estoy bien, puedes quedarte pendiente de mi un momento?'.",
        "bajar_estimulos": "Estoy contigo. Primero bajemos una sola demanda: ruido, preguntas, gente o luz. Solo una.",
        "frase_literal": "Ahora usa pocas palabras. Puedes decir: 'Estoy aquí. No tienes que explicar nada. Vamos a bajar esto.'",
        "distancia_segura": "Mantén distancia segura y no invadas el espacio. Quédate cerca, pero sin arrinconar ni tocar si eso aumenta la crisis.",
        "no_discutir": "No discutas ni intentes convencer ahora. En crisis, menos palabras suele ayudar más: una frase corta, pausa y entorno más bajo.",
        "crisis_hijo_coregulacion": "Si es tu hijo o hija, primero baja tú el ritmo: voz lenta, cuerpo tranquilo y pocas palabras. No necesita una explicación larga, necesita seguridad.",
        "seguridad_entorno": "Mira el entorno: retira objetos que puedan lastimar, baja gente alrededor y deja una salida clara. Seguridad primero, explicación después.",
    },
    "sueno": {
        "rutina_bajada": "Haz una bajada de 10 minutos: baja luz, aleja pantalla y evita conversaciones exigentes. El objetivo no es dormir a la fuerza, es avisarle al cuerpo que ya puede bajar.",
        "mente_acelerada": "Si la mente no se apaga, no pelees con ella. Escribe una sola preocupación en una nota y cierra la nota. La idea no es resolverla, es sacarla de la cama.",
        "cuerpo_activado": "Si el cuerpo sigue activo, no pelees con dormir: afloja hombros, mandíbula y manos. Respira más lento tres veces y vuelve a intentar sin pantalla.",
        "entorno": "Cambia una sola cosa del entorno: menos luz, menos ruido, temperatura más cómoda o pantalla lejos. Solo una, para no activar más la cabeza.",
        "pensamientos_intrusivos": "Si aparecen pensamientos intrusivos, trátalos como ruido mental, no como tareas. Di por dentro: 'es un pensamiento, no una orden', y vuelve a una sensación física simple.",
        "si_no_puede_dormir": "Si no puedes dormir, sal de la pelea con dormir. Quédate en poca luz, sin pantalla, con algo monótono y vuelve a la cama cuando baje un poco la activación.",
        "meditacion_sueno": "Vamos con una meditación para dormir: nota el peso del cuerpo, afloja la cara y sigue el aire sin obligarte a dormir. Si aparece un pensamiento, lo dejas pasar y vuelves al peso del cuerpo.",
        "limite_medicacion": "No puedo decirte qué medicamento tomar ni recomendar dosis. Si el sueño o la ansiedad están afectando mucho, lo más seguro es consultarlo con un profesional de salud.",
    },
    "bloqueo_ejecutivo": {
        "abrir_material": "Si no sabes por dónde empezar, empieza por abrir el archivo, cuaderno o material que tengas más cerca. Nada más.",
        "tres_opciones": "Te doy tres entradas: abrir el archivo, escribir el título o poner temporizador de 2 minutos. Si no puedes elegir, empieza por abrir el archivo.",
        "temporizador": "Pon un temporizador de 2 minutos y haz solo el primer movimiento. Cuando suene, puedes parar o seguir, pero no negocies antes de empezar.",
        "titulo_feo": "Escribe solo el título o una primera frase fea. No tiene que quedar bien; tiene que existir.",
        "primer_movimiento": "Elige el movimiento más físico y pequeño: abrir, copiar una línea, poner fecha o escribir una palabra. Solo eso cuenta como empezar.",
        "si_no_sabe_que_toca": "Si no sabes qué toca, no intentes ordenar todo. Mira solo qué vence primero o qué está más a la mano, y abre eso.",
        "reducir_friccion": "Quita una fricción: deja visible el material, acerca el cargador, abre la pestaña o despeja un espacio mínimo. Preparar el inicio también cuenta.",
    },
    "apoyo_infancia_neurodivergente": {
        "sobrepensamiento": "Cuando sobrepiensa, no conviene darle muchas explicaciones. Ayúdale a sacar una sola preocupación. Una. La escriben o la dicen en voz alta y no abren las demás todavía.",
        "corregulacion": "Primero baja tú el ritmo: voz más lenta, pocas palabras y cuerpo tranquilo. Muchas veces no necesita una explicación perfecta, necesita sentir que alguien sostiene el momento.",
        "comunicacion_concreta": "Usa frases cortas y concretas: 'solo una preocupación ahora', 'no tenemos que resolverlas todas hoy', 'primero bajamos el cuerpo'.",
        "rutina_visual": "Hazlo visible: dibuja o escribe tres pasos máximos. Primero bajar estímulos, luego una preocupación, después descanso. Que pueda verlo sin sostenerlo todo en la cabeza.",
        "reduccion_sensorial": "Baja estímulos antes de explicar: menos luz, menos ruido, menos preguntas y menos gente hablando a la vez. El sistema nervioso necesita menos entrada.",
        "pensamientos_intrusivos": "Si hay pensamientos intrusivos, no los discutan uno por uno. Pueden decir: 'es un pensamiento molesto, no una instrucción', y volver a una acción segura y concreta.",
        "sueno_infancia": "Para ayudarles a dormir, baja anticipación y estímulos: misma secuencia breve, luz baja, pantalla fuera y una frase repetible como 'ahora solo toca descansar'.",
        "teen_sueno_activacion_cognitiva": "Para tu adolescente, baja activacion sin abrir temas grandes: nada de revisar pendientes ni conversaciones intensas en la cama. Deja solo una actividad tranquila y repetible.",
        "teen_rutina_baja_demanda": "Usa una rutina de baja demanda: higiene minima, luz baja, pantalla cargando fuera del cuarto y una actividad tranquila. Nada de negociar todo en plena noche.",
        "teen_descompresion_sensorial": "Antes de pedir dormir, deja una descompresion sensorial breve: menos luz, menos ruido, ropa comoda o peso del cuerpo sobre la cama. Solo un ajuste.",
        "teen_ansiedad_anticipatoria": "Si anticipa mucho el dia siguiente, separen una sola preocupacion: 'esto lo miramos manana a tal hora'. Luego vuelven a una accion simple de descanso.",
    },
    "sobrecarga_cuidador": {
        "validacion_cuidador": "Tiene sentido que tu sistema este saturado si vienes sosteniendo demasiado. Ahora no resolvemos todo: ubicamos una carga concreta.",
        "bajar_carga": "Baja una sola carga por ahora: una tarea que pueda esperar, una explicacion que no hace falta dar o una decision que no toca tomar hoy.",
        "prioridad_cuidador": "Elige una prioridad realista para hoy: seguridad, descanso o lo urgente. Si todo parece urgente, empieza por descanso minimo.",
        "pedir_ayuda_concreta": "Pide ayuda de forma cerrada: una hora, una tarea o una accion especifica. 'Puedes encargarte de esto 20 minutos?' funciona mejor que pedir ayuda en general.",
        "pausa_sin_culpa": "Haz una pausa minima sin convertirla en otro deber: agua, bano, sentarte cinco minutos o respirar afuera. Solo bajar un poco la carga.",
    },
}


def get_catalog_subroutes(route_id: Domain) -> Tuple[str, ...]:
    return PLAYBOOK_CATALOG.get(route_id, ())


# =========================================================
# Utilidades
# =========================================================

def normalize_input(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(text or "").strip().lower())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    return " ".join(normalized.split())


def normalize_text(text: str) -> str:
    return normalize_input(text)


def contains_any(text: str, phrases: Sequence[str]) -> bool:
    t = normalize_input(text)
    return any(normalize_input(phrase) in t for phrase in phrases)


def _has_any(normalized_text: str, phrases: Sequence[str]) -> bool:
    return any(normalize_input(phrase) in normalized_text for phrase in phrases)


def _text(signal: UserSignal) -> str:
    return normalize_text(signal.user_text)


def _active_subroute(signal: UserSignal) -> str:
    return normalize_text(signal.active_subroute or "")


def _dedupe(items: Sequence[str]) -> List[str]:
    seen: List[str] = []
    for item in items:
        cleaned = str(item or "").strip()
        if cleaned and cleaned not in seen:
            seen.append(cleaned)
    return seen


def _plan(
    route_id: Domain,
    subroute_id: Optional[str],
    *,
    goal: Optional[str] = None,
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
    humanization_required: bool = True,
    tags: Optional[List[str]] = None,
) -> ResponsePlan:
    merged_tags = _dedupe(
        [
            route_id,
            subroute_id or "",
            *(tags or []),
        ]
    )
    return ResponsePlan(
        goal=goal or subroute_id or "support_step",
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
        humanization_required=humanization_required,
        tags=merged_tags,
    )


# =========================================================
# Interceptores criticos de seguridad / limites
# =========================================================

MED_REQUEST_MARKERS = [
    "pastilla",
    "pastillas",
    "medicina",
    "medicamento",
    "medicamentos",
    "dosis",
    "que tomo",
    "que me tomo",
    "que pastilla",
    "que me recomiendas tomar",
    "recetame",
    "algo para dormir",
    "algo para calmarme",
    "algo para la ansiedad",
    "que le doy",
    "que le puedo dar",
]

HIGH_RISK_MARKERS = [
    "quiero morirme",
    "me quiero morir",
    "hacerme dano",
    "lastimarme",
    "lastimarlo",
    "lastimarla",
    "suicid",
    "matarme",
    "matarlo",
    "matarla",
    "no puedo mantenerlo seguro",
    "no puedo mantenerla segura",
]


CHILD_AGGRESSION_MARKERS = [
    "grita",
    "gritando",
    "esta gritando",
    "quiere golpear",
    "quiere pegar",
    "golpear a su papa",
    "golpear a su padre",
    "agresivo",
    "agresiva",
    "se esta lastimando",
    "quiere lastimar",
    "quiere lastimarse",
]


def _is_child_or_teen_context(signal: UserSignal) -> bool:
    text = _text(signal)
    return _has_any(
        text,
        [
            "mi hijo",
            "mi hija",
            "mis hijos",
            "mis hijas",
            "adolescente",
            "hijo",
            "hija",
        ],
    )


def _is_child_aggression_context(signal: UserSignal) -> bool:
    return _has_any(_text(signal), CHILD_AGGRESSION_MARKERS) and (
        signal.domain == "crisis" or _is_child_or_teen_context(signal)
    )


def intercept_medication_request(signal: UserSignal) -> Optional[ResponsePlan]:
    if signal.asks_for_meds or contains_any(signal.user_text, MED_REQUEST_MARKERS):
        route_id: Domain = signal.domain if signal.domain in PLAYBOOK_CATALOG else "general"
        subroute_id = "sleep_medication_boundary" if signal.domain == "sueno" else None
        optional_followup = (
            "Si quieres, te dejo una medida no farmacologica para esta noche."
            if signal.domain == "sueno"
            else "Si quieres, si puedo ayudarte con una medida sencilla y no farmacologica para este momento."
        )
        return _plan(
            route_id=route_id,
            subroute_id=subroute_id,
            goal="safe_medication_boundary",
            tone="calido_claro_seguro",
            validation="Entiendo que buscas algo que ayude ya.",
            main_response=(
                "No puedo decirte que medicamento tomar ni recomendar dosis. "
                "Si esto te esta pegando fuerte, lo mas seguro es consultarlo con un profesional de salud."
            ),
            optional_followup=optional_followup,
            needs_professional_redirect=True,
            state_subroute_id=signal.active_subroute,
            tags=["safety", "medication_boundary"],
        )
    return None


def intercept_high_risk(signal: UserSignal) -> Optional[ResponsePlan]:
    if signal.mentions_risk or contains_any(signal.user_text, HIGH_RISK_MARKERS):
        route_id: Domain = signal.domain if signal.domain in PLAYBOOK_CATALOG else "general"
        return _plan(
            route_id=route_id,
            subroute_id=None,
            goal="high_risk_redirect",
            tone="calido_firme_seguro",
            validation="Gracias por decirlo. No conviene que te quedes sola/o con esto.",
            main_response=(
                "Ahora mismo lo importante es la seguridad inmediata. Busca apoyo presencial o de emergencia cerca de ti ya. "
                "Si hay alguien contigo o a quien puedas llamar, hazlo en este momento."
            ),
            optional_followup=(
                "Mientras llega apoyo, alejate de objetos peligrosos y no te quedes sola/o si puedes evitarlo."
            ),
            safety_note="prioridad_seguridad_inmediata",
            needs_professional_redirect=True,
            state_subroute_id=signal.active_subroute,
            tags=["safety", "high_risk"],
        )
    return None


# =========================================================
# Detectores de subrutas
# =========================================================

def _sleep_track(signal: UserSignal) -> str:
    text = _text(signal)
    active = _active_subroute(signal)
    if _has_any(
        text,
        [
            "mente acelerada",
            "cabeza acelerada",
            "pensando mucho",
            "no apago la mente",
            "la mente no se calla",
        ],
    ):
        return "sleep_mind_racing"
    if _has_any(
        text,
        [
            "cuerpo activado",
            "cuerpo inquieto",
            "corazon acelerado",
            "palpitaciones",
            "muy activada",
            "muy activado",
        ],
    ):
        return "sleep_body_activated"
    if _has_any(text, ["ruido", "luz", "pantalla", "calor", "frio", "entorno", "ambiente", "temperatura"]):
        return "sleep_environment"
    if _has_any(
        text,
        [
            "desvelo",
            "insomnio",
            "no puedo dormir",
            "me cuesta dormir",
            "llevo horas despierta",
            "llevo horas despierto",
            "me desperte",
            "me desperte a media noche",
            "me desperte en la madrugada",
            "ya me desperte",
        ],
    ):
        return "sleep_insomnia"
    if active in {
        "sleep_mind_racing",
        "sleep_body_activated",
        "sleep_environment",
        "sleep_insomnia",
    }:
        return active
    return "sleep_initial"


def _block_track(signal: UserSignal) -> str:
    text = _text(signal)
    active = _active_subroute(signal)
    if _has_any(text, ["linea de que", "que linea", "que pongo", "que escribo primero"]):
        return "executive_linea_de_que"
    if _has_any(text, ["no se que toca", "no se que sigue", "no se que hacer"]):
        return "executive_no_se_que_toca"
    if _has_any(text, ["no entiendo", "no le entiendo", "no entiendo la tarea", "no entiendo la consigna"]):
        return "executive_no_entiendo"
    if _has_any(text, ["no puedo empezar", "no puedo arrancar", "no puedo iniciar", "no puedo ni empezar"]):
        return "executive_no_puedo_empezar"
    if _has_any(text, ["decide tu", "elige tu", "escoge tu", "tu dime", "yo no quiero elegir"]):
        return "executive_decide_for_user"
    if active in set(PLAYBOOK_CATALOG["bloqueo_ejecutivo"]):
        return active
    return "executive_initial"


def _child_support_track(signal: UserSignal) -> str:
    text = _text(signal)
    active = _active_subroute(signal)
    if _has_any(text, ["escuela", "maestra", "maestro", "familia", "hermano", "hermana", "visita", "social"]):
        return "child_social_or_family_context"
    if _has_any(text, ["sobrepiensa", "sobre pensar", "sobrepensar", "sobrepensamiento", "le da muchas vueltas", "piensa demasiado"]):
        return "child_overthinking_support"
    if _has_any(text, ["saturacion", "se satura", "sobrecarga", "demasiado estimulo", "demasiado ruido"]):
        return "child_saturation_support"
    if _has_any(text, ["como le digo", "como le hablo", "que le digo", "que le puedo decir", "frase"]):
        return "child_clear_communication"
    if _has_any(text, ["estimulos", "ruido", "luz", "pantalla", "ambiente", "entorno"]):
        return "child_reduce_stimuli"
    if _has_any(text, ["rutina", "anticipacion", "transicion", "cambio", "preparar antes", "avisarle antes"]):
        return "child_anticipation_routines"
    if active in set(PLAYBOOK_CATALOG["apoyo_infancia_neurodivergente"]):
        return active
    return "child_co_regulation"


def _caregiver_track(signal: UserSignal) -> str:
    text = _text(signal)
    active = _active_subroute(signal)
    if _has_any(text, ["culpa", "me siento mal por descansar", "no deberia parar", "descansar"]):
        return "caregiver_self_care_without_guilt"
    if _has_any(text, ["nadie me ayuda", "estoy sola", "estoy solo", "no tengo apoyo", "necesito ayuda"]):
        return "caregiver_ask_for_help"
    if _has_any(text, ["no se que soltar", "todo me cae a mi", "todo depende de mi", "todo me toca"]):
        return "caregiver_reduce_load"
    if _has_any(text, ["que hago primero", "que priorizo", "que atiendo primero", "no se por donde"]):
        return "caregiver_single_priority"
    if active in set(PLAYBOOK_CATALOG["sobrecarga_cuidador"]):
        return active
    return "caregiver_validation"


def _meditation_track(signal: UserSignal) -> str:
    text = _text(signal)
    active = _active_subroute(signal)
    if _has_any(text, ["respiracion", "respirar", "un minuto", "1 minuto"]):
        return "one_minute_breath"
    if _has_any(text, ["5 sentidos", "cinco sentidos", "grounding", "aterrizar", "volver aqui"]):
        return "grounding_5_senses"
    if active in set(PLAYBOOK_CATALOG["meditacion_guiada"]):
        return active
    return "pause_guided"


def _rejection_track(signal: UserSignal) -> str:
    text = _text(signal)
    active = _active_subroute(signal)
    if _has_any(text, ["no sirves", "no ayudas", "no me ayudas", "me desespera esto", "esto me frustra"]):
        return "strategy_repair"
    if active in set(PLAYBOOK_CATALOG["rechazo_estrategia"]):
        return active
    return "strategy_switch"


def _meta_track(signal: UserSignal) -> str:
    text = _text(signal)
    if _has_any(text, ["como puedo llamarte", "como te llamo", "tu nombre"]):
        return "how_can_i_call_you"
    if _has_any(text, ["puedo platicar contigo", "puedo hablar contigo", "estas ahi", "estas aqui"]):
        return "can_i_talk_to_you"
    if _has_any(text, ["que puedes hacer", "como ayudas", "en que ayudas", "que haces"]):
        return "what_can_you_do"
    return "who_are_you"


def _clarification_track(signal: UserSignal) -> str:
    text = _text(signal)
    active = _active_subroute(signal)
    if _has_any(text, ["que frase", "que digo", "cual frase", "como se lo digo"]):
        return "what_phrase"
    if _has_any(text, ["que tipo", "como cual", "cuales", "ejemplos"]):
        return "what_type"
    if _has_any(text, ["por donde", "donde empiezo", "como empiezo", "con que empiezo"]):
        return "where_do_i_start"
    if active in set(PLAYBOOK_CATALOG["clarificacion"]):
        return active
    return "i_dont_understand"


def _close_track(signal: UserSignal) -> str:
    text = _text(signal)
    if _has_any(text, ["pausa", "paramos aqui", "por ahora"]):
        return "pause_here"
    return "enough_for_now"


# =========================================================
# Modo demo estable / respuestas deterministicas
# =========================================================

DETERMINISTIC_SUPPORT_ROUTES = {
    "crisis",
    "ansiedad",
    "sueno",
    "bloqueo_ejecutivo",
    "apoyo_infancia_neurodivergente",
    "sobrecarga_cuidador",
    "meta_question",
    "meditacion_guiada",
    "rechazo_estrategia",
}


def _canonical_route_id(route_id: Optional[str]) -> str:
    return normalize_input(str(route_id or "")).replace(" ", "_")


def _canonical_subroute_id(subroute_id: Optional[str]) -> str:
    return normalize_input(str(subroute_id or "")).replace(" ", "_")


def _canonical_recent_subroutes(recent_subroutes: Optional[Sequence[str]]) -> List[str]:
    return [_canonical_subroute_id(item) for item in (recent_subroutes or []) if str(item or "").strip()]


def _demo_has(normalized_text: str, phrases: Sequence[str]) -> bool:
    return _has_any(normalized_text, phrases)


def _demo_wants_next(normalized_text: str) -> bool:
    return _demo_has(
        normalized_text,
        [
            "ok",
            "que sigue",
            "que mas",
            "que hago",
            "dime que hago",
            "dime que sigue",
            "y luego",
            "y ahora",
            "dale",
            "va",
        ],
    )


def _demo_rejects_or_reports_repeat(normalized_text: str) -> bool:
    return _demo_has(
        normalized_text,
        [
            "eso no me funciona",
            "no me funciona",
            "no funciona",
            "no me sirve",
            "eso ya me lo dijiste",
            "ya me lo dijiste",
            "ya lo dijiste",
            "sigues repitiendo",
            "estas repitiendo",
            "repites lo mismo",
        ],
    )


def _demo_asks_for_meds(normalized_text: str) -> bool:
    return _demo_has(normalized_text, MED_REQUEST_MARKERS)


def is_deterministic_support_route(route_id: Optional[str]) -> bool:
    return _canonical_route_id(route_id) in DETERMINISTIC_SUPPORT_ROUTES


def render_crisis_response(
    route_id: Optional[str],
    subroute_id: Optional[str],
    user_message: str,
    recent_subroutes: Optional[Sequence[str]],
) -> str:
    route = _canonical_route_id(route_id)
    subroute = _canonical_subroute_id(subroute_id)
    text = normalize_input(user_message)
    recent = _canonical_recent_subroutes(recent_subroutes)

    if route != "crisis":
        return ""
    if _demo_has(text, CHILD_AGGRESSION_MARKERS) or _demo_has(text, ["crisis es de mi hijo", "crisis es de mi hija"]):
        return (
            "Gracias por aclararlo. Si tu hijo esta gritando o quiere golpear, ahora la prioridad es seguridad fisica: "
            "separa a su papa si puedes, retira objetos que puedan lastimar y no intentes razonar con el. "
            "Usa pocas palabras: 'Estoy aqui. Vamos a darte espacio'. Si hay riesgo inmediato, pide apoyo presencial o servicios de emergencia."
        )
    if _demo_rejects_or_reports_repeat(text):
        return "Está bien, cambiamos. Si no bajó con palabras, cambia el entorno: menos gente, menos ruido o más espacio físico."
    if subroute in {"crisis_first_step", "crisis_check_effect", "crisis_demand_examples"} and "crisis_literal_phrase" in recent:
        return "Ahora cambia una sola cosa del entorno: menos gente, menos ruido o más espacio físico. No agregues explicación ni debate."
    if subroute == "crisis_literal_phrase" or (
        "crisis_initial" in recent and "crisis_literal_phrase" not in recent and _demo_wants_next(text)
    ):
        return "Ahora usa pocas palabras. Puedes decir: 'Estoy aquí. No tienes que explicar nada. Vamos a bajar esto.' Mantén distancia segura y no discutas."
    if subroute == "crisis_close_temporarily":
        return "Por ahora no agregues otra demanda. Sostén pocas palabras, distancia segura y el entorno lo más bajo posible."
    return "Estoy contigo. Primero bajemos una sola demanda: ruido, preguntas, gente o luz. Solo una."


def render_sleep_response(
    route_id: Optional[str],
    subroute_id: Optional[str],
    user_message: str,
    recent_subroutes: Optional[Sequence[str]],
) -> str:
    route = _canonical_route_id(route_id)
    subroute = _canonical_subroute_id(subroute_id)
    text = normalize_input(user_message)
    recent = _canonical_recent_subroutes(recent_subroutes)

    if route != "sueno":
        return ""
    if _demo_has(text, ["no es sobrepensamiento", "adolescente", "adolescentes", "mis hijos adolescentes"]):
        return "Tienes razon, me centro en sueno. Con adolescentes suele funcionar mejor negociar antes, no en plena noche: pantalla cargando fuera del cuarto, luz baja y una actividad tranquila de 10 a 15 minutos."
    if _demo_rejects_or_reports_repeat(text):
        return "Tienes razon, cambiamos sin salirnos de sueno: menos negociacion en plena noche, pantalla fuera de la cama y una actividad tranquila de 10 a 15 minutos."
    if _demo_asks_for_meds(text) or subroute == "sleep_medication_boundary":
        return "No puedo decirte qué medicamento tomar ni recomendar dosis. Si el sueño está afectando mucho, lo más seguro es consultarlo con un profesional de salud. Sí puedo ayudarte con una medida no farmacológica para esta noche."
    if _demo_rejects_or_reports_repeat(text):
        return "Está bien, cambiamos. Para esta noche, deja solo una bajada: menos luz o menos pantalla durante 10 minutos."
    if subroute == "sleep_followup" or (_demo_wants_next(text) and recent):
        return "Para esta noche: baja luz o pantalla durante 10 minutos. Si la mente sigue acelerada, escribe una sola preocupación en una nota y ciérrala."
    if subroute == "sleep_mind_racing":
        return "Si la mente va rápido, no intentes resolver todo en la cama. Escribe una sola preocupación y cierra la nota."
    if subroute == "sleep_body_activated":
        return "Si el cuerpo está activado, no fuerces dormir todavía. Baja luz, afloja mandíbula y deja el cuerpo quieto unos minutos."
    if subroute == "sleep_environment":
        return "Ajusta una sola cosa del entorno: luz, ruido, pantalla o temperatura. Solo una."
    return "Sí, el sueño puede mover todo lo demás. Vamos a ubicar qué parte pesa más: mente acelerada, cuerpo activado o entorno."


def render_executive_response(
    route_id: Optional[str],
    subroute_id: Optional[str],
    user_message: str,
    recent_subroutes: Optional[Sequence[str]],
) -> str:
    route = _canonical_route_id(route_id)
    subroute = _canonical_subroute_id(subroute_id)
    text = normalize_input(user_message)
    recent = _canonical_recent_subroutes(recent_subroutes)

    if route != "bloqueo_ejecutivo":
        return ""
    if _demo_has(text, ["no tengo archivo", "no hay archivo", "no tengo nada que abrir", "no tengo en que escribir", "no tengo donde escribir"]):
        return "No necesitas archivo ni hoja para empezar. Di en voz alta el nombre de la tarea y elige solo el primer verbo: leer, buscar, escribir o revisar."
    if _demo_rejects_or_reports_repeat(text):
        return "Tienes razón. No repito eso. Cambio de vía: te doy una acción distinta y concreta. Pon un temporizador de 2 minutos y abre el archivo."
    if _demo_has(text, ["no se como", "no entiendo", "como lo hago"]) or subroute in {"executive_no_entiendo", "executive_no_puedo_empezar"}:
        return "Entonces lo hago más concreto: abre el archivo o cuaderno que tengas más cerca. No escribas nada todavía. Solo abrirlo."
    if subroute in {"executive_visible_next_step", "executive_no_se_que_toca", "executive_linea_de_que"} or (_demo_wants_next(text) and recent):
        return "Ahora escribe solo el título o una primera frase fea. No tiene que quedar bien; solo tiene que existir."
    return "No empecemos por organizar todo. Elige una de estas tres: abrir el archivo, escribir el título o poner un temporizador de 2 minutos."


def render_anxiety_response(
    route_id: Optional[str],
    subroute_id: Optional[str],
    user_message: str,
    recent_subroutes: Optional[Sequence[str]],
) -> str:
    route = _canonical_route_id(route_id)
    subroute = _canonical_subroute_id(subroute_id)
    text = normalize_input(user_message)
    recent = _canonical_recent_subroutes(recent_subroutes)

    if route != "ansiedad":
        return ""
    if _demo_has(text, ["lo escribo aqui", "la escribo aqui", "las escribo aqui", "escribo aqui"]):
        return "Si, puedes escribirlo aqui si quieres. Puede ser solo una linea; no tiene que estar completa."
    if _demo_has(text, ["no tengo ganas de escribir", "no quiero escribir", "no puedo escribir", "no tengo en que escribir"]):
        return "Entonces no escribimos. Dilo en voz baja o nombralo mentalmente: 'lo que mas pesa es...'. Con eso basta por ahora."
    if _demo_rejects_or_reports_repeat(text):
        return "Tienes razón. No repito eso. Cambio de vía: escribe solo lo que sí vence hoy y deja quieto lo que puede esperar."
    if subroute in {"anxiety_visible_action", "anxiety_change_modality"} or (_demo_wants_next(text) and recent):
        return "Ahora saca una preocupación de la cabeza: escribe una sola línea con lo que más pesa. No la resuelvas todavía."
    if subroute == "anxiety_binary_decision":
        return "Ahora ciérralo en una decisión simple: si vence hoy, atiende solo eso; si no vence hoy, queda quieto por ahora."
    return "Estoy contigo. Primero baja una sola señal del cuerpo: apoya ambos pies y suelta el aire lento una vez."


def render_child_support_response(
    route_id: Optional[str],
    subroute_id: Optional[str],
    user_message: str,
    recent_subroutes: Optional[Sequence[str]],
) -> str:
    route = _canonical_route_id(route_id)
    subroute = _canonical_subroute_id(subroute_id)
    text = normalize_input(user_message)
    recent = _canonical_recent_subroutes(recent_subroutes)

    if route != "apoyo_infancia_neurodivergente":
        return ""
    if _demo_has(text, ["no es sobrepensamiento"]) and _demo_has(text, ["sueno", "sue o", "dormir"]):
        return "Tienes razon, me centro en sueno. Con adolescentes, negocia antes y no en plena noche: pantalla fuera del cuarto, luz baja y una actividad tranquila de 10 a 15 minutos."
    if _demo_has(text, ["adolescente", "adolescentes", "mis hijos adolescentes"]) and _demo_has(text, ["sueno", "sue o", "dormir", "insomnio"]):
        return "Con adolescentes suele funcionar mejor un acuerdo breve: pantalla cargando fuera del cuarto, luz baja y una actividad tranquila. Si no aceptan todo, empieza por pantalla fuera de la cama."
    if _demo_rejects_or_reports_repeat(text):
        return "Tienes razón. No repito eso. Cambio de vía: vuelve al foco de tu hija o hijo con una sola ayuda concreta."
    if _demo_has(text, ["sobrepiensa", "sobrepensar", "sobrepensamiento"]) or subroute == "child_overthinking_support":
        return "Cuando sobrepiensa, suele ayudar más bajar velocidad que explicar más. Pídele que elija una sola preocupación. Una. La escriben o la dicen en voz alta, y no abren las demás todavía."
    if subroute == "child_clear_communication":
        return "Usa una frase corta y repetible: 'solo una preocupación ahora; las demás no las abrimos todavía'."
    if subroute == "child_reduce_stimuli":
        return "Para tus hijos, baja un estímulo concreto: menos luz, menos ruido, menos pantalla o menos gente cerca. Solo uno."
    if _demo_wants_next(text) and recent:
        return "Sigue dentro del mismo foco: menos estímulos, frases cortas y una sola preocupación afuera de la cabeza."
    return "Claro. Aquí el foco son tus hijos. Para esta noche, no intentaría convencerlos con muchas explicaciones. Haría tres cosas: bajar estímulos, usar frases cortas y sacar una sola preocupación a papel o voz. Por ejemplo: 'solo vamos a escribir una preocupación y luego descansamos'."


def render_caregiver_response(
    route_id: Optional[str],
    subroute_id: Optional[str],
    user_message: str,
    recent_subroutes: Optional[Sequence[str]],
) -> str:
    route = _canonical_route_id(route_id)
    subroute = _canonical_subroute_id(subroute_id)
    text = normalize_input(user_message)
    recent = _canonical_recent_subroutes(recent_subroutes)

    if route != "sobrecarga_cuidador":
        return ""
    if _demo_rejects_or_reports_repeat(text):
        return "Tienes razón. No repito eso. Cambio de vía: baja una sola carga concreta que pueda esperar."
    if subroute == "caregiver_ask_for_help":
        return "Pide una ayuda cerrada, no ayuda en general: una hora, una tarea o una decisión concreta."
    if subroute == "caregiver_self_care_without_guilt":
        return "Haz una pausa mínima sin culpa: agua, baño, sentarte cinco minutos o respirar fuera."
    if subroute == "caregiver_single_priority" or (_demo_wants_next(text) and recent):
        return "Cierra una sola prioridad para hoy: seguridad, descanso o lo que vence hoy. Solo una."
    return "Esto es mucho para sostenerlo sola/o. Baja una sola carga ahora: una tarea que pueda esperar, una petición concreta o una pausa mínima."


def render_meta_response(
    route_id: Optional[str],
    subroute_id: Optional[str],
    user_message: str,
    recent_subroutes: Optional[Sequence[str]],
) -> str:
    route = _canonical_route_id(route_id)
    subroute = _canonical_subroute_id(subroute_id)
    text = normalize_input(user_message)
    _ = _canonical_recent_subroutes(recent_subroutes)

    if route != "meta_question":
        return ""
    if subroute == "how_can_i_call_you" or _demo_has(text, ["como puedo llamarte", "como te llamo", "tu nombre"]):
        return "Puedes llamarme NeuroGuIA."
    if subroute == "can_i_talk_to_you" or _demo_has(text, ["puedo hablar contigo", "puedo platicar contigo"]):
        return "Sí. Puedes hablar conmigo aquí; te respondo con pasos claros y cuidado."
    if subroute == "what_can_you_do" or _demo_has(text, ["que puedes hacer", "como ayudas", "que haces"]):
        return "Puedo ayudarte con crisis, ansiedad, sueño, bloqueo, apoyo a hijas/os neurodivergentes y sobrecarga de cuidado, con pasos breves."
    return "Soy NeuroGuIA. Estoy aquí para acompañar, ordenar lo que pasa y ayudarte a encontrar un paso claro."


def render_meditation_response(
    route_id: Optional[str],
    subroute_id: Optional[str],
    user_message: str,
    recent_subroutes: Optional[Sequence[str]],
) -> str:
    route = _canonical_route_id(route_id)
    subroute = _canonical_subroute_id(subroute_id)
    _ = normalize_input(user_message)
    _recent = _canonical_recent_subroutes(recent_subroutes)

    if route != "meditacion_guiada":
        return ""
    if subroute == "one_minute_breath":
        return "Hagamos un minuto: inhala normal, suelta el aire lento y deja bajar los hombros. Repite tres veces."
    if subroute == "grounding_5_senses":
        return "Aterriza con cinco sentidos: nombra cinco cosas que ves, cuatro que tocas, tres que oyes, dos que hueles y una que saboreas o recuerdas."
    return "Haz una pausa breve conmigo: baja hombros, nota tres cosas que ves y suelta el aire una vez."


def render_rejection_response(
    route_id: Optional[str],
    subroute_id: Optional[str],
    user_message: str,
    recent_subroutes: Optional[Sequence[str]],
) -> str:
    route = _canonical_route_id(route_id)
    _ = _canonical_subroute_id(subroute_id)
    _text = normalize_input(user_message)
    _recent = _canonical_recent_subroutes(recent_subroutes)

    if route != "rechazo_estrategia":
        return ""
    return "Tienes razón. No repito eso. Cambio de vía: te doy una acción distinta y concreta."


def render_deterministic_support_response(
    route_id: Optional[str],
    subroute_id: Optional[str],
    user_message: str,
    recent_subroutes: Optional[Sequence[str]] = None,
) -> str:
    route = _canonical_route_id(route_id)
    if route == "crisis":
        return render_crisis_response(route_id, subroute_id, user_message, recent_subroutes)
    if route == "ansiedad":
        return render_anxiety_response(route_id, subroute_id, user_message, recent_subroutes)
    if route == "sueno":
        return render_sleep_response(route_id, subroute_id, user_message, recent_subroutes)
    if route == "bloqueo_ejecutivo":
        return render_executive_response(route_id, subroute_id, user_message, recent_subroutes)
    if route == "apoyo_infancia_neurodivergente":
        return render_child_support_response(route_id, subroute_id, user_message, recent_subroutes)
    if route == "sobrecarga_cuidador":
        return render_caregiver_response(route_id, subroute_id, user_message, recent_subroutes)
    if route == "meta_question":
        return render_meta_response(route_id, subroute_id, user_message, recent_subroutes)
    if route == "meditacion_guiada":
        return render_meditation_response(route_id, subroute_id, user_message, recent_subroutes)
    if route == "rechazo_estrategia":
        return render_rejection_response(route_id, subroute_id, user_message, recent_subroutes)
    return ""


# =========================================================
# Playbooks especificos
# =========================================================

def playbook_meta_question(signal: UserSignal) -> ResponsePlan:
    track = _meta_track(signal)
    if track == "how_can_i_call_you":
        return _plan(
            route_id="meta_question",
            subroute_id=track,
            goal="answer_about_system_briefly",
            tone="calido_humano_directo",
            validation="",
            main_response="Puedes llamarme NeuroGuIA, o como te salga mas natural.",
            close_softly=True,
            tags=["meta", "identity"],
        )
    if track == "can_i_talk_to_you":
        return _plan(
            route_id="meta_question",
            subroute_id=track,
            goal="answer_about_system_briefly",
            tone="calido_humano_directo",
            validation="",
            main_response="Si, claro. Puedes hablar conmigo aqui y lo vemos contigo, paso a paso.",
            close_softly=True,
            tags=["meta", "availability"],
        )
    if track == "what_can_you_do":
        return _plan(
            route_id="meta_question",
            subroute_id=track,
            goal="answer_about_system_briefly",
            tone="calido_humano_directo",
            validation="",
            main_response=(
                "Puedo ayudarte a bajar una crisis, aterrizar ansiedad, ordenar un bloqueo, "
                "pensar el sueño y darte frases o pasos concretos."
            ),
            optional_followup="Si quieres, cuentame que esta pesando mas ahorita.",
            tags=["meta", "capabilities"],
        )
    return _plan(
        route_id="meta_question",
        subroute_id="who_are_you",
        goal="answer_about_system_briefly",
        tone="calido_humano_directo",
        validation="",
        main_response="Soy NeuroGuIA. Estoy aqui para acompanar, ordenar lo que esta pasando y ayudarte a encontrar un paso claro cuando haga falta.",
        optional_followup="Si quieres, cuentame que esta pasando ahorita.",
        tags=["meta", "identity"],
    )


def playbook_crisis(signal: UserSignal) -> ResponsePlan:
    text = _text(signal)
    active = _active_subroute(signal)

    if _is_child_aggression_context(signal):
        return _plan(
            route_id="crisis",
            subroute_id="crisis_first_step",
            goal="child_aggression_safety_first",
            tone="calido_firme_breve",
            validation="Gracias por aclararlo.",
            main_response=(
                "Si tu hijo esta gritando o quiere golpear, ahora la prioridad es seguridad fisica: separa a su papa si puedes, "
                "retira objetos que puedan lastimar y no intentes razonar con el en este momento."
            ),
            literal_phrase="Estoy aqui. Vamos a darte espacio.",
            optional_followup="Si hay riesgo inmediato de dano, pide apoyo presencial o servicios de emergencia.",
            safety_note="prioridad_seguridad_fisica",
            tags=["crisis", "hijo", "seguridad_fisica"],
        )

    if signal.turn_family == "closure_or_pause" or signal.wants_to_pause:
        return _plan(
            route_id="crisis",
            subroute_id="crisis_close_temporarily",
            goal="pause_after_crisis_step",
            tone="calido_suave",
            validation="Esta bien.",
            main_response="Por ahora basta. Sosten la frase breve y el entorno mas bajo un momento.",
            optional_followup="Si vuelve a subir, vuelves aqui y seguimos desde una sola cosa a la vez.",
            close_softly=True,
            state_subroute_id=active or "crisis_close_temporarily",
            tags=["crisis", "cierre_temporal"],
        )

    if signal.turn_family == "literal_phrase_request" or signal.asks_for_phrase:
        return _plan(
            route_id="crisis",
            subroute_id="crisis_literal_phrase",
            goal="literal_phrase_for_crisis",
            tone="calido_firme_breve",
            validation="",
            main_response="Puedes decirle esto, tal cual:",
            literal_phrase="Estoy aqui contigo. No te voy a exigir nada ahora. Vamos a bajar esto juntos.",
            optional_followup="Dilo con voz baja y sin meter otra instruccion al mismo tiempo.",
            tags=["crisis", "frase_literal"],
        )

    if signal.turn_family == "clarification_request" or signal.expresses_confusion:
        if _has_any(text, ["que tipo", "como cuales", "cuales", "ejemplos"]) or active == "crisis_demand_examples":
            return _plan(
                route_id="crisis",
                subroute_id="crisis_demand_examples",
                goal="clarify_crisis_examples",
                tone="claro_firme",
                validation="Si, te digo ejemplos concretos.",
                main_response="Baja una sola demanda concreta: menos gente cerca, menos preguntas, menos ruido, menos luz o menos contacto.",
                optional_followup="Elige solo una y cambia esa primero.",
                tags=["crisis", "demanda_examples"],
            )
        return _plan(
            route_id="crisis",
            subroute_id="crisis_first_step",
            goal="clarify_crisis_step",
            tone="claro_firme",
            validation="Si, te lo digo directo.",
            main_response="Haz primero una sola cosa visible: saca preguntas, baja ruido o aleja gente de alrededor.",
            next_step="Saca preguntas, baja ruido o aleja gente de alrededor",
            optional_followup="Cuando eso baje un poco, te doy la frase breve.",
            tags=["crisis", "primer_paso_concreto"],
        )

    if signal.turn_family == "specific_action_request":
        return _plan(
            route_id="crisis",
            subroute_id="crisis_first_step",
            goal="first_concrete_step_in_crisis",
            tone="firme_claro",
            validation="Estoy contigo.",
            main_response="Empieza por una sola cosa visible: baja ruido, saca gente o corta las preguntas alrededor.",
            next_step="Baja ruido, saca gente o corta las preguntas alrededor",
            optional_followup="Despues usas una frase breve y no discutes.",
            tags=["crisis", "primer_paso_concreto"],
        )

    if signal.turn_family == "strategy_rejection":
        return _plan(
            route_id="crisis",
            subroute_id="crisis_first_step",
            goal="change_modality_after_no_effect_crisis",
            tone="calido_firme",
            validation="Entiendo la frustracion. No voy a insistir con algo que no bajo esto.",
            main_response="Cambiemos rapido: menos palabras, mas espacio seguro y una sola accion del entorno.",
            next_step="Deja menos palabras y baja una sola demanda del entorno",
            optional_followup="Si quieres, te doy la frase exacta para hacer ese cambio.",
            tags=["crisis", "cambio_de_via"],
        )

    if signal.turn_family == "followup_acceptance" or signal.asks_for_next_step or signal.wants_to_continue:
        if active in {"crisis_initial", "crisis_first_step", "crisis_demand_examples"}:
            return _plan(
                route_id="crisis",
                subroute_id="crisis_literal_phrase",
                goal="next_step_after_initial_crisis_containment",
                tone="firme_claro",
                validation="Si, aqui sigo.",
                main_response="Ahora sosten una sola frase breve y quedate presente sin discutir.",
                literal_phrase="Estoy aquí. No tienes que explicar nada. Vamos a bajar esto.",
                optional_followup="Mantén distancia segura y no discutas.",
                tags=["crisis", "seguimiento"],
            )
        return _plan(
            route_id="crisis",
            subroute_id="crisis_check_effect",
            goal="check_effect_or_next_step_crisis",
            tone="firme_claro",
            validation="Si, mira solo esto ahora.",
            main_response="Revisa si hay menos ruido, menos tension o un poco mas de espacio seguro que hace un momento.",
            optional_followup="Si bajo un poco, sostengan eso. Si no, quitamos una demanda mas.",
            tags=["crisis", "seguimiento"],
        )

    if signal.turn_family == "post_action_followup":
        return _plan(
            route_id="crisis",
            subroute_id="crisis_check_effect",
            goal="check_effect_or_next_step_crisis",
            tone="firme_claro",
            validation="",
            main_response="Mira solo esto: hay un poco menos de ruido, menos tension o mas espacio seguro que hace un momento.",
            optional_followup="Si si, sostengan eso un momento. Si no, quitamos una sola demanda mas.",
            tags=["crisis", "seguimiento"],
        )

    if signal.turn_family == "outcome_report":
        if signal.outcome in ("partial_relief", "improved"):
            return _plan(
                route_id="crisis",
                subroute_id="crisis_close_temporarily",
                goal="hold_after_effect_crisis",
                tone="calido_firme",
                validation="Bien, aunque sea un poco, eso ya importa.",
                main_response="Quedense con lo que ya bajo y no agreguen otra demanda por ahora.",
                close_softly=True,
                state_subroute_id=active or "crisis_close_temporarily",
                tags=["crisis", "sostener"],
            )
        if signal.outcome in ("no_change", "worse"):
            return _plan(
                route_id="crisis",
                subroute_id="crisis_demand_examples",
                goal="change_modality_after_no_effect_crisis",
                tone="firme_claro",
                validation="Gracias por decirmelo.",
                main_response="Entonces baja una sola demanda distinta: menos gente, menos ruido, menos luz o menos contacto.",
                next_step="Quita una sola demanda distinta del entorno",
                optional_followup="Si quieres, tambien te doy la frase exacta para ese cambio.",
                tags=["crisis", "cambio_de_via"],
            )

    return _plan(
        route_id="crisis",
        subroute_id="crisis_initial",
        goal="initial_crisis_containment",
        tone="calido_firme_breve",
        validation="Estoy contigo.",
        main_response="Lo primero es bajar una sola demanda alrededor. Quita ruido, preguntas, gente o luz, pero solo una.",
        next_step="Quita una sola demanda alrededor",
        optional_followup="Cuando eso baje un poco, te doy el siguiente paso sin abrir todo a la vez.",
        tags=["crisis", "inicio"],
    )


def playbook_anxiety(signal: UserSignal) -> ResponsePlan:
    active = _active_subroute(signal)
    text = _text(signal)

    if _has_any(text, ["lo escribo aqui", "la escribo aqui", "las escribo aqui", "escribo aqui"]):
        return _plan(
            route_id="ansiedad",
            subroute_id="anxiety_visible_action",
            goal="answer_where_to_write",
            tone="calido_directo",
            validation="Si.",
            main_response="Puedes escribirlo aqui si quieres. Puede ser solo una linea; no tiene que estar completa.",
            tags=["ansiedad", "pregunta_directa"],
        )
    if _has_any(text, ["no tengo ganas de escribir", "no quiero escribir", "no puedo escribir", "no tengo en que escribir"]):
        return _plan(
            route_id="ansiedad",
            subroute_id="anxiety_visible_action",
            goal="no_writing_alternative",
            tone="calido_directo",
            validation="Entonces no escribimos.",
            main_response="Dilo en voz baja o nombralo mentalmente: 'lo que mas pesa es...'. Con eso basta por ahora.",
            tags=["ansiedad", "sin_escritura"],
        )

    if signal.turn_family == "clarification_request" or signal.expresses_confusion:
        if active == "anxiety_visible_action":
            return _plan(
                route_id="ansiedad",
                subroute_id="anxiety_visible_action",
                goal="clarify_anxiety_step",
                tone="claro_calido",
                validation="Si, te lo bajo.",
                main_response="Abre una nota y escribe una sola linea con lo que te preocupa mas ahorita.",
                next_step="Escribe una sola linea con la preocupacion principal",
                tags=["ansiedad", "accion_visible"],
            )
        return _plan(
            route_id="ansiedad",
            subroute_id="anxiety_initial_grounding",
            goal="clarify_anxiety_step",
            tone="claro_calido",
            validation="Si, te lo digo directo.",
            main_response="Si la ansiedad está encima, baja primero una señal del cuerpo: apoya ambos pies y suelta el aire lento una vez.",
            next_step="Apoya ambos pies y suelta el aire lento una vez",
            micro_practice="grounding_exhale",
            tags=["ansiedad", "grounding"],
        )

    if signal.turn_family == "blocked_followup" or signal.expresses_overwhelm:
        return _plan(
            route_id="ansiedad",
            subroute_id="anxiety_initial_grounding",
            goal="reduce_anxiety_now",
            tone="calido_contenedor",
            validation="Si la ansiedad ya se desbordó, no la resolvemos pensando más fuerte.",
            main_response="Primero baja una señal del cuerpo: apoya ambos pies y suelta el aire lento una vez.",
            next_step="Apoya ambos pies y suelta el aire lento una vez",
            micro_practice="grounding_exhale",
            optional_followup="Cuando baje un poco, sacamos una preocupación concreta de la cabeza.",
            tags=["ansiedad", "grounding"],
        )

    if signal.turn_family == "specific_action_request":
        return _plan(
            route_id="ansiedad",
            subroute_id="anxiety_visible_action",
            goal="one_real_next_step_for_anxiety",
            tone="calido_directo",
            validation="",
            main_response="Abre una nota y escribe una linea con lo que te preocupa mas ahorita.",
            next_step="Abre una nota y escribe una linea con la preocupacion principal",
            optional_followup="No hace falta resolverlo todavia. Solo sacarlo un poco de la cabeza.",
            tags=["ansiedad", "accion_visible"],
        )

    if signal.turn_family == "followup_acceptance" or signal.asks_for_next_step or signal.wants_to_continue:
        return _plan(
            route_id="ansiedad",
            subroute_id="anxiety_binary_decision",
            goal="closed_decision_after_grounding",
            tone="calido_directo",
            validation="Bien, ya no vamos a abrir todo junto.",
            main_response="Vamos a cerrarlo en una decision simple: si eso no vence hoy, lo dejas quieto por ahora. Si si vence hoy, te quedas solo con eso.",
            optional_followup="Si quieres, escribeme cual de las dos aplica y seguimos solo por esa.",
            state_subroute_id="anxiety_binary_decision",
            tags=["ansiedad", "decision_cerrada"],
        )

    if signal.turn_family == "strategy_rejection":
        return _plan(
            route_id="ansiedad",
            subroute_id="anxiety_repair_after_rejection",
            goal="repair_after_frustration",
            tone="calido_claro",
            validation="Gracias por decirme que asi no te sirve.",
            main_response="No voy a insistir con lo mismo. Tomo otra entrada para la ansiedad ahora.",
            optional_followup="Podemos ir por cuerpo treinta segundos o por una sola linea en una nota. Si no quieres elegir, elijo yo.",
            tags=["ansiedad", "reparacion"],
        )

    if signal.turn_family == "outcome_report":
        if signal.outcome in ("partial_relief", "improved"):
            return _plan(
                route_id="ansiedad",
                subroute_id="anxiety_hold_after_partial_relief",
            goal="hold_or_close_after_partial_effect",
            tone="calido_claro",
            validation="Bien, eso ya movio algo.",
            main_response="No metas otra tecnica ahora. Deja quieto lo demas y conserva solo lo que ya aflojo.",
            close_softly=True,
            state_subroute_id="anxiety_hold_after_partial_relief",
            tags=["ansiedad", "sostener"],
            )
        if signal.outcome in ("no_change", "worse"):
            return _plan(
                route_id="ansiedad",
                subroute_id="anxiety_change_modality",
                goal="change_modality_after_no_effect",
                tone="calido_claro",
                validation="Gracias por decirmelo.",
                main_response="Entonces no seguimos por el mismo carril. Cambiamos a algo mas visible: una sola frase en una nota o mover el cuerpo treinta segundos.",
                optional_followup="Si quieres, te digo cual de las dos veo mas facil para ti ahora.",
                state_subroute_id="anxiety_visible_action",
                tags=["ansiedad", "cambio_de_modalidad"],
            )

    return _plan(
        route_id="ansiedad",
        subroute_id="anxiety_initial_grounding",
        goal="initial_anxiety_support",
        tone="calido_contenedor",
        validation="La ansiedad puede abrir demasiados frentes a la vez.",
        main_response="No abras otro frente. Baja primero una señal del cuerpo: apoya ambos pies y suelta el aire lento una vez.",
        next_step="Apoya ambos pies y suelta el aire lento una vez",
        micro_practice="grounding_exhale",
        optional_followup="Después vemos si hace falta una acción visible o una decisión corta.",
        tags=["ansiedad", "inicio"],
    )


def playbook_executive_block(signal: UserSignal) -> ResponsePlan:
    track = _block_track(signal)
    text = _text(signal)

    if _has_any(text, ["no tengo archivo", "no hay archivo", "no tengo nada que abrir", "no tengo en que escribir", "no tengo donde escribir"]):
        return _plan(
            route_id="bloqueo_ejecutivo",
            subroute_id="executive_initial",
            goal="start_without_materials",
            tone="calido_practico",
            validation="No necesitas tener archivo abierto.",
            main_response="Empieza por una accion sin material: di en voz alta el nombre de la tarea y elige solo el primer verbo: leer, buscar, escribir o revisar.",
            next_step="Di en voz alta el nombre de la tarea y elige el primer verbo",
            tags=["bloqueo", "sin_materiales"],
        )

    if signal.turn_family == "strategy_rejection":
        return _plan(
            route_id="bloqueo_ejecutivo",
            subroute_id="executive_decide_for_user",
            goal="replace_rejected_strategy",
            tone="calido_claro",
            validation="Esta bien, no voy a empujarte por donde no te sirve.",
            main_response="Entonces lo cierro yo contigo: abre la tarea que vence primero o la mas corta, y escribe solo el titulo.",
            next_step="Abre la tarea que vence primero o la mas corta, y escribe solo el titulo",
            optional_followup="Con eso basta por ahora.",
            tags=["bloqueo", "decision_guiada"],
        )

    if signal.turn_family == "clarification_request" or signal.expresses_confusion or track == "executive_no_entiendo":
        return _plan(
            route_id="bloqueo_ejecutivo",
            subroute_id="executive_no_entiendo",
            goal="clarify_blocking_step",
            tone="claro_calido",
            validation="Si, vamos a bajarlo mas.",
            main_response="No intentes entenderlo todo ahorita. Abre la tarea y mira solo la consigna o la primera linea.",
            next_step="Abre la tarea y mira solo la consigna o la primera linea",
            optional_followup="Si sigue confuso, puedes pegarme esa parte y la partimos contigo.",
            tags=["bloqueo", "no_entiendo"],
        )

    if signal.expresses_impossibility or signal.turn_family == "blocked_followup":
        if track == "executive_no_se_que_toca":
            return _plan(
                route_id="bloqueo_ejecutivo",
                subroute_id="executive_no_se_que_toca",
                goal="resolve_unknown_next_task",
                tone="calido_claro",
                validation="No pasa nada si ahorita no ves que toca.",
                main_response="Haz solo esto: abre la materia o tarea que venza primero hoy. Si hay empate, abre la mas corta.",
                next_step="Abre la materia o tarea que venza primero hoy",
                optional_followup="Si quieres, dime dos opciones y elijo contigo.",
                tags=["bloqueo", "no_se_que_toca"],
            )
        if track == "executive_linea_de_que":
            return _plan(
                route_id="bloqueo_ejecutivo",
                subroute_id="executive_linea_de_que",
                goal="clarify_current_action",
                tone="claro_directo",
                validation="",
                main_response="La primera linea puede ser una de estas: el titulo, la consigna copiada o la primera frase mas obvia.",
                next_step="Escribe el titulo, la consigna o la primera frase mas obvia",
                optional_followup="No tiene que quedar bien. Solo tiene que abrir la entrada.",
                tags=["bloqueo", "linea_de_arranque"],
            )
        if track == "executive_no_puedo_empezar":
            return _plan(
                route_id="bloqueo_ejecutivo",
                subroute_id="executive_no_puedo_empezar",
                goal="lower_demand_for_start",
                tone="calido_claro",
                validation="No tienes que poder con todo para empezar.",
                main_response="Haz lo minimo visible: abre el archivo o cuaderno y escribe solo el titulo.",
                next_step="Abre el archivo o cuaderno y escribe solo el titulo",
                optional_followup="Con eso basta por ahora.",
                tags=["bloqueo", "no_puedo_empezar"],
            )
        if track == "executive_decide_for_user":
            return _plan(
                route_id="bloqueo_ejecutivo",
                subroute_id="executive_decide_for_user",
                goal="lower_demand_for_block",
                tone="claro_directo",
                validation="",
                main_response="No decidas mas. Abre la tarea mas corta o la que vence primero, y escribe solo el titulo.",
                next_step="Abre la tarea mas corta o la que vence primero, y escribe solo el titulo",
                tags=["bloqueo", "decision_guiada"],
            )
        return _plan(
            route_id="bloqueo_ejecutivo",
            subroute_id="executive_no_puedo_empezar",
            goal="lower_demand_for_block",
            tone="calido_claro",
            validation="No tienes que poder con todo ahora.",
            main_response="Haz lo mas pequeno posible: deja el archivo abierto y la mano en el material. Solo eso.",
            next_step="Deja el archivo abierto y la mano en el material",
            optional_followup="Si sale eso, ya arrancaste.",
            tags=["bloqueo", "inicio_minimo"],
        )

    if signal.turn_family == "specific_action_request":
        if track in {
            "executive_no_se_que_toca",
            "executive_linea_de_que",
            "executive_no_entiendo",
            "executive_no_puedo_empezar",
            "executive_decide_for_user",
        }:
            signal.active_subroute = track
            return playbook_executive_block(
                UserSignal(
                    **{
                        **signal.__dict__,
                        "turn_family": "blocked_followup",
                    }
                )
            )
        return _plan(
            route_id="bloqueo_ejecutivo",
            subroute_id="executive_initial",
            goal="first_visible_step",
            tone="claro_directo",
            validation="",
            main_response="Empieza aqui: abre solo el material que toca y deja el cursor o la hoja lista.",
            next_step="Abre el material que toca y deja el cursor o la hoja lista",
            optional_followup="No pienses en terminar. Solo en dejar la entrada abierta.",
            tags=["bloqueo", "inicio"],
        )

    if signal.turn_family == "followup_acceptance" or signal.asks_for_next_step or signal.wants_to_continue:
        return _plan(
            route_id="bloqueo_ejecutivo",
            subroute_id="executive_visible_next_step",
            goal="next_step_after_opening_material",
            tone="claro_directo",
            validation="Bien, seguimos pequeno.",
            main_response="El siguiente paso es dejar una salida visible: escribe solo el titulo, una vieta o una primera linea minima.",
            next_step="Escribe solo el titulo, una vieta o una primera linea minima",
            optional_followup="No hace falta que quede bien. Solo visible.",
            state_subroute_id="executive_visible_next_step",
            tags=["bloqueo", "salida_visible"],
        )

    if track == "executive_no_se_que_toca":
        return _plan(
            route_id="bloqueo_ejecutivo",
            subroute_id=track,
            goal="initial_block_support",
            tone="calido_practico",
            validation="Si, cuando no se ve que toca, todo se frena.",
            main_response="Empieza por la tarea que vence primero hoy. Si no sabes cual, abre la mas corta.",
            next_step="Abre la tarea que vence primero hoy",
            optional_followup="Luego te dejo la primera marca visible.",
            tags=["bloqueo", "no_se_que_toca"],
        )
    if track == "executive_linea_de_que":
        return _plan(
            route_id="bloqueo_ejecutivo",
            subroute_id=track,
            goal="clarify_current_action",
            tone="claro_directo",
            validation="",
            main_response="La primera linea puede ser el titulo, la consigna copiada o la primera frase mas obvia del tema.",
            next_step="Escribe el titulo, la consigna o la primera frase mas obvia",
            optional_followup="Solo necesitas abrir la entrada.",
            tags=["bloqueo", "linea_de_arranque"],
        )
    if track == "executive_no_puedo_empezar":
        return _plan(
            route_id="bloqueo_ejecutivo",
            subroute_id=track,
            goal="initial_block_support",
            tone="calido_practico",
            validation="Si, esto puede bloquear mucho.",
            main_response="No empieces por hacer mucho. Empieza por abrir el archivo o cuaderno y escribir solo el titulo.",
            next_step="Abre el archivo o cuaderno y escribe solo el titulo",
            optional_followup="Con eso ya no esta en cero.",
            tags=["bloqueo", "no_puedo_empezar"],
        )
    if track == "executive_decide_for_user":
        return _plan(
            route_id="bloqueo_ejecutivo",
            subroute_id=track,
            goal="initial_block_support",
            tone="calido_practico",
            validation="Esta bien, yo cierro la decision contigo.",
            main_response="Abre la tarea mas corta o la que vence primero, y escribe solo el titulo.",
            next_step="Abre la tarea mas corta o la que vence primero, y escribe solo el titulo",
            optional_followup="Despues te doy el siguiente paso sin abrir todo.",
            tags=["bloqueo", "decision_guiada"],
        )
    return _plan(
        route_id="bloqueo_ejecutivo",
        subroute_id="executive_initial",
        goal="initial_block_support",
        tone="calido_practico",
        validation="Si, esto puede bloquear mucho.",
        main_response="Empieza aqui: abre solo el archivo, cuaderno o material que toca.",
        next_step="Abre solo el archivo, cuaderno o material que toca",
        optional_followup="Con eso alcanza por ahora.",
        tags=["bloqueo", "inicio"],
    )


def playbook_sleep(signal: UserSignal) -> ResponsePlan:
    track = _sleep_track(signal)

    if signal.turn_family == "strategy_rejection":
        return _plan(
            route_id="sueno",
            subroute_id="sleep_followup",
            goal="change_sleep_modality",
            tone="calido_claro",
            validation="Tienes razón, eso no fue suficientemente directo para dormir.",
            main_response=(
                "Vamos a algo más concreto: apaga o aleja la pantalla, baja la luz y deja una rutina de "
                "10 minutos sin exigirte dormir todavía."
            ),
            optional_followup="Si la mente sigue acelerada, sacas una sola preocupación a papel y cierras la nota.",
            state_subroute_id=track if track != "sleep_initial" else "sleep_followup",
            tags=["sueno", "cambio_de_via"],
        )

    if signal.turn_family == "followup_acceptance" or signal.turn_family == "post_action_followup" or signal.asks_for_next_step or signal.wants_to_continue:
        followup_text = {
            "sleep_mind_racing": "Despues de sacar eso al papel, deja una sola frase de cierre y no abras otro tema esta noche.",
            "sleep_body_activated": "Ahora busca quietud, no sueño forzado: postura cómoda, luz baja y respiración sin esfuerzo.",
            "sleep_environment": "Sosten ese ajuste unos minutos y no agregues otra medida todavia.",
            "sleep_insomnia": "Cuando sientas un poco menos de activacion, vuelve a la cama sin forzarlo.",
        }.get(track, "Ahora no sumes otra medida. Sosten la bajada de estimulo 5 a 10 minutos.")
        followup_line = {
            "sleep_mind_racing": "Eso lo veo manana. Ahorita no tengo que resolverlo.",
        }.get(track)
        return _plan(
            route_id="sueno",
            subroute_id="sleep_followup",
            goal="next_sleep_step",
            tone="calido_suave",
            validation="Bien.",
            main_response=followup_text,
            literal_phrase=followup_line,
            optional_followup="Si sigue igual despues, cambiamos una sola cosa y nada mas.",
            state_subroute_id=track,
            tags=["sueno", "seguimiento"],
        )

    if signal.turn_family == "outcome_report":
        if signal.outcome in ("partial_relief", "improved"):
            return _plan(
                route_id="sueno",
                subroute_id="sleep_followup",
                goal="hold_sleep_gain",
                tone="calido",
                validation="Bien, eso ya da una pista.",
                main_response="Sosten solo lo que ayudo y no metas mas cosas por ahora.",
                close_softly=True,
                state_subroute_id=track,
                tags=["sueno", "sostener"],
            )
        if signal.outcome in ("no_change", "worse"):
            next_state = "sleep_body_activated" if track == "sleep_mind_racing" else track
            return _plan(
                route_id="sueno",
                subroute_id="sleep_followup",
                goal="change_sleep_modality",
                tone="calido_claro",
                validation="Gracias por decirmelo.",
                main_response="Entonces cambiamos de via. En vez de seguir intentando dormir ya, haz una bajada de cinco a diez minutos sin pantalla ni exigencia.",
                optional_followup="Y si esto te esta afectando mucho o pasa seguido, lo mas seguro es hablarlo con un profesional de salud.",
                state_subroute_id=next_state,
                tags=["sueno", "cambio_de_via"],
            )

    if track == "sleep_mind_racing":
        return _plan(
            route_id="sueno",
            subroute_id=track,
            goal="initial_sleep_mind_support",
            tone="calido_suave",
            validation="Si, cuando la mente no para, dormir se vuelve mucho mas dificil.",
            main_response="No intentes callarla a la fuerza. Saca a una hoja tres pendientes o preocupaciones y luego cierra la hoja.",
            next_step="Escribe tres pendientes o preocupaciones y cierra la hoja",
            optional_followup="Despues dejamos una sola frase de cierre y nada mas.",
            tags=["sueno", "mente_acelerada"],
        )
    if track == "sleep_body_activated":
        return _plan(
            route_id="sueno",
            subroute_id=track,
            goal="initial_sleep_body_support",
            tone="calido_suave",
            validation="Si, con el cuerpo tan arriba cuesta mucho bajar a dormir.",
            main_response="Primero baja cuerpo, no sueño forzado: afloja mandíbula, hombros y deja tres exhalaciones largas.",
            next_step="Afloja mandíbula, hombros y deja tres exhalaciones largas",
            micro_practice="body_settle_exhale",
            optional_followup="Cuando el cuerpo ceda un poco, vuelves a intentar dormir.",
            tags=["sueno", "cuerpo_activado"],
        )
    if track == "sleep_environment":
        return _plan(
            route_id="sueno",
            subroute_id=track,
            goal="initial_sleep_environment_support",
            tone="calido_suave",
            validation="Si, a veces el problema no es solo adentro sino alrededor.",
            main_response="Ajusta una sola cosa del entorno que estorbe: luz, ruido, pantalla o temperatura.",
            next_step="Ajusta una sola cosa del entorno que estorbe",
            optional_followup="No cambies todo. Una sola cosa primero.",
            tags=["sueno", "entorno"],
        )
    if track == "sleep_insomnia":
        return _plan(
            route_id="sueno",
            subroute_id=track,
            goal="initial_sleep_insomnia_support",
            tone="calido_suave",
            validation="Si, el desvelo suele empeorar cuando tratamos de forzarlo.",
            main_response="Si ya estás muy despierta/o, sal un momento de la pelea con el sueño: poca luz, sin pantalla y sin exigencia.",
            next_step="Poca luz, sin pantalla y sin exigencia por unos minutos",
            optional_followup="Cuando baje un poco la activacion, vuelves a la cama.",
            tags=["sueno", "desvelo"],
        )
    return _plan(
        route_id="sueno",
        subroute_id="sleep_initial",
        goal="initial_sleep_support",
        tone="calido_suave",
        validation="Sí, el sueño puede mover todo lo demás.",
        main_response="Vamos con algo concreto: baja una sola fuente de estimulo como luz, ruido o pantalla.",
        next_step="Baja una sola fuente de estimulo como luz, ruido o pantalla",
        optional_followup="Si quieres, luego vemos si el peso esta mas en la mente, el cuerpo o el entorno.",
        tags=["sueno", "inicio"],
    )


def playbook_child_support(signal: UserSignal) -> ResponsePlan:
    track = _child_support_track(signal)
    text = _text(signal)

    if _has_any(text, ["no es sobrepensamiento"]) and _has_any(text, ["sueno", "sue o", "dormir"]):
        return _plan(
            route_id="apoyo_infancia_neurodivergente",
            subroute_id="child_anticipation_routines",
            goal="teen_sleep_support_without_overthinking",
            tone="calido_practico",
            validation="Tienes razon, me centro en sueno.",
            main_response=(
                "Con adolescentes suele funcionar mejor negociar antes, no en plena noche: pantalla cargando fuera del cuarto, "
                "luz baja y una actividad tranquila de 10 a 15 minutos."
            ),
            optional_followup="Si no aceptan todo, empieza por una sola cosa: pantalla fuera de la cama.",
            tags=["child_support", "sueno", "adolescentes"],
        )
    if _has_any(text, ["adolescente", "adolescentes"]) and _has_any(text, ["dormir", "sueno", "sue o", "insomnio"]):
        return _plan(
            route_id="apoyo_infancia_neurodivergente",
            subroute_id="child_anticipation_routines",
            goal="teen_sleep_support",
            tone="calido_practico",
            validation="Con adolescentes conviene hacerlo breve y pactado.",
            main_response="Propón un acuerdo concreto: pantalla cargando fuera del cuarto, luz baja y una actividad tranquila 10 a 15 minutos.",
            optional_followup="No negocies todo en plena noche; empieza por pantalla fuera de la cama si no aceptan lo demas.",
            tags=["child_support", "sueno", "adolescentes"],
        )

    if signal.turn_family == "literal_phrase_request" or signal.asks_for_phrase or track == "child_clear_communication":
        return _plan(
            route_id="apoyo_infancia_neurodivergente",
            subroute_id="child_clear_communication",
            goal="child_support_literal_phrase",
            tone="calido_directo",
            validation="",
            main_response="Puedes decirle esto, tal cual:",
            literal_phrase="Vamos con una sola parte. Ahora esto, luego descansamos o cerramos.",
            optional_followup="Haz la frase corta y con voz tranquila.",
            tags=["child_support", "comunicacion_concreta"],
        )

    if signal.turn_family == "strategy_rejection":
        return _plan(
            route_id="apoyo_infancia_neurodivergente",
            subroute_id=track if track in set(PLAYBOOK_CATALOG["apoyo_infancia_neurodivergente"]) else "child_overthinking_support",
            goal="repair_child_support_path",
            tone="calido_claro",
            validation="Tienes razón. Me centro en tu hija o hijo.",
            main_response=(
                "Para ayudarle a sobrepensar menos, no le des muchas explicaciones. "
                "Ayúdale a elegir una sola preocupación y acompáñale a bajarla a palabras."
            ),
            optional_followup="Una preocupación a la vez; no abran todas las demás juntas.",
            tags=["child_support", "cambio_de_via"],
        )

    if signal.turn_family == "followup_acceptance" or signal.asks_for_next_step or signal.wants_to_continue:
        if track == "child_overthinking_support":
            return _plan(
                route_id="apoyo_infancia_neurodivergente",
                subroute_id="child_overthinking_support",
                goal="child_overthinking_followup",
                tone="calido_practico",
                validation="Bien.",
                main_response="Despues de sacar una sola preocupacion, ayudale a mirar si eso esta pasando ahorita o si solo es una posibilidad.",
                optional_followup="Si es una posibilidad, cierren la nota y vuelvan luego.",
                tags=["child_support", "sobrepensamiento", "seguimiento"],
            )
        if track == "child_saturation_support":
            return _plan(
                route_id="apoyo_infancia_neurodivergente",
                subroute_id="child_co_regulation",
                goal="child_overload_followup",
                tone="calido_practico",
                validation="Bien.",
                main_response="Ahora sosten menos palabras y mas presencia. Una instruccion corta o ninguna, segun como este.",
                optional_followup="Si sigue subiendo, baja otro estimulo. No agregues debate.",
                state_subroute_id="child_co_regulation",
                tags=["child_support", "saturacion", "seguimiento"],
            )
        if track == "child_anticipation_routines":
            return _plan(
                route_id="apoyo_infancia_neurodivergente",
                subroute_id="child_anticipation_routines",
                goal="child_routine_followup",
                tone="calido_practico",
                validation="Bien.",
                main_response="Dejale una secuencia corta y visible: ahora esto, luego esto, y despues descanso o cierre.",
                optional_followup="Si puedes, dilo siempre con las mismas palabras.",
                tags=["child_support", "anticipacion", "seguimiento"],
            )
        if track == "child_social_or_family_context":
            return _plan(
                route_id="apoyo_infancia_neurodivergente",
                subroute_id="child_social_or_family_context",
                goal="child_support_next_step",
                tone="calido_practico",
                validation="Bien.",
                main_response="Ahora cuida que las otras personas no metan varias indicaciones a la vez. Una sola voz y una sola consigna corta.",
                optional_followup="Eso suele bajar mucho la carga alrededor.",
                tags=["child_support", "contexto_social", "seguimiento"],
            )
        return _plan(
            route_id="apoyo_infancia_neurodivergente",
            subroute_id="child_co_regulation",
            goal="child_support_next_step",
            tone="calido_practico",
            validation="Bien.",
            main_response="Ahora manten una sola ayuda, no varias: o presencia calmada, o frase corta, o ajuste de estimulos.",
            optional_followup="Si quieres, te digo cual veo mas clara para este caso.",
            state_subroute_id="child_co_regulation",
            tags=["child_support", "seguimiento"],
        )

    if track == "child_overthinking_support":
        return _plan(
            route_id="apoyo_infancia_neurodivergente",
            subroute_id=track,
            goal="child_overthinking_support",
            tone="calido_contenedor",
            validation="Claro. Si quien está sobrepensando es tu hija o hijo, no intentaría convencerle con muchas explicaciones.",
            main_response="Ayuda más bajar velocidad: pídele que saque una sola preocupación, en voz o en papel. Una sola.",
            next_step="Sacar una sola preocupación, en voz o en papel",
            optional_followup="Luego pueden mirarla juntas sin abrir todas las demás.",
            tags=["child_support", "sobrepensamiento"],
        )
    if track == "child_saturation_support":
        return _plan(
            route_id="apoyo_infancia_neurodivergente",
            subroute_id=track,
            goal="child_overload_support",
            tone="calido_contenedor",
            validation="Si, cuando ya hay saturacion, menos suele ayudar mas.",
            main_response="Primero baja estimulos y baja palabras. No busques corregir todo al mismo tiempo.",
            next_step="Baja estimulos y baja palabras",
            optional_followup="Tu calma y tu tono pesan mas que una explicacion larga.",
            tags=["child_support", "saturacion"],
        )
    if track == "child_reduce_stimuli":
        return _plan(
            route_id="apoyo_infancia_neurodivergente",
            subroute_id=track,
            goal="child_reduce_stimulus",
            tone="calido_contenedor",
            validation="Si, a veces el entorno esta empujando mucho.",
            main_response="Haz un solo ajuste visible: menos luz, menos ruido o menos gente cerca.",
            next_step="Haz un solo ajuste visible del entorno",
            optional_followup="Observa si con eso su cuerpo baja un poco.",
            tags=["child_support", "reduccion_estimulos"],
        )
    if track == "child_anticipation_routines":
        return _plan(
            route_id="apoyo_infancia_neurodivergente",
            subroute_id=track,
            goal="child_anticipation_support",
            tone="calido_contenedor",
            validation="Si, anticipar y hacer predecible suele bajar bastante la carga.",
            main_response="Antes del cambio, dile solo las dos siguientes cosas: que pasa ahora y que pasa despues.",
            next_step="Decirle que pasa ahora y que pasa despues",
            optional_followup="Si puedes repetir siempre la misma secuencia, mejor.",
            tags=["child_support", "anticipacion"],
        )
    if track == "child_social_or_family_context":
        return _plan(
            route_id="apoyo_infancia_neurodivergente",
            subroute_id=track,
            goal="child_social_context_support",
            tone="calido_contenedor",
            validation="Si, cuando hay mas gente alrededor, la carga puede subir mucho.",
            main_response="Pidele a las otras personas una sola linea comun: una voz, una frase corta y sin correcciones cruzadas.",
            next_step="Pide una sola voz, una sola frase corta y sin correcciones cruzadas",
            optional_followup="Eso suele bajar la confusion y la exigencia alrededor.",
            tags=["child_support", "contexto_social"],
        )
    return _plan(
        route_id="apoyo_infancia_neurodivergente",
        subroute_id="child_co_regulation",
        goal="child_coregulation_support",
        tone="calido_contenedor",
        validation="Si, ayudar a una hija/o neurodivergente suele empezar mas por presencia que por discurso.",
        main_response="Empieza por corregulacion: presencia tranquila, voz baja y una sola referencia clara.",
        next_step="Presencia tranquila, voz baja y una sola referencia clara",
        optional_followup="Si quieres, te doy la frase exacta para ese momento.",
        tags=["child_support", "corregulacion"],
    )


def playbook_caregiver_overload(signal: UserSignal) -> ResponsePlan:
    track = _caregiver_track(signal)

    if signal.turn_family == "strategy_rejection":
        return _plan(
            route_id="sobrecarga_cuidador",
            subroute_id="caregiver_single_priority",
            goal="replace_relief_path_for_caregiver",
            tone="calido_claro",
            validation="Gracias por decirlo. No voy a dejarte con una salida que no te ayude.",
            main_response="Entonces cierro la entrada contigo: primero seguridad, luego lo que vence hoy, y despues lo demas.",
            optional_followup="Si quieres, dime cual de esas dos esta viva ahorita y lo bajamos contigo.",
            tags=["cuidador", "cambio_de_via"],
        )

    if signal.turn_family == "followup_acceptance" or signal.asks_for_next_step or signal.wants_to_continue:
        if track == "caregiver_ask_for_help":
            return _plan(
                route_id="sobrecarga_cuidador",
                subroute_id="caregiver_ask_for_help",
                goal="ask_for_help_concretely",
                tone="calido_practico",
                validation="Bien.",
                main_response="Pide ayuda sobre algo cerrado y concreto, no sobre todo.",
                literal_phrase="Hoy necesito que tomes esta parte concreta para que yo pueda bajar un poco.",
                optional_followup="Cuanto mas especifico, mas facil que te respondan.",
                tags=["cuidador", "pedir_ayuda"],
            )
        if track == "caregiver_reduce_load":
            return _plan(
                route_id="sobrecarga_cuidador",
                subroute_id="caregiver_self_care_without_guilt",
                goal="reduce_load_concretely",
                tone="calido_practico",
                validation="Bien.",
                main_response="Ahora deja una pausa minima sin culpa: agua, sentarte cinco minutos, respirar afuera o ir al bano sin apuro.",
                next_step="Haz una pausa minima sin culpa",
                optional_followup="Eso tambien sostiene el cuidado.",
                state_subroute_id="caregiver_self_care_without_guilt",
                tags=["cuidador", "autocuidado"],
            )
        return _plan(
            route_id="sobrecarga_cuidador",
            subroute_id="caregiver_single_priority",
            goal="choose_one_priority_for_caregiver",
            tone="calido_practico",
            validation="Bien.",
            main_response="Ahora elige una sola prioridad para hoy: seguridad, descanso o una tarea urgente. Solo una.",
            optional_followup="Lo demas puede quedarse quieto por este momento.",
            tags=["cuidador", "una_prioridad"],
        )

    if track == "caregiver_ask_for_help":
        return _plan(
            route_id="sobrecarga_cuidador",
            subroute_id=track,
            goal="caregiver_help_request_path",
            tone="calido_contenedor",
            validation="Si, cargar sola/o tanto desgasta muchisimo.",
            main_response="No pidas ayuda en general. Pidela sobre algo concreto, con hora o tarea cerrada.",
            next_step="Pide ayuda sobre una hora o una tarea cerrada",
            optional_followup="Si quieres, te ayudo a redactar ese mensaje.",
            tags=["cuidador", "pedir_ayuda"],
        )
    if track == "caregiver_reduce_load":
        return _plan(
            route_id="sobrecarga_cuidador",
            subroute_id=track,
            goal="reduce_caregiver_overload",
            tone="calido_contenedor",
            validation="Si, esto puede sentirse demasiado para una sola persona.",
            main_response="No intentes sostenerlo todo hoy. Busca una sola carga que pueda esperar y sueltala por ahora.",
            next_step="Busca una sola carga que pueda esperar y sueltala por ahora",
            optional_followup="Luego elegimos solo lo que si toca hoy.",
            tags=["cuidador", "reducir_carga"],
        )
    if track == "caregiver_single_priority":
        return _plan(
            route_id="sobrecarga_cuidador",
            subroute_id=track,
            goal="choose_one_priority_for_caregiver",
            tone="calido_contenedor",
            validation="Tiene sentido que cueste elegir cuando todo se siente urgente.",
            main_response="Vamos a cerrarlo asi: primero seguridad, luego lo que vence hoy, y despues lo demas.",
            optional_followup="Si quieres, dime cual de esas dos esta viva ahorita y lo bajamos contigo.",
            tags=["cuidador", "una_prioridad"],
        )
    if track == "caregiver_self_care_without_guilt":
        return _plan(
            route_id="sobrecarga_cuidador",
            subroute_id=track,
            goal="caregiver_self_care_without_guilt",
            tone="calido_contenedor",
            validation="Descansar un poco no te hace fallar.",
            main_response="Haz una pausa minima sin culpa: agua, sentarte cinco minutos, respirar afuera o ir al bano sin apuro.",
            next_step="Haz una pausa minima sin culpa",
            optional_followup="Eso tambien ayuda a sostener lo demas.",
            tags=["cuidador", "autocuidado"],
        )
    return _plan(
        route_id="sobrecarga_cuidador",
        subroute_id="caregiver_validation",
        goal="validate_caregiver_overload",
        tone="calido_contenedor",
        validation="Si, esto es mucho para llevarlo sola/o.",
        main_response="Antes de resolver, te diria una cosa: no tendrias que poder con todo al mismo tiempo.",
        optional_followup="Si quieres, ahora elegimos una sola carga para bajar.",
        tags=["cuidador", "validacion"],
    )


def playbook_validation(signal: UserSignal) -> ResponsePlan:
    return _plan(
        route_id="general",
        subroute_id=None,
        goal="brief_validation",
        tone="calido_claro",
        validation="",
        main_response="Si, tiene sentido que esto te este pesando asi.",
        optional_followup="Si quieres, lo vemos con mas calma o vamos a algo concreto.",
        close_softly=True,
        tags=["validation"],
    )


def playbook_clarification(signal: UserSignal) -> ResponsePlan:
    track = _clarification_track(signal)
    if track == "what_phrase":
        return _plan(
            route_id="clarificacion",
            subroute_id=track,
            goal="clarify_in_one_step",
            tone="claro_calido",
            validation="Si, te dejo una frase directa.",
            main_response="La idea es usar una frase corta, literal y sin agregar otra instruccion encima.",
            literal_phrase="Vamos con una sola parte ahora.",
            tags=["clarification", "phrase"],
        )
    if track == "what_type":
        return _plan(
            route_id="clarificacion",
            subroute_id=track,
            goal="clarify_in_one_step",
            tone="claro_calido",
            validation="Si, te doy tipos concretos.",
            main_response="Piensalo asi: puede ser una frase, un cambio de entorno, una marca fuera de la cabeza o una pausa corta. Elige solo una.",
            tags=["clarification", "types"],
        )
    if track == "where_do_i_start":
        return _plan(
            route_id="clarificacion",
            subroute_id=track,
            goal="clarify_in_one_step",
            tone="claro_calido",
            validation="Si, empecemos por el punto de entrada.",
            main_response="Empieza por la accion mas pequena y visible que puedas hacer ya, sin preparar nada mas.",
            tags=["clarification", "starting_point"],
        )
    return _plan(
        route_id="clarificacion",
        subroute_id="i_dont_understand",
        goal="clarify_in_one_step",
        tone="claro_calido",
        validation="Voy más concreto.",
        main_response="Toma solo el paso anterior: la frase, el inicio o el siguiente movimiento. Uno.",
        tags=["clarification"],
    )


def playbook_strategy_rejection(signal: UserSignal) -> ResponsePlan:
    track = _rejection_track(signal)
    if track == "strategy_repair":
        return _plan(
            route_id="rechazo_estrategia",
            subroute_id=track,
            goal="repair_after_frustration",
            tone="calido_claro",
            validation="Veo que esto te frustro, y gracias por decirmelo asi de claro.",
            main_response="No voy a pelear contigo ni a repetirte lo mismo. Voy a cambiar la forma para que esto se sienta mas util.",
            optional_followup="Si quieres, te doy una salida mas directa ahora mismo.",
            tags=["strategy_rejection", "repair_bond"],
        )
    return _plan(
        route_id="rechazo_estrategia",
        subroute_id="strategy_switch",
        goal="change_strategy_without_pressure",
        tone="calido_claro",
        validation="Tienes razón.",
        main_response="No repito eso. Cambio de vía: te doy una acción distinta y concreta.",
        optional_followup="Si no puedes elegir, tomo el paso más simple y seguimos desde ahí.",
        tags=["strategy_rejection", "change_path"],
    )


def playbook_next_step(signal: UserSignal) -> ResponsePlan:
    return _plan(
        route_id="general",
        subroute_id=None,
        goal="offer_next_step_without_reset",
        tone="calido_directo",
        validation="Bien, seguimos sin abrir de mas.",
        main_response="Sigue con una sola cosa concreta de lo que ya traías.",
        optional_followup="Si te trabas, toma el paso más pequeño disponible y no abras otro frente.",
        tags=["next_step"],
    )


def playbook_meditation(signal: UserSignal) -> ResponsePlan:
    track = _meditation_track(signal)
    if track == "one_minute_breath":
        return _plan(
            route_id="meditacion_guiada",
            subroute_id=track,
            goal="teach_short_meditation",
            tone="calido_guiado",
            validation="",
            main_response="Vamos con un minuto de respiracion. Inhala normal. Ahora suelta el aire un poco mas largo. Hazlo tres veces sin forzarte.",
            micro_practice="1_minute_breath",
            optional_followup="Si quieres, despues hacemos una pausa todavia mas corta.",
            tags=["meditacion", "respiracion_un_minuto"],
        )
    if track == "grounding_5_senses":
        return _plan(
            route_id="meditacion_guiada",
            subroute_id=track,
            goal="teach_short_grounding",
            tone="calido_guiado",
            validation="",
            main_response="Vamos a aterrizar con cinco sentidos: nombra 5 cosas que ves, 4 que tocas, 3 que oyes, 2 que hueles y 1 que saboreas o recuerdas.",
            micro_practice="5_senses_grounding",
            optional_followup="Con eso basta por ahora.",
            tags=["meditacion", "grounding"],
        )
    return _plan(
        route_id="meditacion_guiada",
        subroute_id="pause_guided",
        goal="teach_guided_pause",
        tone="calido_guiado",
        validation="",
        main_response="Haz una pausa breve conmigo: afloja hombros, suelta el aire y deja quieta la mirada unos segundos.",
        micro_practice="guided_pause",
        optional_followup="Si quieres, luego hacemos una de respiracion o una para dormir.",
        tags=["meditacion", "pausa_guiada"],
    )


def playbook_simple_question(signal: UserSignal) -> ResponsePlan:
    return _plan(
        route_id="pregunta_simple",
        subroute_id=None,
        goal="answer_simple_question_briefly",
        tone="claro_directo",
        validation="",
        main_response="Si, puedo ayudarte con orientacion breve, acompanamiento emocional y pasos concretos segun lo que este pasando.",
        close_softly=True,
        tags=["simple_question"],
    )


def playbook_close(signal: UserSignal) -> ResponsePlan:
    track = _close_track(signal)
    if track == "pause_here":
        return _plan(
            route_id="cierre",
            subroute_id=track,
            goal="closure_or_pause",
            tone="calido_suave",
            validation="Esta bien.",
            main_response="Aqui podemos hacer una pausa. Si luego quieres seguir, retomamos desde donde lo dejamos.",
            close_softly=True,
            tags=["closure", "pause"],
        )
    return _plan(
        route_id="cierre",
        subroute_id="enough_for_now",
        goal="closure_or_pause",
        tone="calido_suave",
        validation="Esta bien.",
        main_response="Con esto basta por ahora. Si luego necesitas volver, aqui sigo contigo.",
        close_softly=True,
        tags=["closure", "enough_for_now"],
    )


def playbook_low_energy(signal: UserSignal) -> ResponsePlan:
    return _plan(
        route_id="depresion_baja_energia",
        subroute_id=None,
        goal="support_low_energy_without_forcing",
        tone="calido_suave",
        validation="Si, esto puede dejarte sin energia hasta para lo pequeno.",
        main_response="No hace falta empujarte demasiado ahora. Cambia de postura y quédate ahí un momento.",
        optional_followup="Si quieres, despues vemos si hay una sola cosa pequena que si sea posible hoy.",
        tags=["baja_energia"],
    )


def playbook_general(signal: UserSignal) -> ResponsePlan:
    return _plan(
        route_id="general",
        subroute_id=None,
        goal="general_support",
        tone="calido_claro",
        validation="Aqui estoy contigo.",
        main_response="Cuentame que parte pesa mas y lo vemos contigo, paso a paso.",
        tags=["general"],
    )


# =========================================================
# Specs
# =========================================================

PLAYBOOK_SPECS: Dict[Domain, PlaybookSpec] = {
    "crisis": PlaybookSpec(
        route_id="crisis",
        tone_objective="calido_firme_breve",
        validation_base="Estoy contigo.",
        max_steps=4,
        expected_user_responses=["si, ayudame", "que le digo", "sigue igual", "ya bajo un poco", "paramos aqui"],
        if_not_understood="clarification_request",
        if_rejected="strategy_rejection",
        if_continue="followup_acceptance",
        if_pause="closure_or_pause",
    ),
    "ansiedad": PlaybookSpec(
        route_id="ansiedad",
        tone_objective="calido_contenedor",
        validation_base="Sí, esto puede estar pesando mucho.",
        max_steps=4,
        expected_user_responses=["no puedo con todo", "y luego", "no me sirve", "ya aflojo un poco", "paramos aqui"],
        if_not_understood="clarification_request",
        if_rejected="strategy_rejection",
        if_continue="followup_acceptance",
        if_pause="closure_or_pause",
    ),
    "bloqueo_ejecutivo": PlaybookSpec(
        route_id="bloqueo_ejecutivo",
        tone_objective="claro_calido",
        validation_base="Si, esto puede bloquear mucho.",
        max_steps=4,
        expected_user_responses=["no puedo empezar", "no se que toca", "no entiendo", "y luego", "eso no me sirve"],
        if_not_understood="clarification_request",
        if_rejected="strategy_rejection",
        if_continue="followup_acceptance",
        if_pause="closure_or_pause",
    ),
    "sueno": PlaybookSpec(
        route_id="sueno",
        tone_objective="calido_suave",
        validation_base="Sí, el sueño puede mover todo lo demás.",
        max_steps=4,
        expected_user_responses=["mente acelerada", "desvelo", "ya, que mas", "sigue igual", "paramos aqui"],
        if_not_understood="clarification_request",
        if_rejected="strategy_rejection",
        if_continue="followup_acceptance",
        if_pause="closure_or_pause",
    ),
    "apoyo_infancia_neurodivergente": PlaybookSpec(
        route_id="apoyo_infancia_neurodivergente",
        tone_objective="calido_contenedor",
        validation_base="Si, ayudar a una hija/o neurodivergente puede requerir mucha precision y calma.",
        max_steps=4,
        expected_user_responses=["como ayudo a mi hija", "que le digo", "se satura", "sobrepiensa", "y luego"],
        if_not_understood="clarification_request",
        if_rejected="strategy_rejection",
        if_continue="followup_acceptance",
        if_pause="closure_or_pause",
    ),
    "sobrecarga_cuidador": PlaybookSpec(
        route_id="sobrecarga_cuidador",
        tone_objective="calido_contenedor",
        validation_base="Si, esto puede sentirse demasiado para una sola persona.",
        max_steps=3,
        expected_user_responses=["ya no puedo con esto", "nadie me ayuda", "que hago primero", "y luego"],
        if_not_understood="clarification_request",
        if_rejected="strategy_rejection",
        if_continue="followup_acceptance",
        if_pause="closure_or_pause",
    ),
    "pregunta_simple": PlaybookSpec(
        route_id="pregunta_simple",
        tone_objective="claro_directo",
        validation_base="",
        max_steps=1,
        expected_user_responses=["que haces", "me ayudas con esto"],
        if_not_understood="clarification_request",
        if_rejected="strategy_rejection",
        if_continue="followup_acceptance",
        if_pause="closure_or_pause",
    ),
    "meta_question": PlaybookSpec(
        route_id="meta_question",
        tone_objective="calido_humano_directo",
        validation_base="",
        max_steps=1,
        expected_user_responses=["quien eres", "como puedo llamarte", "puedo platicar contigo", "que puedes hacer"],
        if_not_understood="clarification_request",
        if_rejected="strategy_rejection",
        if_continue="followup_acceptance",
        if_pause="closure_or_pause",
    ),
    "meditacion_guiada": PlaybookSpec(
        route_id="meditacion_guiada",
        tone_objective="calido_guiado",
        validation_base="",
        max_steps=2,
        expected_user_responses=["un minuto", "grounding", "pausa guiada"],
        if_not_understood="clarification_request",
        if_rejected="strategy_rejection",
        if_continue="followup_acceptance",
        if_pause="closure_or_pause",
    ),
    "clarificacion": PlaybookSpec(
        route_id="clarificacion",
        tone_objective="claro_calido",
        validation_base="Si, te lo digo mas simple.",
        max_steps=1,
        expected_user_responses=["no entiendo", "como", "cual", "por donde"],
        if_not_understood="clarification_request",
        if_rejected="strategy_rejection",
        if_continue="followup_acceptance",
        if_pause="closure_or_pause",
    ),
    "rechazo_estrategia": PlaybookSpec(
        route_id="rechazo_estrategia",
        tone_objective="calido_claro",
        validation_base="Gracias por decirlo claro.",
        max_steps=2,
        expected_user_responses=["no me sirve", "no sirves", "otra cosa"],
        if_not_understood="clarification_request",
        if_rejected="strategy_rejection",
        if_continue="followup_acceptance",
        if_pause="closure_or_pause",
    ),
    "cierre": PlaybookSpec(
        route_id="cierre",
        tone_objective="calido_suave",
        validation_base="Esta bien.",
        max_steps=1,
        expected_user_responses=["ya estuvo", "aqui paro", "por ahora"],
        if_not_understood="clarification_request",
        if_rejected="strategy_rejection",
        if_continue="followup_acceptance",
        if_pause="closure_or_pause",
    ),
    "general": PlaybookSpec(
        route_id="general",
        tone_objective="calido_claro",
        validation_base="Aqui estoy contigo.",
        max_steps=2,
        expected_user_responses=["no se", "que sigue", "paramos aqui"],
        if_not_understood="clarification_request",
        if_rejected="strategy_rejection",
        if_continue="followup_acceptance",
        if_pause="closure_or_pause",
    ),
}

PLAYBOOK_BUILDERS: Dict[Domain, Callable[[UserSignal], ResponsePlan]] = {
    "crisis": playbook_crisis,
    "ansiedad": playbook_anxiety,
    "bloqueo_ejecutivo": playbook_executive_block,
    "sueno": playbook_sleep,
    "apoyo_infancia_neurodivergente": playbook_child_support,
    "sobrecarga_cuidador": playbook_caregiver_overload,
    "pregunta_simple": playbook_simple_question,
    "meta_question": playbook_meta_question,
    "meditacion_guiada": playbook_meditation,
    "clarificacion": playbook_clarification,
    "rechazo_estrategia": playbook_strategy_rejection,
    "cierre": playbook_close,
    "general": playbook_general,
}


def get_playbook_spec(route_id: Domain) -> Optional[PlaybookSpec]:
    return PLAYBOOK_SPECS.get(route_id)


def get_playbook_builder(route_id: Domain) -> Optional[Callable[[UserSignal], ResponsePlan]]:
    return PLAYBOOK_BUILDERS.get(route_id)


# =========================================================
# Router principal
# =========================================================

def build_response_plan(signal: UserSignal) -> ResponsePlan:
    """
    Punto principal de entrada.
    Primero intercepta seguridad/limites, luego resuelve playbook.
    """

    high_risk = intercept_high_risk(signal)
    if high_risk:
        return high_risk

    meds = intercept_medication_request(signal)
    if meds:
        return meds

    if signal.turn_family == "meta_question" or signal.domain == "meta_question":
        return playbook_meta_question(signal)

    if signal.domain == "crisis":
        return playbook_crisis(signal)

    if signal.turn_family == "closure_or_pause" or signal.domain == "cierre":
        return playbook_close(signal)

    if signal.domain == "ansiedad":
        return playbook_anxiety(signal)

    if signal.domain == "bloqueo_ejecutivo":
        return playbook_executive_block(signal)

    if signal.domain == "sueno":
        return playbook_sleep(signal)

    if signal.domain == "apoyo_infancia_neurodivergente":
        return playbook_child_support(signal)

    if signal.domain == "sobrecarga_cuidador":
        return playbook_caregiver_overload(signal)

    if signal.domain == "meditacion_guiada":
        return playbook_meditation(signal)

    if signal.turn_family == "validation_request":
        return playbook_validation(signal)

    if signal.turn_family == "strategy_rejection" or signal.domain == "rechazo_estrategia":
        return playbook_strategy_rejection(signal)

    if signal.turn_family == "clarification_request" or signal.domain == "clarificacion":
        return playbook_clarification(signal)

    if signal.turn_family == "followup_acceptance" or signal.asks_for_next_step:
        return playbook_next_step(signal)

    if signal.turn_family == "simple_question" or signal.domain == "pregunta_simple":
        return playbook_simple_question(signal)

    if signal.domain == "depresion_baja_energia":
        return playbook_low_energy(signal)

    return playbook_general(signal)


# =========================================================
# Helper basico para pruebas rapidas
# =========================================================

def infer_basic_signal(user_text: str, domain: Domain, turn_family: TurnFamily) -> UserSignal:
    """
    Helper basico por si necesitas prototipar rapido.
    No sustituye routers mas finos, pero sirve para conectar playbooks.
    """

    text = normalize_text(user_text)

    outcome: OutcomePolarity = "unknown"
    if contains_any(text, ["sigo igual", "no cambio", "no ayudo", "no funciono"]):
        outcome = "no_change"
    elif contains_any(text, ["empeoro", "peor", "subio mas"]):
        outcome = "worse"
    elif contains_any(text, ["bajo un poco", "me ayudo un poco", "aflojo un poco"]):
        outcome = "partial_relief"
    elif contains_any(text, ["ya estoy mejor", "ya bajo", "me ayudo"]):
        outcome = "improved"

    return UserSignal(
        domain=domain,
        turn_family=turn_family,
        outcome=outcome,
        user_text=user_text,
        asks_for_meds=contains_any(text, MED_REQUEST_MARKERS),
        asks_for_phrase=contains_any(
            text,
            [
                "que frase",
                "que digo",
                "que le digo",
                "que puedo decirle",
                "como le digo",
            ],
        ),
        asks_for_next_step=contains_any(
            text,
            [
                "y luego",
                "que sigue",
                "que mas",
                "y despues",
                "y ahora que",
            ],
        ),
        expresses_confusion=contains_any(
            text,
            [
                "no entiendo",
                "no te entiendo",
                "como",
            ],
        ),
        expresses_overwhelm=contains_any(
            text,
            [
                "me gana",
                "no puedo con todo",
                "todo se me junta",
                "me rebasa",
            ],
        ),
        expresses_rejection=contains_any(
            text,
            [
                "no me sirve",
                "no me ayuda",
                "otra cosa",
                "eso no funciona",
                "no sirves",
            ],
        ),
        expresses_impossibility=contains_any(
            text,
            [
                "no puedo",
                "no me sale",
                "no me da",
                "no logro",
                "no puedo empezar",
            ],
        ),
        wants_to_pause=contains_any(text, ["por ahora ya", "ya estuvo", "aqui paro"]),
        wants_to_continue=contains_any(text, ["si", "ok", "dale", "continua", "ayudame"]),
        mentions_risk=contains_any(text, HIGH_RISK_MARKERS),
    )


if __name__ == "__main__":
    examples = [
        infer_basic_signal("Esta ocurriendo una crisis y necesito ayuda", "crisis", "new_request"),
        infer_basic_signal("que le digo?", "crisis", "literal_phrase_request"),
        infer_basic_signal("mejor dime qué pastillas tomar", "sueno", "specific_action_request"),
        infer_basic_signal("quien eres?", "meta_question", "meta_question"),
        infer_basic_signal("no puedo ni empezar", "bloqueo_ejecutivo", "blocked_followup"),
    ]

    for signal in examples:
        plan = build_response_plan(signal)
        print("=" * 60)
        print("USER:", signal.user_text)
        print("ROUTE:", plan.route_id)
        print("SUBROUTE:", plan.subroute_id)
        print("GOAL:", plan.goal)
        print("MAIN:", plan.main_response)
        if plan.literal_phrase:
            print("PHRASE:", plan.literal_phrase)
        if plan.optional_followup:
            print("FOLLOWUP:", plan.optional_followup)
