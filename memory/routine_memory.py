from __future__ import annotations

import json
import re
import unicodedata
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from database.database import NeuroGuiaDB


class RoutineMemory:
    """Persistencia híbrida de rutinas para neuroguIA.

    Usa la tabla ``routines`` como contrato interno estable:

    - SQLite: tabla local ``routines``.
    - PostgreSQL/Supabase:
      vista de compatibilidad ``routines`` -> ``ng_routines``.

    Esta clase no decide cuándo generar una rutina.
    Únicamente la guarda, recupera, actualiza o desactiva
    cuando existe contexto válido de familia y perfil.
    """

    JSON_FIELDS = {
        "steps",
        "short_version",
        "adjustments",
        "indicators",
    }

    MUTABLE_FIELDS = {
        "routine_type",
        "routine_name",
        "goal",
        "steps",
        "short_version",
        "adjustments",
        "indicators",
        "followup_question",
        "source_case_id",
        "is_active",
    }

    def __init__(
        self,
        db_path: str = "neuroguia.db",
        backend: Optional[str] = None,
        env_path: str = ".env",
    ) -> None:
        self.db = NeuroGuiaDB(
            db_path=db_path,
            backend=backend,
            env_path=env_path,
        )

    # =========================================================
    # UTILIDADES
    # =========================================================

    def close(self) -> None:
        self.db.close()

    def _generate_id(self) -> str:
        return str(uuid.uuid4())

    def _now(self) -> str:
        return datetime.now().isoformat()

    def _json_dump(
        self,
        value: Any,
        default: Any,
    ) -> str:
        payload = (
            default
            if value is None
            else value
        )

        return json.dumps(
            payload,
            ensure_ascii=False,
        )

    def _json_load(
        self,
        value: Any,
        default: Any,
    ) -> Any:

        if value is None or value == "":
            return default

        if isinstance(
            value,
            (list, dict),
        ):
            return value

        try:
            return json.loads(value)

        except Exception:
            return default

    def _bool_to_db(
        self,
        value: bool,
    ) -> Any:

        if self.db.backend_name == "postgres":
            return bool(value)

        return 1 if bool(value) else 0

    def _normalize_identity_text(self, value: Any) -> str:
        """Normaliza texto usado para identificar una misma rutina.

        La comparación se realiza en Python para no depender de diferencias
        entre SQLite, PostgreSQL y la vista de compatibilidad ``routines``.
        También tolera espacios repetidos y variantes Unicode equivalentes.
        """

        text = unicodedata.normalize(
            "NFKC",
            str(value or ""),
        )
        return re.sub(r"\s+", " ", text).strip().casefold()

    def _row_to_routine(
        self,
        row: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:

        if not row:
            return None

        result = dict(row)

        result["steps"] = self._json_load(
            result.get("steps"),
            [],
        )

        result["short_version"] = self._json_load(
            result.get("short_version"),
            [],
        )

        result["adjustments"] = self._json_load(
            result.get("adjustments"),
            [],
        )

        result["indicators"] = self._json_load(
            result.get("indicators"),
            [],
        )

        result["is_active"] = bool(
            result.get("is_active")
        )

        return result

    # =========================================================
    # GUARDADO
    # =========================================================

    def save_routine(
        self,
        routine_payload: Dict[str, Any],
        family_id: str,
        profile_id: str,
        source_case_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Guarda una rutina completa con contexto válido."""

        family_id = str(
            family_id or ""
        ).strip()

        profile_id = str(
            profile_id or ""
        ).strip()

        if not family_id:

            return {
                "stored": False,
                "reason": "missing_family_id",
                "routine_id": None,
            }

        if not profile_id:

            return {
                "stored": False,
                "reason": "missing_profile_id",
                "routine_id": None,
            }

        routine_type = str(
            routine_payload.get(
                "routine_type"
            )
            or ""
        ).strip()

        routine_name = str(
            routine_payload.get(
                "routine_name"
            )
            or ""
        ).strip()

        if (
            not routine_type
            or not routine_name
        ):

            return {
                "stored": False,
                "reason": "invalid_routine_payload",
                "routine_id": None,
            }

        # Obtiene las rutinas activas dentro del ámbito válido y compara su
        # identidad en Python. Esto evita falsos negativos producidos por
        # espacios, Unicode, mayúsculas o diferencias del backend/vista SQL.
        candidate_rows = self.db.execute(
            """
            SELECT *
            FROM routines
            WHERE family_id = ?
              AND profile_id = ?
              AND is_active = ?
            ORDER BY
                updated_at DESC,
                created_at DESC
            LIMIT 100
            """,
            (
                family_id,
                profile_id,
                self._bool_to_db(True),
            ),
            fetch=True,
        ) or []

        normalized_name = self._normalize_identity_text(
            routine_name
        )
        matching_routines = []
        for row in candidate_rows:
            candidate = self._row_to_routine(row)
            if (
                candidate
                and self._normalize_identity_text(
                    candidate.get("routine_name")
                ) == normalized_name
            ):
                matching_routines.append(candidate)

        # Si ya hay duplicados históricos, usa como registro canónico el que
        # conserva más memoria útil. No elimina ni desactiva las otras filas.
        existing = None
        if matching_routines:
            existing = max(
                matching_routines,
                key=lambda item: (
                    bool(item.get("adjustments")),
                    item.get("followup_question") is None,
                    str(item.get("updated_at") or ""),
                    str(item.get("created_at") or ""),
                ),
            )

        if existing:
            existing_adjustments = list(
                existing.get("adjustments") or []
            )
            incoming_adjustments = list(
                routine_payload.get("adjustments") or []
            )
            merged_adjustments: List[Any] = []
            seen_adjustments = set()
            for adjustment in existing_adjustments + incoming_adjustments:
                text = str(adjustment or "").strip()
                key = text.casefold()
                if text and key not in seen_adjustments:
                    merged_adjustments.append(adjustment)
                    seen_adjustments.add(key)

            # Una pregunta ya respondida se representa con NULL. No debe
            # reaparecer al regenerar la misma rutina.
            existing_followup = existing.get("followup_question")
            followup_question = (
                None
                if existing_followup is None
                else routine_payload.get("followup_question")
            )

            updates: Dict[str, Any] = {
                "routine_type": routine_type,
                "routine_name": routine_name,
                "goal": routine_payload.get("goal"),
                "steps": routine_payload.get("steps") or [],
                "short_version": routine_payload.get("short_version") or [],
                "adjustments": merged_adjustments,
                "indicators": routine_payload.get("indicators") or [],
                "followup_question": followup_question,
                "is_active": True,
            }
            if source_case_id is not None:
                updates["source_case_id"] = source_case_id

            updated = self.update_routine(
                routine_id=str(existing.get("routine_id") or ""),
                family_id=family_id,
                profile_id=profile_id,
                **updates,
            )
            return {
                "stored": bool(updated.get("updated")),
                "reason": (
                    "updated_existing"
                    if updated.get("updated")
                    else str(updated.get("reason") or "update_existing_failed")
                ),
                "routine_id": updated.get("routine_id"),
                "routine": updated.get("routine"),
                "created_new": False,
                "matching_active_count": len(matching_routines),
            }

        routine_id = self._generate_id()
        now = self._now()

        self.db.execute(
            """
            INSERT INTO routines (
                routine_id,
                family_id,
                profile_id,
                routine_type,
                routine_name,
                goal,
                steps,
                short_version,
                adjustments,
                indicators,
                followup_question,
                source_case_id,
                is_active,
                created_at,
                updated_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?
            )
            """,
            (
                routine_id,
                family_id,
                profile_id,
                routine_type,
                routine_name,
                routine_payload.get(
                    "goal"
                ),
                self._json_dump(
                    routine_payload.get(
                        "steps"
                    ),
                    [],
                ),
                self._json_dump(
                    routine_payload.get(
                        "short_version"
                    ),
                    [],
                ),
                self._json_dump(
                    routine_payload.get(
                        "adjustments"
                    ),
                    [],
                ),
                self._json_dump(
                    routine_payload.get(
                        "indicators"
                    ),
                    [],
                ),
                routine_payload.get(
                    "followup_question"
                ),
                source_case_id,
                self._bool_to_db(True),
                now,
                now,
            ),
        )

        return {
            "stored": True,
            "reason": "stored",
            "routine_id": routine_id,
            "created_new": True,
            "routine": self.get_routine(
                routine_id
            ),
        }

    # =========================================================
    # RECUPERACIÓN
    # =========================================================

    def get_routine(
        self,
        routine_id: str,
    ) -> Optional[Dict[str, Any]]:

        row = self.db.execute(
            """
            SELECT *
            FROM routines
            WHERE routine_id = ?
            LIMIT 1
            """,
            (
                routine_id,
            ),
            fetch_one=True,
        )

        return self._row_to_routine(
            row
        )

    def get_active_routine(
        self,
        family_id: str,
        profile_id: str,
        routine_type: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:

        conditions = [
            "family_id = ?",
            "profile_id = ?",
            "is_active = ?",
        ]

        params: List[Any] = [
            family_id,
            profile_id,
            self._bool_to_db(True),
        ]

        if routine_type:

            conditions.append(
                "routine_type = ?"
            )

            params.append(
                routine_type
            )

        row = self.db.execute(
            f"""
            SELECT *
            FROM routines
            WHERE {' AND '.join(conditions)}
            ORDER BY
                updated_at DESC,
                created_at DESC
            LIMIT 1
            """,
            tuple(params),
            fetch_one=True,
        )

        return self._row_to_routine(
            row
        )

    def list_active_routines(
        self,
        family_id: str,
        profile_id: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:

        rows = self.db.execute(
            """
            SELECT *
            FROM routines
            WHERE family_id = ?
              AND profile_id = ?
              AND is_active = ?
            ORDER BY
                updated_at DESC,
                created_at DESC
            LIMIT ?
            """,
            (
                family_id,
                profile_id,
                self._bool_to_db(True),
                limit,
            ),
            fetch=True,
        ) or []

        result: List[
            Dict[str, Any]
        ] = []

        for row in rows:

            routine = (
                self._row_to_routine(
                    row
                )
            )

            if routine is not None:
                result.append(
                    routine
                )

        return result

    # =========================================================
    # ACTUALIZACIÓN
    # =========================================================

    def update_routine(
        self,
        routine_id: str,
        family_id: str,
        profile_id: str,
        **updates: Any,
    ) -> Dict[str, Any]:
        """Actualiza una rutina solo dentro de su familia y perfil."""

        current = self.db.execute(
            """
            SELECT *
            FROM routines
            WHERE routine_id = ?
              AND family_id = ?
              AND profile_id = ?
            LIMIT 1
            """,
            (
                routine_id,
                family_id,
                profile_id,
            ),
            fetch_one=True,
        )

        if not current:

            return {
                "updated": False,
                "reason":
                    "routine_not_found_in_scope",
                "routine_id":
                    routine_id,
            }

        filtered = {
            key: value
            for key, value
            in updates.items()
            if key in self.MUTABLE_FIELDS
        }

        if not filtered:

            return {
                "updated": False,
                "reason":
                    "no_valid_updates",
                "routine_id":
                    routine_id,
            }

        fields: List[str] = []
        values: List[Any] = []

        for key, value in filtered.items():

            if key in self.JSON_FIELDS:

                value = self._json_dump(
                    value,
                    [],
                )

            elif key == "is_active":

                value = self._bool_to_db(
                    bool(value)
                )

            fields.append(
                f"{key} = ?"
            )

            values.append(
                value
            )

        fields.append(
            "updated_at = ?"
        )

        values.append(
            self._now()
        )

        values.extend(
            [
                routine_id,
                family_id,
                profile_id,
            ]
        )

        self.db.execute(
            f"""
            UPDATE routines
            SET {', '.join(fields)}
            WHERE routine_id = ?
              AND family_id = ?
              AND profile_id = ?
            """,
            tuple(values),
        )

        return {
            "updated": True,
            "reason": "updated",
            "routine_id": routine_id,
            "routine": self.get_routine(
                routine_id
            ),
        }

    def set_primary_strategy(
        self,
        routine_id: str,
        family_id: str,
        profile_id: str,
        strategy: str,
    ) -> Dict[str, Any]:
        """Guarda una estrategia principal sin perder los ajustes existentes.

        La estrategia se conserva en ``adjustments`` para mantener el contrato
        actual de la tabla ``routines``. Si ya existía otra estrategia
        principal, se reemplaza; los demás ajustes permanecen intactos. La
        pregunta de seguimiento se limpia porque esta operación representa la
        respuesta explícita de la persona a dicha pregunta.
        """

        routine_id = str(routine_id or "").strip()
        family_id = str(family_id or "").strip()
        profile_id = str(profile_id or "").strip()
        strategy = str(strategy or "").strip().strip("\"'“”")

        if not strategy:
            return {
                "updated": False,
                "reason": "missing_primary_strategy",
                "routine_id": routine_id or None,
            }

        current_row = self.db.execute(
            """
            SELECT *
            FROM routines
            WHERE routine_id = ?
              AND family_id = ?
              AND profile_id = ?
            LIMIT 1
            """,
            (
                routine_id,
                family_id,
                profile_id,
            ),
            fetch_one=True,
        )
        current = self._row_to_routine(current_row)

        if not current:
            return {
                "updated": False,
                "reason": "routine_not_found_in_scope",
                "routine_id": routine_id or None,
            }

        prefix = "estrategia principal:"
        adjustments = [
            str(item).strip()
            for item in list(current.get("adjustments") or [])
            if str(item or "").strip()
            and not str(item).strip().casefold().startswith(prefix)
        ]
        primary_adjustment = f"Estrategia principal: {strategy}"
        adjustments.insert(0, primary_adjustment)

        result = self.update_routine(
            routine_id=routine_id,
            family_id=family_id,
            profile_id=profile_id,
            adjustments=adjustments,
            followup_question=None,
        )
        result["primary_strategy"] = strategy
        result["primary_adjustment"] = primary_adjustment
        return result

    # =========================================================
    # DESACTIVACIÓN
    # =========================================================

    def deactivate_routine(
        self,
        routine_id: str,
        family_id: str,
        profile_id: str,
    ) -> Dict[str, Any]:

        return self.update_routine(
            routine_id=routine_id,
            family_id=family_id,
            profile_id=profile_id,
            is_active=False,
        )
