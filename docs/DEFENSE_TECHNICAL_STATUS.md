# neuroguIA — Estado técnico de cierre para defensa 2026

## 1. Propósito

Este documento registra el estado técnico de neuroguIA utilizado para la preparación de la defensa de tesis.

Las actividades descritas aquí corresponden a consolidación, pruebas de regresión, reproducibilidad, persistencia, continuidad conversacional y tolerancia a fallos.

No modifican:

- la versión histórica documentada en la tesis;
- el diseño experimental;
- la muestra;
- los resultados estadísticos;
- las conclusiones;
- las cifras reportadas en el manuscrito final.

---

## 2. Rama técnica de cierre

La consolidación previa a defensa se realizó en:

`defensa-2026`

Esta rama se utilizó para aislar las pruebas y ajustes técnicos del código principal hasta confirmar que las modificaciones no introdujeran regresiones.

---

## 3. Contrato con la tesis

Se incorporó una validación automática que comprueba la conservación de elementos técnicos documentados en la tesis, entre ellos:

- arquitectura híbrida;
- recuperación semántica;
- modelo de embeddings `all-MiniLM-L6-v2`;
- OpenAI Responses API;
- siete propósitos funcionales consolidados;
- estructuras persistentes `ng_*`;
- componentes de memoria;
- rutinas;
- orquestación.

La finalidad de este contrato es evitar que los ajustes de cierre técnico contradigan el sistema documentado académicamente.

---

## 4. Persistencia SQLite ↔ PostgreSQL/Supabase

neuroguIA conserva dos entornos de persistencia:

- SQLite para desarrollo, pruebas y ejecución local;
- PostgreSQL/Supabase para persistencia estructurada en producción.

La infraestructura productiva utiliza estructuras canónicas:

- `ng_families`
- `ng_profiles`
- `ng_messages`
- `ng_case_memory`
- `ng_response_memory`
- `ng_user_context_memory`
- `ng_routines`

Los nombres históricos utilizados por algunos componentes se mantienen mediante una capa de compatibilidad, cuyo estado esperado es:

`COMPATIBLE_WITH_BRIDGE`

Esta compatibilidad se encuentra documentada y protegida mediante pruebas automatizadas.

---

## 5. Persistencia de rutinas

Durante la consolidación técnica se verificó que una rutina generada pueda:

1. asociarse a una familia;
2. asociarse a un perfil;
3. vincularse con el caso conversacional que la originó;
4. persistirse;
5. recuperarse posteriormente;
6. actualizarse;
7. desactivarse;
8. mantenerse aislada de otros perfiles.

La capa interna utiliza el contrato `routines`, compatible con:

`ng_routines`

en PostgreSQL/Supabase.

---

## 6. Continuidad conversacional de rutinas

También se comprobó el flujo de continuidad entre sesiones.

El sistema puede:

- generar una rutina;
- persistirla;
- cerrar una sesión;
- recuperar la rutina en una sesión posterior;
- identificarla dentro del perfil activo;
- mostrarla mediante conversación;
- modificar pasos mediante lenguaje natural;
- persistir la modificación;
- recuperar posteriormente la versión modificada.

Las operaciones se limitan al ámbito de familia y perfil correspondiente.

---

## 7. Puerta automática de validación

El ejecutor:

`scripts/run_defense_checks.py`

concentra las validaciones técnicas obligatorias.

Estado final comprobado:

### 10/10 verificaciones superadas

1. `thesis_contract`
2. `supabase_bridge_contract`
3. `functional_support`
4. `routine_delivery`
5. `routine_persistence`
6. `orchestrator_routine_persistence`
7. `routine_conversational_recall`
8. `routine_conversational_update`
9. `gateway_contract`
10. `conversation_continuity`

Resultado esperado:

`ESTADO DE DEFENSA: VALIDACIONES BASE SUPERADAS`

---

## 8. Automatización mediante GitHub Actions

El workflow:

`.github/workflows/defense-validation.yml`

ejecuta automáticamente las comprobaciones técnicas sobre la rama de defensa.

El pipeline incluye:

- descarga del repositorio;
- configuración de Python;
- instalación de dependencias;
- compilación del código;
- auditoría de persistencia;
- ejecución de las validaciones;
- generación de evidencia técnica.

Los resultados se almacenan en:

`validation_outputs/`

y como artefacto del workflow.

---

## 9. Alcance de las validaciones

Las validaciones anteriores son pruebas técnicas de:

- regresión;
- integración;
- persistencia;
- continuidad;
- separación por contexto;
- compatibilidad de infraestructura;
- cumplimiento del contrato técnico documentado.

No constituyen una nueva intervención experimental ni sustituyen los análisis científicos reportados en la tesis.

---

## 10. Estado de cierre

Al momento del cierre para defensa:

`10/10 VALIDACIONES BASE SUPERADAS`

La implementación conserva congruencia con el sistema documentado en la tesis y cuenta con mecanismos automatizados para detectar regresiones durante cambios posteriores.

---

## 11. Reglas posteriores al cierre

Después de este estado:

- no deben introducirse cambios funcionales no indispensables antes de la defensa;
- cualquier modificación deberá ejecutar nuevamente la puerta automática;
- no deben alterarse cifras históricas ni resultados experimentales;
- no deben añadirse credenciales ni secretos al repositorio;
- los datos utilizados para distribución deben permanecer anonimizados.
