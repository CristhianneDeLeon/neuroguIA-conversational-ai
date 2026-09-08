# neuroguIA — Congelamiento técnico para defensa 2026

## Propósito

Este documento establece los elementos de neuroguIA que permanecen congelados durante la preparación técnica para la defensa de tesis.

La fuente académica rectora es la tesis final:

**“Inteligencia Artificial basada en Procesamiento de Lenguaje Natural (PLN) para el apoyo socioemocional en contextos de neurodivergencia: diseño y validación en madres y cuidadores.”**

Universidad Politécnica Metropolitana de Hidalgo, septiembre de 2026.

Los cambios realizados durante el cierre para defensa tienen como finalidad:

- verificar funcionamiento;
- fortalecer pruebas;
- mejorar reproducibilidad;
- corregir errores técnicos;
- mejorar tolerancia a fallos;
- documentar el estado del repositorio;
- asegurar congruencia entre código, dashboard y documentación.

Estos cambios no redefinen retrospectivamente la intervención experimental.

---

## 1. Evolución tecnológica congelada

La evolución documentada de neuroguIA permanece definida como:

- V1–V3: validación inicial mediante conversación básica y categorías temáticas.
- V5–V7: clasificación estructurada, rutas conversacionales y organización funcional.
- V10: memoria contextual y perfiles familiares.
- V14: consolidación mediante recuperación semántica, personalización y arquitectura híbrida.

No se crearán nuevas denominaciones de versión para reinterpretar el sistema descrito en la tesis.

---

## 2. Arquitectura tecnológica congelada

La arquitectura documentada para neuroguIA conserva los siguientes componentes:

- Streamlit como interfaz.
- Python y lógica modular como motor conversacional.
- TF-IDF para representación textual clásica.
- Regresión logística para clasificación supervisada.
- Sentence-Transformers para representación semántica.
- `all-MiniLM-L6-v2` como modelo de embeddings.
- Similitud coseno para recuperación semántica.
- Base de conocimiento y mecanismo RAG.
- Memoria contextual persistente.
- Supabase/PostgreSQL como infraestructura de persistencia.
- OpenAI Responses API como componente generativo supervisado.
- Reglas, verificaciones funcionales y fallback como mecanismos de validación y seguridad.

La generación mediante modelo de lenguaje no sustituye las decisiones críticas del sistema.

---

## 3. Taxonomías

La tesis distingue tres niveles que no deben confundirse:

1. Clasificador histórico:
   - 1,020 registros.
   - 9 categorías.
   - Accuracy histórica: 0.93.
   - F1 macro: 0.931.

2. Corpus operativo reproducible:
   - 6,463 registros.
   - 7 categorías técnicas.

3. Interfaz funcional consolidada:
   - 7 propósitos funcionales:
     - Regulación emocional.
     - Acompañamiento escolar.
     - Organización familiar.
     - Regulación sensorial.
     - Bienestar del cuidador.
     - Manejo de crisis.
     - Rutinas y hábitos.

Estas capas cumplen funciones distintas y no deben convertirse artificialmente en una sola taxonomía.

---

## 4. Diseño experimental congelado

- Muestra total: 562 participantes.
- Grupo experimental: 281.
- Grupo control no equivalente: 281.
- Semana preparatoria y pretest: 5–11 de enero de 2026.
- Intervención activa: 12 de enero–17 de mayo de 2026.
- Duración de la intervención: 18 semanas completas.
- Postest y cierre: 18–21 de mayo de 2026.

---

## 5. Registros experimentales

Durante la ventana experimental se conservan como cifras oficiales:

- 1,325 sesiones.
- 10,212 mensajes.

Los indicadores correspondientes al corpus técnico completo deben mantenerse diferenciados de los registros pertenecientes exclusivamente a la intervención experimental.

---

## 6. Principio de no retroactividad

Las mejoras implementadas después del cierre experimental pueden fortalecer:

- continuidad conversacional;
- tolerancia a fallos;
- persistencia;
- recuperación de memoria;
- rutinas;
- validaciones;
- pruebas;
- documentación.

Estas mejoras deben identificarse como consolidación técnica posterior y no como funcionalidades añadidas retrospectivamente al periodo experimental.

---

## 7. Regla para la defensa

Ninguna modificación realizada en la rama `defensa-2026` podrá alterar:

- resultados estadísticos;
- tamaño de muestra;
- periodo experimental;
- duración de la intervención;
- evolución histórica de versiones;
- métricas históricas del clasificador;
- interpretación de la hipótesis;
- resultados psicométricos;
- resultados de uso;
- conclusiones de la tesis.

Toda modificación debe ser trazable mediante GitHub y estar orientada exclusivamente al cierre técnico y documental del sistema.
