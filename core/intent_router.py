from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Optional

from core.classic_text_classifier import get_default_intent_classifier
from core.semantic_encoder import get_default_intent_semantic_encoder


class IntentRouter:
    INTENT_RULES = {
        "urgent_support": {
            "keywords": [
                "ayuda urgente", "ya no puedo", "no se que hacer", "esta en crisis",
                "no lo puedo controlar", "no lo puedo calmar", "hay riesgo",
                "esta golpeando", "esta gritando", "se salio de control", "me urge",
                "esta ocurriendo una crisis", "ocurriendo una crisis", "crisis ahora",
                "necesito ayuda para manejarla",
            ],
            "base_score": 0.28,
            "question_bias": 0.02,
        },
        "prevention_request": {
            "keywords": [
                "como evito", "como prevenir", "evitar que pase", "que no se repita",
                "que se repitan", "vuelva a pasar", "antes de que escale", "que hago antes",
                "como detectar antes", "como anticiparlo", "me preocupa que vuelva a pasar",
            ],
            "base_score": 0.34,
            "question_bias": 0.10,
        },
        "strategy_feedback": {
            "keywords": [
                "eso ya lo intente", "ya lo intente", "ya lo probe", "no funciono",
                "no ha funcionado", "eso no ayudo", "eso empeoro", "ya hice eso",
                "eso no me sirve", "no me ayuda", "eso no funciona", "no otra cosa",
                "eso no aplica",
            ],
            "base_score": 0.26,
            "question_bias": 0.03,
        },
        "about_system": {
            "keywords": [
                "quien eres", "para que sirves", "como ayudas", "como funcionas",
                "que puedes hacer", "que no puedes hacer", "eres un bot", "eres una ia",
            ],
            "base_score": 0.34,
            "question_bias": 0.14,
        },
        "anxiety_relief_request": {
            "keywords": [
                "me da ansiedad", "ataques de ansiedad", "ansiedad", "me angustia",
                "ansiosa", "ansioso", "me siento muy ansiosa", "me siento muy ansioso",
                "me abruma", "no dejo de pensar", "pienso demasiado", "muchos pendientes",
                "todos los pendientes", "saturacion mental", "overthinking", "rumio mucho",
                "no se como calmarme",
            ],
            "base_score": 0.34,
            "question_bias": 0.10,
        },
        "executive_support_request": {
            "keywords": [
                "no puedo empezar", "no logro empezar", "me bloqueo", "no arranco",
                "no se por donde empezar", "procrastino", "me paralizo", "no puedo avanzar",
                "no puedo priorizar", "se me juntan las cosas",
            ],
            "base_score": 0.34,
            "question_bias": 0.08,
        },
        "routine_request": {
            "keywords": [
                "dame una rutina", "dame pasos", "quiero pasos", "quiero una rutina",
                "que puedo hacer", "quiero una estrategia", "que estrategia", "algo concreto",
            ],
            "base_score": 0.18,
            "question_bias": 0.06,
        },
        "clarification_request": {
            "keywords": [
                "explicame", "aclarame", "a que te refieres", "no comprendo", "no entiendo",
                "no entendi", "me perdi", "explicamelo", "puedes decirlo mas simple",
                "que significa", "como funciona",
            ],
            "base_score": 0.16,
            "question_bias": 0.12,
        },
        "followup": {
            "keywords": ["seguimos", "continuamos", "retomemos", "te actualizo", "seguimiento", "otra vez"],
            "base_score": 0.14,
            "question_bias": 0.01,
        },
        "profile_question": {
            "keywords": ["por que", "que le pasa", "esto es normal", "como entender", "que podria estar pasando"],
            "base_score": 0.18,
            "question_bias": 0.08,
        },
        "emotional_venting": {
            "keywords": [
                "me siento", "estoy harta", "estoy harto", "estoy desesperada", "estoy desesperado",
                "me rebasa", "me supera", "estoy frustrada", "estoy frustrado", "me siento culpable",
            ],
            "base_score": 0.18,
            "question_bias": -0.04,
        },
        "general_support": {
            "keywords": ["ayudame", "necesito ayuda", "quiero apoyo", "me preocupa", "estoy confundida", "estoy confundido"],
            "base_score": 0.15,
            "question_bias": 0.05,
        },
    }

    PRIORITY_ORDER = [
        "urgent_support", "about_system", "prevention_request", "strategy_feedback", "anxiety_relief_request",
        "executive_support_request", "routine_request", "clarification_request", "followup",
        "profile_question", "emotional_venting", "general_support",
    ]

    AFFIRMATION_TOKENS = {"si", "ok", "okay", "va", "aja", "de acuerdo", "dale", "claro", "continua", "ayudame"}
    EXPLICIT_CLARIFICATION_MARKERS = ["no comprendo", "no entiendo", "no entendi", "me perdi", "explicamelo", "puedes decirlo mas simple"]
    EXPLICIT_ABOUT_SYSTEM_MARKERS = ["quien eres", "para que sirves", "como ayudas", "como funcionas", "que puedes hacer", "que no puedes hacer", "eres un bot", "eres una ia"]
    PAST_EVENT_MARKERS = ["tuvo una crisis", "ayer", "paso", "gritaba", "golpeaba", "despues", "la vez pasada"]

    def __init__(self) -> None:
        self.classic_classifier = get_default_intent_classifier()
        self.semantic_encoder = get_default_intent_semantic_encoder()

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

    def _has_negated_crisis(self, text: str) -> bool:
        patterns = [r"\bno\s+esta\s+en\s+crisis\b", r"\bno\s+hay\s+crisis\b", r"\bno\s+es\s+una\s+crisis\b", r"\bsin\s+crisis\b"]
        return any(re.search(pattern, text) for pattern in patterns)

    def _priority_rank(self, intent: str) -> int:
        return self.PRIORITY_ORDER.index(intent) if intent in self.PRIORITY_ORDER else len(self.PRIORITY_ORDER)

    def _build_classic_ml_signal(self, message: str) -> Dict[str, Any]:
        return self.classic_classifier.predict(message, top_k=3)

    def _build_semantic_signal(self, message: str) -> Dict[str, Any]:
        return self.semantic_encoder.predict(message, top_k=3)

    def _with_signals(self, payload: Dict[str, Any], classic_ml_signal: Dict[str, Any], semantic_signal: Dict[str, Any]) -> Dict[str, Any]:
        enriched = dict(payload)
        enriched["classic_ml_signal"] = classic_ml_signal
        enriched["semantic_signal"] = semantic_signal
        return enriched

    def _estimate_question_density(self, text: str) -> float:
        if not text:
            return 0.0
        normalized = self._normalize_text(text)
        question_marks = text.count("?")
        interrogatives = ["que", "como", "por que", "cuando", "cual", "quien"]
        hits = sum(1 for token in interrogatives if self._contains_phrase(normalized, token))
        return min(question_marks * 0.08 + hits * 0.03, 0.22)

    def _last_assistant_text(self, history_hint: Optional[List[Dict[str, Any]]]) -> str:
        if not history_hint:
            return ""
        return self._normalize_text(str(history_hint[-1].get("assistant") or ""))

    def _is_short_affirmation(self, normalized_message: str) -> bool:
        return normalized_message in self.AFFIRMATION_TOKENS

    def _continuation_intent(self, normalized_message: str, history_hint: Optional[List[Dict[str, Any]]]) -> Optional[str]:
        if not self._is_short_affirmation(normalized_message):
            return None
        last_assistant = self._last_assistant_text(history_hint)
        if not last_assistant:
            return None
        if any(token in last_assistant for token in ["senal", "señal", "antes de que escale", "respuesta temprana"]):
            return "prevention_request"
        if any(token in last_assistant for token in ["pendiente", "saturacion", "prioridad", "ansiedad"]):
            return "anxiety_relief_request"
        if any(token in last_assistant for token in ["primer paso", "arranque", "micro", "bloqueo"]):
            return "executive_support_request"
        if any(token in last_assistant for token in ["despues del episodio", "reparar", "cuando ya baje"]):
            return "strategy_feedback"
        return "followup"

    def _is_past_event_prevention_request(self, text: str) -> bool:
        has_past = any(self._contains_phrase(text, token) for token in self.PAST_EVENT_MARKERS)
        has_prevention = any(self._contains_phrase(text, token) for token in ["se repitan", "que no se repita", "evitar", "prevenir", "vuelva a pasar"])
        return has_past and has_prevention

    def route(
        self,
        message: str,
        state_analysis: Optional[Dict[str, Any]] = None,
        category_analysis: Optional[Dict[str, Any]] = None,
        history_hint: Optional[List[Dict[str, Any]]] = None,
        extra_context: Optional[Dict[str, Any]] = None,
        profile: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        state_analysis = state_analysis or {}
        category_analysis = category_analysis or {}
        extra_context = extra_context or {}
        profile = profile or {}

        normalized_message = self._normalize_text(message)
        classic_ml_signal = self._build_classic_ml_signal(message)
        semantic_signal = self._build_semantic_signal(message)

        if any(self._contains_phrase(normalized_message, marker) for marker in self.EXPLICIT_ABOUT_SYSTEM_MARKERS):
            return self._with_signals({
                "detected_intent": "about_system",
                "confidence": 0.95,
                "alternatives": ["general_support", "profile_question"],
                "candidates": [{"intent": "about_system", "score": 0.95, "matched_keywords": ["explicit_about_system"], "priority_rank": self._priority_rank("about_system")}],
                "reasoning": {"message": "La pregunta apunta a identidad, alcance o limites del sistema."},
            }, classic_ml_signal, semantic_signal)

        if any(self._contains_phrase(normalized_message, marker) for marker in self.EXPLICIT_CLARIFICATION_MARKERS):
            return self._with_signals({
                "detected_intent": "clarification_request",
                "confidence": 0.92,
                "alternatives": ["general_support", "followup"],
                "candidates": [{"intent": "clarification_request", "score": 0.92, "matched_keywords": ["explicit_clarification_request"], "priority_rank": self._priority_rank("clarification_request")}],
                "reasoning": {"message": "El usuario pide reformulacion o simplificacion explicita."},
            }, classic_ml_signal, semantic_signal)

        continuation_intent = self._continuation_intent(normalized_message, history_hint)
        if continuation_intent:
            return self._with_signals({
                "detected_intent": continuation_intent,
                "confidence": 0.88 if continuation_intent != "followup" else 0.82,
                "alternatives": ["followup", "general_support"],
                "candidates": [{"intent": continuation_intent, "score": 0.88 if continuation_intent != "followup" else 0.82, "matched_keywords": ["affirmative_continuation"], "priority_rank": self._priority_rank(continuation_intent)}],
                "reasoning": {"message": "Confirmacion breve dentro de un hilo ya activo."},
            }, classic_ml_signal, semantic_signal)

        if self._is_past_event_prevention_request(normalized_message):
            return self._with_signals({
                "detected_intent": "prevention_request",
                "confidence": 0.92,
                "alternatives": ["general_support", "routine_request"],
                "candidates": [{"intent": "prevention_request", "score": 0.92, "matched_keywords": ["past_event_plus_prevention"], "priority_rank": self._priority_rank("prevention_request")}],
                "reasoning": {"message": "Se relata un evento pasado, pero la necesidad actual es preventiva."},
            }, classic_ml_signal, semantic_signal)

        extra_text = self._normalize_text(" ".join([str(extra_context.get("user_extra_context") or ""), str(extra_context.get("context_notes") or ""), str(profile.get("alias") or "")]))
        full_text = " ".join([normalized_message, extra_text]).strip()
        question_density = self._estimate_question_density(message)
        primary_state = self._normalize_text(state_analysis.get("primary_state"))
        detected_category = self._normalize_text(category_analysis.get("detected_category"))

        results: List[Dict[str, Any]] = []
        for intent, rule in self.INTENT_RULES.items():
            matches = self._contains_any(full_text, rule["keywords"])
            score = 0.0
            if matches:
                score += rule["base_score"] + min(len(matches) * 0.08, 0.28)

            has_direct_evidence = bool(matches)
            if not has_direct_evidence and intent == "urgent_support" and detected_category == "crisis_activa" and primary_state in {"meltdown", "shutdown"}:
                score = 0.34
                has_direct_evidence = True

            if has_direct_evidence:
                score += max(rule.get("question_bias", 0.0), -0.06) * ((question_density / 0.22) if question_density else 0.0)

                if intent == "urgent_support" and detected_category == "crisis_activa":
                    score += 0.16
                if intent == "prevention_request" and detected_category == "prevencion_escalada":
                    score += 0.14
                if intent == "anxiety_relief_request" and detected_category == "ansiedad_cognitiva":
                    score += 0.16
                if intent == "executive_support_request" and detected_category == "disfuncion_ejecutiva":
                    score += 0.16
                if intent == "urgent_support" and primary_state in {"meltdown", "shutdown"}:
                    score += 0.12
                if intent == "urgent_support" and self._has_negated_crisis(full_text):
                    score -= 0.85
                if intent == "urgent_support" and any(self._contains_phrase(full_text, token) for token in ["ansiedad", "pendientes", "me abruma pensar", "no dejo de pensar"]):
                    score -= 0.32
                if intent == "anxiety_relief_request" and any(self._contains_phrase(full_text, token) for token in ["no puedo empezar", "me bloqueo", "procrastino"]):
                    score -= 0.08
                if intent == "executive_support_request" and any(self._contains_phrase(full_text, token) for token in ["ataques de ansiedad", "me da ansiedad", "me angustia"]):
                    score -= 0.08

            score = max(min(score, 0.99), 0.0)
            if score > 0:
                results.append({"intent": intent, "score": round(score, 4), "matched_keywords": matches, "priority_rank": self._priority_rank(intent)})

        if not results:
            return self._with_signals({"detected_intent": "general_support", "confidence": 0.25, "alternatives": [], "candidates": [], "reasoning": {"message": "No hubo evidencia fuerte para una intencion especifica."}}, classic_ml_signal, semantic_signal)

        results.sort(key=lambda item: (-item["score"], item["priority_rank"], item["intent"]))
        best = results[0]
        return self._with_signals({
            "detected_intent": best["intent"],
            "confidence": best["score"],
            "alternatives": [item["intent"] for item in results if item["intent"] != best["intent"]][:4],
            "candidates": results[:8],
            "reasoning": {
                "matched_keywords": best.get("matched_keywords", []),
                "primary_state": primary_state or None,
                "detected_category": detected_category or None,
                "question_density": round(question_density, 4),
            },
        }, classic_ml_signal, semantic_signal)


def route_intent(
    message: str,
    state_analysis: Optional[Dict[str, Any]] = None,
    category_analysis: Optional[Dict[str, Any]] = None,
    history_hint: Optional[List[Dict[str, Any]]] = None,
    extra_context: Optional[Dict[str, Any]] = None,
    profile: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    router = IntentRouter()
    return router.route(
        message=message,
        state_analysis=state_analysis,
        category_analysis=category_analysis,
        history_hint=history_hint,
        extra_context=extra_context,
        profile=profile,
        **kwargs,
    )

