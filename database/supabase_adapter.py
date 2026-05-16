# database/supabase_adapter.py

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from .database_postgres import PostgresDatabase, PostgresConfig, load_env_file

try:
    from supabase import Client, create_client
except Exception:  # pragma: no cover
    Client = Any  # type: ignore
    create_client = None  # type: ignore


class SupabaseAdapter:
    """
    Adaptador orientado a la app para Supabase.

    Qué hace:
    - inicializa cliente Supabase
    - valida credenciales
    - permite acceso PostgreSQL directo para verificación estructural
    - prepara la base para futuras integraciones
    """

    def __init__(self, env_path: str = ".env") -> None:
        load_env_file(env_path)

        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_anon_key = os.getenv("SUPABASE_ANON_KEY")
        self.supabase_service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

        self._client: Optional[Client] = None
        self.pg = PostgresDatabase(
            config=PostgresConfig.from_env(env_path=env_path),
            env_path=env_path,
        )

    # -----------------------------------------------------
    # CLIENTE SUPABASE
    # -----------------------------------------------------
    def get_client(self, use_service_role: bool = False) -> Client:
        if create_client is None:
            raise ImportError(
                "La librería supabase no está instalada. Instala con: pip install supabase"
            )

        key = self.supabase_service_role_key if use_service_role else self.supabase_anon_key

        if not self.supabase_url or not key:
            raise ValueError(
                "Faltan SUPABASE_URL y/o la key correspondiente "
                "(SUPABASE_ANON_KEY o SUPABASE_SERVICE_ROLE_KEY)."
            )

        if self._client is None or use_service_role:
            self._client = create_client(self.supabase_url, key)

        return self._client

    def validate_config(self) -> Dict[str, Any]:
        return {
            "has_supabase_url": bool(self.supabase_url),
            "has_anon_key": bool(self.supabase_anon_key),
            "has_service_role_key": bool(self.supabase_service_role_key),
            "postgres_ready": True,
        }

    # -----------------------------------------------------
    # AUTH
    # -----------------------------------------------------
    def sign_in_with_password(self, email: str, password: str) -> Any:
        client = self.get_client(use_service_role=False)
        return client.auth.sign_in_with_password({"email": email, "password": password})

    def sign_up(self, email: str, password: str) -> Any:
        client = self.get_client(use_service_role=False)
        return client.auth.sign_up({"email": email, "password": password})

    def get_current_user(self) -> Any:
        client = self.get_client(use_service_role=False)
        return client.auth.get_user()

    # -----------------------------------------------------
    # STORAGE
    # -----------------------------------------------------
    def list_buckets(self) -> Any:
        client = self.get_client(use_service_role=True)
        return client.storage.list_buckets()

    # -----------------------------------------------------
    # TABLAS APP (REST)
    # -----------------------------------------------------
    def fetch_profiles(self, family_id: Optional[str] = None, limit: int = 50) -> Any:
        client = self.get_client(use_service_role=False)
        query = client.table("profiles").select("*").limit(limit)

        if family_id:
            query = query.eq("family_id", family_id)

        return query.execute()

    def fetch_recent_cases(self, limit: int = 20) -> Any:
        client = self.get_client(use_service_role=False)
        return (
            client.table("ng_case_memory")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )

    def insert_case(self, payload: Dict[str, Any]) -> Any:
        client = self.get_client(use_service_role=True)
        return client.table("ng_case_memory").insert(payload).execute()

    def insert_response_memory(self, payload: Dict[str, Any]) -> Any:
        client = self.get_client(use_service_role=True)
        return client.table("response_memory").insert(payload).execute()

    # -----------------------------------------------------
    # POSTGRES DIRECTO
    # -----------------------------------------------------
    def test_postgres(self) -> Dict[str, Any]:
        return self.pg.test_connection()

    def validate_schema(self) -> Dict[str, Any]:
        return self.pg.schema_exists()

    def list_tables(self) -> List[Dict[str, Any]]:
        return self.pg.list_tables()

    def get_table_columns(self, table_name: str) -> List[Dict[str, Any]]:
        return self.pg.get_table_columns(table_name)

    def close(self) -> None:
        try:
            close_method = getattr(self.pg, "close", None)
            if callable(close_method):
                close_method()
        except Exception:
            pass


def get_supabase_adapter(env_path: str = ".env") -> SupabaseAdapter:
    return SupabaseAdapter(env_path=env_path)
