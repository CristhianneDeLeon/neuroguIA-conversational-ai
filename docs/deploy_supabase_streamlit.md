# Deploy real: Supabase + Streamlit Community Cloud

## Supabase
1. Crea un proyecto en Supabase.
2. Abre el SQL Editor.
3. Ejecuta `schema_supabase.sql`.
4. En el panel Connect, copia tu cadena de conexión PostgreSQL.
5. Si tu entorno necesita IPv4, usa el pooler / Supavisor que aparece en Connect.

## Variables locales
1. Copia `.env.example` como `.env`.
2. Llena:
   - DB_BACKEND=postgres
   - DATABASE_URL=...
   - SUPABASE_URL=...
   - SUPABASE_ANON_KEY=...
   - SUPABASE_SERVICE_ROLE_KEY=...

## Repositorio
Sube:
- app.py
- database.py
- database_postgres.py
- supabase_adapter.py
- schema_supabase.sql
- requirements.txt
- todos los módulos premium

## Streamlit Community Cloud
1. Subir tu proyecto a GitHub.
2. Iniciar sesión en Streamlit Community Cloud.
3. Elegir Deploy an app.
4. Seleccionar el repo y el entrypoint `app.py`.
5. En Secrets, se pega el contenido equivalente a `secrets.toml`.
6. Realizar deploy.

## Verificación posterior
- crear una unidad
- crear un perfil
- procesar un caso
- verificar inserciones en families, profiles, ng_case_memory y response_memory
