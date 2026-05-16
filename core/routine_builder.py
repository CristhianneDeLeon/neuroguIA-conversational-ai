from __future__ import annotations

from typing import Any, Dict, List, Optional


class RoutineBuilder:
    """
    Constructor premium de rutinas para NeuroGuía.

    Objetivo:
    construir rutinas y secuencias de apoyo proporcionadas al perfil,
    al estado funcional, a la etapa conversacional, a la capacidad actual
    del cuidador/usuario y a la memoria previa del caso.

    No diagnostica.
    No redacta respuestas finales completas.
    """

    ROUTINE_LIBRARY: Dict[str, Dict[str, Any]] = {
        "sleep": {
            "name": "Rutina nocturna de aterrizaje suave",
            "goal": "reducir activación antes del sueño y aumentar previsibilidad",
            "default_steps": [
                "avisar con anticipación breve que se acerca el momento de dormir",
                "bajar luz y ruido de manera gradual",
                "evitar correcciones largas o conversaciones exigentes",
                "hacer una actividad repetitiva y tranquila",
                "cerrar con una frase predecible",
            ],
            "short_steps": [
                "avisar que ya viene el momento de dormir",
                "bajar estímulos",
                "cerrar con una misma frase tranquila",
            ],
            "adjustments": {
                "sensory": [
                    "cuidar luz, ruido, textura y temperatura",
                    "permitir objeto regulador si ayuda",
                ],
                "low_capacity": [
                    "reducir la rutina a tres pasos máximos",
                    "priorizar ambiente suave sobre perfección",
                ],
                "rigidity": [
                    "mantener secuencia muy parecida cada noche",
                    "avisar cambios con anticipación si la rutina varía",
                ],
            },
            "indicators": [
                "menos oposición al ir a dormir",
                "menos activación nocturna",
                "transición más suave al sueño",
            ],
            "followup_question": "¿Qué ayudó más: bajar estímulos o mantener la misma frase de cierre?",
        },
        "executive_block": {
            "name": "Rutina de desbloqueo ejecutivo",
            "goal": "facilitar el inicio de tareas cuando hay bloqueo o saturación",
            "default_steps": [
                "nombrar una sola tarea",
                "reducirla al paso más pequeño posible",
                "hacer visible el primer paso",
                "usar un tiempo corto y alcanzable",
                "detenerse después del primer avance si por ahora eso ya era suficiente",
            ],
            "short_steps": [
                "elegir solo una tarea",
                "hacer únicamente el primer paso",
                "parar y revisar si eso ya fue suficiente por ahora",
            ],
            "adjustments": {
                "tdah": [
                    "usar inicio mínimo muy concreto",
                    "evitar listas largas",
                ],
                "aacc": [
                    "cuidar que la tarea conserve sentido y dignidad",
                    "evitar tono infantilizado",
                ],
                "anxiety": [
                    "quitar presión de resultado",
                    "recordar que empezar ya cuenta como avance",
                ],
                "low_capacity": [
                    "usar versión corta de tres pasos",
                    "no añadir organización compleja",
                ],
            },
            "indicators": [
                "logra iniciar más rápido",
                "reduce parálisis o evitación",
                "menos sensación de caos ante tareas",
            ],
            "followup_question": "¿Ayudó más reducir a un paso o poner un tiempo corto?",
        },
        "post_crisis": {
            "name": "Rutina postcrisis de recuperación gradual",
            "goal": "recuperar estabilidad sin culpa ni sobreanálisis inmediato",
            "default_steps": [
                "confirmar seguridad física y emocional",
                "bajar estímulos y reducir demanda verbal",
                "permitir un tiempo corto de recuperación sin presión",
                "volver poco a poco a una sola actividad simple",
                "dejar cualquier análisis profundo para después",
            ],
            "short_steps": [
                "priorizar seguridad",
                "bajar estímulos",
                "dejar que la recuperación ocurra sin presión",
            ],
            "adjustments": {
                "meltdown": [
                    "no intentar razonar durante el pico",
                    "usar frases muy breves",
                ],
                "shutdown": [
                    "ofrecer pocas opciones",
                    "permitir silencio y espacio",
                ],
                "low_capacity": [
                    "elegir solo una meta de recuperación",
                    "evitar reparación perfecta",
                ],
            },
            "indicators": [
                "retorno gradual a la calma",
                "menos reactivación posterior",
                "menor culpa o fricción tras la crisis",
            ],
            "followup_question": "¿Qué ayudó más después de la crisis: el silencio, el espacio o una sola indicación breve?",
        },
        "caregiver_recovery": {
            "name": "Rutina breve para cuidador saturado",
            "goal": "bajar carga funcional y emocional del cuidador sin exigir perfección",
            "default_steps": [
                "detenerse un momento y bajar exigencia interna",
                "elegir solo una prioridad real para este momento",
                "descartar temporalmente lo no esencial",
                "hacer una microacción de regulación",
                "cerrar con permiso explícito de imperfecto",
            ],
            "short_steps": [
                "bajar exigencia",
                "elegir una sola prioridad",
                "hacer una microacción breve para regularte",
            ],
            "adjustments": {
                "burnout": [
                    "usar tono muy amable",
                    "evitar productividad compleja",
                ],
                "sleep_loss": [
                    "reducir metas al mínimo viable",
                    "evitar decisiones largas",
                ],
                "low_support": [
                    "priorizar supervivencia funcional",
                    "registrar solo lo urgente",
                ],
            },
            "indicators": [
                "menor sensación de desborde",
                "más claridad para la siguiente acción",
                "disminución de culpa inmediata",
            ],
            "followup_question": "¿Te ayudó más elegir una prioridad o darte permiso de bajar exigencia?",
        },
        "sensory_regulation": {
            "name": "Rutina de regulación sensorial",
            "goal": "reducir carga sensorial acumulada y recuperar tolerancia funcional",
            "default_steps": [
                "identificar el estímulo que más molesta en este momento",
                "bajar uno o dos estímulos clave",
                "permitir una pausa o espacio regulador",
                "usar un recurso sensorial seguro si ayuda",
                "volver poco a poco a la actividad",
            ],
            "short_steps": [
                "identificar qué estímulo está pesando más",
                "bajar ese estímulo",
                "dar una pausa breve para regular",
            ],
            "adjustments": {
                "tea": [
                    "evitar cambios bruscos",
                    "mantener claridad sobre lo que sigue",
                ],
                "high_intensity": [
                    "reducir mucho las palabras",
                    "priorizar ambiente y seguridad",
                ],
                "sleep_related": [
                    "usar una versión más lenta y suave",
                    "evitar luz fuerte por la noche",
                ],
            },
            "indicators": [
                "menos irritabilidad",
                "menos rechazo al entorno",
                "mayor tolerancia progresiva",
            ],
            "followup_question": "¿Qué reguló mejor: bajar ruido, bajar luz o hacer una pausa breve?",
        },
        "school_transition": {
            "name": "Rutina de transición escolar",
            "goal": "facilitar el paso hacia actividades escolares sin saturación temprana",
            "default_steps": [
                "anticipar visual o verbalmente lo que sigue",
                "preparar una sola prioridad del día",
                "usar una señal o recurso regulador",
                "evitar dar demasiadas instrucciones al mismo tiempo",
                "tener un plan B breve si algo se complica",
            ],
            "short_steps": [
                "anticipar qué sigue",
                "elegir solo una prioridad",
                "usar una señal reguladora",
            ],
            "adjustments": {
                "executive": [
                    "mostrar solo el primer paso",
                    "hacer visible la secuencia",
                ],
                "anxiety": [
                    "nombrar qué sí está claro hoy",
                    "evitar presión de rendimiento desde el inicio",
                ],
                "low_capacity": [
                    "centrarse solo en lo indispensable",
                    "dejar fuera exigencias no urgentes",
                ],
            },
            "indicators": [
                "menos resistencia matutina",
                "menos discusiones antes de iniciar",
                "mejor arranque funcional",
            ],
            "followup_question": "¿Qué ayudó más: anticipar lo que seguía o reducir instrucciones?",
        },
        "emotional_landing": {
            "name": "Rutina de aterrizaje emocional",
            "goal": "bajar activación emocional y recuperar sensación de seguridad",
            "default_steps": [
                "nombrar que este momento está siendo difícil",
                "validar sin exagerar ni minimizar",
                "hacer una pausa breve",
                "ofrecer una acción pequeña y segura",
                "cerrar con continuidad amable",
            ],
            "short_steps": [
                "nombrar que el momento está pesado",
                "hacer una pausa breve",
                "elegir una acción pequeña y segura",
            ],
            "adjustments": {
                "anxiety": [
                    "dar una certeza pequeña",
                    "evitar abrir muchos escenarios",
                ],
                "aacc": [
                    "mantener respeto por la profundidad emocional",
                    "no trivializar lo que siente",
                ],
                "low_capacity": [
                    "centrarse en una sola cosa por ahora",
                    "no exigir reflexión larga",
                ],
            },
            "indicators": [
                "baja activación emocional",
                "más disposición a continuar",
                "menos sensación de aislamiento",
            ],
            "followup_question": "¿Qué te ayudó más: sentirte validada o tener una acción pequeña clara?",
        },
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
        profile = profile or {}
        state_analysis = state_analysis or {}
        stage_result = stage_result or {}
        memory_payload = memory_payload or {}
        context = context or {}

        detected_routine_type = routine_type or self._infer_routine_type(
            profile=profile,
            state_analysis=state_analysis,
            stage_result=stage_result,
            context=context,
        )

        template = self.ROUTINE_LIBRARY.get(detected_routine_type, self.ROUTINE_LIBRARY["emotional_landing"])

        conditions = [str(c).upper() for c in profile.get("conditions", []) or []]
        primary_state = str(state_analysis.get("primary_state") or "").lower()
        flags = state_analysis.get("flags", {}) or {}

        adjustments = self._build_adjustments(
            routine_type=detected_routine_type,
            template=template,
            conditions=conditions,
            primary_state=primary_state,
            caregiver_capacity=caregiver_capacity,
            emotional_intensity=emotional_intensity,
            flags=flags,
            context=context,
        )

        steps = self._adapt_steps(
            base_steps=list(template["default_steps"]),
            routine_type=detected_routine_type,
            conditions=conditions,
            primary_state=primary_state,
            caregiver_capacity=caregiver_capacity,
            emotional_intensity=emotional_intensity,
            context=context,
        )

        short_version = self._build_short_version(
            template=template,
            adjusted_steps=steps,
            caregiver_capacity=caregiver_capacity,
            emotional_intensity=emotional_intensity,
            primary_state=primary_state,
        )

        memory_suggestions = self._build_memory_suggestions(memory_payload)
        indicators = self._build_indicators(template, memory_payload)

        return {
            "routine_type": detected_routine_type,
            "routine_name": template["name"],
            "goal": template["goal"],
            "target_profile": {
                "profile_id": profile.get("profile_id"),
                "alias": profile.get("alias"),
                "role": profile.get("role"),
                "age": profile.get("age"),
                "conditions": profile.get("conditions", []),
            },
            "context_summary": {
                "primary_state": state_analysis.get("primary_state"),
                "stage": stage_result.get("stage"),
                "caregiver_capacity": caregiver_capacity,
                "emotional_intensity": emotional_intensity,
            },
            "steps": steps,
            "short_version": short_version,
            "adjustments": adjustments,
            "memory_suggestions": memory_suggestions,
            "indicators": indicators,
            "followup_question": template.get("followup_question"),
        }

    # =========================================================
    # INFERENCIA DE TIPO DE RUTINA
    # =========================================================
    def _infer_routine_type(
        self,
        profile: Dict[str, Any],
        state_analysis: Dict[str, Any],
        stage_result: Dict[str, Any],
        context: Dict[str, Any],
    ) -> str:
        primary_state = str(state_analysis.get("primary_state") or "").lower()
        detected_category = str(context.get("detected_category") or "").lower()
        text_hint = str(context.get("text_hint") or "").lower()

        if primary_state == "sleep_disruption" or "sueño" in detected_category or "dorm" in text_hint:
            return "sleep"

        if primary_state in {"meltdown", "shutdown"}:
            return "post_crisis"

        if primary_state == "executive_dysfunction" or "bloqueo" in detected_category or "tarea" in text_hint:
            return "executive_block"

        if primary_state == "sensory_overload" or "sensorial" in detected_category:
            return "sensory_regulation"

        if primary_state in {"burnout", "parental_fatigue"} or "cuidador" in detected_category:
            return "caregiver_recovery"

        if "escuela" in detected_category or "transicion" in detected_category or "transición" in detected_category:
            return "school_transition"

        return "emotional_landing"

    # =========================================================
    # AJUSTES
    # =========================================================
    def _build_adjustments(
        self,
        routine_type: str,
        template: Dict[str, Any],
        conditions: List[str],
        primary_state: str,
        caregiver_capacity: Optional[float],
        emotional_intensity: Optional[float],
        flags: Dict[str, bool],
        context: Dict[str, Any],
    ) -> List[str]:
        adjustments: List[str] = []

        if self._is_low_capacity(caregiver_capacity):
            adjustments.extend(template.get("adjustments", {}).get("low_capacity", []))

        if "TEA" in conditions or flags.get("needs_sensory_reduction"):
            adjustments.extend(template.get("adjustments", {}).get("sensory", []))
            adjustments.extend(template.get("adjustments", {}).get("tea", []))

        if "TDAH" in conditions or "DISFUNCION_EJECUTIVA" in conditions or flags.get("needs_microsteps"):
            adjustments.extend(template.get("adjustments", {}).get("executive", []))
            adjustments.extend(template.get("adjustments", {}).get("tdah", []))

        if "AACC" in conditions:
            adjustments.extend(template.get("adjustments", {}).get("aacc", []))

        if "ANSIEDAD" in conditions:
            adjustments.extend(template.get("adjustments", {}).get("anxiety", []))

        if primary_state == "meltdown":
            adjustments.extend(template.get("adjustments", {}).get("meltdown", []))

        if primary_state == "shutdown":
            adjustments.extend(template.get("adjustments", {}).get("shutdown", []))

        if primary_state == "burnout":
            adjustments.extend(template.get("adjustments", {}).get("burnout", []))

        if self._is_high_intensity(emotional_intensity):
            adjustments.extend(template.get("adjustments", {}).get("high_intensity", []))

        sleep_profile = str(context.get("sleep_profile") or "").lower()
        if "desvelo" in sleep_profile or "insomnio" in sleep_profile:
            adjustments.extend(template.get("adjustments", {}).get("sleep_loss", []))
            adjustments.extend(template.get("adjustments", {}).get("sleep_related", []))

        support_network = str(context.get("support_network") or "").lower()
        if any(token in support_network for token in ["nula", "poca", "sin apoyo", "escasa"]):
            adjustments.extend(template.get("adjustments", {}).get("low_support", []))

        if flags.get("needs_predictability"):
            adjustments.extend(template.get("adjustments", {}).get("rigidity", []))

        return self._deduplicate(adjustments)

    def _adapt_steps(
        self,
        base_steps: List[str],
        routine_type: str,
        conditions: List[str],
        primary_state: str,
        caregiver_capacity: Optional[float],
        emotional_intensity: Optional[float],
        context: Dict[str, Any],
    ) -> List[str]:
        steps = list(base_steps)

        if self._is_low_capacity(caregiver_capacity):
            steps = steps[:3]
            steps = [self._soften_step(step) for step in steps]

        if self._is_high_intensity(emotional_intensity):
            steps = [self._compress_step(step) for step in steps]

        if "AACC" in conditions:
            steps = [self._respect_depth(step) for step in steps]

        if "TEA" in conditions:
            steps = [self._increase_predictability(step) for step in steps]

        if "TDAH" in conditions or "DISFUNCION_EJECUTIVA" in conditions:
            steps = [self._make_step_concrete(step) for step in steps]

        if primary_state in {"meltdown", "shutdown"}:
            steps = steps[:3]

        if routine_type == "executive_block":
            steps = self._ensure_microstep_sequence(steps)

        return self._deduplicate(steps)

    def _build_short_version(
        self,
        template: Dict[str, Any],
        adjusted_steps: List[str],
        caregiver_capacity: Optional[float],
        emotional_intensity: Optional[float],
        primary_state: str,
    ) -> List[str]:
        if self._is_low_capacity(caregiver_capacity) or self._is_high_intensity(emotional_intensity):
            return adjusted_steps[:3]

        if primary_state in {"meltdown", "shutdown", "burnout"}:
            return adjusted_steps[:3]

        base_short = template.get("short_steps", []) or []
        if base_short:
            return base_short[:3]

        return adjusted_steps[:3]

    def _build_memory_suggestions(self, memory_payload: Dict[str, Any]) -> List[str]:
        suggestions: List[str] = []

        for item in (memory_payload.get("help_patterns", []) or [])[:3]:
            if isinstance(item, str) and item.strip():
                suggestions.append(f"recuperar algo que antes ayudó: {item.strip()}")

        for item in (memory_payload.get("recommended_microactions", []) or [])[:2]:
            if isinstance(item, str) and item.strip():
                suggestions.append(f"microacción previamente útil: {item.strip()}")

        return self._deduplicate(suggestions)

    def _build_indicators(self, template: Dict[str, Any], memory_payload: Dict[str, Any]) -> List[str]:
        indicators = list(template.get("indicators", []))
        for item in (memory_payload.get("recommended_microactions", []) or [])[:2]:
            if isinstance(item, str) and item.strip():
                indicators.append(f"observar si vuelve a ayudar: {item.strip()}")
        return self._deduplicate(indicators)

    # =========================================================
    # TRANSFORMACIONES
    # =========================================================
    def _soften_step(self, step: str) -> str:
        replacements = {
            "hacer": "probar",
            "usar": "apoyarse en",
            "confirmar": "buscar",
            "identificar": "notar",
            "volver": "regresar poco a poco",
        }
        result = step
        for old, new in replacements.items():
            result = result.replace(old, new)
        return result

    def _compress_step(self, step: str) -> str:
        compressions = [
            ("de manera gradual", ""),
            ("sin presión", ""),
            ("de forma", ""),
            ("muy", ""),
        ]
        result = step
        for old, new in compressions:
            result = result.replace(old, new)
        return " ".join(result.split())

    def _respect_depth(self, step: str) -> str:
        if "infantil" in step.lower():
            return step.replace("infantil", "claro y digno")
        return step

    def _increase_predictability(self, step: str) -> str:
        lowered = step.lower()
        if any(token in lowered for token in ["anticip", "predec", "secuencia", "misma frase", "mismo"]):
            return step
        return f"{step} y mantenerlo de forma predecible"

    def _make_step_concrete(self, step: str) -> str:
        lowered = step.lower()
        if "primer paso" in lowered or "solo" in lowered or "únicamente" in lowered:
            return step
        return f"{step}, empezando por una sola parte"

    def _ensure_microstep_sequence(self, steps: List[str]) -> List[str]:
        if not steps:
            return [
                "elegir una sola tarea",
                "hacer únicamente el primer paso",
                "parar y revisar si eso ya fue suficiente por ahora",
            ]
        return steps[:3]

    # =========================================================
    # HELPERS
    # =========================================================
    def _normalize_text(self, text: Optional[str]) -> str:
        if not text:
            return ""
        return " ".join(str(text).strip().lower().split())

    def _is_low_capacity(self, caregiver_capacity: Optional[float]) -> bool:
        if caregiver_capacity is None:
            return False
        try:
            return float(caregiver_capacity) <= 0.35
        except (TypeError, ValueError):
            return False

    def _is_high_intensity(self, emotional_intensity: Optional[float]) -> bool:
        if emotional_intensity is None:
            return False
        try:
            return float(emotional_intensity) >= 0.70
        except (TypeError, ValueError):
            return False

    def _deduplicate(self, items: List[Any]) -> List[Any]:
        seen = set()
        result = []
        for item in items:
            key = item if not isinstance(item, str) else self._normalize_text(item)
            if key not in seen:
                seen.add(key)
                result.append(item)
        return result


def build_personalized_routine(
    profile: Optional[Dict[str, Any]] = None,
    state_analysis: Optional[Dict[str, Any]] = None,
    stage_result: Optional[Dict[str, Any]] = None,
    memory_payload: Optional[Dict[str, Any]] = None,
    routine_type: Optional[str] = None,
    caregiver_capacity: Optional[float] = None,
    emotional_intensity: Optional[float] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    builder = RoutineBuilder()
    return builder.build_routine(
        profile=profile,
        state_analysis=state_analysis,
        stage_result=stage_result,
        memory_payload=memory_payload,
        routine_type=routine_type,
        caregiver_capacity=caregiver_capacity,
        emotional_intensity=emotional_intensity,
        context=context,
    )


def infer_routine_type(
    profile: Optional[Dict[str, Any]] = None,
    state_analysis: Optional[Dict[str, Any]] = None,
    stage_result: Optional[Dict[str, Any]] = None,
    context: Optional[Dict[str, Any]] = None,
) -> str:
    builder = RoutineBuilder()
    return builder._infer_routine_type(
        profile=profile or {},
        state_analysis=state_analysis or {},
        stage_result=stage_result or {},
        context=context or {},
    )
