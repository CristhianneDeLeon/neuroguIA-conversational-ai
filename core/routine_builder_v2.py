from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.routine_builder import RoutineBuilder


class RoutineBuilderV2(RoutineBuilder):
    """Extiende el constructor original con rutinas funcionales completas."""

    ROUTINE_LIBRARY: Dict[str, Dict[str, Any]] = {
        **RoutineBuilder.ROUTINE_LIBRARY,
        "crisis_safety": {
            "name": "Secuencia inmediata de seguridad",
            "goal": "reducir riesgo y carga durante una situación de alta intensidad",
            "default_steps": [
                "revisar primero si existe riesgo de golpearse, lastimar a alguien o alcanzar objetos peligrosos",
                "bajar ruido, luz, personas e instrucciones; usar pocas palabras y mantener distancia segura",
                "pedir apoyo presencial o contactar los servicios de emergencia de tu localidad si el riesgo es inmediato",
            ],
            "short_steps": [
                "revisar si hay riesgo físico inmediato",
                "bajar estímulos y usar pocas palabras",
                "pedir apoyo presencial o de emergencia si el riesgo continúa",
            ],
            "adjustments": {
                "meltdown": [
                    "no razonar ni corregir durante el pico",
                    "priorizar espacio, seguridad y una frase breve",
                ],
                "shutdown": [
                    "permitir silencio y reducir las preguntas",
                    "ofrecer solo una opción segura a la vez",
                ],
                "high_intensity": [
                    "mantener la secuencia en tres pasos",
                ],
            },
            "indicators": [
                "disminuye el riesgo físico",
                "baja la intensidad del entorno",
                "la persona recupera gradualmente control o seguridad",
            ],
            "followup_question": "¿Hay riesgo físico inmediato para alguien en este momento?",
        },
        "school_support": {
            "name": "Rutina breve de acompañamiento escolar",
            "goal": "hacer abordable una tarea o actividad académica sin aumentar saturación",
            "default_steps": [
                "definir una sola tarea o entrega para este momento",
                "convertirla en un primer paso visible que pueda hacerse en menos de diez minutos",
                "preparar únicamente el material necesario para ese paso",
                "trabajar durante un bloque corto con una pausa prevista",
                "cerrar registrando qué avanzó y cuál será el siguiente paso",
            ],
            "short_steps": [
                "elegir una sola tarea",
                "hacer visible el primer paso",
                "trabajar un bloque corto y registrar el avance",
            ],
            "adjustments": {
                "executive": [
                    "mostrar una instrucción a la vez",
                    "usar una lista visual de máximo tres elementos",
                ],
                "tdah": [
                    "reducir distracciones y usar un temporizador breve",
                    "permitir movimiento entre bloques",
                ],
                "anxiety": [
                    "separar comenzar de terminar",
                    "evitar hablar de todas las entregas al mismo tiempo",
                ],
                "low_capacity": [
                    "acompañar solo el arranque y dejar el resto para después",
                ],
            },
            "indicators": [
                "inicia con menos resistencia",
                "puede identificar el siguiente paso",
                "disminuye la discusión alrededor de la tarea",
            ],
            "followup_question": "¿La dificultad principal está en empezar, comprender la tarea o sostener la atención?",
        },
        "family_organization": {
            "name": "Rutina familiar de coordinación sencilla",
            "goal": "distribuir actividades y responsabilidades sin concentrar toda la carga en una persona",
            "default_steps": [
                "anotar únicamente las actividades indispensables del día o de la semana",
                "asignar cada actividad a una persona concreta y acordar qué apoyo necesita",
                "hacer visible el acuerdo en una lista, calendario o tablero sencillo",
                "definir una revisión breve sin convertirla en regaño",
                "ajustar lo que no funcionó antes de agregar nuevas responsabilidades",
            ],
            "short_steps": [
                "elegir las actividades indispensables",
                "asignar una persona y un apoyo para cada una",
                "dejar el acuerdo visible y revisarlo brevemente",
            ],
            "adjustments": {
                "executive": [
                    "usar nombres, verbos y horarios concretos",
                    "evitar categorías vagas como ayudar más",
                ],
                "sensory": [
                    "mantener el tablero visual limpio y con pocos elementos",
                ],
                "low_capacity": [
                    "repartir solo dos o tres responsabilidades por ahora",
                ],
            },
            "indicators": [
                "hay menos dudas sobre quién hace cada actividad",
                "disminuyen recordatorios repetidos",
                "la carga deja de recaer en una sola persona",
            ],
            "followup_question": "¿Qué responsabilidad está generando más confusión o carga en casa?",
        },
        "morning_organization": {
            "name": "Rutina de mañana con baja carga",
            "goal": "hacer más predecible la salida de casa sin concentrar demasiadas demandas al mismo tiempo",
            "default_steps": [
                "dejar preparados desde la noche anterior la ropa, la mochila y solo lo indispensable",
                "usar una señal de inicio estable, como una alarma suave, una frase breve o una imagen",
                "seguir una secuencia visible de cuatro bloques: levantarse, asearse, vestirse y desayunar",
                "dar una sola indicación a la vez y marcar cada bloque cuando termine",
                "reservar un pequeño margen antes de salir para absorber retrasos sin convertirlos en crisis",
            ],
            "short_steps": [
                "dejar ropa y mochila preparadas",
                "seguir una lista visible de cuatro bloques",
                "dar una sola indicación y conservar un pequeño margen antes de salir",
            ],
            "adjustments": {
                "executive": [
                    "usar verbos concretos y mostrar únicamente el paso actual",
                    "colocar la lista donde realmente ocurre la rutina",
                ],
                "tdah": [
                    "usar un temporizador breve por bloque y permitir movimiento entre pasos",
                ],
                "sensory": [
                    "reducir ruido, luz intensa y decisiones de último momento",
                ],
                "rigidity": [
                    "mantener el mismo orden y anticipar cualquier cambio desde la noche anterior",
                ],
                "low_capacity": [
                    "considerar suficiente completar los tres pasos indispensables",
                ],
            },
            "indicators": [
                "hay menos recordatorios repetidos",
                "la persona identifica qué sigue",
                "disminuye la tensión antes de salir",
            ],
            "followup_question": "¿Esta rutina es para ti, para tu hijo o para toda la familia?",
        },
        "daily_habits": {
            "name": "Rutina mínima de hábitos sostenibles",
            "goal": "convertir una actividad cotidiana en una secuencia sencilla y repetible",
            "default_steps": [
                "elegir un solo hábito y definir para qué sirve",
                "vincularlo a una señal que ya ocurre, como despertar, comer o llegar a casa",
                "reducirlo a una versión mínima que pueda cumplirse incluso en un día difícil",
                "dejar preparado el material o recordatorio necesario",
                "revisar durante una semana qué ayudó y ajustar sin castigo",
            ],
            "short_steps": [
                "elegir un solo hábito",
                "vincularlo a una señal cotidiana",
                "hacer una versión mínima y registrarla",
            ],
            "adjustments": {
                "executive": [
                    "usar una señal visible y una sola acción",
                    "preparar el entorno antes del momento del hábito",
                ],
                "tdah": [
                    "usar recordatorios breves y variar la recompensa funcional",
                ],
                "rigidity": [
                    "mantener una secuencia estable y anticipar cambios",
                ],
                "low_capacity": [
                    "considerar suficiente la versión mínima",
                ],
            },
            "indicators": [
                "la actividad requiere menos recordatorios",
                "se puede retomar después de una interrupción",
                "la rutina se sostiene sin elevar demasiado la carga",
            ],
            "followup_question": "¿Qué momento del día quieres organizar primero?",
        },
    }

    FUNCTIONAL_ROUTINE_MAP = {
        "regulacion_emocional": "emotional_landing",
        "acompanamiento_escolar": "school_support",
        "organizacion_familiar": "family_organization",
        "regulacion_sensorial": "sensory_regulation",
        "bienestar_cuidador": "caregiver_recovery",
        "manejo_crisis": "crisis_safety",
        "rutinas_habitos": "daily_habits",
    }

    def build_routine(
        self,
        profile: Optional[Dict[str, Any]] = None,
        state_analysis: Optional[Dict[str, Any]] = None,
        stage_result: Optional[Dict[str, Any]] = None,
        memory_payload: Optional[Dict[str, Any]] = None,
        routine_type: Optional[str] = None,
        caregiver_capacity: Optional[float] = None,
        emotional_intensity: Optional[float] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        context = context or {}
        functional_category = str(context.get("functional_category") or "").strip()
        selected_type = routine_type or self.FUNCTIONAL_ROUTINE_MAP.get(functional_category)

        payload = super().build_routine(
            profile=profile,
            state_analysis=state_analysis,
            stage_result=stage_result,
            memory_payload=memory_payload,
            routine_type=selected_type,
            caregiver_capacity=caregiver_capacity,
            emotional_intensity=emotional_intensity,
            context=context,
        )
        payload["functional_category"] = functional_category or None
        payload["functional_category_label"] = context.get("functional_category_label")
        payload["functional_category_purpose"] = context.get("functional_category_purpose")
        payload["display_mode"] = context.get("display_mode") or "full"
        payload["activation_reason"] = context.get("activation_reason")
        payload["generated_by"] = "routine_builder_v2"
        return payload

    def _infer_routine_type(
        self,
        profile: Dict[str, Any],
        state_analysis: Dict[str, Any],
        stage_result: Dict[str, Any],
        context: Dict[str, Any],
    ) -> str:
        functional_category = str(context.get("functional_category") or "").strip()
        if functional_category in self.FUNCTIONAL_ROUTINE_MAP:
            mapped = self.FUNCTIONAL_ROUTINE_MAP[functional_category]
            text_hint = self._normalize_text(context.get("text_hint"))
            if functional_category == "rutinas_habitos":
                if any(token in text_hint for token in ("mañana", "manana", "matut", "despert", "antes de salir")):
                    return "morning_organization"
                if any(token in text_hint for token in ("dorm", "sueño", "sueno", "noche")):
                    return "sleep"
                if any(token in text_hint for token in ("tarea", "pendiente", "empezar", "bloqueo")):
                    return "executive_block"
            return mapped
        return super()._infer_routine_type(
            profile=profile,
            state_analysis=state_analysis,
            stage_result=stage_result,
            context=context,
        )


def render_routine_payload(
    routine_payload: Optional[Dict[str, Any]],
    display_mode: Optional[str] = None,
) -> str:
    """Convierte una rutina estructurada en texto conversacional visible."""
    payload = routine_payload or {}
    if not payload:
        return ""

    mode = str(display_mode or payload.get("display_mode") or "full").strip().lower()
    steps = list(
        payload.get("short_version") if mode == "short" else payload.get("steps")
        or []
    )
    if not steps:
        steps = list(payload.get("steps") or payload.get("short_version") or [])
    steps = [str(item).strip() for item in steps if str(item).strip()]
    max_steps = 3 if mode == "short" else 5
    steps = steps[:max_steps]
    if not steps:
        return ""

    title = str(payload.get("routine_name") or "Rutina sugerida").strip()
    goal = str(payload.get("goal") or "").strip()
    lines: List[str] = [f"**{title}**"]
    if goal and mode != "short":
        lines.append(f"Objetivo: {goal}.")
    lines.extend(f"{index}. {step[0].upper() + step[1:] if step else step}." for index, step in enumerate(steps, 1))

    adjustments = [str(item).strip() for item in payload.get("adjustments", []) if str(item).strip()]
    if adjustments and mode != "short":
        lines.append(f"Ajuste útil: {adjustments[0]}.")

    question = str(payload.get("followup_question") or "").strip()
    if question:
        lines.append(question)

    return "\n".join(lines)


def attach_routine_to_response(
    response_package: Optional[Dict[str, Any]],
    routine_payload: Optional[Dict[str, Any]],
    functional_analysis: Optional[Dict[str, Any]],
    routine_activation: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Añade una rutina visible y metadatos funcionales a cualquier ruta de respuesta."""
    package = dict(response_package or {})
    routine = dict(routine_payload or {})
    functional = dict(functional_analysis or {})
    activation = dict(routine_activation or {})

    base_text = str(package.get("response") or package.get("text") or "").strip()
    routine_text = render_routine_payload(
        routine,
        display_mode=activation.get("display_mode"),
    )
    if routine_text:
        routine_name = str(routine.get("routine_name") or "").strip()
        functional_category = str(functional.get("functional_category") or "").strip()
        intro_by_category = {
            "regulacion_emocional": "Vamos a bajarlo a una secuencia breve y amable.",
            "acompanamiento_escolar": "Vamos a convertir la demanda escolar en pasos visibles y alcanzables.",
            "organizacion_familiar": "Vamos a repartir la carga con un acuerdo sencillo y visible.",
            "regulacion_sensorial": "Primero reduzcamos la carga del entorno con una secuencia corta.",
            "bienestar_cuidador": "Vamos a proteger un poco tu energía sin exigirte más.",
            "manejo_crisis": "En este momento la prioridad es la seguridad y bajar estímulos.",
            "rutinas_habitos": "Claro. Vamos a construir una secuencia sencilla, realista y ajustable.",
        }
        should_replace_base = bool(activation.get("explicit_request")) or functional_category in {
            "organizacion_familiar",
            "rutinas_habitos",
        }
        if routine_name and routine_name.lower() in base_text.lower():
            final_text = base_text
        elif should_replace_base:
            intro = intro_by_category.get(functional_category, "Vamos a ordenarlo en pasos concretos.")
            final_text = f"{intro}\n\n{routine_text}".strip()
        else:
            final_text = f"{base_text}\n\n{routine_text}".strip()
        package["response"] = final_text
        package["text"] = final_text
        package["routine_generated"] = True
        package["routine_type"] = routine.get("routine_type")
        package["routine_name"] = routine.get("routine_name")
    else:
        package["routine_generated"] = False

    metadata = dict(package.get("response_metadata") or {})
    metadata.update(
        {
            "functional_category": functional.get("functional_category"),
            "functional_category_label": functional.get("functional_category_label"),
            "functional_category_purpose": functional.get("functional_category_purpose"),
            "functional_category_confidence": functional.get("confidence"),
            "routine_generated": bool(routine_text),
            "routine_type": routine.get("routine_type"),
            "routine_name": routine.get("routine_name"),
            "routine_activation_reason": activation.get("reason"),
            "routine_activation_score": activation.get("activation_score"),
            "routine_display_mode": activation.get("display_mode"),
        }
    )
    package["response_metadata"] = metadata
    package["functional_category"] = functional.get("functional_category")
    package["routine_payload"] = routine
    return package
