# Corrección integral del dashboard neuroguIA · v3

## Problemas encontrados en la versión anterior

1. `dashboard_data_loader.py` reemplazaba la cronología real con una tabla fija de 16 semanas.
2. `dashboard.py` contenía cifras incrustadas: 46,820 mensajes, 28.65 % de reducción del estrés y 16 semanas.
3. El uso técnico completo se presentaba como si correspondiera íntegramente al periodo experimental.
4. MSPSS agregado, apoyo auxiliar individual y una reconstrucción calibrada aparecían sin una separación suficientemente visible.
5. El módulo histórico de PLN y el corpus operativo se interpretaban como una sola evaluación.
6. Las exportaciones CSV podían quedar desactualizadas aunque se modificara el Excel maestro.
7. Existían varias copias de `dashboard.py`, lo que dificultaba identificar la versión desplegada.

## Cambios aplicados

- Fuente única: `data/NeuroGuIA_Documento_Maestro_Oficial_v3_AUDITADO.xlsx`.
- Once secciones construidas desde las hojas canónicas.
- Validación automática de participantes, familias, semanas, sesiones y crosswalk.
- Separación entre 1,325 sesiones de intervención y 6,463 sesiones técnicas.
- DASS-21 con pre/post, ANCOVA, supuestos, no paramétricas, Cohen d, Hedges g e IC95%.
- MSPSS oficial agregado separado del índice auxiliar individual.
- WHOQOL enlazado mediante EXP/CON ↔ PT ↔ FAM.
- Uso semanal de 18 semanas y cuatro días de postest/cierre.
- Correlaciones diferenciadas para muestra total y grupo experimental.
- PLN histórico separado del módulo operativo reproducible.
- Usabilidad sin fabricar alfas ni respuestas por reactivo ausentes.
- Panel de metodología, faltantes, exclusiones, Boateng–COSMIN y reproducibilidad.
- Descarga directa del Excel, script, JSON y tablas CSV.
- Datos individuales ocultos por defecto; auditoría mediante `DASHBOARD_AUDIT_MODE=true`.


## v3.1 privacidad de despliegue

- Se retiró la descarga pública del Excel maestro.
- Se retiró la exportación de tablas individuales.
- La descarga del dashboard contiene únicamente tablas agregadas.
- Se eliminó el `app.py` alternativo para evitar seleccionar un entrypoint incorrecto.
