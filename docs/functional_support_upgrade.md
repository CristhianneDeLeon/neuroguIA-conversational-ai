# Categorías funcionales y generación de rutinas en neuroguIA

## Propósito de la mejora

La aplicación conservaba categorías técnicas útiles para el motor conversacional, pero no exponía de forma completa la taxonomía funcional comprometida en la tesis. Además, varias rutas comunes devolvían orientación general sin construir una rutina visible, aunque la necesidad del turno sí se beneficiara de una secuencia práctica.

La actualización mantiene las categorías técnicas para no romper la trazabilidad histórica y agrega una segunda capa funcional orientada al tipo de apoyo que necesita la persona.

## Taxonomía funcional incorporada

| Categoría | Propósito principal | Rutina predeterminada |
|---|---|---|
| Regulación emocional | Apoyo para el manejo de emociones y situaciones de estrés | `emotional_landing` |
| Acompañamiento escolar | Estrategias relacionadas con tareas, aprendizaje y organización académica | `school_support` |
| Organización familiar | Planificación de actividades y distribución de responsabilidades | `family_organization` |
| Regulación sensorial | Orientaciones para situaciones de sobrecarga o saturación sensorial | `sensory_regulation` |
| Bienestar del cuidador | Estrategias dirigidas al autocuidado y reducción del agotamiento | `caregiver_recovery` |
| Manejo de crisis | Acciones orientadas a situaciones de alta intensidad emocional | `crisis_safety` |
| Rutinas y hábitos | Organización de actividades cotidianas y seguimiento de objetivos | `daily_habits` |

## Archivos incorporados

### `core/functional_category_router.py`

Clasifica cada turno en una de las siete categorías funcionales. La clasificación combina:

- señales textuales del mensaje;
- categoría técnica existente;
- estado funcional detectado;
- contexto escolar, familiar, sensorial o de cuidado;
- continuidad con el turno anterior.

La salida incluye clave, nombre legible, propósito, confianza, señales detectadas y rutina sugerida.

### `core/routine_activation_engine.py`

Decide si una rutina debe generarse. No crea rutinas en todos los turnos: pondera solicitudes explícitas, necesidades prácticas, intensidad emocional, capacidad del cuidador, crisis activa y rechazo expreso de la persona.

También evita repetir el mismo bloque completo en dos seguimientos consecutivos. La supresión no se aplica cuando:

- la persona vuelve a pedir expresamente una rutina;
- cambia el tipo de necesidad;
- persiste una crisis activa y la seguridad sigue siendo prioritaria.

### `core/routine_builder_v2.py`

Extiende el constructor ya existente y agrega rutinas específicas para:

- seguridad durante crisis;
- acompañamiento escolar;
- coordinación familiar;
- hábitos cotidianos.

Las rutinas previas de regulación emocional, regulación sensorial, sueño, bloqueo ejecutivo, recuperación del cuidador y recuperación posterior a crisis siguen disponibles.

Cada rutina se devuelve como estructura de datos y también se convierte en texto visible para la interfaz.

## Archivos modificados

### `core/orchestrator_v2.py`

El orquestador ahora:

1. conserva la categoría técnica;
2. determina la categoría funcional;
3. evalúa si corresponde generar rutina;
4. construye una rutina adaptada;
5. integra sus pasos en el texto de respuesta;
6. devuelve metadatos de categoría, activación y rutina;
7. evita la repetición inmediata de la misma rutina.

La integración se aplica tanto al flujo normal como a las rutas deterministas de demostración estable y a los flujos de apoyo que antes omitían la construcción de rutinas.

### `app.py`

Se agregó un acceso visible **“Crear una rutina”** en los botones de ayuda rápida. El botón envía una solicitud explícita al motor, por lo que la rutina se adapta a la necesidad descrita en la conversación.

## Criterios de activación

Una rutina se genera cuando ocurre al menos una combinación suficiente de señales, por ejemplo:

- solicitud explícita: “necesito una rutina”, “hazme un plan”, “paso a paso”;
- tarea o actividad escolar que no puede iniciarse;
- responsabilidades familiares sin distribución clara;
- sobrecarga sensorial;
- agotamiento del cuidador;
- hábito o secuencia cotidiana que necesita estructura;
- necesidad emocional acompañada de una petición práctica;
- crisis activa, en cuyo caso se genera una secuencia corta de seguridad.

No se genera cuando la persona dice que no quiere una rutina o realiza una pregunta metaconversacional sobre la aplicación.

## Validación

Desde la raíz del proyecto:

```powershell
python -m py_compile `
  core\functional_category_router.py `
  core\routine_activation_engine.py `
  core\routine_builder_v2.py `
  core\orchestrator_v2.py `
  app.py
```

Después:

```powershell
python scripts\validate_functional_support.py
```

La prueba valida las siete categorías, la visibilidad de las rutinas, el rechazo expreso, la no repetición consecutiva y la continuidad de la secuencia de seguridad en una crisis activa.

También puede ejecutarse la validación conversacional previa:

```powershell
python scripts\validate_conversation_behavior.py --mode auto
```

## Privacidad y despliegue

Los archivos de esta actualización no contienen claves, contraseñas, tokens ni valores de `secrets.toml`. La configuración sensible debe seguir administrándose mediante variables de entorno o secretos de Streamlit.

## Alcance actual

Esta versión **genera, muestra y devuelve** las rutinas dentro del resultado del orquestador. No añade todavía persistencia automática en una tabla de rutinas, porque el proyecto contiene referencias históricas a nombres de tabla distintos. Esa persistencia debe implementarse en una fase separada, después de fijar un único esquema oficial, para no duplicar registros ni escribir en una tabla equivocada.
