from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Optional


class StateGuardian:
    """Local state analyzer with stricter phrase matching and temporal guards."""

    def analyze(self, message: str, extra_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        extra_context = extra_context or {}
        text = self._normalize(message)
        ctx = self._normalize(str(extra_context.get("user_extra_context", "")))

        scores = {
            "meltdown": 0.0,
            "shutdown": 0.0,
            "burnout": 0.0,
            "parental_fatigue": 0.0,
            "emotional_dysregulation": 0.0,
            "executive_dysfunction": 0.0,
            "sleep_disruption": 0.0,
            "general_distress": 0.0,
            "sensory_overload": 0.0,
            "cognitive_anxiety": 0.0,
        }

        past_markers = [
            "ayer", "la vez pasada", "en otra ocasion", "ya paso", "ya paso eso",
            "tuvo una crisis", "tuvo crisis", "despues", "luego", "cuando ya se calmo",
            "gritaba", "golpeaba", "pegaba", "rompia cosas",
        ]
        present_crisis_markers = [
            "esta en crisis", "esta gritando", "esta golpeando",
            "nos quiere golpear", "me quiere golpear", "hay riesgo", "se salio de control",
            "rompio cosas", "esta agresivo", "esta violento", "no lo puedo calmar",
            "no lo puedo controlar", "en este momento", "ahorita",
            "esta ocurriendo una crisis", "ocurriendo una crisis", "crisis ahora",
        ]
        prevention_markers = [
            "como evitar", "prevenir", "que no se repita", "que se repitan",
            "vuelva a pasar", "antes de que escale", "que hago antes",
        ]
        anxiety_markers = [
            "ansiedad", "me da ansiedad", "ataques de ansiedad", "me angustia",
            "me abruma", "no dejo de pensar", "pienso demasiado", "rumio",
            "muchos pendientes", "todos los pendientes", "saturacion mental",
            "ansiosa", "ansioso", "me siento muy ansiosa", "me siento muy ansioso",
            "no se como calmarme",
        ]
        executive_markers = [
            "no puedo empezar", "no logro empezar", "me bloqueo", "no arranco",
            "no se por donde empezar", "procrastino", "me paralizo", "no puedo avanzar",
            "no puedo priorizar", "se me juntan las cosas",
        ]
        sensory_markers = [
            "mucho ruido", "demasiado ruido", "mucha luz", "luces", "muchos estimulos",
            "sobrestimulacion", "no tolera el ruido", "no tolera el contacto",
            "mucha gente", "demasiada gente", "texturas", "olores fuertes",
        ]
        sleep_markers = [
            "no duerme", "duerme mal", "no descansa", "no estoy durmiendo bien",
            "no duermo bien", "desvelo", "insomnio", "se despierta mucho",
            "le cuesta dormir", "tarda mucho en dormir", "cansancio", "mucho cansancio",
        ]
        caregiver_markers = [
            "ya no puedo", "estoy agotada", "estoy agotado", "estoy cansada", "estoy cansado",
            "me rebasa", "me supera", "todo recae en mi", "yo tambien estoy mal",
        ]
        shutdown_markers = [
            "se cerro", "se aislo", "no responde", "se quedo inmovil", "se apago",
        ]
        emotional_markers = [
            "llora", "muy alterado", "muy alterada", "frustrado", "frustrada", "desbordado", "desbordada",
        ]

        has_past = self._matches_any(text, past_markers)
        has_present_crisis = self._matches_any(text, present_crisis_markers) and not self._has_negated_crisis(text)
        has_prevention = self._matches_any(text, prevention_markers)
        has_anxiety = self._matches_any(text, anxiety_markers)
        has_executive = self._matches_any(text, executive_markers)
        has_sensory = self._matches_any(text, sensory_markers)
        has_sleep = self._matches_any(text, sleep_markers) or self._matches_any(ctx, ["desvelo", "insomnio", "cansancio"])
        has_caregiver = self._matches_any(text, caregiver_markers)

        if has_present_crisis:
            scores["meltdown"] += 0.95
            scores["general_distress"] += 0.18
        elif self._contains(text, "crisis") and has_past and not self._has_negated_crisis(text):
            scores["meltdown"] += 0.22
            scores["general_distress"] += 0.26
        elif self._contains(text, "crisis") and not self._has_negated_crisis(text):
            scores["meltdown"] += 0.55

        if self._has_negated_crisis(text):
            scores["general_distress"] += 0.20

        if self._matches_any(text, shutdown_markers):
            scores["shutdown"] += 0.80

        if has_caregiver:
            scores["burnout"] += 0.66
            scores["parental_fatigue"] += 0.74

        if has_anxiety:
            scores["cognitive_anxiety"] += 0.82
            scores["general_distress"] += 0.20

        if has_executive:
            scores["executive_dysfunction"] += 0.84
            scores["general_distress"] += 0.14

        if has_sensory:
            scores["sensory_overload"] += 0.78
            scores["emotional_dysregulation"] += 0.20

        if has_sleep:
            scores["sleep_disruption"] += 0.74
            scores["general_distress"] += 0.10

        if self._matches_any(text, emotional_markers):
            scores["emotional_dysregulation"] += 0.62

        scores["general_distress"] += 0.18
        if self._matches_any(text, ["no se que hacer", "me preocupa mucho", "estoy estresada", "estoy estresado"]):
            scores["general_distress"] += 0.18

        if has_past and has_prevention and not has_present_crisis:
            scores["meltdown"] -= 0.24
            scores["general_distress"] += 0.28
            scores["parental_fatigue"] += 0.20

        if has_anxiety:
            scores["meltdown"] -= 0.24
            scores["shutdown"] -= 0.05
        if has_executive:
            scores["meltdown"] -= 0.22
        if has_sensory and not has_present_crisis:
            scores["meltdown"] -= 0.12
        if has_sleep and not has_present_crisis:
            scores["meltdown"] -= 0.10
        if self._has_negated_crisis(text):
            scores["meltdown"] -= 0.35

        scores = {key: max(value, 0.0) for key, value in scores.items()}
        sorted_states = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        primary_state, intensity = sorted_states[0]

        if primary_state == "meltdown" and (has_past or self._has_negated_crisis(text)) and len(sorted_states) > 1 and sorted_states[1][1] >= 0.40:
            primary_state, intensity = sorted_states[1]
        if primary_state == "general_distress" and len(sorted_states) > 1 and sorted_states[1][1] >= 0.52:
            second_state, second_score = sorted_states[1]
            if not (has_past and has_prevention and second_state == "meltdown"):
                primary_state, intensity = second_state, second_score

        return {
            "primary_state": primary_state,
            "intensity": round(float(intensity), 2),
            "all_scores": scores,
            "time_context": {
                "has_past_markers": has_past,
                "has_present_crisis_markers": has_present_crisis,
                "has_prevention_focus": has_prevention,
                "has_anxiety_markers": has_anxiety,
                "has_executive_markers": has_executive,
                "has_sensory_markers": has_sensory,
                "has_sleep_markers": has_sleep,
            },
        }

    def _normalize(self, text: Optional[str]) -> str:
        if not text:
            return ""
        text = str(text).strip().lower()
        text = unicodedata.normalize("NFKD", text)
        text = "".join(char for char in text if not unicodedata.combining(char))
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    def _contains(self, text: str, phrase: str) -> bool:
        phrase = self._normalize(phrase)
        if not text or not phrase:
            return False
        pattern = r"(?<!\w)" + re.escape(phrase).replace(r"\ ", r"\s+") + r"(?!\w)"
        return bool(re.search(pattern, text))

    def _matches_any(self, text: str, phrases: List[str]) -> bool:
        return any(self._contains(text, phrase) for phrase in phrases)

    def _has_negated_crisis(self, text: str) -> bool:
        patterns = [
            r"\bno\s+esta\s+en\s+crisis\b",
            r"\bno\s+hay\s+crisis\b",
            r"\bno\s+es\s+una\s+crisis\b",
            r"\bsin\s+crisis\b",
        ]
        return any(re.search(pattern, text) for pattern in patterns)
