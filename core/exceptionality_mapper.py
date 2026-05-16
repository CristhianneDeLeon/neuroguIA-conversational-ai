from __future__ import annotations

from typing import Any, Dict, List, Optional


class ExceptionalityMapper:
    """
    Versión premium REAL alineada con todo el sistema.

    ✔ Compatible con orchestrator_v2
    ✔ Compatible con confidence_engine
    ✔ Compatible con decision_engine
    """

    CONDITION_MAP = {
        "TEA": {
            "supports": ["predictibilidad", "baja_estimulación", "estructura_clara"],
            "alerts": ["sobrecarga_sensorial", "rigidez"],
        },
        "TDAH": {
            "supports": ["microacciones", "inicio_simple", "estructura_flexible"],
            "alerts": ["impulsividad", "disfuncion_ejecutiva"],
        },
        "AACC": {
            "supports": ["profundidad", "sentido", "autonomía"],
            "alerts": ["aburrimiento", "desregulación_emocional"],
        },
        "ANSIEDAD": {
            "supports": ["certeza", "reduccion_incertidumbre"],
            "alerts": ["hiperactivación", "evitación"],
        },
        "BURNOUT": {
            "supports": ["baja_exigencia", "microacciones"],
            "alerts": ["colapso_funcional"],
        },
    }

    def analyze_profile(self, profile: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        profile = profile or {}

        raw_conditions = profile.get("conditions", []) or []

        if isinstance(raw_conditions, str):
            conditions = [c.strip().upper() for c in raw_conditions.split(",") if c.strip()]
        else:
            conditions = [str(c).upper() for c in raw_conditions]

        supports = []
        alerts = []

        for cond in conditions:
            data = self.CONDITION_MAP.get(cond, {})
            supports.extend(data.get("supports", []))
            alerts.extend(data.get("alerts", []))

        contradictions = self._detect_contradictions(conditions)

        return {
            "profile_id": profile.get("profile_id"),
            "conditions": conditions,
            "supports": self._deduplicate(supports),
            "alerts": self._deduplicate(alerts),
            "contradictions": contradictions,
            "exceptionality_level": self._get_exceptionality_level(conditions),
        }

    def map_profile_to_support_plan(self, profile: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        analysis = self.analyze_profile(profile)

        conditions = analysis["conditions"]
        contradictions = analysis["contradictions"]

        complexity_level = self._get_complexity_label(conditions, contradictions)

        return {
            "complexity_level": complexity_level,
            "support_priorities": analysis["supports"],
            "response_alerts": analysis["alerts"],
            "functional_contradictions": contradictions,
        }

    def _get_exceptionality_level(self, conditions: List[str]) -> str:
        if len(conditions) >= 3:
            return "triple"
        if len(conditions) == 2:
            return "double"
        if len(conditions) == 1:
            return "single"
        return "none"

    def _get_complexity_label(self, conditions: List[str], contradictions: List[str]) -> str:
        if len(conditions) >= 3 or len(contradictions) >= 2:
            return "triple_or_high_complexity"
        if len(conditions) == 2 or len(contradictions) == 1:
            return "double_exceptionality_or_cooccurrence"
        return "low_or_single"

    def _detect_contradictions(self, conditions: List[str]) -> List[str]:
        contradictions = []

        if "TEA" in conditions and "TDAH" in conditions:
            contradictions.append("rigidez_vs_impulsividad")

        if "AACC" in conditions and "TDAH" in conditions:
            contradictions.append("alto_potencial_vs_inconsistencia")

        if "TEA" in conditions and "ANSIEDAD" in conditions:
            contradictions.append("control_vs_saturacion")

        return contradictions

    def _deduplicate(self, items: List[Any]) -> List[Any]:
        seen = set()
        result = []
        for item in items:
            if item not in seen:
                seen.add(item)
                result.append(item)
        return result


def analyze_profile(profile: Dict[str, Any]) -> Dict[str, Any]:
    return ExceptionalityMapper().analyze_profile(profile)


def map_profile_to_support_plan(profile: Dict[str, Any]) -> Dict[str, Any]:
    return ExceptionalityMapper().map_profile_to_support_plan(profile)
