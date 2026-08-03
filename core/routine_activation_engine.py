from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, Optional


class RoutineActivationEngine:
    """Decide cuándo una necesidad requiere una rutina estructurada.

    La activación evita dos extremos: generar rutinas en cada turno o no
    generarlas nunca. Prioriza solicitudes explícitas y necesidades funcionales
    que se benefician de una secuencia repetible.
    """

    EXPLICIT_MARKERS = (
        "necesito una rutina", "quiero una rutina", "hazme una rutina",
        "crea una rutina", "crear una rutina", "armar una rutina",
        "dame un plan", "hazme un plan", "paso a paso", "que hago cada dia",
        "que hago cada día", "organiza mi dia", "organiza mi día",
        "organizar la semana", "horario", "calendario", "secuencia",
    )

    REJECTION_MARKERS = (
        "no quiero una rutina", "sin rutina", "no me des un plan",
        "no quiero pasos", "solo quiero hablar", "solo queria contarte",
        "solo quería contarte",
    )

    META_MARKERS = (
        "que eres", "qué eres", "como funcionas", "cómo funcionas",
        "quien te creo", "quién te creó", "que puedes hacer", "qué puedes hacer",
    )

    PRACTICAL_MARKERS = (
        "que hago", "qué hago", "como lo hago", "cómo lo hago", "ayudame a",
        "ayúdame a", "no puedo empezar", "no se organizar", "no sé organizar",
        "necesito organizar", "se repite", "todos los dias", "todos los días",
        "cada mañana", "cada noche", "antes de", "despues de", "después de",
    )

    def evaluate(
        self,
        message: str,
        functional_analysis: Optional[Dict[str, Any]] = None,
        technical_category: Optional[str] = None,
        primary_state: Optional[str] = None,
        turn_family: Optional[str] = None,
        emotional_intensity: Optional[float] = None,
        caregiver_capacity: Optional[float] = None,
        previous_frame: Optional[Dict[str, Any]] = None,
        **_: Any,
    ) -> Dict[str, Any]:
        functional_analysis = functional_analysis or {}
        previous_frame = previous_frame or {}
        text = self._normalize(message)
        category = str(functional_analysis.get("functional_category") or "regulacion_emocional")
        technical = self._normalize_key(technical_category)
        state = self._normalize_key(primary_state)
        turn = self._normalize_key(turn_family)

        explicit = any(self._normalize(marker) in text for marker in self.EXPLICIT_MARKERS)
        rejected = any(self._normalize(marker) in text for marker in self.REJECTION_MARKERS)
        meta = any(self._normalize(marker) in text for marker in self.META_MARKERS)
        practical = any(self._normalize(marker) in text for marker in self.PRACTICAL_MARKERS)

        if rejected:
            return self._result(
                False, None, "routine_explicitly_rejected", "none", 0.0, category
            )
        if meta or technical == "apoyo_general" and turn == "meta":
            return self._result(False, None, "meta_turn", "none", 0.0, category)

        routine_type = self._routine_type(category, text, technical, state)
        score = 0.0
        reasons = []

        if explicit:
            score += 0.72
            reasons.append("explicit_routine_request")

        if practical:
            score += 0.18
            reasons.append("practical_sequence_request")

        auto_categories = {
            "acompanamiento_escolar",
            "organizacion_familiar",
            "regulacion_sensorial",
            "bienestar_cuidador",
            "rutinas_habitos",
        }
        if category in auto_categories:
            score += 0.52
            reasons.append(f"functional_category:{category}")

        crisis_present = bool(functional_analysis.get("crisis_present")) or technical == "crisis_activa"
        if category == "manejo_crisis" and crisis_present:
            score = max(score, 0.95)
            reasons.append("active_crisis_requires_short_safety_sequence")
            routine_type = "crisis_safety"

        if category == "manejo_crisis" and not crisis_present:
            if any(token in text for token in ("despues de la crisis", "ya se calmo", "cuando ya paso")):
                score = max(score, 0.68)
                reasons.append("post_crisis_recovery")
                routine_type = "post_crisis"

        if category == "regulacion_emocional":
            emotional_need = any(
                token in text
                for token in (
                    "no se como calmarme", "ansiedad", "estres", "me sobrepasa",
                    "regular mis emociones", "manejar el enojo", "saturacion emocional",
                )
            )
            if emotional_need:
                score += 0.52
                reasons.append("emotional_regulation_need")

        if state in {"meltdown", "shutdown", "sensory_overload", "burnout", "sleep_disruption"}:
            score += 0.18
            reasons.append(f"primary_state:{state}")

        if technical in {
            "disfuncion_ejecutiva", "sobrecarga_sensorial", "sobrecarga_cuidador",
            "sueno_regulacion", "regulacion_post_evento",
        }:
            score += 0.14
            reasons.append(f"technical_category:{technical}")

        # Evita repetir el mismo bloque estructurado en dos turnos consecutivos.
        # La rutina vuelve a mostrarse cuando la persona la solicita expresamente,
        # cambia la necesidad funcional o persiste una crisis activa.
        previous_routine_type = self._normalize_key(
            previous_frame.get("last_routine_type")
        )
        followup_families = {
            "followup",
            "followup_acceptance",
            "followup_request",
            "continuation",
            "clarification",
            "post_action_followup",
            "blocked_followup",
        }
        if (
            previous_routine_type
            and previous_routine_type == self._normalize_key(routine_type)
            and turn in followup_families
            and not explicit
            and not crisis_present
        ):
            score -= 0.72
            reasons.append("consecutive_duplicate_routine_suppressed")

        if len(text.split()) <= 2 and not explicit and not crisis_present:
            score -= 0.35
            reasons.append("very_short_turn")

        should_generate = score >= 0.50
        mode = self._display_mode(
            crisis_present=crisis_present,
            emotional_intensity=emotional_intensity,
            caregiver_capacity=caregiver_capacity,
            text=text,
        )
        if not should_generate:
            routine_type = None
            mode = "none"

        return {
            "should_generate": should_generate,
            "routine_type": routine_type,
            "reason": "|".join(reasons) if reasons else "no_activation_signal",
            "display_mode": mode,
            "activation_score": round(max(0.0, min(1.0, score)), 3),
            "functional_category": category,
            "max_steps": 3 if mode == "short" else 5,
            "explicit_request": explicit,
            "source": "routine_activation_engine_v2",
        }

    def _routine_type(
        self,
        category: str,
        text: str,
        technical: str,
        state: str,
    ) -> str:
        if category == "manejo_crisis":
            return "crisis_safety"
        if category == "regulacion_sensorial":
            return "sensory_regulation"
        if category == "acompanamiento_escolar":
            return "school_support"
        if category == "organizacion_familiar":
            return "family_organization"
        if category == "bienestar_cuidador":
            return "caregiver_recovery"
        if category == "rutinas_habitos":
            if any(token in text for token in ("dormir", "sueno", "noche", "insomnio")):
                return "sleep"
            if technical in {"disfuncion_ejecutiva", "bloqueo_ejecutivo"} or state == "executive_dysfunction":
                return "executive_block"
            return "daily_habits"
        return "emotional_landing"

    def _display_mode(
        self,
        crisis_present: bool,
        emotional_intensity: Optional[float],
        caregiver_capacity: Optional[float],
        text: str,
    ) -> str:
        if crisis_present:
            return "short"
        try:
            if emotional_intensity is not None and float(emotional_intensity) >= 0.70:
                return "short"
        except (TypeError, ValueError):
            pass
        try:
            if caregiver_capacity is not None and float(caregiver_capacity) <= 0.35:
                return "short"
        except (TypeError, ValueError):
            pass
        if any(token in text for token in ("rapido", "rápido", "breve", "ahora mismo")):
            return "short"
        return "full"

    def _result(
        self,
        should_generate: bool,
        routine_type: Optional[str],
        reason: str,
        display_mode: str,
        score: float,
        category: str,
    ) -> Dict[str, Any]:
        return {
            "should_generate": should_generate,
            "routine_type": routine_type,
            "reason": reason,
            "display_mode": display_mode,
            "activation_score": score,
            "functional_category": category,
            "max_steps": 0,
            "explicit_request": False,
            "source": "routine_activation_engine_v2",
        }

    def _normalize(self, value: Any) -> str:
        text = unicodedata.normalize("NFKD", str(value or "").strip().lower())
        text = "".join(char for char in text if not unicodedata.combining(char))
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    def _normalize_key(self, value: Any) -> str:
        return self._normalize(value).replace(" ", "_")
