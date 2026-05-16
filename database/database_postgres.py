from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Generator, Iterable, List, Optional

try:
    import psycopg
    from psycopg.rows import dict_row
except Exception:  # pragma: no cover
    psycopg = None
    dict_row = None


# =========================================================
# UTILIDADES DE ENTORNO
# =========================================================
def load_env_file(env_path: str = ".env") -> None:
    """
    Carga un archivo .env simple sin depender de python-dotenv.
    No sobreescribe variables ya existentes.
    """
    path = Path(env_path)
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and key not in os.environ:
            os.environ[key] = value


def str_to_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


# =========================================================
# CONFIG
# =========================================================
@dataclass
class PostgresConfig:
    backend: str = "postgres"
    database_url: Optional[str] = None
    host: Optional[str] = None
    port: int = 5432
    database: Optional[str] = None
    user: Optional[str] = None
    password: Optional[str] = None
    sslmode: str = "require"

    @classmethod
    def from_env(cls, env_path: str = ".env") -> "PostgresConfig":
        load_env_file(env_path)

        return cls(
            backend=os.getenv("DB_BACKEND", "postgres"),
            database_url=os.getenv("DATABASE_URL"),
            host=os.getenv("POSTGRES_HOST"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            database=os.getenv("POSTGRES_DB", "postgres"),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD"),
            sslmode=os.getenv("POSTGRES_SSLMODE", "require"),
        )

    def build_dsn(self) -> str:
        if self.database_url:
            return self.database_url

        if not all([self.host, self.database, self.user, self.password]):
            raise ValueError(
                "Faltan variables de entorno para PostgreSQL. "
                "Configura DATABASE_URL o POSTGRES_HOST / POSTGRES_DB / POSTGRES_USER / POSTGRES_PASSWORD."
            )

        return (
            f"postgresql://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
            f"?sslmode={self.sslmode}"
        )


# =========================================================
# CONEXIÓN POSTGRES
# =========================================================
class PostgresDatabase:
    """
    Adaptador limpio para PostgreSQL / Supabase.

    Úsalo para:
    - probar conexión
    - ejecutar consultas
    - validar que el esquema exista
    - integrar poco a poco NeuroGuía con Supabase
    """

    def __init__(self, config: Optional[PostgresConfig] = None, env_path: str = ".env") -> None:
        if psycopg is None:
            raise ImportError(
                "psycopg no está instalado. Instala con: pip install psycopg[binary]"
            )

        self.config = config or PostgresConfig.from_env(env_path=env_path)
        self.dsn = self.config.build_dsn()
        self._last_connection: Optional[Any] = None

    def connect(self):
        conn = psycopg.connect(self.dsn, row_factory=dict_row)
        self._last_connection = conn
        return conn

    @contextmanager
    def connection(self) -> Generator[Any, None, None]:
        conn = self.connect()
        try:
            yield conn
        finally:
            try:
                conn.close()
            except Exception:
                pass
            if self._last_connection is conn:
                self._last_connection = None

    @contextmanager
    def cursor(self) -> Generator[Any, None, None]:
        with self.connection() as conn:
            with conn.cursor() as cur:
                yield cur
                conn.commit()

    # -----------------------------------------------------
    # QUERIES BÁSICAS
    # -----------------------------------------------------
    def execute(
        self,
        query: str,
        params: Optional[Iterable[Any]] = None,
        fetch: bool = False,
        fetch_one: bool = False,
    ) -> Optional[Any]:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params or ())
                result = None
                if fetch_one:
                    result = cur.fetchone()
                elif fetch:
                    result = cur.fetchall()
                conn.commit()
                return result

    def test_connection(self) -> Dict[str, Any]:
        result = self.execute(
            "select current_database() as db, now() as server_time;",
            fetch_one=True,
        )
        return {
            "ok": True,
            "database": result["db"] if result else None,
            "server_time": str(result["server_time"]) if result else None,
            "backend": self.config.backend,
        }

    def list_tables(self, schema: str = "public") -> List[Dict[str, Any]]:
        query = """
        select table_schema, table_name
        from information_schema.tables
        where table_schema = %s
        order by table_name;
        """
        rows = self.execute(query, (schema,), fetch=True) or []
        return list(rows)

    def get_table_columns(self, table_name: str, schema: str = "public") -> List[Dict[str, Any]]:
        query = """
        select column_name, data_type, is_nullable
        from information_schema.columns
        where table_schema = %s and table_name = %s
        order by ordinal_position;
        """
        rows = self.execute(query, (schema, table_name), fetch=True) or []
        return list(rows)

    def schema_exists(self, expected_tables: Optional[List[str]] = None) -> Dict[str, Any]:
        expected_tables = expected_tables or [
            "app_meta",
            "families",
            "profiles",
            "ng_case_memory",
            "learned_patterns",
            "response_memory",
            "user_context_memory",
            "conversation_curation",
            "routines",
        ]
        found_rows = self.list_tables(schema="public")
        found = {row["table_name"] for row in found_rows}

        missing = [table for table in expected_tables if table not in found]
        return {
            "ok": len(missing) == 0,
            "expected_tables": expected_tables,
            "found_tables": sorted(found),
            "missing_tables": missing,
        }

    # -----------------------------------------------------
    # HELPERS ÚTILES PARA MIGRACIÓN
    # -----------------------------------------------------
    def fetch_profiles(self, family_id: Optional[str] = None, only_active: bool = True) -> List[Dict[str, Any]]:
        conditions = []
        params: List[Any] = []

        if family_id:
            conditions.append("family_id = %s")
            params.append(family_id)

        if only_active:
            conditions.append("is_active = true")

        where_clause = ""
        if conditions:
            where_clause = "where " + " and ".join(conditions)

        query = f"""
        select *
        from public.profiles
        {where_clause}
        order by updated_at desc;
        """
        rows = self.execute(query, params, fetch=True) or []
        return list(rows)

    def fetch_recent_cases(self, limit: int = 20) -> List[Dict[str, Any]]:
        query = """
        select *
        from public.ng_case_memory
        order by created_at desc
        limit %s;
        """
        rows = self.execute(query, (limit,), fetch=True) or []
        return list(rows)

    def fetch_reusable_responses(self, limit: int = 20) -> List[Dict[str, Any]]:
        query = """
        select *
        from public.response_memory
        where is_active = true
        order by approved_for_reuse desc, updated_at desc
        limit %s;
        """
        rows = self.execute(query, (limit,), fetch=True) or []
        return list(rows)

    # -----------------------------------------------------
    # CIERRE
    # -----------------------------------------------------
    def close(self) -> None:
        """
        Mantiene compatibilidad con adaptadores superiores.
        Normalmente las conexiones ya se cierran por contexto, pero este método
        permite cierre explícito seguro si alguna conexión quedó referenciada.
        """
        if self._last_connection is not None:
            try:
                self._last_connection.close()
            except Exception:
                pass
            finally:
                self._last_connection = None


# =========================================================
# FUNCIONES DE CONVENIENCIA
# =========================================================
def get_postgres_db(env_path: str = ".env") -> PostgresDatabase:
    return PostgresDatabase(env_path=env_path)


def test_postgres_connection(env_path: str = ".env") -> Dict[str, Any]:
    db = PostgresDatabase(env_path=env_path)
    try:
        return db.test_connection()
    finally:
        db.close()


def validate_supabase_schema(env_path: str = ".env") -> Dict[str, Any]:
    db = PostgresDatabase(env_path=env_path)
    try:
        return db.schema_exists()
    finally:
        db.close()
