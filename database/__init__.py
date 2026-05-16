# database/__init__.py

from .database import (
    NeuroGuiaDB,
    DatabaseConfig,
    initialize_database,
    load_env_file,
    str_to_bool,
)

from .database_postgres import (
    PostgresDatabase,
    PostgresConfig,
)

from .supabase_adapter import (
    SupabaseAdapter,
    get_supabase_adapter,
)


def get_database(
    db_path: str = "neuroguia.db",
    backend: str | None = None,
    env_path: str = ".env",
) -> NeuroGuiaDB:
    """
    Devuelve una instancia del adaptador principal de base de datos.
    Sirve para mantener compatibilidad con app.py y otros módulos.
    """
    return NeuroGuiaDB(
        db_path=db_path,
        backend=backend,
        env_path=env_path,
    )


__all__ = [
    "NeuroGuiaDB",
    "DatabaseConfig",
    "initialize_database",
    "load_env_file",
    "str_to_bool",
    "PostgresDatabase",
    "PostgresConfig",
    "SupabaseAdapter",
    "get_supabase_adapter",
    "get_database",
]