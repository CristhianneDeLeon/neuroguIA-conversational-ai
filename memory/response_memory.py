from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from database.database import NeuroGuiaDB


class ResponseMemory:
    """
    Memoria de respuestas reutilizables para NeuroGuIA.

    Compatible con:
    - create_from_system_response(...)
    - create_from_llm_fallback(...)
    - create_response(...)
    - build_reuse_payload(...)
    - register_response_outcome(...)
    """

    def __init__(
        self,
        db_path: str = "neuroguia.db",
        backend: Optional[str] = None,
        env_path: str = ".env",
    ) -> None:
        self.db = NeuroGuiaDB(db_path=db_path, backend=backend, env_path=env_path)
        self.backend_name = getattr(self.db, "backend_name", "sqlite")

    # =========================================================
    # HELPERS
    # =========================================================
    def _id(self) -> str:
        return str(uuid.uuid4())

    def _now(self) -> str:
        return datetime.now().isoformat()

    def _bool_db(self, value: bool) -> Any:
        if self.backend_name == "postgres":
            return bool(value)
        return 1 if value else 0

    def _json_dump(self, value: Any) -> str:
        return json.dumps(value if value is not None else {}, ensure_ascii=False)

    def _json_load(self, value: Any) -> Any:
        if value is None:
            return {}
        if isinstance(value, (dict, list)):
            return value
        if not isinstance(value, str):
            return {}
        try:
            return json.loads(value)
        except Exception:
            return {}

    def _normalize_row(self, row: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not row:
            return {}

        data = dict(row)

        data["approved_for_reuse"] = bool(data.get("approved_for_reuse"))
        data["is_active"] = bool(data.get("is_active"))

        structure = self._json_load(data.get("response_structure_json"))
        data["response_structure_json"] = structure

        # Compatibilidad hacia adelante
        if "conditions_signature" not in data:
            data["conditions_signature"] = structure.get("conditions_signature", []) if isinstance(structure, dict) else []

        if "complexity_signature" not in data:
            data["complexity_signature"] = structure.get("complexity_signature") if isinstance(structure, dict) else None

        if "tags" not in data:
            data["tags"] = structure.get("tags", []) if isinstance(structure, dict) else []

        return data

    def _fetch_all(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        try:
            rows = self.db.execute(query, params, fetch=True)
        except TypeError:
            rows = self.db.execute(query, params)
        return rows or []

    def _fetch_one(self, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        try:
            row = self.db.execute(query, params, fetch_one=True)
            return row or None
        except TypeError:
            rows = self.db.execute(query, params)
            if isinstance(rows, list):
                return rows[0] if rows else None
            return rows

    # =========================================================
    # CREACIÓN GENÉRICA
    # =========================================================
    def create_response(
        self,
        response_text: str,
        detected_intent: Optional[str] = None,
        detected_category: Optional[str] = None,
        primary_state: Optional[str] = None,
        conversation_stage: Optional[str] = None,
        profile_id: Optional[str] = None,
        family_id: Optional[str] = None,
        conditions_signature: Optional[List[str]] = None,
        complexity_signature: Optional[Any] = None,
        response_structure_json: Optional[Dict[str, Any]] = None,
        confidence_score: Optional[float] = None,
        approved_for_reuse: bool = False,
        tags: Optional[List[str]] = None,
        origin_case_id: Optional[str] = None,
        notes: Optional[str] = None,
        source_type: str = "generic",
        llm_prompt_version: Optional[str] = None,
        usefulness_score: Optional[float] = None,
    ) -> str:
        response_id = self._id()
        now = self._now()

        conditions_signature = conditions_signature or []
        tags = tags or []
        response_structure_json = response_structure_json or {}

        merged_structure = {
            **response_structure_json,
            "conditions_signature": conditions_signature,
            "complexity_signature": complexity_signature,
            "tags": tags,
            "origin_case_id": origin_case_id,
            "notes": notes,
        }

        self.db.execute(
            """
            INSERT INTO response_memory (
                response_id,
                response_text,
                source_type,
                detected_intent,
                detected_category,
                primary_state,
                conversation_stage,
                profile_id,
                family_id,
                confidence_score,
                usefulness_score,
                response_structure_json,
                llm_prompt_version,
                approved_for_reuse,
                usage_count,
                success_count,
                failure_count,
                is_active,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                response_id,
                response_text,
                source_type,
                detected_intent,
                detected_category,
                primary_state,
                conversation_stage,
                profile_id,
                family_id,
                confidence_score,
                usefulness_score,
                self._json_dump(merged_structure),
                llm_prompt_version,
                self._bool_db(approved_for_reuse),
                0,
                0,
                0,
                self._bool_db(True),
                now,
                now,
            ),
        )

        return response_id

    # =========================================================
    # SISTEMA / LLM
    # =========================================================
    def create_from_system_response(
        self,
        response_text: str,
        detected_intent: Optional[str] = None,
        detected_category: Optional[str] = None,
        primary_state: Optional[str] = None,
        conversation_stage: Optional[str] = None,
        profile_id: Optional[str] = None,
        family_id: Optional[str] = None,
        conditions_signature: Optional[List[str]] = None,
        complexity_signature: Optional[Any] = None,
        response_structure_json: Optional[Dict[str, Any]] = None,
        confidence_score: Optional[float] = None,
        approved_for_reuse: bool = False,
        tags: Optional[List[str]] = None,
        origin_case_id: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> str:
        return self.create_response(
            response_text=response_text,
            detected_intent=detected_intent,
            detected_category=detected_category,
            primary_state=primary_state,
            conversation_stage=conversation_stage,
            profile_id=profile_id,
            family_id=family_id,
            conditions_signature=conditions_signature,
            complexity_signature=complexity_signature,
            response_structure_json=response_structure_json,
            confidence_score=confidence_score,
            approved_for_reuse=approved_for_reuse,
            tags=tags,
            origin_case_id=origin_case_id,
            notes=notes,
            source_type="system_generated",
            usefulness_score=None,
        )

    def create_from_llm_fallback(
        self,
        response_text: str,
        detected_intent: Optional[str] = None,
        detected_category: Optional[str] = None,
        primary_state: Optional[str] = None,
        conversation_stage: Optional[str] = None,
        profile_id: Optional[str] = None,
        family_id: Optional[str] = None,
        conditions_signature: Optional[List[str]] = None,
        complexity_signature: Optional[Any] = None,
        response_structure_json: Optional[Dict[str, Any]] = None,
        confidence_score: Optional[float] = None,
        approved_for_reuse: bool = False,
        tags: Optional[List[str]] = None,
        origin_case_id: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> str:
        llm_prompt_version = None
        if isinstance(response_structure_json, dict):
            llm_prompt_version = (
                response_structure_json.get("prompt_mode")
                or response_structure_json.get("llm_prompt_version")
            )

        return self.create_response(
            response_text=response_text,
            detected_intent=detected_intent,
            detected_category=detected_category,
            primary_state=primary_state,
            conversation_stage=conversation_stage,
            profile_id=profile_id,
            family_id=family_id,
            conditions_signature=conditions_signature,
            complexity_signature=complexity_signature,
            response_structure_json=response_structure_json,
            confidence_score=confidence_score,
            approved_for_reuse=approved_for_reuse,
            tags=tags,
            origin_case_id=origin_case_id,
            notes=notes,
            source_type="llm_curated",
            llm_prompt_version=llm_prompt_version,
            usefulness_score=None,
        )

    # =========================================================
    # REUSO
    # =========================================================
    def build_reuse_payload(
        self,
        detected_intent: Optional[str] = None,
        detected_category: Optional[str] = None,
        primary_state: Optional[str] = None,
        conversation_stage: Optional[str] = None,
        complexity_signature: Optional[Any] = None,
        conditions_signature: Optional[List[str]] = None,
        profile_id: Optional[str] = None,
        family_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        min_reuse_score: float = 0.50,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """
        Compatible con el nuevo orchestrator_v2.
        """
        tags = tags or []
        conditions_signature = conditions_signature or []

        rows = self._fetch_all(
            "SELECT * FROM response_memory WHERE is_active = ?",
            (self._bool_db(True),),
        )

        scored_candidates: List[Dict[str, Any]] = []

        for raw in rows:
            row = self._normalize_row(raw)
            score = 0.0

            # Coincidencias principales
            if detected_category and row.get("detected_category") == detected_category:
                score += 0.34

            if detected_intent and row.get("detected_intent") == detected_intent:
                score += 0.22

            if primary_state and row.get("primary_state") == primary_state:
                score += 0.18

            if conversation_stage and row.get("conversation_stage") == conversation_stage:
                score += 0.10

            # Coincidencia contextual
            if profile_id and row.get("profile_id") == profile_id:
                score += 0.06

            if family_id and row.get("family_id") == family_id:
                score += 0.05

            row_conditions = row.get("conditions_signature", []) or []
            row_complexity = row.get("complexity_signature")
            row_tags = row.get("tags", []) or []

            if complexity_signature and row_complexity and row_complexity == complexity_signature:
                score += 0.03

            overlap_conditions = 0
            if conditions_signature and row_conditions:
                overlap_conditions = len(
                    set(map(str, conditions_signature)).intersection(set(map(str, row_conditions)))
                )
                score += min(overlap_conditions * 0.015, 0.03)

            overlap_tags = 0
            if tags and row_tags:
                overlap_tags = len(set(map(str, tags)).intersection(set(map(str, row_tags))))
                score += min(overlap_tags * 0.01, 0.02)

            # Ajuste por desempeño histórico
            usage_count = int(row.get("usage_count", 0) or 0)
            success_count = int(row.get("success_count", 0) or 0)

            if usage_count > 0:
                success_rate = success_count / max(usage_count, 1)
                score += min(success_rate * 0.05, 0.05)
            elif bool(row.get("approved_for_reuse")):
                score += 0.03

            usefulness_score = row.get("usefulness_score")
            if usefulness_score is not None:
                try:
                    score += min(float(usefulness_score) * 0.03, 0.03)
                except Exception:
                    pass

            confidence_score = row.get("confidence_score")
            if confidence_score is not None:
                try:
                    score += min(float(confidence_score) * 0.02, 0.02)
                except Exception:
                    pass

            score = round(min(score, 0.99), 4)

            candidate = {
                **row,
                "reuse_score": score,
                "overlap_conditions": overlap_conditions,
                "overlap_tags": overlap_tags,
            }
            scored_candidates.append(candidate)

        scored_candidates.sort(
            key=lambda x: (
                -(x.get("reuse_score") or 0.0),
                -(1 if x.get("approved_for_reuse") else 0),
                -(x.get("success_count") or 0),
                -(x.get("usage_count") or 0),
            )
        )

        filtered = [c for c in scored_candidates if (c.get("reuse_score") or 0.0) >= min_reuse_score]
        best_response = filtered[0] if filtered else (scored_candidates[0] if scored_candidates else None)

        return {
            "response_candidates": filtered[:limit],
            "all_candidates": scored_candidates[:limit],
            "best_response": best_response,
            "selected_response": best_response.get("response_text") if best_response else None,
            "reuse_confidence": float(best_response.get("reuse_score", 0.0)) if best_response else 0.0,
            "can_reuse_directly": bool(best_response and (best_response.get("reuse_score", 0.0) >= 0.75)),
        }

    # =========================================================
    # FEEDBACK
    # =========================================================
    def register_response_outcome(
        self,
        response_id: str,
        used: bool = True,
        successful: Optional[bool] = None,
        usefulness_score: Optional[float] = None,
        notes: Optional[str] = None,
    ) -> bool:
        row = self._fetch_one(
            "SELECT * FROM response_memory WHERE response_id = ?",
            (response_id,),
        )
        if not row:
            return False

        row = self._normalize_row(row)

        usage_count = int(row.get("usage_count", 0) or 0)
        success_count = int(row.get("success_count", 0) or 0)
        failure_count = int(row.get("failure_count", 0) or 0)

        if used:
            usage_count += 1

        if successful is True:
            success_count += 1
        elif successful is False:
            failure_count += 1

        current_structure = row.get("response_structure_json", {}) or {}
        if notes:
            current_structure["latest_feedback_note"] = notes

        self.db.execute(
            """
            UPDATE response_memory
            SET usage_count = ?,
                success_count = ?,
                failure_count = ?,
                usefulness_score = ?,
                response_structure_json = ?,
                updated_at = ?
            WHERE response_id = ?
            """,
            (
                usage_count,
                success_count,
                failure_count,
                usefulness_score,
                self._json_dump(current_structure),
                self._now(),
                response_id,
            ),
        )

        return True

    # Alias por compatibilidad
    def register_feedback(
        self,
        response_id: str,
        success: bool,
        usefulness_score: Optional[float] = None,
    ) -> bool:
        return self.register_response_outcome(
            response_id=response_id,
            used=True,
            successful=success,
            usefulness_score=usefulness_score,
            notes=None,
        )

    # =========================================================
    # LECTURA
    # =========================================================
    def get_response_by_id(self, response_id: str) -> Optional[Dict[str, Any]]:
        row = self._fetch_one(
            "SELECT * FROM response_memory WHERE response_id = ?",
            (response_id,),
        )
        if not row:
            return None
        return self._normalize_row(row)

    def list_responses(
        self,
        limit: int = 50,
        only_active: bool = True,
    ) -> List[Dict[str, Any]]:
        if only_active:
            rows = self._fetch_all(
                "SELECT * FROM response_memory WHERE is_active = ? ORDER BY created_at DESC LIMIT ?",
                (self._bool_db(True), limit),
            )
        else:
            rows = self._fetch_all(
                "SELECT * FROM response_memory ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
        return [self._normalize_row(r) for r in rows]

    # =========================================================
    # MANTENIMIENTO
    # =========================================================
    def deactivate_response(self, response_id: str) -> bool:
        self.db.execute(
            """
            UPDATE response_memory
            SET is_active = ?, updated_at = ?
            WHERE response_id = ?
            """,
            (self._bool_db(False), self._now(), response_id),
        )
        return True

    def close(self) -> None:
        try:
            self.db.close()
        except Exception:
            pass