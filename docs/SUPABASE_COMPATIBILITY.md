# Compatibilidad de persistencia SQLite ↔ Supabase

## Propósito

neuroguIA conserva compatibilidad entre dos entornos de persistencia:

- SQLite para ejecución local, desarrollo y pruebas sin infraestructura externa.
- PostgreSQL/Supabase para persistencia estructurada en el despliegue web.

Esta compatibilidad forma parte de la consolidación técnica del sistema y no modifica
la versión histórica V14 ni los resultados experimentales documentados en la tesis.

---

## 1. Nomenclatura canónica en Supabase

La infraestructura persistente documentada para el despliegue utiliza las siguientes
estructuras canónicas:

- `ng_families`
- `ng_profiles`
- `ng_messages`
- `ng_case_memory`
- `ng_response_memory`
- `ng_user_context_memory`
- `ng_routines`

Estas estructuras corresponden a las entidades descritas en la tesis final.

---

## 2. Nomenclatura de compatibilidad local

El backend SQLite conserva algunos nombres históricos utilizados durante el desarrollo:

- `families`
- `profiles`
- `response_memory`
- `user_context_memory`
- `routines`

`ng_case_memory` conserva la misma denominación en ambos entornos.

La permanencia de estos nombres evita romper la ejecución local y permite mantener
compatibilidad con código desarrollado durante distintas etapas de neuroguIA.

---

## 3. Puente PostgreSQL/Supabase

Cuando neuroguIA se ejecuta con PostgreSQL/Supabase, `app.py` implementa una capa de
compatibilidad entre las referencias históricas y las tablas canónicas.

Correspondencias:

| Compatibilidad interna | Supabase canónico |
|---|---|
| `families` | `ng_families` |
| `profiles` | `ng_profiles` |
| `case_memory` | `ng_case_memory` |
| `response_memory` | `ng_response_memory` |
| `user_context_memory` | `ng_user_context_memory` |
| `routines` | `ng_routines` |
| `learned_patterns` | `ng_learned_patterns` |

De esta forma, los componentes que todavía utilizan la nomenclatura histórica pueden
operar sobre la infraestructura canónica de Supabase sin duplicar la información.

---

## 4. Interpretación técnica

El estado esperado del sistema puede describirse como:

`COMPATIBLE_WITH_BRIDGE`

Este estado no significa que existan dos bases productivas independientes ni dos fuentes
de verdad.

La infraestructura de producción utiliza las tablas canónicas `ng_*`.

Los nombres históricos se conservan exclusivamente como capa de compatibilidad para
componentes que también deben operar sobre SQLite.

---

## 5. Regla para la defensa

Durante el cierre técnico para defensa:

- no se sustituirán indiscriminadamente los nombres históricos por `ng_*`;
- no se modificarán las versiones documentadas en la tesis;
- no se modificarán resultados experimentales;
- no se realizarán migraciones destructivas sobre Supabase;
- cualquier modificación de persistencia deberá conservar compatibilidad SQLite y PostgreSQL;
- la integridad del puente se comprobará mediante pruebas automatizadas.

---

## 6. Alcance

La existencia del puente garantiza compatibilidad estructural.

Las funciones concretas de persistencia y recuperación —incluidas las rutinas— deben
validarse adicionalmente mediante pruebas funcionales de extremo a extremo.
