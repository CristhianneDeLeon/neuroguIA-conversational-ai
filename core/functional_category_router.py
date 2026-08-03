from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, Iterable, List, Optional


class FunctionalCategoryRouter:
    """Clasifica la necesidad del turno en una taxonomía funcional de siete categorías.

    La taxonomía funcional complementa —sin sustituir— las categorías técnicas
    utilizadas por el enrutador conversacional. De esta manera se conserva la
    trazabilidad histórica del proyecto y, al mismo tiempo, se hace explícito
    qué tipo de apoyo práctico debe ofrecer neuroguIA.
    """

    DEFINITIONS: Dict[str, Dict[str, str]] = {
        "regulacion_emocional": {
            "label": "Regulación emocional",
            "purpose": "Apoyo para el manejo de emociones y situaciones de estrés",
            "default_routine_type": "emotional_landing",
        },
        "acompanamiento_escolar": {
            "label": "Acompañamiento escolar",
            "purpose": "Estrategias relacionadas con tareas, aprendizaje y organización académica",
            "default_routine_type": "school_support",
        },
        "organizacion_familiar": {
            "label": "Organización familiar",
            "purpose": "Planificación de actividades y distribución de responsabilidades",
            "default_routine_type": "family_organization",
        },
        "regulacion_sensorial": {
            "label": "Regulación sensorial",
            "purpose": "Orientaciones para situaciones de sobrecarga o saturación sensorial",
            "default_routine_type": "sensory_regulation",
        },
        "bienestar_cuidador": {
            "label": "Bienestar del cuidador",
            "purpose": "Estrategias dirigidas al autocuidado y reducción del agotamiento",
            "default_routine_type": "caregiver_recovery",
        },
        "manejo_crisis": {
            "label": "Manejo de crisis",
            "purpose": "Acciones orientadas a situaciones de alta intensidad emocional",
            "default_routine_type": "crisis_safety",
        },
        "rutinas_habitos": {
            "label": "Rutinas y hábitos",
            "purpose": "Organización de actividades cotidianas y seguimiento de objetivos",
            "default_routine_type": "daily_habits",
        },
    }

    RULES: Dict[str, List[str]] = {
        "manejo_crisis": [
            "esta en crisis", "está en crisis", "crisis ahora", "crisis en este momento",
            "se esta golpeando", "se está golpeando", "esta golpeando", "está golpeando",
            "se puede lastimar", "puede lastimarse", "hay riesgo", "esta agresivo",
            "está agresivo", "rompio cosas", "rompió cosas", "perdio el control",
            "perdió el control", "alta intensidad", "desborde", "meltdown",
            "despues de la crisis", "después de la crisis", "ya se calmo", "ya se calmó",
        ],
        "regulacion_sensorial": [
            "sobrecarga sensorial", "saturacion sensorial", "saturación sensorial",
            "mucho ruido", "demasiado ruido", "ruido le molesta", "mucha luz",
            "luces fuertes", "texturas", "olor fuerte", "muchos estimulos",
            "muchos estímulos", "se sobreestimula", "no tolera el ruido",
            "no tolera el contacto", "demasiada gente", "necesidad sensorial",
        ],
        "acompanamiento_escolar": [
            "tarea escolar", "tareas escolares", "tarea de la escuela", "actividad escolar",
            "trabajo escolar", "escuela", "colegio", "clase", "aula", "maestra",
            "maestro", "docente", "examen", "estudiar", "aprendizaje", "materia",
            "organizar la tarea", "no quiere hacer la tarea", "no puede empezar la tarea",
            "entrega", "proyecto escolar", "horario escolar",
        ],
        "organizacion_familiar": [
            "organizacion familiar", "organización familiar", "responsabilidades en casa",
            "repartir responsabilidades", "distribuir responsabilidades", "quien hace que",
            "quién hace qué", "tareas del hogar", "pendientes de la casa",
            "actividades familiares", "agenda familiar", "plan familiar",
            "todos en casa", "en casa nadie", "coordinar a la familia",
            "repartir tareas", "acuerdos familiares",
        ],
        "bienestar_cuidador": [
            "estoy agotada", "estoy agotado", "ya no puedo", "me siento rebasada",
            "me siento rebasado", "todo recae en mi", "todo recae en mí",
            "no tengo tiempo para mi", "no tengo tiempo para mí", "agotamiento del cuidador",
            "burnout parental", "estoy cansada de cuidar", "estoy cansado de cuidar",
            "cuidar me supera", "necesito cuidarme", "necesito descansar",
            "me siento sola", "me siento solo", "sobrecarga del cuidador",
        ],
        "rutinas_habitos": [
            "necesito una rutina", "quiero una rutina", "crear una rutina",
            "hazme una rutina", "armar una rutina", "organizar una rutina",
            "rutina diaria", "rutina de mañana", "rutina de la mañana",
            "rutina de noche", "habito", "hábito", "habitos", "hábitos",
            "horario", "calendario", "secuencia diaria", "todos los dias",
            "todos los días", "seguimiento de objetivos", "recordatorio",
            "pasos para cada dia", "pasos para cada día", "plan semanal",
        ],
        "regulacion_emocional": [
            "ansiedad", "estres", "estrés", "me siento abrumada", "me siento abrumado",
            "me siento triste", "me siento enojada", "me siento enojado",
            "no se como calmarme", "no sé cómo calmarme", "regular mis emociones",
            "regular sus emociones", "manejar mis emociones", "manejar el enojo",
            "frustracion", "frustración", "angustia", "me sobrepasa",
            "saturacion emocional", "saturación emocional", "me siento mal",
        ],
    }

    TECHNICAL_MAP: Dict[str, str] = {
        "crisis_activa": "manejo_crisis",
        "escalada_emocional": "manejo_crisis",
        "prevencion_escalada": "manejo_crisis",
        "regulacion_post_evento": "manejo_crisis",
        "sobrecarga_sensorial": "regulacion_sensorial",
        "saturacion_sensorial": "regulacion_sensorial",
        "sobrecarga_cuidador": "bienestar_cuidador",
        "parental_fatigue": "bienestar_cuidador",
        "burnout": "bienestar_cuidador",
        "ansiedad_cognitiva": "regulacion_emocional",
        "cognitive_anxiety": "regulacion_emocional",
        "disfuncion_ejecutiva": "rutinas_habitos",
        "bloqueo_ejecutivo": "rutinas_habitos",
        "sueno_regulacion": "rutinas_habitos",
        "sleep_disruption": "rutinas_habitos",
        "transicion_rigidez": "rutinas_habitos",
        "apoyo_infancia_neurodivergente": "regulacion_emocional",
    }

    PRIMARY_STATE_MAP: Dict[str, str] = {
        "meltdown": "manejo_crisis",
        "shutdown": "manejo_crisis",
        "sensory_overload": "regulacion_sensorial",
        "burnout": "bienestar_cuidador",
        "parental_fatigue": "bienestar_cuidador",
        "executive_dysfunction": "rutinas_habitos",
        "sleep_disruption": "rutinas_habitos",
        "cognitive_anxiety": "regulacion_emocional",
        "emotional_saturation": "regulacion_emocional",
    }

    PRIORITY = [
        "manejo_crisis",
        "regulacion_sensorial",
        "acompanamiento_escolar",
        "organizacion_familiar",
        "bienestar_cuidador",
        "rutinas_habitos",
        "regulacion_emocional",
    ]

    PRESENT_CRISIS_MARKERS = [
        "ahora", "ahorita", "en este momento", "esta en crisis", "crisis ahora",
        "esta golpeando", "se esta golpeando", "hay riesgo", "puede lastimarse",
    ]
    NEGATED_CRISIS_MARKERS = [
        "no esta en crisis", "no hay crisis", "no es una crisis", "sin crisis",
    ]

    def route(
        self,
        message: str,
        technical_category: Optional[str] = None,
        primary_state: Optional[str] = None,
        conversation_domain: Optional[str] = None,
        profile: Optional[Dict[str, Any]] = None,
        previous_frame: Optional[Dict[str, Any]] = None,
        **_: Any,
    ) -> Dict[str, Any]:
        text = self._normalize(message)
        technical = self._normalize_key(technical_category or conversation_domain)
        state = self._normalize_key(primary_state)
        previous_frame = previous_frame or {}
        profile = profile or {}

        scores = {key: 0.0 for key in self.DEFINITIONS}
        reasons: Dict[str, List[str]] = {key: [] for key in self.DEFINITIONS}

        mapped_technical = self.TECHNICAL_MAP.get(technical)
        if mapped_technical:
            scores[mapped_technical] += 0.34
            reasons[mapped_technical].append(f"technical_category:{technical}")

        mapped_state = self.PRIMARY_STATE_MAP.get(state)
        if mapped_state:
            scores[mapped_state] += 0.30
            reasons[mapped_state].append(f"primary_state:{state}")

        for category, phrases in self.RULES.items():
            matched = self._matches(text, phrases)
            if not matched:
                continue
            phrase_score = min(0.62, 0.18 + (0.10 * len(matched)))
            scores[category] += phrase_score
            reasons[category].extend(f"text:{item}" for item in matched[:5])

        # Ajustes de desambiguación.
        has_school_context = any(
            token in text
            for token in ("escuela", "escolar", "tarea", "clase", "maestra", "maestro", "examen", "estudiar")
        )
        if technical in {"disfuncion_ejecutiva", "bloqueo_ejecutivo"} and has_school_context:
            scores["acompanamiento_escolar"] += 0.28
            reasons["acompanamiento_escolar"].append("executive_block_in_school_context")

        has_family_organization = any(
            token in text
            for token in ("responsabilidades", "tareas del hogar", "agenda familiar", "repartir", "coordinar")
        )
        if has_family_organization:
            scores["organizacion_familiar"] += 0.20
            reasons["organizacion_familiar"].append("family_coordination_need")

        crisis_negated = any(marker in text for marker in self.NEGATED_CRISIS_MARKERS)
        crisis_present = (
            not crisis_negated
            and any(marker in text for marker in self.PRESENT_CRISIS_MARKERS)
        )
        if crisis_present:
            scores["manejo_crisis"] = max(scores["manejo_crisis"], 0.96)
            reasons["manejo_crisis"].append("present_crisis_marker")
        elif crisis_negated:
            scores["manejo_crisis"] = min(scores["manejo_crisis"], 0.18)
            reasons["manejo_crisis"].append("negated_crisis")

        # El perfil solo aporta una señal tenue; nunca impone una categoría.
        profile_text = self._normalize(
            " ".join(
                str(item)
                for item in (
                    profile.get("school_profile"),
                    profile.get("sleep_profile"),
                    profile.get("executive_profile"),
                    profile.get("sensory_needs"),
                )
                if item
            )
        )
        if profile_text and "sensor" in profile_text:
            scores["regulacion_sensorial"] += 0.05
        if profile_text and any(token in profile_text for token in ("escuela", "escolar", "aprendiz")):
            scores["acompanamiento_escolar"] += 0.05

        # Continuidad funcional suave.
        previous_category = self._normalize_key(previous_frame.get("functional_category"))
        if previous_category in scores and len(text.split()) <= 6:
            scores[previous_category] += 0.08
            reasons[previous_category].append("short_turn_continuity")

        if not any(value > 0 for value in scores.values()):
            scores["regulacion_emocional"] = 0.20
            reasons["regulacion_emocional"].append("safe_default")

        ranked = sorted(
            scores,
            key=lambda key: (-scores[key], self.PRIORITY.index(key)),
        )
        selected = ranked[0]
        selected_score = max(0.0, scores[selected])
        confidence = round(min(0.99, max(0.45, 0.42 + selected_score)), 3)
        definition = self.DEFINITIONS[selected]

        candidates = [
            {
                "functional_category": key,
                "label": self.DEFINITIONS[key]["label"],
                "score": round(scores[key], 3),
                "signals": reasons[key],
            }
            for key in ranked[:3]
            if scores[key] > 0
        ]

        return {
            "functional_category": selected,
            "functional_category_label": definition["label"],
            "functional_category_purpose": definition["purpose"],
            "default_routine_type": definition["default_routine_type"],
            "confidence": confidence,
            "signals": reasons[selected],
            "candidates": candidates,
            "crisis_present": crisis_present,
            "source": "functional_category_router_v1",
        }

    def _normalize(self, value: Any) -> str:
        text = unicodedata.normalize("NFKD", str(value or "").strip().lower())
        text = "".join(char for char in text if not unicodedata.combining(char))
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    def _normalize_key(self, value: Any) -> str:
        return self._normalize(value).replace(" ", "_")

    def _matches(self, text: str, phrases: Iterable[str]) -> List[str]:
        matched: List[str] = []
        for phrase in phrases:
            normalized = self._normalize(phrase)
            if normalized and normalized in text and normalized not in matched:
                matched.append(normalized)
        return matched
