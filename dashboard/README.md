# neuroguIA · Dashboard científico v3.1

Dashboard Streamlit alineado con `NeuroGuIA_Documento_Maestro_Oficial_v3_AUDITADO.xlsx`.

## Regla de privacidad

Este repositorio debe permanecer **privado**, porque contiene el documento maestro con
registros pseudonimizados. El dashboard puede compartirse públicamente desde Streamlit,
pero el código no ofrece la descarga del Excel maestro ni de tablas individuales.

Nunca subas:

- `.streamlit/secrets.toml`
- `.env`
- claves de OpenAI, Supabase o PostgreSQL

## Estructura

```text
.streamlit/config.toml
assets/
data/NeuroGuIA_Documento_Maestro_Oficial_v3_AUDITADO.xlsx
exports/NeuroGuIA_resultados_reproducidos_v3.json
dashboard.py
dashboard_data_loader.py
dashboard_selfcheck.py
neuroguia_analisis_oficial_v3.py
requirements.txt
README.md
CAMBIOS_V3.md
MANIFESTO_DASHBOARD_V3.json
TEST_REPORT.txt
.gitignore
```

## Ejecución local

```bash
python dashboard_selfcheck.py
streamlit run dashboard.py
```

## Despliegue en Streamlit Community Cloud

Selecciona:

- Repositorio: el repositorio privado del dashboard
- Rama: `main`
- Main file path: `dashboard.py`

En Secrets configura como mínimo:

```toml
DASHBOARD_AUDIT_MODE = false
```

Después copia la URL pública generada y agrégala en los Secrets de la app principal:

```toml
DASHBOARD_URL = "https://TU-DASHBOARD.streamlit.app"
```

## Fuente canónica

El maestro debe permanecer en:

```text
data/NeuroGuIA_Documento_Maestro_Oficial_v3_AUDITADO.xlsx
```

La ruta puede sustituirse localmente con `NEUROGUIA_MASTER_XLSX`.
