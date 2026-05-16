from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, Iterable, List, Optional

try:
    import psycopg
    from psycopg.rows import dict_row
except Exception:  # pragma: no cover
    psycopg = None
    dict_row = None


# =========================================================
# ENV HELPERS
# =========================================================
def load_env_file(env_path: str = ".env") -> None:
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
class DatabaseConfig:
    def __init__(
        self,
        backend: str = "sqlite",
        sqlite_db_path: str = "neuroguia.db",
        database_url: Optional[str] = None,
        postgres_host: Optional[str] = None,
        postgres_port: int = 5432,
        postgres_db: str = "postgres",
        postgres_user: str = "postgres",
        postgres_password: Optional[str] = None,
        postgres_sslmode: str = "require",
    ) -> None:
        self.backend = backend
        self.sqlite_db_path = sqlite_db_path
        self.database_url = database_url
        self.postgres_host = postgres_host
        self.postgres_port = postgres_port
        self.postgres_db = postgres_db
        self.postgres_user = postgres_user
        self.postgres_password = postgres_password
        self.postgres_sslmode = postgres_sslmode

    @classmethod
    def from_env(cls, env_path: str = ".env") -> "DatabaseConfig":
        load_env_file(env_path)
        return cls(
            backend=os.getenv("DB_BACKEND", "sqlite").strip().lower(),
            sqlite_db_path=os.getenv("SQLITE_DB_PATH", "neuroguia.db"),
            database_url=os.getenv("DATABASE_URL"),
            postgres_host=os.getenv("POSTGRES_HOST"),
            postgres_port=int(os.getenv("POSTGRES_PORT", "5432")),
            postgres_db=os.getenv("POSTGRES_DB", "postgres"),
            postgres_user=os.getenv("POSTGRES_USER", "postgres"),
            postgres_password=os.getenv("POSTGRES_PASSWORD"),
            postgres_sslmode=os.getenv("POSTGRES_SSLMODE", "require"),
        )

    def build_postgres_dsn(self) -> str:
        if self.database_url:
            return self.database_url

        if not all([self.postgres_host, self.postgres_db, self.postgres_user, self.postgres_password]):
            raise ValueError(
                "Faltan variables de entorno para PostgreSQL. "
                "Configura DATABASE_URL o POSTGRES_HOST / POSTGRES_DB / POSTGRES_USER / POSTGRES_PASSWORD."
            )

        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
            f"?sslmode={self.postgres_sslmode}"
        )


# =========================================================
# BACKEND ABSTRACTION
# =========================================================
class BaseBackend:
    backend_name: str = "base"

    def execute(
        self,
        query: str,
        params: Optional[Iterable[Any]] = None,
        fetch: bool = False,
        fetch_one: bool = False,
    ) -> Optional[Any]:
        raise NotImplementedError

    def get_table_columns(self, table_name: str) -> List[str]:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError


class SQLiteBackend(BaseBackend):
    backend_name = "sqlite"

    def __init__(self, db_path: str = "neuroguia.db") -> None:
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    def execute(
        self,
        query: str,
        params: Optional[Iterable[Any]] = None,
        fetch: bool = False,
        fetch_one: bool = False,
    ) -> Optional[Any]:
        cur = self.conn.cursor()
        cur.execute(query, tuple(params or ()))
        result = None
        if fetch_one:
            row = cur.fetchone()
            result = dict(row) if row else None
        elif fetch:
            rows = cur.fetchall()
            result = [dict(row) for row in rows]
        self.conn.commit()
        return result

    def get_table_columns(self, table_name: str) -> List[str]:
        rows = self.execute(f"PRAGMA table_info({table_name})", fetch=True) or []
        return [row["name"] for row in rows]

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass


class PostgresBackend(BaseBackend):
    backend_name = "postgres"

    def __init__(self, dsn: str) -> None:
        if psycopg is None:
            raise ImportError("psycopg no está instalado. Instala con: pip install psycopg[binary]")
        self.dsn = dsn
        self.conn = psycopg.connect(self.dsn, row_factory=dict_row)

    def _translate_query(self, query: str) -> str:
        # Traducción simple SQLite -> Postgres para placeholders.
        return query.replace("?", "%s")

    def execute(
        self,
        query: str,
        params: Optional[Iterable[Any]] = None,
        fetch: bool = False,
        fetch_one: bool = False,
    ) -> Optional[Any]:
        translated = self._translate_query(query)
        with self.conn.cursor() as cur:
            cur.execute(translated, tuple(params or ()))
            result = None
            if fetch_one:
                result = cur.fetchone()
            elif fetch:
                result = cur.fetchall()
            self.conn.commit()
            return result

    def get_table_columns(self, table_name: str) -> List[str]:
        rows = self.execute(
            """
            select column_name
            from information_schema.columns
            where table_schema = 'public' and table_name = %s
            order by ordinal_position
            """,
            (table_name,),
            fetch=True,
        ) or []
        return [row["column_name"] for row in rows]

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass


# =========================================================
# MAIN WRAPPER
# =========================================================
class NeuroGuiaDB:
    """
    Adaptador híbrido para NeuroGuía.

    Soporta:
    - SQLite para desarrollo local
    - PostgreSQL / Supabase para despliegue

    Mantiene una interfaz pequeña y estable para el resto de módulos.
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        backend: Optional[str] = None,
        env_path: str = ".env",
    ) -> None:
        self.config = DatabaseConfig.from_env(env_path=env_path)

        if backend:
            self.config.backend = backend.strip().lower()
        if db_path and (self.config.backend == "sqlite" or not self.config.backend):
            self.config.sqlite_db_path = db_path

        if self.config.backend == "postgres":
            self._backend = PostgresBackend(self.config.build_postgres_dsn())
        else:
            self._backend = SQLiteBackend(self.config.sqlite_db_path)

        # Compatibilidad con módulos existentes
        self.backend_name = self._backend.backend_name
        self.conn = getattr(self._backend, "conn", None)

    def execute(
        self,
        query: str,
        params: Optional[Iterable[Any]] = None,
        fetch: bool = False,
        fetch_one: bool = False,
    ) -> Optional[Any]:
        return self._backend.execute(query, params=params, fetch=fetch, fetch_one=fetch_one)

    def get_table_columns(self, table_name: str) -> List[str]:
        return self._backend.get_table_columns(table_name)

    def test_connection(self) -> Dict[str, Any]:
        if self.backend_name == "sqlite":
            return {
                "ok": True,
                "backend": "sqlite",
                "db_path": self.config.sqlite_db_path,
            }

        row = self.execute("select current_database() as db, now() as server_time", fetch_one=True)
        return {
            "ok": True,
            "backend": "postgres",
            "database": row["db"] if row else None,
            "server_time": str(row["server_time"]) if row else None,
        }

    def close(self) -> None:
        self._backend.close()


# =========================================================
# SQLITE SCHEMA INIT
# =========================================================
def initialize_database(db_path: str = "neuroguia.db") -> NeuroGuiaDB:
    """
    Inicializa SQLite local con el esquema mínimo que usan los módulos premium.
    Para PostgreSQL / Supabase se recomienda usar schema_supabase.sql.
    """
    db = NeuroGuiaDB(db_path=db_path, backend="sqlite")
    conn = db.conn
    cur = conn.cursor()

    # families
    cur.execute("""
    CREATE TABLE IF NOT EXISTS families (
        family_id TEXT PRIMARY KEY,
        unit_type TEXT DEFAULT 'individual',
        caregiver_alias TEXT,
        context_notes TEXT,
        support_network TEXT,
        environmental_factors TEXT,
        global_history TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # profiles
    cur.execute("""
    CREATE TABLE IF NOT EXISTS profiles (
        profile_id TEXT PRIMARY KEY,
        family_id TEXT,
        alias TEXT,
        age INTEGER,
        role TEXT,
        conditions TEXT,
        strengths TEXT,
        triggers TEXT,
        early_signs TEXT,
        helpful_strategies TEXT,
        harmful_strategies TEXT,
        sensory_needs TEXT,
        emotional_needs TEXT,
        autonomy_level TEXT,
        sleep_profile TEXT,
        school_profile TEXT,
        executive_profile TEXT,
        evolution_notes TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (family_id) REFERENCES families(family_id) ON DELETE CASCADE
    )
    """)

    # ng_case_memory
    cur.execute("""
    CREATE TABLE IF NOT EXISTS ng_case_memory (
        case_id TEXT PRIMARY KEY,
        family_id TEXT,
        profile_id TEXT,
        unit_type TEXT,
        created_at TEXT,
        updated_at TEXT,
        raw_input TEXT,
        normalized_summary TEXT,
        detected_category TEXT,
        detected_stage TEXT,
        primary_state TEXT,
        secondary_states TEXT,
        emotional_intensity REAL,
        caregiver_capacity REAL,
        sensory_overload_risk REAL,
        executive_block_risk REAL,
        meltdown_risk REAL,
        shutdown_risk REAL,
        burnout_risk REAL,
        sleep_disruption_risk REAL,
        suggested_strategy TEXT,
        suggested_microaction TEXT,
        suggested_routine_type TEXT,
        response_mode TEXT,
        user_feedback TEXT,
        observed_result TEXT,
        usefulness_score REAL,
        applied_successfully INTEGER DEFAULT 0,
        helps_patterns TEXT,
        worsens_patterns TEXT,
        followup_needed INTEGER DEFAULT 0,
        tags TEXT
    )
    """)

    # learned_patterns
    cur.execute("""
    CREATE TABLE IF NOT EXISTS learned_patterns (
        pattern_id TEXT PRIMARY KEY,
        family_id TEXT,
        profile_id TEXT,
        context_key TEXT,
        helps TEXT,
        worsens TEXT,
        confidence_level REAL,
        usage_count INTEGER,
        last_seen TEXT,
        created_at TEXT,
        updated_at TEXT
    )
    """)

    # response_memory
    cur.execute("""
    CREATE TABLE IF NOT EXISTS response_memory (
        response_id TEXT PRIMARY KEY,
        family_id TEXT,
        profile_id TEXT,
        detected_intent TEXT,
        detected_category TEXT,
        primary_state TEXT,
        conversation_stage TEXT,
        complexity_signature TEXT,
        conditions_signature TEXT,
        response_text TEXT,
        response_structure_json TEXT,
        source_type TEXT,
        confidence_score REAL,
        usefulness_score REAL,
        approved_for_reuse INTEGER DEFAULT 0,
        usage_count INTEGER DEFAULT 0,
        success_count INTEGER DEFAULT 0,
        failure_count INTEGER DEFAULT 0,
        avoid_rules TEXT,
        must_include TEXT,
        supporting_patterns TEXT,
        tags TEXT,
        llm_prompt_version TEXT,
        origin_case_id TEXT,
        notes TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TEXT,
        updated_at TEXT
    )
    """)

    # user_context_memory
    cur.execute("""
    CREATE TABLE IF NOT EXISTS user_context_memory (
        scope_key TEXT PRIMARY KEY,
        scope_type TEXT,
        family_id TEXT,
        profile_id TEXT,
        session_scope_id TEXT,
        inferred_user_role TEXT,
        role_confidence REAL,
        role_source TEXT,
        conversation_preferences_json TEXT,
        recurrent_topics_json TEXT,
        recurrent_signals_json TEXT,
        helpful_strategies_json TEXT,
        helpful_routines_json TEXT,
        last_useful_domain TEXT,
        last_useful_phase TEXT,
        summary_snapshot_json TEXT,
        source_case_id TEXT,
        created_at TEXT,
        updated_at TEXT
    )
    """)

    # conversation_curation
    cur.execute("""
    CREATE TABLE IF NOT EXISTS conversation_curation (
        curation_id TEXT PRIMARY KEY,
        dedupe_key TEXT,
        scope_key TEXT,
        scope_type TEXT,
        family_id TEXT,
        profile_id TEXT,
        session_scope_id TEXT,
        source_case_id TEXT,
        review_status TEXT,
        candidate_targets_json TEXT,
        review_notes TEXT,
        input_summary_json TEXT,
        detected_category TEXT,
        detected_intent TEXT,
        primary_state TEXT,
        secondary_states_json TEXT,
        conversation_domain TEXT,
        conversation_phase TEXT,
        speaker_role TEXT,
        signal_summary_json TEXT,
        response_text TEXT,
        response_structure_json TEXT,
        response_mode TEXT,
        generation_source TEXT,
        provider TEXT,
        model TEXT,
        used_stub_fallback INTEGER DEFAULT 0,
        fallback_reason TEXT,
        llm_enabled INTEGER DEFAULT 0,
        llm_quality_score REAL,
        llm_approved INTEGER DEFAULT 0,
        metadata_json TEXT,
        created_at TEXT,
        updated_at TEXT
    )
    """)

    cur.execute("""
    CREATE UNIQUE INDEX IF NOT EXISTS uq_conversation_curation_dedupe_key
    ON conversation_curation (dedupe_key)
    """)

    # routines
    cur.execute("""
    CREATE TABLE IF NOT EXISTS routines (
        routine_id TEXT PRIMARY KEY,
        family_id TEXT,
        profile_id TEXT,
        routine_type TEXT,
        routine_name TEXT,
        goal TEXT,
        steps TEXT,
        short_version TEXT,
        adjustments TEXT,
        indicators TEXT,
        followup_question TEXT,
        source_case_id TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    return db


# =========================================================
# FACTORIES
# =========================================================
def get_database(
    db_path: Optional[str] = None,
    backend: Optional[str] = None,
    env_path: str = ".env",
) -> NeuroGuiaDB:
    return NeuroGuiaDB(db_path=db_path, backend=backend, env_path=env_path)


def test_database_connection(
    db_path: Optional[str] = None,
    backend: Optional[str] = None,
    env_path: str = ".env",
) -> Dict[str, Any]:
    db = NeuroGuiaDB(db_path=db_path, backend=backend, env_path=env_path)
    try:
        return db.test_connection()
    finally:
        db.close()
