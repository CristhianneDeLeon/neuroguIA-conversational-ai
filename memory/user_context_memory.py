from __future__ import annotations

import json
import unicodedata
from datetime import datetime
from typing import Any, Dict, List, Optional

from database.database import NeuroGuiaDB


class UserContextMemory:
    """
    Memoria contextual selectiva para personalizacion en vivo.

    Esta capa no guarda transcripciones completas ni identidad explicita.
    Solo conserva una ficha funcional y breve que puede ayudar a dar
    continuidad entre turnos o sesiones:
    - rol inferido cuando hay evidencia
    - preferencias conversacionales explicitas
    - temas y senales recurrentes
    - estrategias o rutinas que ya mostraron alguna senal razonable
      de utilidad o continuidad

    No modifica reglas, taxonomia ni modelos por si sola.
    """

    MAX_TOPICS = 8
    MAX_SIGNALS = 8
    MAX_STRATEGIES = 6
    MAX_ROUTINES = 4

    CATEGORY_TO_TOPIC = {
        "crisis_activa": "crisis",
        "escalada_emocional": "desregulacion",
        "prevencion_escalada": "prevencion",
        "regulacion_post_evento": "recuperacion",
        "ansiedad_cognitiva": "ansiedad",
        "disfuncion_ejecutiva": "organizacion",
        "sobrecarga_sensorial": "saturacion",
        "transicion_rigidez": "transiciones",
        "sueno_regulacion": "sueno",
        "sobrecarga_cuidador": "cuidado",
        "apoyo_general": "acompanamiento",
    }

    STATE_TO_SIGNAL = {
        "meltdown": "crisis",
        "shutdown": "bloqueo",
        "burnout": "agotamiento",
        "parental_fatigue": "cansancio_cuidador",
        "sensory_overload": "saturacion",
        "executive_dysfunction": "organizacion",
        "sleep_disruption": "sueno",
        "emotional_dysregulation": "desregulacion",
        "cognitive_anxiety": "ansiedad",
        "general_distress": "malestar",
    }

    def __init__(
        self,
        db_path: str = "neuroguia.db",
        backend: Optional[str] = None,
        env_path: str = ".env",
    ) -> None:
        self.db = NeuroGuiaDB(db_path=db_path, backend=backend, env_path=env_path)

    # =========================================================
    # HELPERS
    # =========================================================
    def close(self) -> None:
        self.db.close()

    def _now(self) -> str:
        return datetime.now().isoformat()

    def _normalize_text(self, value: Optional[str]) -> str:
        if not value:
            return ""
        normalized = unicodedata.normalize("NFKD", str(value))
        plain = "".join(char for char in normalized if not unicodedata.combining(char))
        return " ".join(plain.strip().lower().split())

    def _json_dump(self, value: Any, default: Any) -> str:
        return json.dumps(value if value is not None else default, ensure_ascii=False)

    def _json_load(self, value: Any, default: Any) -> Any:
        if value is None or value == "":
            return default
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(value)
        except Exception:
            return default

    def _dedupe(self, items: List[Any], limit: int) -> List[Any]:
        result: List[Any] = []
        seen = set()
        for item in items:
            if item is None:
                continue
            if isinstance(item, str):
                key = self._normalize_text(item)
                value = item.strip()
                if not key:
                    continue
            else:
                key = json.dumps(item, sort_keys=True, ensure_ascii=False)
                value = item
            if key in seen:
                continue
            seen.add(key)
            result.append(value)
            if len(result) >= limit:
                break
        return result

    def _candidate_scopes(
        self,
        profile_id: Optional[str] = None,
        family_id: Optional[str] = None,
        session_scope_id: Optional[str] = None,
    ) -> List[Dict[str, Optional[str]]]:
        scopes: List[Dict[str, Optional[str]]] = []

        if profile_id:
            scopes.append(
                {
                    "scope_key": f"profile:{profile_id}",
                    "scope_type": "profile",
                    "profile_id": profile_id,
                    "family_id": family_id,
                    "session_scope_id": session_scope_id,
                }
            )

        if family_id:
            scopes.append(
                {
                    "scope_key": f"family:{family_id}",
                    "scope_type": "family",
                    "profile_id": profile_id,
                    "family_id": family_id,
                    "session_scope_id": session_scope_id,
                }
            )

        if session_scope_id:
            scopes.append(
                {
                    "scope_key": f"session:{session_scope_id}",
                    "scope_type": "session",
                    "profile_id": profile_id,
                    "family_id": family_id,
                    "session_scope_id": session_scope_id,
                }
            )

        return scopes

    def _fetch_scope_row(self, scope_key: str) -> Optional[Dict[str, Any]]:
        row = self.db.execute(
            "SELECT * FROM user_context_memory WHERE scope_key = ? LIMIT 1",
            (scope_key,),
            fetch_one=True,
        )
        if not row:
            return None
        return self._normalize_row(row)

    def _normalize_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        data = dict(row)
        data["conversation_preferences"] = self._json_load(data.get("conversation_preferences_json"), {})
        data["recurrent_topics"] = self._json_load(data.get("recurrent_topics_json"), [])
        data["recurrent_signals"] = self._json_load(data.get("recurrent_signals_json"), [])
        data["helpful_strategies"] = self._json_load(data.get("helpful_strategies_json"), [])
        data["helpful_routines"] = self._json_load(data.get("helpful_routines_json"), [])
        data["summary_snapshot"] = self._json_load(data.get("summary_snapshot_json"), {})
        return data

    def _infer_user_role(
        self,
        source_message: str,
        conversation_frame: Dict[str, Any],
        extra_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        explicit_role = self._normalize_text(extra_context.get("speaker_role"))
        if explicit_role:
            return {"role": explicit_role, "confidence": 0.95, "source": "extra_context"}

        msg = self._normalize_text(source_message)

        caregiver_tokens = [
            "mi hijo",
            "mi hija",
            "mi nino",
            "mi nina",
            "mi adolescente",
            "como mama",
            "como papa",
            "como cuidador",
            "como cuidadora",
        ]
        if any(token in msg for token in caregiver_tokens):
            return {"role": "cuidador", "confidence": 0.86, "source": "message_inference"}

        teacher_tokens = [
            "soy docente",
            "como docente",
            "en mi aula",
            "en el salon",
            "en el salón",
            "mi alumno",
            "mi alumna",
        ]
        if any(token in msg for token in teacher_tokens):
            return {"role": "docente", "confidence": 0.88, "source": "message_inference"}

        direct_user_tokens = [
            "me siento",
            "me pasa",
            "no puedo",
            "necesito ayuda",
            "quiero entender",
            "estoy muy",
            "me cuesta",
        ]
        if any(token in msg for token in direct_user_tokens):
            return {"role": "usuario", "confidence": 0.68, "source": "message_inference"}

        frame_role = self._normalize_text(conversation_frame.get("speaker_role"))
        if frame_role in {"cuidador", "docente"}:
            return {"role": frame_role, "confidence": 0.72, "source": "conversation_frame"}

        return {"role": "indefinido", "confidence": 0.0, "source": "insufficient_evidence"}

    def _extract_preferences(self, source_message: str) -> Dict[str, Any]:
        msg = self._normalize_text(source_message)
        preferences: Dict[str, Any] = {}

        if any(token in msg for token in ["paso a paso", "poco a poco", "despacio"]):
            preferences["pace"] = "paso_a_paso"

        if any(token in msg for token in ["breve", "corto", "sin mucho texto", "solo una cosa", "directo"]):
            preferences["preferred_length"] = "breve"

        if any(token in msg for token in ["claro", "simple", "concreto", "sin vueltas"]):
            preferences["preferred_style"] = "claro"

        if any(token in msg for token in ["acompaname", "acompaniame", "escuchame", "escuchame un poco", "validame"]):
            preferences["needs_validation"] = True

        return preferences

    def _extract_topics(
        self,
        source_message: str,
        conversation_frame: Dict[str, Any],
        category_analysis: Dict[str, Any],
        intent_analysis: Dict[str, Any],
    ) -> List[str]:
        topics: List[str] = []

        category = category_analysis.get("detected_category")
        domain = conversation_frame.get("conversation_domain")
        intent = self._normalize_text(intent_analysis.get("detected_intent"))
        msg = self._normalize_text(source_message)

        if category in self.CATEGORY_TO_TOPIC:
            topics.append(self.CATEGORY_TO_TOPIC[category])
        if domain in self.CATEGORY_TO_TOPIC:
            topics.append(self.CATEGORY_TO_TOPIC[domain])

        if "routine" in intent:
            topics.append("rutinas")
        if "followup" in intent or "feedback" in intent:
            topics.append("seguimiento")

        keyword_map = {
            "sueno": ["sueno", "dormir", "insomnio", "desvelo"],
            "ansiedad": ["ansiedad", "me abruma", "me abruma", "nerviosa", "nervioso"],
            "organizacion": ["organizar", "pendientes", "empezar", "bloqueada", "bloqueado"],
            "saturacion": ["saturada", "saturado", "ruido", "sobrecarga", "sensorial"],
            "crisis": ["crisis", "exploto", "estallo", "desborde"],
            "transiciones": ["transicion", "cambio", "anticipar", "cambiar"],
        }
        for label, tokens in keyword_map.items():
            if any(token in msg for token in tokens):
                topics.append(label)

        return self._dedupe(topics, self.MAX_TOPICS)

    def _extract_signals(
        self,
        state_analysis: Dict[str, Any],
        category_analysis: Dict[str, Any],
    ) -> List[str]:
        signals: List[str] = []

        primary_state = state_analysis.get("primary_state")
        secondary_states = state_analysis.get("secondary_states", []) or []
        category = category_analysis.get("detected_category")

        if primary_state in self.STATE_TO_SIGNAL:
            signals.append(self.STATE_TO_SIGNAL[primary_state])

        for state in secondary_states:
            if state in self.STATE_TO_SIGNAL:
                signals.append(self.STATE_TO_SIGNAL[state])

        if category in self.CATEGORY_TO_TOPIC:
            signals.append(self.CATEGORY_TO_TOPIC[category])

        return self._dedupe(signals, self.MAX_SIGNALS)

    def _has_useful_outcome_signal(
        self,
        conversation_frame: Dict[str, Any],
        confidence_payload: Dict[str, Any],
        memory_payload: Dict[str, Any],
        response_memory_payload: Dict[str, Any],
        llm_curated_payload: Dict[str, Any],
    ) -> bool:
        continuity_score = float(conversation_frame.get("continuity_score", 0.0) or 0.0)
        overall_confidence = float(confidence_payload.get("overall_confidence", 0.0) or 0.0)
        reuse_confidence = float(response_memory_payload.get("reuse_confidence", 0.0) or 0.0)
        avg_usefulness = float(memory_payload.get("average_usefulness_in_similar_cases", 0.0) or 0.0)
        curated_quality = float(llm_curated_payload.get("quality_score", 0.0) or 0.0)

        return any(
            [
                bool(llm_curated_payload.get("approved")),
                continuity_score >= 0.86,
                reuse_confidence >= 0.72,
                avg_usefulness >= 0.62,
                overall_confidence >= 0.74,
                curated_quality >= 0.70,
            ]
        )

    def _select_helpful_items(
        self,
        decision_payload: Dict[str, Any],
        conversation_frame: Dict[str, Any],
        confidence_payload: Dict[str, Any],
        memory_payload: Dict[str, Any],
        response_memory_payload: Dict[str, Any],
        llm_curated_payload: Dict[str, Any],
    ) -> Dict[str, List[str]]:
        helpful_strategies: List[str] = []
        helpful_routines: List[str] = []

        if self._has_useful_outcome_signal(
            conversation_frame=conversation_frame,
            confidence_payload=confidence_payload,
            memory_payload=memory_payload,
            response_memory_payload=response_memory_payload,
            llm_curated_payload=llm_curated_payload,
        ):
            selected_strategy = decision_payload.get("selected_strategy")
            selected_routine = decision_payload.get("selected_routine_type")

            if selected_strategy:
                helpful_strategies.append(str(selected_strategy))
            if selected_routine:
                helpful_routines.append(str(selected_routine))

        return {
            "helpful_strategies": self._dedupe(helpful_strategies, self.MAX_STRATEGIES),
            "helpful_routines": self._dedupe(helpful_routines, self.MAX_ROUTINES),
        }

    def _build_summary_snapshot(
        self,
        role_info: Dict[str, Any],
        conversation_frame: Dict[str, Any],
        category_analysis: Dict[str, Any],
        intent_analysis: Dict[str, Any],
        signals: List[str],
        helpful_items: Dict[str, List[str]],
    ) -> Dict[str, Any]:
        snapshot = {
            "role": role_info.get("role") if role_info.get("role") != "indefinido" else None,
            "current_focus": (
                intent_analysis.get("detected_intent")
                or category_analysis.get("detected_category")
                or conversation_frame.get("conversation_domain")
            ),
            "main_domain": conversation_frame.get("conversation_domain"),
            "last_phase": conversation_frame.get("conversation_phase"),
            "signals": list(signals[:3]),
            "helpful_strategies": list(helpful_items.get("helpful_strategies", [])[:2]),
            "helpful_routines": list(helpful_items.get("helpful_routines", [])[:2]),
        }
        return {key: value for key, value in snapshot.items() if value not in (None, [], {}, "")}

    def _build_candidate_payload(
        self,
        source_message: str,
        extra_context: Dict[str, Any],
        conversation_frame: Dict[str, Any],
        category_analysis: Dict[str, Any],
        intent_analysis: Dict[str, Any],
        state_analysis: Dict[str, Any],
        confidence_payload: Dict[str, Any],
        decision_payload: Dict[str, Any],
        memory_payload: Dict[str, Any],
        response_memory_payload: Dict[str, Any],
        llm_curated_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        role_info = self._infer_user_role(
            source_message=source_message,
            conversation_frame=conversation_frame,
            extra_context=extra_context,
        )
        preferences = self._extract_preferences(source_message)
        topics = self._extract_topics(
            source_message=source_message,
            conversation_frame=conversation_frame,
            category_analysis=category_analysis,
            intent_analysis=intent_analysis,
        )
        signals = self._extract_signals(
            state_analysis=state_analysis,
            category_analysis=category_analysis,
        )
        helpful_items = self._select_helpful_items(
            decision_payload=decision_payload,
            conversation_frame=conversation_frame,
            confidence_payload=confidence_payload,
            memory_payload=memory_payload,
            response_memory_payload=response_memory_payload,
            llm_curated_payload=llm_curated_payload,
        )

        useful_turn = self._has_useful_outcome_signal(
            conversation_frame=conversation_frame,
            confidence_payload=confidence_payload,
            memory_payload=memory_payload,
            response_memory_payload=response_memory_payload,
            llm_curated_payload=llm_curated_payload,
        )

        return {
            "inferred_user_role": role_info.get("role", "indefinido"),
            "role_confidence": round(float(role_info.get("confidence", 0.0) or 0.0), 4),
            "role_source": role_info.get("source"),
            "conversation_preferences": preferences,
            "recurrent_topics": topics,
            "recurrent_signals": signals,
            "helpful_strategies": helpful_items.get("helpful_strategies", []),
            "helpful_routines": helpful_items.get("helpful_routines", []),
            "last_useful_domain": conversation_frame.get("conversation_domain") if useful_turn else None,
            "last_useful_phase": conversation_frame.get("conversation_phase") if useful_turn else None,
            "summary_snapshot": self._build_summary_snapshot(
                role_info=role_info,
                conversation_frame=conversation_frame,
                category_analysis=category_analysis,
                intent_analysis=intent_analysis,
                signals=signals,
                helpful_items=helpful_items,
            ),
        }

    def _is_candidate_meaningful(self, candidate: Dict[str, Any]) -> bool:
        return any(
            [
                candidate.get("inferred_user_role") not in (None, "", "indefinido"),
                bool(candidate.get("conversation_preferences")),
                bool(candidate.get("recurrent_topics")),
                bool(candidate.get("recurrent_signals")),
                bool(candidate.get("helpful_strategies")),
                bool(candidate.get("helpful_routines")),
                bool(candidate.get("last_useful_domain")),
                bool(candidate.get("last_useful_phase")),
            ]
        )

    def _merge_with_existing(
        self,
        existing: Optional[Dict[str, Any]],
        candidate: Dict[str, Any],
    ) -> Dict[str, Any]:
        existing = existing or {}
        current_role = existing.get("inferred_user_role") or "indefinido"
        current_role_confidence = float(existing.get("role_confidence", 0.0) or 0.0)

        candidate_role = candidate.get("inferred_user_role") or "indefinido"
        candidate_role_confidence = float(candidate.get("role_confidence", 0.0) or 0.0)

        if candidate_role != "indefinido" and candidate_role_confidence >= current_role_confidence:
            merged_role = candidate_role
            merged_role_confidence = candidate_role_confidence
            role_source = candidate.get("role_source")
        else:
            merged_role = current_role
            merged_role_confidence = current_role_confidence
            role_source = existing.get("role_source")

        merged = {
            "inferred_user_role": merged_role,
            "role_confidence": round(merged_role_confidence, 4),
            "role_source": role_source,
            "conversation_preferences": {
                **(existing.get("conversation_preferences") or {}),
                **(candidate.get("conversation_preferences") or {}),
            },
            "recurrent_topics": self._dedupe(
                list(candidate.get("recurrent_topics", [])) + list(existing.get("recurrent_topics", [])),
                self.MAX_TOPICS,
            ),
            "recurrent_signals": self._dedupe(
                list(candidate.get("recurrent_signals", [])) + list(existing.get("recurrent_signals", [])),
                self.MAX_SIGNALS,
            ),
            "helpful_strategies": self._dedupe(
                list(candidate.get("helpful_strategies", [])) + list(existing.get("helpful_strategies", [])),
                self.MAX_STRATEGIES,
            ),
            "helpful_routines": self._dedupe(
                list(candidate.get("helpful_routines", [])) + list(existing.get("helpful_routines", [])),
                self.MAX_ROUTINES,
            ),
            "last_useful_domain": candidate.get("last_useful_domain") or existing.get("last_useful_domain"),
            "last_useful_phase": candidate.get("last_useful_phase") or existing.get("last_useful_phase"),
            "summary_snapshot": candidate.get("summary_snapshot") or existing.get("summary_snapshot") or {},
        }
        return merged

    def _same_effective_payload(
        self,
        existing: Optional[Dict[str, Any]],
        merged: Dict[str, Any],
    ) -> bool:
        if not existing:
            return False

        comparable_existing = {
            "inferred_user_role": existing.get("inferred_user_role"),
            "role_confidence": round(float(existing.get("role_confidence", 0.0) or 0.0), 4),
            "role_source": existing.get("role_source"),
            "conversation_preferences": existing.get("conversation_preferences") or {},
            "recurrent_topics": existing.get("recurrent_topics") or [],
            "recurrent_signals": existing.get("recurrent_signals") or [],
            "helpful_strategies": existing.get("helpful_strategies") or [],
            "helpful_routines": existing.get("helpful_routines") or [],
            "last_useful_domain": existing.get("last_useful_domain"),
            "last_useful_phase": existing.get("last_useful_phase"),
            "summary_snapshot": existing.get("summary_snapshot") or {},
        }
        return comparable_existing == merged

    def _upsert_scope(
        self,
        scope: Dict[str, Optional[str]],
        payload: Dict[str, Any],
        source_case_id: Optional[str],
    ) -> None:
        now = self._now()
        self.db.execute(
            """
            INSERT INTO user_context_memory (
                scope_key,
                scope_type,
                family_id,
                profile_id,
                session_scope_id,
                inferred_user_role,
                role_confidence,
                role_source,
                conversation_preferences_json,
                recurrent_topics_json,
                recurrent_signals_json,
                helpful_strategies_json,
                helpful_routines_json,
                last_useful_domain,
                last_useful_phase,
                summary_snapshot_json,
                source_case_id,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(scope_key) DO UPDATE SET
                scope_type = excluded.scope_type,
                family_id = excluded.family_id,
                profile_id = excluded.profile_id,
                session_scope_id = excluded.session_scope_id,
                inferred_user_role = excluded.inferred_user_role,
                role_confidence = excluded.role_confidence,
                role_source = excluded.role_source,
                conversation_preferences_json = excluded.conversation_preferences_json,
                recurrent_topics_json = excluded.recurrent_topics_json,
                recurrent_signals_json = excluded.recurrent_signals_json,
                helpful_strategies_json = excluded.helpful_strategies_json,
                helpful_routines_json = excluded.helpful_routines_json,
                last_useful_domain = excluded.last_useful_domain,
                last_useful_phase = excluded.last_useful_phase,
                summary_snapshot_json = excluded.summary_snapshot_json,
                source_case_id = excluded.source_case_id,
                updated_at = excluded.updated_at
            """,
            (
                scope.get("scope_key"),
                scope.get("scope_type"),
                scope.get("family_id"),
                scope.get("profile_id"),
                scope.get("session_scope_id"),
                payload.get("inferred_user_role"),
                payload.get("role_confidence"),
                payload.get("role_source"),
                self._json_dump(payload.get("conversation_preferences"), {}),
                self._json_dump(payload.get("recurrent_topics"), []),
                self._json_dump(payload.get("recurrent_signals"), []),
                self._json_dump(payload.get("helpful_strategies"), []),
                self._json_dump(payload.get("helpful_routines"), []),
                payload.get("last_useful_domain"),
                payload.get("last_useful_phase"),
                self._json_dump(payload.get("summary_snapshot"), {}),
                source_case_id,
                now,
                now,
            ),
        )

    # =========================================================
    # API PUBLICA
    # =========================================================
    def build_live_context_payload(
        self,
        profile_id: Optional[str] = None,
        family_id: Optional[str] = None,
        session_scope_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        scopes = self._candidate_scopes(
            profile_id=profile_id,
            family_id=family_id,
            session_scope_id=session_scope_id,
        )

        for scope in scopes:
            row = self._fetch_scope_row(str(scope.get("scope_key") or ""))
            if not row:
                continue
            return {
                "available": True,
                "scope_key": row.get("scope_key"),
                "scope_type": row.get("scope_type"),
                "inferred_user_role": row.get("inferred_user_role") or "indefinido",
                "role_confidence": float(row.get("role_confidence", 0.0) or 0.0),
                "conversation_preferences": row.get("conversation_preferences") or {},
                "recurrent_topics": row.get("recurrent_topics") or [],
                "recurrent_signals": row.get("recurrent_signals") or [],
                "helpful_strategies": row.get("helpful_strategies") or [],
                "helpful_routines": row.get("helpful_routines") or [],
                "last_useful_domain": row.get("last_useful_domain"),
                "last_useful_phase": row.get("last_useful_phase"),
                "summary_snapshot": row.get("summary_snapshot") or {},
                "updated_at": row.get("updated_at"),
            }

        return {
            "available": False,
            "scope_key": scopes[0]["scope_key"] if scopes else None,
            "scope_type": scopes[0]["scope_type"] if scopes else None,
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

    def register_turn_context(
        self,
        source_message: str,
        family_id: Optional[str] = None,
        profile_id: Optional[str] = None,
        session_scope_id: Optional[str] = None,
        extra_context: Optional[Dict[str, Any]] = None,
        conversation_frame: Optional[Dict[str, Any]] = None,
        category_analysis: Optional[Dict[str, Any]] = None,
        intent_analysis: Optional[Dict[str, Any]] = None,
        state_analysis: Optional[Dict[str, Any]] = None,
        confidence_payload: Optional[Dict[str, Any]] = None,
        decision_payload: Optional[Dict[str, Any]] = None,
        memory_payload: Optional[Dict[str, Any]] = None,
        response_memory_payload: Optional[Dict[str, Any]] = None,
        llm_curated_payload: Optional[Dict[str, Any]] = None,
        source_case_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        scopes = self._candidate_scopes(
            profile_id=profile_id,
            family_id=family_id,
            session_scope_id=session_scope_id,
        )
        if not scopes:
            return {"stored": False, "reason": "no_scope_available", "payload": None}

        scope = scopes[0]
        existing = self._fetch_scope_row(str(scope.get("scope_key") or ""))

        candidate = self._build_candidate_payload(
            source_message=source_message,
            extra_context=extra_context or {},
            conversation_frame=conversation_frame or {},
            category_analysis=category_analysis or {},
            intent_analysis=intent_analysis or {},
            state_analysis=state_analysis or {},
            confidence_payload=confidence_payload or {},
            decision_payload=decision_payload or {},
            memory_payload=memory_payload or {},
            response_memory_payload=response_memory_payload or {},
            llm_curated_payload=llm_curated_payload or {},
        )

        if not self._is_candidate_meaningful(candidate):
            return {"stored": False, "reason": "no_useful_context_detected", "payload": candidate}

        merged = self._merge_with_existing(existing=existing, candidate=candidate)
        if self._same_effective_payload(existing=existing, merged=merged):
            return {"stored": False, "reason": "no_meaningful_change", "payload": merged}

        self._upsert_scope(scope=scope, payload=merged, source_case_id=source_case_id)
        return {
            "stored": True,
            "reason": "context_memory_updated",
            "scope_key": scope.get("scope_key"),
            "scope_type": scope.get("scope_type"),
            "payload": merged,
        }
