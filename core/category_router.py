from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Optional

from core.classic_text_classifier import get_default_category_classifier
from core.semantic_encoder import get_default_category_semantic_encoder


class CategoryRouter:
    LEGACY_CATEGORY_ALIASES = {
        "crisis_emocional": "crisis_activa",
        "saturacion_sensorial": "sobrecarga_sensorial",
        "bloqueo_ejecutivo": "disfuncion_ejecutiva",
        "sleep": "sueno_regulacion",
        "agotamiento_cuidador": "sobrecarga_cuidador",
        "sueno_descanso": "sueno_regulacion",
        "transicion": "transicion_rigidez",
    }

    CATEGORY_RULES = {
        "crisis_activa": {
            "keywords": [
                "esta en crisis", "ahorita esta mal", "esta golpeando", "esta gritando",
                "no lo puedo controlar", "no lo puedo calmar", "se salio de control",
                "hay riesgo", "rompio cosas", "esta agresivo", "esta violento",
                "esta ocurriendo una crisis", "ocurriendo una crisis", "crisis ahora",
                "necesito ayuda para manejarla",
            ],
            "base_score": 0.36,
        },
        "escalada_emocional": {
            "keywords": [
                "se empieza a alterar", "se empieza a enojar", "va subiendo", "se va escalando",
                "se pone irritable", "se pone inquieto", "se pone rigido", "se tensa",
                "antes de explotar", "antes del desborde", "se desregula", "se frustra rapido",
            ],
            "base_score": 0.30,
        },
        "prevencion_escalada": {
            "keywords": [
                "como evito", "evitar que pase", "evitar que vuelva a pasar", "que no se repita",
                "que se repitan", "como prevenir", "prevenir", "como detectar antes",
                "que hago antes", "como anticiparlo", "me preocupa que vuelva a pasar",
                "antes de que escale", "antes del pico",
            ],
            "base_score": 0.34,
        },
        "ansiedad_cognitiva": {
            "keywords": [
                "ansiedad", "me da ansiedad", "ataques de ansiedad", "me siento ansiosa", "me siento ansioso",
                "me siento muy ansiosa", "me siento muy ansioso", "estoy ansiosa", "estoy ansioso",
                "me abruma", "me sobrepasa", "no dejo de pensar", "pienso demasiado",
                "muchos pendientes", "todos los pendientes", "saturacion mental", "me angustia",
                "me da ansiedad pensar", "overthinking", "no se como calmarme",
            ],
            "base_score": 0.33,
        },
        "disfuncion_ejecutiva": {
            "keywords": [
                "no puedo empezar", "no puedo iniciar", "me bloqueo", "no arranco",
                "no se por donde empezar", "no termino", "se me juntan las cosas",
                "procrastino", "no puedo organizarme", "me cuesta hacer el primer paso",
            ],
            "base_score": 0.31,
        },
        "sobrecarga_sensorial": {
            "keywords": [
                "mucho ruido", "demasiado ruido", "luces", "mucha luz", "muchos estimulos",
                "se sobreestimula", "sobrestimulacion", "se satura", "no tolera el ruido",
                "no tolera el contacto", "le molestan los sonidos", "le molestan las texturas",
                "demasiada gente", "olor fuerte", "desorden visual",
            ],
            "base_score": 0.28,
        },
        "regulacion_post_evento": {
            "keywords": [
                "despues de la crisis", "cuando ya se calma", "cuando ya paso",
                "despues de que baje", "que hago despues", "como lo ayudo despues",
                "ya se calmo", "que hacemos despues", "hablar despues",
            ],
            "base_score": 0.29,
        },
        "sobrecarga_cuidador": {
            "keywords": [
                "ya no puedo", "estoy agotada", "estoy agotado", "estoy cansada", "estoy cansado",
                "me siento rebasada", "me siento rebasado", "esto me supera", "me rebasa",
                "no puedo con esto", "me siento sola", "todo recae en mi", "yo tambien estoy mal",
            ],
            "base_score": 0.27,
        },
        "sueno_regulacion": {
            "keywords": [
                "no duerme", "duerme mal", "no descansa", "desvelo", "insomnio",
                "no concilia el sueno", "se despierta mucho", "tarda mucho en dormir",
                "le cuesta dormir", "se duerme muy tarde", "no estoy durmiendo bien",
                "no duermo bien", "cansancio", "mucho cansancio",
            ],
            "base_score": 0.24,
        },
        "transicion_rigidez": {
            "keywords": [
                "cambio de plan", "cambios de plan", "cambios inesperados", "transicion",
                "transiciones", "rigido", "rigida", "rigidez", "le cuesta cambiar",
                "se altera con cambios", "se pone rigido con cambios",
            ],
            "base_score": 0.25,
        },
        "apoyo_general": {
            "keywords": ["ayudame", "necesito ayuda", "quiero orientacion", "me preocupa", "quiero entender", "que me recomiendas"],
            "base_score": 0.14,
        },
    }

    PRIORITY_ORDER = [
        "crisis_activa", "prevencion_escalada", "escalada_emocional", "ansiedad_cognitiva",
        "disfuncion_ejecutiva", "sobrecarga_sensorial", "regulacion_post_evento",
        "sobrecarga_cuidador", "sueno_regulacion", "transicion_rigidez", "apoyo_general",
    ]

    AFFIRMATION_TOKENS = {"si", "ok", "okay", "va", "aja", "de acuerdo", "dale", "claro", "continua", "ayudame"}
    PAST_EVENT_MARKERS = ["tuvo una crisis", "tuvo crisis", "ayer", "la vez pasada", "paso", "despues", "ya paso"]
    PRESENT_CRISIS_MARKERS = ["esta en crisis", "esta ocurriendo una crisis", "ocurriendo una crisis", "crisis ahora", "ahorita", "en este momento", "esta gritando", "esta golpeando", "no lo puedo controlar", "no lo puedo calmar", "hay riesgo"]

    def __init__(self) -> None:
        self.classic_classifier = get_default_category_classifier()
        self.semantic_encoder = get_default_category_semantic_encoder()

    def _normalize_text(self, text: Optional[str]) -> str:
        if not text:
            return ""
        text = str(text).strip().lower()
        text = unicodedata.normalize("NFKD", text)
        text = "".join(char for char in text if not unicodedata.combining(char))
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    def _contains_phrase(self, text: str, phrase: str) -> bool:
        phrase = self._normalize_text(phrase)
        if not text or not phrase:
            return False
        pattern = r"(?<!\w)" + re.escape(phrase).replace(r"\ ", r"\s+") + r"(?!\w)"
        return bool(re.search(pattern, text))

    def _contains_any(self, text: str, keywords: List[str]) -> List[str]:
        return [kw for kw in keywords if self._contains_phrase(text, kw)]

    def _canonicalize_category(self, category: Optional[str]) -> Optional[str]:
        if not category:
            return category
        return self.LEGACY_CATEGORY_ALIASES.get(category, category)

    def _priority_rank(self, category: str) -> int:
        category = self._canonicalize_category(category) or category
        return self.PRIORITY_ORDER.index(category) if category in self.PRIORITY_ORDER else len(self.PRIORITY_ORDER)

    def _build_classic_ml_signal(self, message: str) -> Dict[str, Any]:
        return self.classic_classifier.predict(message, top_k=3)

    def _build_semantic_signal(self, message: str) -> Dict[str, Any]:
        return self.semantic_encoder.predict(message, top_k=3)

    def _with_signals(self, payload: Dict[str, Any], classic_ml_signal: Dict[str, Any], semantic_signal: Dict[str, Any]) -> Dict[str, Any]:
        enriched = dict(payload)
        enriched["classic_ml_signal"] = classic_ml_signal
        enriched["semantic_signal"] = semantic_signal
        return enriched

    def _last_assistant_text(self, history_hint: Optional[List[Dict[str, Any]]]) -> str:
        if not history_hint:
            return ""
        return self._normalize_text(str(history_hint[-1].get("assistant") or ""))

    def _is_short_affirmation(self, normalized_message: str) -> bool:
        return normalized_message in self.AFFIRMATION_TOKENS

    def _continuation_category(self, normalized_message: str, history_hint: Optional[List[Dict[str, Any]]]) -> Optional[str]:
        if not self._is_short_affirmation(normalized_message):
            return None
        last_assistant = self._last_assistant_text(history_hint)
        if not last_assistant:
            return None
        if any(token in last_assistant for token in ["senal", "señal", "antes de que escale", "respuesta temprana"]):
            return "prevencion_escalada"
        if any(token in last_assistant for token in ["ansiedad", "saturacion", "prioridad", "pendiente"]):
            return "ansiedad_cognitiva"
        if any(token in last_assistant for token in ["primer paso", "arranque", "bloqueo", "micro"]):
            return "disfuncion_ejecutiva"
        if any(token in last_assistant for token in ["despues del episodio", "reparar", "cuando ya baje"]):
            return "regulacion_post_evento"
        return None

    def _is_past_event_prevention_request(self, text: str) -> bool:
        has_past = any(self._contains_phrase(text, token) for token in self.PAST_EVENT_MARKERS)
        has_prevention = any(self._contains_phrase(text, token) for token in ["se repitan", "que no se repita", "evitar", "prevenir", "vuelva a pasar", "constantemente"])
        return has_past and has_prevention

    def _has_negated_crisis(self, text: str) -> bool:
        patterns = [r"\bno\s+esta\s+en\s+crisis\b", r"\bno\s+hay\s+crisis\b", r"\bno\s+es\s+una\s+crisis\b", r"\bsin\s+crisis\b"]
        return any(re.search(pattern, text) for pattern in patterns)

    def route(
        self,
        message: str,
        state_analysis: Optional[Dict[str, Any]] = None,
        intent_analysis: Optional[Dict[str, Any]] = None,
        history_hint: Optional[List[Dict[str, Any]]] = None,
        extra_context: Optional[Dict[str, Any]] = None,
        profile: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        state_analysis = state_analysis or {}
        intent_analysis = intent_analysis or {}
        extra_context = extra_context or {}
        profile = profile or {}

        normalized_message = self._normalize_text(message)
        classic_ml_signal = self._build_classic_ml_signal(message)
        semantic_signal = self._build_semantic_signal(message)

        continuation_category = self._continuation_category(normalized_message, history_hint)
        if continuation_category:
            return self._with_signals({
                "detected_category": continuation_category,
                "confidence": 0.90,
                "alternatives": ["apoyo_general"],
                "candidates": [{"category": continuation_category, "score": 0.90, "matched_keywords": ["affirmative_continuation"], "priority_rank": self._priority_rank(continuation_category)}],
                "reasoning": {"message": "Continuidad de un hilo ya activo."},
            }, classic_ml_signal, semantic_signal)

        if self._is_past_event_prevention_request(normalized_message):
            return self._with_signals({
                "detected_category": "prevencion_escalada",
                "confidence": 0.92,
                "alternatives": ["regulacion_post_evento", "sobrecarga_cuidador"],
                "candidates": [{"category": "prevencion_escalada", "score": 0.92, "matched_keywords": ["past_event_plus_prevention"], "priority_rank": self._priority_rank("prevencion_escalada")}],
                "reasoning": {"message": "Se narra una crisis previa, pero la necesidad actual es preventiva."},
            }, classic_ml_signal, semantic_signal)

        extra_text = self._normalize_text(" ".join([
            str(extra_context.get("user_extra_context") or ""),
            str(extra_context.get("context_notes") or ""),
            str(profile.get("alias") or ""),
            " ".join(profile.get("conditions", []) or []),
            " ".join(profile.get("triggers", []) or []),
        ]))
        full_text = " ".join([normalized_message, extra_text]).strip()

        primary_state = self._normalize_text(state_analysis.get("primary_state"))
        detected_intent = self._normalize_text(intent_analysis.get("detected_intent"))
        has_past = any(self._contains_phrase(full_text, token) for token in self.PAST_EVENT_MARKERS)
        has_present = any(self._contains_phrase(full_text, token) for token in self.PRESENT_CRISIS_MARKERS) and not self._has_negated_crisis(full_text)

        results: List[Dict[str, Any]] = []
        for category, rule in self.CATEGORY_RULES.items():
            canonical = self._canonicalize_category(category) or category
            matches = self._contains_any(full_text, rule["keywords"])
            score = 0.0
            if matches:
                score += rule["base_score"] + min(len(matches) * 0.08, 0.28)

            if canonical == "prevencion_escalada" and detected_intent == "prevention_request":
                score += 0.20
            if canonical == "crisis_activa" and detected_intent == "urgent_support":
                score += 0.18
            if canonical == "regulacion_post_evento" and detected_intent in {"followup", "strategy_feedback"}:
                score += 0.10

            if canonical == "crisis_activa" and primary_state == "meltdown":
                score += 0.18
            if canonical == "sobrecarga_cuidador" and primary_state in {"burnout", "parental_fatigue"}:
                score += 0.12
            if canonical == "disfuncion_ejecutiva" and primary_state in {"executive_dysfunction", "executive_block"}:
                score += 0.14
            if canonical == "sueno_regulacion" and primary_state == "sleep_disruption":
                score += 0.14
            if canonical == "sobrecarga_sensorial" and primary_state in {"sensory_overload", "emotional_dysregulation"}:
                score += 0.10

            if canonical == "crisis_activa" and (has_past and not has_present):
                score -= 0.40
            if canonical == "crisis_activa" and self._has_negated_crisis(full_text):
                score -= 0.85
            if canonical == "crisis_activa" and detected_intent == "prevention_request":
                score -= 0.28
            if canonical == "crisis_activa" and any(self._contains_phrase(full_text, token) for token in ["ansiedad", "pendientes", "me abruma", "no dejo de pensar", "cansancio", "no duermo bien"]):
                score -= 0.32
            if canonical == "ansiedad_cognitiva" and any(self._contains_phrase(full_text, token) for token in ["pendientes", "abruma", "no dejo de pensar", "ansiedad", "saturacion mental"]):
                score += 0.12
            if canonical == "disfuncion_ejecutiva" and any(self._contains_phrase(full_text, token) for token in ["no puedo empezar", "bloqueo", "procrastino", "no se por donde empezar"]):
                score += 0.12
            if canonical == "regulacion_post_evento" and any(self._contains_phrase(full_text, token) for token in ["despues", "cuando ya se calma", "que hago despues"]):
                score += 0.10
            if canonical == "prevencion_escalada" and any(self._contains_phrase(full_text, token) for token in ["se repitan", "vuelva a pasar", "antes de que escale", "que hago antes"]):
                score += 0.12
            if canonical == "sueno_regulacion" and any(self._contains_phrase(full_text, token) for token in ["no duermo bien", "no estoy durmiendo bien", "cansancio", "insomnio", "duerme mal"]):
                score += 0.14
            if canonical == "transicion_rigidez" and any(self._contains_phrase(full_text, token) for token in ["cambios de plan", "cambio de plan", "rigido", "rigidez", "se altera con cambios", "transicion"]):
                score += 0.16

            score = max(min(score, 0.99), 0.0)
            if score > 0:
                results.append({"category": canonical, "score": round(score, 4), "matched_keywords": matches, "priority_rank": self._priority_rank(canonical)})

        if not results:
            return self._with_signals({"detected_category": "apoyo_general", "confidence": 0.25, "alternatives": [], "candidates": [], "reasoning": {"message": "No hubo evidencia fuerte para una categoria especifica."}}, classic_ml_signal, semantic_signal)

        results.sort(key=lambda item: (-item["score"], item["priority_rank"], item["category"]))
        best = results[0]
        return self._with_signals({
            "detected_category": best["category"],
            "confidence": best["score"],
            "alternatives": [item["category"] for item in results if item["category"] != best["category"]][:4],
            "candidates": results[:8],
            "reasoning": {
                "matched_keywords": best.get("matched_keywords", []),
                "primary_state": primary_state or None,
                "detected_intent": detected_intent or None,
                "has_past_markers": has_past,
                "has_present_crisis_markers": has_present,
            },
        }, classic_ml_signal, semantic_signal)


def route_category(
    message: str,
    state_analysis: Optional[Dict[str, Any]] = None,
    intent_analysis: Optional[Dict[str, Any]] = None,
    history_hint: Optional[List[Dict[str, Any]]] = None,
    extra_context: Optional[Dict[str, Any]] = None,
    profile: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    router = CategoryRouter()
    return router.route(
        message=message,
        state_analysis=state_analysis,
        intent_analysis=intent_analysis,
        history_hint=history_hint,
        extra_context=extra_context,
        profile=profile,
        **kwargs,
    )

