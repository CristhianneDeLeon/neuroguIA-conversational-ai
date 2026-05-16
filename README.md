# 🧠 neuroguIA

**neuroguIA** es un sistema conversacional híbrido orientado al **apoyo socioemocional y funcional en contextos de neurodivergencia**, diseñado para acompañar a personas usuarias, cuidadores y docentes.

Su propósito es ofrecer un acompañamiento **cálido, claro y adaptativo**, sin sustituir atención clínica, combinando múltiples enfoques de inteligencia artificial bajo un modelo **seguro, controlado y supervisado**.

---

## ✨ ¿Qué hace neuroguIA?

neuroguIA no solo responde:  
**interpreta, organiza, acompaña y personaliza la conversación.**

Entre sus capacidades principales:

### 🧠 Interpretación
- clasificación de intención conversacional
- identificación de categorías funcionales
- detección de estados como:
  - meltdown
  - shutdown
  - burnout
  - disfunción ejecutiva
  - sobrecarga sensorial

### ⚙️ Decisión
- selección de estrategias adaptativas
- generación de microacciones y rutinas
- sistema de confianza basado en múltiples señales

### 💬 Respuesta
- generación de respuestas cálidas y estructuradas
- fallback seguro a generación local
- integración opcional con LLM

### 🔁 Aprendizaje supervisado
- memoria contextual por usuario o sesión
- curación de conversaciones valiosas
- base para mejora iterativa supervisada

---

## 🏗️ Arquitectura de Inteligencia Artificial

neuroguIA implementa una arquitectura híbrida de múltiples capas:

### 1. 🔵 Reglas y lógica interna (núcleo)
Controlan la clasificación, decisión y seguridad del sistema.

---

### 2. 🟢 Aprendizaje automático clásico
Baseline interpretable con:
- `TF-IDF`
- `Logistic Regression`

👉 Se usa como señal auxiliar, no como decisión principal.

---

### 3. 🟣 Similitud semántica (embeddings)
Implementada con:
- `sentence-transformers`
- modelo: `all-MiniLM-L6-v2`

👉 Permite comparar significado, no solo palabras.

---

### 4. 🟡 Generación con LLM (IA generativa)
Integración con OpenAI mediante:
- `core/llm_gateway.py`

Características:
- generación controlada
- fallback automático
- no delega decisiones críticas al LLM

---

### 5. 🧠 Memoria contextual y curación
- memoria supervisada (no invasiva)
- registro de conversaciones valiosas
- sin aprendizaje automático en vivo

---

## 🧩 Funcionalidades principales

- clasificación de intención y categoría
- detección de estado funcional
- decisiones adaptativas
- memoria contextual por sesión
- curación supervisada
- reutilización de respuestas útiles
- soporte multi-backend (SQLite, PostgreSQL, Supabase)
- interfaz con Streamlit

---

## 📁 Estructura del proyecto

```text
neuroguIA/
├── app.py
├── predeploy_check.py
├── validate_experiment.py
├── requirements.txt
├── schema_supabase.sql
├── README.md
├── .gitignore
├── .env.example
├── assets/
├── core/
├── memory/
├── database/
├── scripts/
├── docs/
└── validation_outputs/
---

### 👩‍💻 Autor:
**Cristhianne De León Vargas**