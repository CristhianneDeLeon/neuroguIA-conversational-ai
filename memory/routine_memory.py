from __future__ import annotations

import json
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
