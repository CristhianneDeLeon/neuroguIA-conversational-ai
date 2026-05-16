from __future__ import annotations

import hashlib
import json
import unicodedata
from datetime import datetime
from typing import Any, Dict, List, Optional

from database.database import NeuroGuiaDB


class ConversationCuration:
    """
    Registro supervisado de conversaciones valiosas.

    Esta capa NO aprende en vivo ni altera automaticamente prompts,
    anchors o reglas. Su funcion es dejar una cola de material util para
    revision humana posterior:
    - interacciones con buena senal de valor
    - metadatos de generacion y fallback
    - resumen funcional del turno
    - etiquetas para futura revision

    Las marcas como "util", "revisar" o "candidata a prompt" quedan
    registradas, pero su promocion a cambios reales debe hacerse fuera
    del flujo en vivo.
    """

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

    def _dedupe(self, items: List[str], limit: int = 8) -> List[str]:
        result: List[str] = []
        seen = set()
        for item in items:
            key = self._normalize_text(item)
            if not key or key in seen:
                continue
            seen.add(key)
            result.append(item.strip())
            if len(result) >= limit:
                break
        return result

    def _build_topics(
        self,
        message: str,
        category_analysis: Dict[str, Any],
        conversation_frame: Dict[str, Any],
    ) -> List[str]:
        topics: List[str] = []
        category = category_analysis.get("detected_category")
        domain = conversation_frame.get("conversation_domain")
        msg = self._normalize_text(message)

        if category in self.CATEGORY_TO_TOPIC:
            topics.append(self.CATEGORY_TO_TOPIC[category])
        if domain in self.CATEGORY_TO_TOPIC:
            topics.append(self.CATEGORY_TO_TOPIC[domain])

        keyword_map = {
            "crisis": ["crisis", "estallo", "exploto"],
            "ansiedad": ["ansiedad", "me abruma", "nerviosa", "nervioso"],
            "organizacion": ["organizar", "pendientes", "empezar"],
            "sueno": ["sueno", "insomnio", "desvelo", "dormir"],
            "saturacion": ["ruido", "sensorial", "sobrecarga", "saturada", "saturado"],
        }
        for label, tokens in keyword_map.items():
            if any(token in msg for token in tokens):
                topics.append(label)

        return self._dedupe(topics, limit=6)

    def _build_input_summary(
        self,
        source_message: str,
        conversation_frame: Dict[str, Any],
        category_analysis: Dict[str, Any],
        intent_analysis: Dict[str, Any],
        state_analysis: Dict[str, Any],
    ) -> Dict[str, Any]:
        normalized = self._normalize_text(source_message)
        length_bucket = "short"
        if len(normalized) >= 180:
            length_bucket = "long"
        elif len(normalized) >= 70:
            length_bucket = "medium"

        return {
            "focus": (
                intent_analysis.get("detected_intent")
                or category_analysis.get("detected_category")
                or conversation_frame.get("conversation_domain")
            ),
            "topics": self._build_topics(
                message=source_message,
                category_analysis=category_analysis,
                conversation_frame=conversation_frame,
            ),
            "speaker_role": conversation_frame.get("speaker_role") or "indefinido",
            "primary_state": state_analysis.get("primary_state"),
            "message_length": length_bucket,
        }

    def _build_signal_summary(
        self,
        category_analysis: Dict[str, Any],
        intent_analysis: Dict[str, Any],
        state_analysis: Dict[str, Any],
        confidence_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        category_ml = category_analysis.get("classic_ml_signal", {}) or {}
        category_semantic = category_analysis.get("semantic_signal", {}) or {}
        intent_ml = intent_analysis.get("classic_ml_signal", {}) or {}
        intent_semantic = intent_analysis.get("semantic_signal", {}) or {}

        return {
            "category_confidence": category_analysis.get("confidence"),
            "intent_confidence": intent_analysis.get("confidence"),
            "overall_confidence": confidence_payload.get("overall_confidence"),
            "primary_state": state_analysis.get("primary_state"),
            "secondary_states": (state_analysis.get("secondary_states", []) or [])[:3],
            "classic_category_label": category_ml.get("predicted_label"),
            "classic_category_confidence": category_ml.get("confidence"),
            "semantic_category_label": category_semantic.get("predicted_label"),
            "semantic_category_similarity": category_semantic.get("similarity"),
            "classic_intent_label": intent_ml.get("predicted_label"),
            "classic_intent_confidence": intent_ml.get("confidence"),
            "semantic_intent_label": intent_semantic.get("predicted_label"),
            "semantic_intent_similarity": intent_semantic.get("similarity"),
        }

    def _build_generation_source(
        self,
        response_package: Dict[str, Any],
        llm_result: Dict[str, Any],
    ) -> str:
        mode = str(response_package.get("mode") or "").strip()
        provider = str(llm_result.get("provider") or "").strip()
        used_stub_fallback = bool(llm_result.get("used_stub_fallback", False))

        if mode == "reuse_response_memory":
            return "response_memory_reuse"
        if mode == "system_generated":
            return "system_generated_local"
        if provider == "openai" and not used_stub_fallback:
            return "openai"
        if provider == "stub_local" and bool(llm_result.get("llm_enabled")):
            return "openai_stub_fallback"
        if provider == "stub_local":
            return "stub_local"
        return provider or mode or "unknown"

    def _should_store_curation(
        self,
        response_package: Dict[str, Any],
        category_analysis: Dict[str, Any],
        confidence_payload: Dict[str, Any],
        response_memory_payload: Dict[str, Any],
        llm_curated_payload: Dict[str, Any],
        decision_payload: Dict[str, Any],
    ) -> bool:
        response_text = str(
            response_package.get("response")
            or response_package.get("text")
            or ""
        ).strip()
        if len(response_text) < 50:
            return False

        category = category_analysis.get("detected_category")
        overall_confidence = float(confidence_payload.get("overall_confidence", 0.0) or 0.0)
        reuse_confidence = float(response_memory_payload.get("reuse_confidence", 0.0) or 0.0)
        quality_score = float(llm_curated_payload.get("quality_score", 0.0) or 0.0)

        return any(
            [
                bool(llm_curated_payload.get("approved")) and quality_score >= 0.68,
                response_package.get("mode") == "reuse_response_memory" and reuse_confidence >= 0.72,
                bool(decision_payload.get("selected_routine_type"))
                and overall_confidence >= 0.70
                and category not in {None, "", "apoyo_general"},
                overall_confidence >= 0.76 and category not in {None, "", "apoyo_general"},
            ]
        )

    def _build_dedupe_key(
        self,
        scope_key: str,
        input_summary: Dict[str, Any],
        detected_category: Optional[str],
        response_text: str,
        generation_source: str,
    ) -> str:
        raw = "||".join(
            [
                scope_key,
                json.dumps(input_summary, sort_keys=True, ensure_ascii=False),
                str(detected_category or ""),
                self._normalize_text(response_text)[:220],
                generation_source,
            ]
        )
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    def _dedupe_exists(self, dedupe_key: str) -> bool:
        row = self.db.execute(
            "SELECT curation_id FROM conversation_curation WHERE dedupe_key = ? LIMIT 1",
            (dedupe_key,),
            fetch_one=True,
        )
        return bool(row)

    def _normalize_entry(self, row: Dict[str, Any]) -> Dict[str, Any]:
        data = dict(row)
        data["candidate_targets"] = self._json_load(data.get("candidate_targets_json"), [])
        data["input_summary"] = self._json_load(data.get("input_summary_json"), {})
        data["secondary_states"] = self._json_load(data.get("secondary_states_json"), [])
        data["signal_summary"] = self._json_load(data.get("signal_summary_json"), {})
        data["response_structure"] = self._json_load(data.get("response_structure_json"), {})
        data["metadata"] = self._json_load(data.get("metadata_json"), {})
        data["used_stub_fallback"] = bool(data.get("used_stub_fallback"))
        data["llm_enabled"] = bool(data.get("llm_enabled"))
        data["llm_approved"] = bool(data.get("llm_approved"))
        return data

    # =========================================================
    # API PUBLICA
    # =========================================================
    def register_curatable_turn(
        self,
        source_message: str,
        family_id: Optional[str] = None,
        profile_id: Optional[str] = None,
        session_scope_id: Optional[str] = None,
        source_case_id: Optional[str] = None,
        conversation_frame: Optional[Dict[str, Any]] = None,
        category_analysis: Optional[Dict[str, Any]] = None,
        intent_analysis: Optional[Dict[str, Any]] = None,
        state_analysis: Optional[Dict[str, Any]] = None,
        confidence_payload: Optional[Dict[str, Any]] = None,
        decision_payload: Optional[Dict[str, Any]] = None,
        stage_result: Optional[Dict[str, Any]] = None,
        response_package: Optional[Dict[str, Any]] = None,
        response_memory_payload: Optional[Dict[str, Any]] = None,
        llm_result: Optional[Dict[str, Any]] = None,
        llm_curated_payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        scopes = self._candidate_scopes(
            profile_id=profile_id,
            family_id=family_id,
            session_scope_id=session_scope_id,
        )
        if not scopes:
            return {"stored": False, "reason": "no_scope_available", "curation_id": None}

        conversation_frame = conversation_frame or {}
        category_analysis = category_analysis or {}
        intent_analysis = intent_analysis or {}
        state_analysis = state_analysis or {}
        confidence_payload = confidence_payload or {}
        decision_payload = decision_payload or {}
        stage_result = stage_result or {}
        response_package = response_package or {}
        response_memory_payload = response_memory_payload or {}
        llm_result = llm_result or {}
        llm_curated_payload = llm_curated_payload or {}

        if not self._should_store_curation(
            response_package=response_package,
            category_analysis=category_analysis,
            confidence_payload=confidence_payload,
            response_memory_payload=response_memory_payload,
            llm_curated_payload=llm_curated_payload,
            decision_payload=decision_payload,
        ):
            return {"stored": False, "reason": "turn_not_curatable", "curation_id": None}

        scope = scopes[0]
        response_text = str(
            response_package.get("response")
            or response_package.get("text")
            or ""
        ).strip()
        generation_source = self._build_generation_source(
            response_package=response_package,
            llm_result=llm_result,
        )
        input_summary = self._build_input_summary(
            source_message=source_message,
            conversation_frame=conversation_frame,
            category_analysis=category_analysis,
            intent_analysis=intent_analysis,
            state_analysis=state_analysis,
        )
        dedupe_key = self._build_dedupe_key(
            scope_key=str(scope.get("scope_key") or ""),
            input_summary=input_summary,
            detected_category=category_analysis.get("detected_category"),
            response_text=response_text,
            generation_source=generation_source,
        )
        if self._dedupe_exists(dedupe_key):
            return {"stored": False, "reason": "duplicate_curated_turn", "curation_id": None}

        now = self._now()
        curation_id = hashlib.sha1(f"{dedupe_key}|{now}".encode("utf-8")).hexdigest()[:24]
        response_structure = (
            llm_curated_payload.get("curated_response_structure")
            or response_package.get("response_structure")
            or response_package.get("response_metadata")
            or {}
        )

        self.db.execute(
            """
            INSERT INTO conversation_curation (
                curation_id,
                dedupe_key,
                scope_key,
                scope_type,
                family_id,
                profile_id,
                session_scope_id,
                source_case_id,
                review_status,
                candidate_targets_json,
                review_notes,
                input_summary_json,
                detected_category,
                detected_intent,
                primary_state,
                secondary_states_json,
                conversation_domain,
                conversation_phase,
                speaker_role,
                signal_summary_json,
                response_text,
                response_structure_json,
                response_mode,
                generation_source,
                provider,
                model,
                used_stub_fallback,
                fallback_reason,
                llm_enabled,
                llm_quality_score,
                llm_approved,
                metadata_json,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                curation_id,
                dedupe_key,
                scope.get("scope_key"),
                scope.get("scope_type"),
                scope.get("family_id"),
                scope.get("profile_id"),
                scope.get("session_scope_id"),
                source_case_id,
                "revisar",
                self._json_dump([], []),
                None,
                self._json_dump(input_summary, {}),
                category_analysis.get("detected_category"),
                intent_analysis.get("detected_intent"),
                state_analysis.get("primary_state"),
                self._json_dump(state_analysis.get("secondary_states", []) or [], []),
                conversation_frame.get("conversation_domain"),
                conversation_frame.get("conversation_phase"),
                conversation_frame.get("speaker_role") or "indefinido",
                self._json_dump(
                    self._build_signal_summary(
                        category_analysis=category_analysis,
                        intent_analysis=intent_analysis,
                        state_analysis=state_analysis,
                        confidence_payload=confidence_payload,
                    ),
                    {},
                ),
                response_text,
                self._json_dump(response_structure, {}),
                response_package.get("mode"),
                generation_source,
                llm_result.get("provider"),
                llm_result.get("model"),
                1 if bool(llm_result.get("used_stub_fallback", False)) else 0,
                llm_result.get("fallback_reason"),
                1 if bool(llm_result.get("llm_enabled", False)) else 0,
                float(llm_curated_payload.get("quality_score", 0.0) or 0.0),
                1 if bool(llm_curated_payload.get("approved", False)) else 0,
                self._json_dump(
                    {
                        "stage": stage_result.get("stage"),
                        "decision_mode": decision_payload.get("decision_mode"),
                        "selected_strategy": decision_payload.get("selected_strategy"),
                        "selected_microaction": decision_payload.get("selected_microaction"),
                        "selected_routine_type": decision_payload.get("selected_routine_type"),
                        "stored_from_turn": True,
                    },
                    {},
                ),
                now,
                now,
            ),
        )

        return {
            "stored": True,
            "reason": "curated_turn_registered",
            "curation_id": curation_id,
            "generation_source": generation_source,
        }

    def list_entries(
        self,
        review_status: Optional[str] = None,
        limit: int = 30,
    ) -> List[Dict[str, Any]]:
        query = "SELECT * FROM conversation_curation"
        params: List[Any] = []
        if review_status:
            query += " WHERE review_status = ?"
            params.append(review_status)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = self.db.execute(query, tuple(params), fetch=True) or []
        return [self._normalize_entry(row) for row in rows if row]

    def mark_entry(
        self,
        curation_id: str,
        review_status: Optional[str] = None,
        candidate_targets: Optional[List[str]] = None,
        review_notes: Optional[str] = None,
    ) -> bool:
        updates: List[str] = []
        params: List[Any] = []

        if review_status is not None:
            updates.append("review_status = ?")
            params.append(review_status)

        if candidate_targets is not None:
            updates.append("candidate_targets_json = ?")
            params.append(self._json_dump(candidate_targets, []))

        if review_notes is not None:
            updates.append("review_notes = ?")
            params.append(review_notes)

        if not updates:
            return False

        updates.append("updated_at = ?")
        params.append(self._now())
        params.append(curation_id)

        query = f"""
        UPDATE conversation_curation
        SET {", ".join(updates)}
        WHERE curation_id = ?
        """
        self.db.execute(query, tuple(params))
        return True
