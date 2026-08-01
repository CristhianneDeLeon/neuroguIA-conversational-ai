# neuroguIA · Dashboard de investigación conectado a Supabase

Panel científico para visualizar los resultados consolidados de neuroguIA a partir de las vistas canónicas creadas en Supabase.

## Fuente de datos

El dashboard consulta en modo de solo lectura:

- `v_dashboard_kpis`
- `v_dashboard_sessions`
- `v_dashboard_prepost`
- `v_dashboard_usage`
- `v_dashboard_categories`
- `v_dashboard_states`
- `v_dashboard_time_bands`
- `v_dashboard_weeks`
- `v_dashboard_whoqol`
- `v_whoqol_participant_scores`

Cuando `DATABASE_URL` no está configurada, utiliza los archivos locales disponibles únicamente como respaldo de desarrollo.

## Ejecución local

```powershell
cd "D:\Documents\00_MIA\000 TESIS NeuroGuía\01_ CÓDIGO_NEUROGUÍA\neuroguIA_dashboard"
pip install -r requirements.txt
streamlit run dashboard.py --server.port 8502
```

Crea `.streamlit/secrets.toml` con:

```toml
DATABASE_URL = "TU_CADENA_DE_CONEXION_SESSION_POOLER"
```

No compartas ese archivo ni lo subas a GitHub.

## Publicación en Streamlit Community Cloud

1. Sube esta carpeta a un repositorio privado o público sin credenciales.
2. Despliega `dashboard.py` como archivo principal.
3. En **Settings → Secrets**, agrega `DATABASE_URL`.
4. Copia la URL pública generada.
5. En los secretos de la aplicación principal de neuroguIA agrega:

```toml
DASHBOARD_URL = "https://URL-DEL-DASHBOARD.streamlit.app"
```

Con ello aparecerá habilitado el botón **Abrir dashboard** dentro de neuroguIA.
