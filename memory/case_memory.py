from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from database import NeuroGuiaDB


class CaseMemory:
    """
    Memoria premium de casos para NeuroGuía, compatible con backend híbrido.

    Soporta:
    - SQLite local
    - PostgreSQL / Supabase

    Responsabilidades:
    - registrar casos
    - recuperar historial por perfil o familia
    - encontrar casos similares
    - registrar feedback del caso
    - aprender patrones útiles / no útiles
    - construir payloads contextuales para el orquestador
    """

    def __init__(self, db_path: str = "neuroguia.db", backend: Optional[str] = None, env_path: str = ".env") -> None:
        self.db = NeuroGuiaDB(db_path=db_path, backend=backend, env_path=env_path)

    # =========================================================
    # UTILIDADES
    # =========================================================
    def _generate_id(self) -> str:
        return str(uuid.uuid4())

    def _now(self) -> str:
        return datetime.now().isoformat()

    def _normalize_text(self, text: Optional[str]) -> str:
        if not text:
            return ""
        return " ".join(str(text).strip().lower().split())

    def _to_json(self, value: Any, default: Any = None) -> str:
        if value is None:
            value = [] if default is None else default
        return json.dumps(value, ensure_ascii=False)

    def _from_json(self, value: Any, default: Any = None) -> Any:
        if value is None or value == "":
            return [] if default is None else default
        if isinstance(value, (list, dict)):
            return value
        try:
            return json.loads(value)
        except Exception:
            return [] if default is None else default

    def _bool_to_db(self, value: bool) -> Any:
        if self.db.backend_name == "postgres":
            return bool(value)
        return 1 if bool(value) else 0

    def _db_to_bool(self, value: Any) -> bool:
        return bool(value)

    def _row_to_case(self, row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not row:
            return None

        result = dict(row)
        json_fields = [
            "secondary_states",
            "helps_patterns",
            "worsens_patterns",
            "tags",
        ]
        for field in json_fields:
            result[field] = self._from_json(result.get(field))
        result["applied_successfully"] = self._db_to_bool(result.get("applied_successfully"))
        result["followup_needed"] = self._db_to_bool(result.get("followup_needed"))
        return result

    def _row_to_pattern(self, row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not row:
            return None

        result = dict(row)
        result["helps"] = self._from_json(result.get("helps"))
        result["worsens"] = self._from_json(result.get("worsens"))
        return result

    def close(self) -> None:
        self.db.close()

    # =========================================================
    # CREACIÓN DE CASOS
    # =========================================================
    def create_case(
        self,
        family_id: Optional[str] = None,
        profile_id: Optional[str] = None,
        unit_type: str = "individual",
        raw_input: str = "",
        normalized_summary: Optional[str] = None,
        detected_category: Optional[str] = None,
        detected_stage: Optional[str] = None,
        primary_state: Optional[str] = None,
        secondary_states: Optional[List[str]] = None,
        emotional_intensity: Optional[float] = None,
        caregiver_capacity: Optional[float] = None,
        sensory_overload_risk: Optional[float] = None,
        executive_block_risk: Optional[float] = None,
        meltdown_risk: Optional[float] = None,
        shutdown_risk: Optional[float] = None,
        burnout_risk: Optional[float] = None,
        sleep_disruption_risk: Optional[float] = None,
        suggested_strategy: Optional[str] = None,
        suggested_microaction: Optional[str] = None,
        suggested_routine_type: Optional[str] = None,
        response_mode: Optional[str] = None,
        user_feedback: Optional[str] = None,
        observed_result: Optional[str] = None,
        usefulness_score: Optional[float] = None,
        applied_successfully: bool = False,
        helps_patterns: Optional[List[str]] = None,
        worsens_patterns: Optional[List[str]] = None,
        followup_needed: bool = False,
        tags: Optional[List[str]] = None,
    ) -> str:
        case_id = self._generate_id()
        now = self._now()

        if normalized_summary is None:
            normalized_summary = self._normalize_text(raw_input)[:500]

        self.db.execute(
            """
            INSERT INTO ng_case_memory (
                case_id, family_id, profile_id, unit_type, created_at, updated_at,
                raw_input, normalized_summary,
                detected_category, detected_stage, primary_state, secondary_states,
                emotional_intensity, caregiver_capacity, sensory_overload_risk,
                executive_block_risk, meltdown_risk, shutdown_risk, burnout_risk,
                sleep_disruption_risk,
                suggested_strategy, suggested_microaction, suggested_routine_type, response_mode,
                user_feedback, observed_result, usefulness_score, applied_successfully,
                helps_patterns, worsens_patterns, followup_needed, tags
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                case_id, family_id, profile_id, unit_type, now, now,
                raw_input, normalized_summary,
                detected_category, detected_stage, primary_state, self._to_json(secondary_states or []),
                emotional_intensity, caregiver_capacity, sensory_overload_risk,
                executive_block_risk, meltdown_risk, shutdown_risk, burnout_risk,
                sleep_disruption_risk,
                suggested_strategy, suggested_microaction, suggested_routine_type, response_mode,
                user_feedback, observed_result, usefulness_score, self._bool_to_db(applied_successfully),
                self._to_json(helps_patterns or []), self._to_json(worsens_patterns or []),
                self._bool_to_db(followup_needed), self._to_json(tags or [])
            ),
        )
        return case_id

    # =========================================================
    # CONSULTAS
    # =========================================================
    def get_case(self, case_id: str) -> Optional[Dict[str, Any]]:
        row = self.db.execute(
            "SELECT * FROM ng_case_memory WHERE case_id = ? LIMIT 1",
            (case_id,),
            fetch_one=True,
        )
        return self._row_to_case(row)

    def list_cases_by_profile(self, profile_id: str, limit: int = 25) -> List[Dict[str, Any]]:
        rows = self.db.execute(
            "SELECT * FROM ng_case_memory WHERE profile_id = ? ORDER BY created_at DESC LIMIT ?",
            (profile_id, limit),
            fetch=True,
        ) or []
        return [self._row_to_case(r) for r in rows if r]

    def list_cases_by_family(self, family_id: str, limit: int = 30) -> List[Dict[str, Any]]:
        rows = self.db.execute(
            "SELECT * FROM ng_case_memory WHERE family_id = ? ORDER BY created_at DESC LIMIT ?",
            (family_id, limit),
            fetch=True,
        ) or []
        return [self._row_to_case(r) for r in rows if r]

    def list_recent_cases(self, limit: int = 30) -> List[Dict[str, Any]]:
        rows = self.db.execute(
            "SELECT * FROM ng_case_memory ORDER BY created_at DESC LIMIT ?",
            (limit,),
            fetch=True,
        ) or []
        return [self._row_to_case(r) for r in rows if r]

    # =========================================================
    # ACTUALIZACIÓN
    # =========================================================
    def update_case(self, case_id: str, **kwargs: Any) -> bool:
        if not kwargs:
            return False

        json_fields = {"secondary_states", "helps_patterns", "worsens_patterns", "tags"}
        bool_fields = {"applied_successfully", "followup_needed"}

        fields: List[str] = []
        values: List[Any] = []

        for key, value in kwargs.items():
            if key in json_fields:
                value = self._to_json(value)
            elif key in bool_fields:
                value = self._bool_to_db(bool(value))

            fields.append(f"{key} = ?")
            values.append(value)

        fields.append("updated_at = ?")
        values.append(self._now())
        values.append(case_id)

        query = f"""
        UPDATE ng_case_memory
        SET {', '.join(fields)}
        WHERE case_id = ?
        """
        self.db.execute(query, tuple(values))
        return True

    def register_case_feedback(
        self,
        case_id: str,
        user_feedback: Optional[str] = None,
        observed_result: Optional[str] = None,
        usefulness_score: Optional[float] = None,
        applied_successfully: Optional[bool] = None,
        helps_patterns: Optional[List[str]] = None,
        worsens_patterns: Optional[List[str]] = None,
        followup_needed: Optional[bool] = None,
    ) -> bool:
        updates: Dict[str, Any] = {}

        if user_feedback is not None:
            updates["user_feedback"] = user_feedback
        if observed_result is not None:
            updates["observed_result"] = observed_result
        if usefulness_score is not None:
            updates["usefulness_score"] = usefulness_score
        if applied_successfully is not None:
            updates["applied_successfully"] = applied_successfully
        if helps_patterns is not None:
            updates["helps_patterns"] = helps_patterns
        if worsens_patterns is not None:
            updates["worsens_patterns"] = worsens_patterns
        if followup_needed is not None:
            updates["followup_needed"] = followup_needed

        if not updates:
            return False

        ok = self.update_case(case_id, **updates)
        if ok:
            case_data = self.get_case(case_id)
            if case_data:
                self._learn_from_case(case_data)
        return ok

    # =========================================================
    # BÚSQUEDA DE SIMILARES
    # =========================================================
    def find_similar_cases(
        self,
        profile_id: Optional[str] = None,
        family_id: Optional[str] = None,
        detected_category: Optional[str] = None,
        primary_state: Optional[str] = None,
        suggested_routine_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 12,
    ) -> List[Dict[str, Any]]:
        rows = self.list_recent_cases(limit=250)
        scored: List[Tuple[float, Dict[str, Any]]] = []

        for row in rows:
            score = 0.0

            if profile_id and row.get("profile_id") == profile_id:
                score += 0.25
            elif family_id and row.get("family_id") == family_id:
                score += 0.18

            if detected_category and row.get("detected_category") == detected_category:
                score += 0.20

            if primary_state and row.get("primary_state") == primary_state:
                score += 0.20

            if suggested_routine_type and row.get("suggested_routine_type") == suggested_routine_type:
                score += 0.10

            row_tags = {self._normalize_text(t) for t in (row.get("tags") or [])}
            target_tags = {self._normalize_text(t) for t in (tags or [])}
            if row_tags and target_tags:
                overlap = len(row_tags.intersection(target_tags))
                if overlap > 0:
                    score += min(overlap * 0.04, 0.12)

            if float(row.get("usefulness_score", 0.0) or 0.0) > 0:
                score += min(float(row.get("usefulness_score", 0.0) or 0.0) * 0.08, 0.08)

            if bool(row.get("applied_successfully", False)):
                score += 0.05

            if score > 0.10:
                scored.append((score, row))

        scored.sort(key=lambda x: (-x[0], x[1].get("created_at", "")))
        return [row for _, row in scored[:limit]]

    # =========================================================
    # APRENDIZAJE DE PATRONES
    # =========================================================
    def _build_context_key(self, case_data: Dict[str, Any]) -> str:
        profile_id = case_data.get("profile_id") or "no_profile"
        category = case_data.get("detected_category") or "general"
        primary_state = case_data.get("primary_state") or "general_distress"
        routine_type = case_data.get("suggested_routine_type") or "no_routine"
        return f"{profile_id}::{category}::{primary_state}::{routine_type}"

    def _merge_unique(self, base: List[str], new: List[str]) -> List[str]:
        result: List[str] = []
        seen = set()
        for item in (base or []) + (new or []):
            key = self._normalize_text(item)
            if key and key not in seen:
                seen.add(key)
                result.append(item)
        return result

    def get_pattern_by_context(
        self,
        profile_id: Optional[str],
        family_id: Optional[str],
        context_key: str,
    ) -> Optional[Dict[str, Any]]:
        rows = self.db.execute(
            "SELECT * FROM learned_patterns WHERE context_key = ?",
            (context_key,),
            fetch=True,
        ) or []

        for row in rows:
            if (row.get("profile_id") or None) == (profile_id or None) and (row.get("family_id") or None) == (family_id or None):
                return self._row_to_pattern(row)
        return None

    def _learn_from_case(self, case_data: Dict[str, Any]) -> None:
        context_key = self._build_context_key(case_data)
        existing = self.get_pattern_by_context(
            profile_id=case_data.get("profile_id"),
            family_id=case_data.get("family_id"),
            context_key=context_key,
        )

        new_helps = case_data.get("helps_patterns", []) or []
        new_worsens = case_data.get("worsens_patterns", []) or []
        usefulness_score = case_data.get("usefulness_score")
        applied_successfully = case_data.get("applied_successfully", False)

        confidence_delta = 0.05
        if usefulness_score is not None:
            confidence_delta += min(max(float(usefulness_score), 0.0), 1.0) * 0.15
        if applied_successfully:
            confidence_delta += 0.10

        now = self._now()

        if existing:
            merged_helps = self._merge_unique(existing.get("helps", []), new_helps)
            merged_worsens = self._merge_unique(existing.get("worsens", []), new_worsens)
            new_confidence = min((existing.get("confidence_level") or 0.20) + confidence_delta, 1.0)
            usage_count = int(existing.get("usage_count") or 0) + 1

            self.db.execute(
                """
                UPDATE learned_patterns
                SET helps = ?, worsens = ?, confidence_level = ?, usage_count = ?, last_seen = ?, updated_at = ?
                WHERE pattern_id = ?
                """,
                (
                    self._to_json(merged_helps),
                    self._to_json(merged_worsens),
                    new_confidence,
                    usage_count,
                    now,
                    now,
                    existing["pattern_id"],
                ),
            )
        else:
            pattern_id = self._generate_id()
            base_confidence = min(0.20 + confidence_delta, 1.0)

            self.db.execute(
                """
                INSERT INTO learned_patterns (
                    pattern_id, family_id, profile_id, context_key,
                    helps, worsens, confidence_level, usage_count,
                    last_seen, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pattern_id,
                    case_data.get("family_id"),
                    case_data.get("profile_id"),
                    context_key,
                    self._to_json(new_helps),
                    self._to_json(new_worsens),
                    base_confidence,
                    1,
                    now,
                    now,
                    now,
                ),
            )

    def get_patterns_for_profile(self, profile_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        rows = self.db.execute(
            "SELECT * FROM learned_patterns WHERE profile_id = ? ORDER BY confidence_level DESC, updated_at DESC LIMIT ?",
            (profile_id, limit),
            fetch=True,
        ) or []
        return [self._row_to_pattern(r) for r in rows if r]

    def get_patterns_for_family(self, family_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        rows = self.db.execute(
            "SELECT * FROM learned_patterns WHERE family_id = ? ORDER BY confidence_level DESC, updated_at DESC LIMIT ?",
            (family_id, limit),
            fetch=True,
        ) or []
        return [self._row_to_pattern(r) for r in rows if r]

    def _get_pattern_scope(
        self,
        profile_id: Optional[str] = None,
        family_id: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        if profile_id:
            return self.get_patterns_for_profile(profile_id, limit=limit)
        if family_id:
            return self.get_patterns_for_family(family_id, limit=limit)
        return []

    def _rank_text_items(self, items: List[str]) -> List[str]:
        counts: Dict[str, Tuple[int, str]] = {}
        for item in items:
            key = self._normalize_text(item)
            if not key:
                continue
            if key in counts:
                counts[key] = (counts[key][0] + 1, counts[key][1])
            else:
                counts[key] = (1, item)

        ranked = sorted(counts.values(), key=lambda x: (-x[0], self._normalize_text(x[1])))
        return [original for _, original in ranked]

    def get_best_help_patterns(
        self,
        profile_id: Optional[str] = None,
        family_id: Optional[str] = None,
        limit: int = 10,
    ) -> List[str]:
        patterns = self._get_pattern_scope(profile_id=profile_id, family_id=family_id, limit=limit)
        helps: List[str] = []
        for pattern in patterns:
            helps.extend(pattern.get("helps", []))
        return self._rank_text_items(helps)

    def get_main_worsening_patterns(
        self,
        profile_id: Optional[str] = None,
        family_id: Optional[str] = None,
        limit: int = 10,
    ) -> List[str]:
        patterns = self._get_pattern_scope(profile_id=profile_id, family_id=family_id, limit=limit)
        worsens: List[str] = []
        for pattern in patterns:
            worsens.extend(pattern.get("worsens", []))
        return self._rank_text_items(worsens)

    # =========================================================
    # RESÚMENES
    # =========================================================
    def build_profile_memory_summary(self, profile_id: str) -> Dict[str, Any]:
        cases = self.list_cases_by_profile(profile_id, limit=25)
        patterns = self.get_patterns_for_profile(profile_id, limit=20)
        return self._build_memory_summary(cases, patterns)

    def build_family_memory_summary(self, family_id: str) -> Dict[str, Any]:
        cases = self.list_cases_by_family(family_id, limit=30)
        patterns = self.get_patterns_for_family(family_id, limit=20)
        return self._build_memory_summary(cases, patterns)

    def _build_memory_summary(self, cases: List[Dict[str, Any]], patterns: List[Dict[str, Any]]) -> Dict[str, Any]:
        total_cases = len(cases)
        successful_cases = sum(1 for c in cases if c.get("applied_successfully"))
        followup_cases = sum(1 for c in cases if c.get("followup_needed"))

        usefulness_values = [
            float(c["usefulness_score"])
            for c in cases
            if c.get("usefulness_score") is not None
        ]
        avg_usefulness = round(sum(usefulness_values) / len(usefulness_values), 4) if usefulness_values else 0.0
        success_rate = round(successful_cases / total_cases, 4) if total_cases > 0 else 0.0

        frequent_categories = self._rank_text_items([c.get("detected_category") for c in cases if c.get("detected_category")])
        frequent_states = self._rank_text_items([c.get("primary_state") for c in cases if c.get("primary_state")])

        return {
            "total_cases": total_cases,
            "successful_cases": successful_cases,
            "success_rate": success_rate,
            "average_usefulness": avg_usefulness,
            "frequent_categories": frequent_categories[:5],
            "frequent_primary_states": frequent_states[:5],
            "best_help_patterns": self.get_best_help_patterns(limit=10, profile_id=cases[0].get("profile_id") if cases and cases[0].get("profile_id") else None),
            "main_worsening_patterns": self.get_main_worsening_patterns(limit=10, profile_id=cases[0].get("profile_id") if cases and cases[0].get("profile_id") else None),
            "pattern_count": len(patterns),
            "followup_cases": followup_cases,
            "latest_case_at": cases[0].get("created_at") if cases else None,
        }

    # =========================================================
    # PAYLOAD CONTEXTUAL PARA ORQUESTADOR
    # =========================================================
    def build_contextual_recommendation_payload(
        self,
        profile_id: Optional[str] = None,
        family_id: Optional[str] = None,
        detected_category: Optional[str] = None,
        primary_state: Optional[str] = None,
        suggested_routine_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 8,
    ) -> Dict[str, Any]:
        similar_cases = self.find_similar_cases(
            profile_id=profile_id,
            family_id=family_id,
            detected_category=detected_category,
            primary_state=primary_state,
            suggested_routine_type=suggested_routine_type,
            tags=tags,
            limit=limit,
        )

        successful_similar = [c for c in similar_cases if c.get("applied_successfully")]
        usefulness_values = [
            float(c["usefulness_score"])
            for c in similar_cases
            if c.get("usefulness_score") is not None
        ]

        recommended_strategies = self._rank_text_items(
            [c.get("suggested_strategy") for c in similar_cases if c.get("suggested_strategy")]
        )[:5]

        recommended_microactions = self._rank_text_items(
            [c.get("suggested_microaction") for c in similar_cases if c.get("suggested_microaction")]
        )[:5]

        recommended_routine_types = self._rank_text_items(
            [c.get("suggested_routine_type") for c in similar_cases if c.get("suggested_routine_type")]
        )[:5]

        help_patterns = self._rank_text_items(
            [item for c in similar_cases for item in (c.get("helps_patterns") or [])]
        )[:6]

        worsen_patterns = self._rank_text_items(
            [item for c in similar_cases for item in (c.get("worsens_patterns") or [])]
        )[:6]

        avg_usefulness = round(sum(usefulness_values) / len(usefulness_values), 4) if usefulness_values else 0.0

        return {
            "similar_cases": similar_cases,
            "similar_case_count": len(similar_cases),
            "successful_similar_case_count": len(successful_similar),
            "average_usefulness_in_similar_cases": avg_usefulness,
            "recommended_strategies": recommended_strategies,
            "recommended_microactions": recommended_microactions,
            "recommended_routine_types": recommended_routine_types,
            "help_patterns": help_patterns,
            "worsening_patterns": worsen_patterns,
        }


# =========================================================
# FUNCIONES DE CONVENIENCIA
# =========================================================
def build_case_contextual_payload(
    db_path: str = "neuroguia.db",
    backend: Optional[str] = None,
    env_path: str = ".env",
    **kwargs: Any,
) -> Dict[str, Any]:
    memory = CaseMemory(db_path=db_path, backend=backend, env_path=env_path)
    try:
        return memory.build_contextual_recommendation_payload(**kwargs)
    finally:
        memory.close()
