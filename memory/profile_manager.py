from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from database.database import NeuroGuiaDB


class ProfileManager:
    """
    Gestor de unidades y perfiles para NeuroGuía.

    Compatible con SQLite y PostgreSQL a través de NeuroGuiaDB.
    """

    def __init__(self, db_path: str = "neuroguia.db", backend: Optional[str] = None, env_path: str = ".env") -> None:
        self.db = NeuroGuiaDB(db_path=db_path, backend=backend, env_path=env_path)

    # =========================================================
    # UTILIDADES
    # =========================================================
    def _id(self) -> str:
        return str(uuid.uuid4())

    def _now(self) -> str:
        return datetime.now().isoformat()

    def _normalize_text(self, value: Optional[str]) -> str:
        if not value:
            return ""
        return " ".join(str(value).strip().lower().split())

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

    def _row_to_unit(self, row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not row:
            return None
        return dict(row)

    def _row_to_profile(self, row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not row:
            return None

        result = dict(row)

        json_fields = [
            "conditions",
            "strengths",
            "triggers",
            "early_signs",
            "helpful_strategies",
            "harmful_strategies",
            "sensory_needs",
            "emotional_needs",
        ]
        for field in json_fields:
            result[field] = self._from_json(result.get(field))

        result["is_active"] = self._db_to_bool(result.get("is_active", True))
        return result

    def close(self) -> None:
        self.db.close()

    # =========================================================
    # UNITS
    # =========================================================
    def create_unit(
        self,
        unit_type: str = "individual",
        caregiver_alias: str = "Usuario",
        context_notes: Optional[str] = None,
        support_network: Optional[str] = None,
        environmental_factors: Optional[str] = None,
        global_history: Optional[str] = None,
    ) -> str:
        family_id = self._id()
        now = self._now()

        self.db.execute(
            """
            INSERT INTO families (
                family_id, unit_type, caregiver_alias,
                context_notes, support_network, environmental_factors, global_history,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                family_id,
                unit_type,
                caregiver_alias,
                context_notes,
                support_network,
                environmental_factors,
                global_history,
                now,
                now,
            ),
        )
        return family_id

    def list_units(self, limit: int = 100) -> List[Dict[str, Any]]:
        rows = self.db.execute(
            "SELECT * FROM families ORDER BY updated_at DESC LIMIT ?",
            (limit,),
            fetch=True,
        ) or []
        return [self._row_to_unit(r) for r in rows if r]

    def get_unit(self, family_id: str) -> Optional[Dict[str, Any]]:
        row = self.db.execute(
            "SELECT * FROM families WHERE family_id = ? LIMIT 1",
            (family_id,),
            fetch_one=True,
        )
        return self._row_to_unit(row)

    def update_unit(self, family_id: str, **kwargs: Any) -> bool:
        if not kwargs:
            return False

        fields: List[str] = []
        values: List[Any] = []

        allowed = {
            "unit_type",
            "caregiver_alias",
            "context_notes",
            "support_network",
            "environmental_factors",
            "global_history",
        }

        for key, value in kwargs.items():
            if key not in allowed:
                continue
            fields.append(f"{key} = ?")
            values.append(value)

        if not fields:
            return False

        fields.append("updated_at = ?")
        values.append(self._now())
        values.append(family_id)

        query = f"""
        UPDATE families
        SET {', '.join(fields)}
        WHERE family_id = ?
        """
        self.db.execute(query, tuple(values))
        return True

    # =========================================================
    # PROFILES
    # =========================================================
    def create_profile(
        self,
        family_id: Optional[str] = None,
        alias: Optional[str] = None,
        age: Optional[int] = None,
        role: Optional[str] = None,
        conditions: Optional[List[str]] = None,
        strengths: Optional[List[str]] = None,
        triggers: Optional[List[str]] = None,
        early_signs: Optional[List[str]] = None,
        helpful_strategies: Optional[List[str]] = None,
        harmful_strategies: Optional[List[str]] = None,
        sensory_needs: Optional[List[str]] = None,
        emotional_needs: Optional[List[str]] = None,
        autonomy_level: Optional[str] = None,
        sleep_profile: Optional[str] = None,
        school_profile: Optional[str] = None,
        executive_profile: Optional[str] = None,
        evolution_notes: Optional[str] = None,
        is_active: bool = True,
    ) -> str:
        if not family_id:
            family_id = self.create_unit()

        profile_id = self._id()
        now = self._now()

        self.db.execute(
            """
            INSERT INTO profiles (
                profile_id, family_id, alias, age, role,
                conditions, strengths, triggers, early_signs,
                helpful_strategies, harmful_strategies,
                sensory_needs, emotional_needs,
                autonomy_level, sleep_profile, school_profile, executive_profile, evolution_notes,
                is_active, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                profile_id,
                family_id,
                alias,
                age,
                role,
                self._to_json(conditions or []),
                self._to_json(strengths or []),
                self._to_json(triggers or []),
                self._to_json(early_signs or []),
                self._to_json(helpful_strategies or []),
                self._to_json(harmful_strategies or []),
                self._to_json(sensory_needs or []),
                self._to_json(emotional_needs or []),
                autonomy_level,
                sleep_profile,
                school_profile,
                executive_profile,
                evolution_notes,
                self._bool_to_db(is_active),
                now,
                now,
            ),
        )
        return profile_id

    def list_profiles(self, family_id: str, only_active: bool = True) -> List[Dict[str, Any]]:
        query = "SELECT * FROM profiles WHERE family_id = ?"
        params: List[Any] = [family_id]

        if only_active:
            query += " AND is_active = ?"
            params.append(self._bool_to_db(True))

        query += " ORDER BY updated_at DESC"

        rows = self.db.execute(query, tuple(params), fetch=True) or []
        return [self._row_to_profile(r) for r in rows if r]

    def get_profile(self, profile_id: str) -> Optional[Dict[str, Any]]:
        row = self.db.execute(
            "SELECT * FROM profiles WHERE profile_id = ? LIMIT 1",
            (profile_id,),
            fetch_one=True,
        )
        return self._row_to_profile(row)

    def update_profile(self, profile_id: str, **kwargs: Any) -> bool:
        if not kwargs:
            return False

        json_fields = {
            "conditions",
            "strengths",
            "triggers",
            "early_signs",
            "helpful_strategies",
            "harmful_strategies",
            "sensory_needs",
            "emotional_needs",
        }
        bool_fields = {"is_active"}

        allowed = {
            "alias",
            "age",
            "role",
            "conditions",
            "strengths",
            "triggers",
            "early_signs",
            "helpful_strategies",
            "harmful_strategies",
            "sensory_needs",
            "emotional_needs",
            "autonomy_level",
            "sleep_profile",
            "school_profile",
            "executive_profile",
            "evolution_notes",
            "is_active",
        }

        fields: List[str] = []
        values: List[Any] = []

        for key, value in kwargs.items():
            if key not in allowed:
                continue

            if key in json_fields:
                value = self._to_json(value)
            elif key in bool_fields:
                value = self._bool_to_db(bool(value))

            fields.append(f"{key} = ?")
            values.append(value)

        if not fields:
            return False

        fields.append("updated_at = ?")
        values.append(self._now())
        values.append(profile_id)

        query = f"""
        UPDATE profiles
        SET {', '.join(fields)}
        WHERE profile_id = ?
        """
        self.db.execute(query, tuple(values))
        return True

    def deactivate_profile(self, profile_id: str) -> bool:
        return self.update_profile(profile_id, is_active=False)

    def activate_profile(self, profile_id: str) -> bool:
        return self.update_profile(profile_id, is_active=True)

    # =========================================================
    # RESOLUCIÓN DE PERFIL ACTIVO
    # =========================================================
    def resolve_active_profile(
        self,
        family_id: Optional[str] = None,
        profile_id: Optional[str] = None,
        profile_alias: Optional[str] = None,
        message: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        if profile_id:
            profile = self.get_profile(profile_id)
            if profile:
                return profile

        if not family_id:
            return None

        profiles = self.list_profiles(family_id=family_id, only_active=True)
        if not profiles:
            return None

        if len(profiles) == 1:
            return profiles[0]

        normalized_alias = self._normalize_text(profile_alias)
        if normalized_alias:
            for profile in profiles:
                if self._normalize_text(profile.get("alias")) == normalized_alias:
                    return profile

        normalized_message = self._normalize_text(message)
        if normalized_message:
            # Busca coincidencia por alias dentro del mensaje
            for profile in profiles:
                alias = self._normalize_text(profile.get("alias"))
                if alias and alias in normalized_message:
                    return profile

        return profiles[0]

    # =========================================================
    # FUNCIONES DE CONVENIENCIA
    # =========================================================
    def get_family_snapshot(self, family_id: str) -> Dict[str, Any]:
        unit = self.get_unit(family_id)
        profiles = self.list_profiles(family_id)
        return {
            "unit": unit,
            "profiles": profiles,
            "profile_count": len(profiles),
        }