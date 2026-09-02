# -*- coding: utf-8 -*-
"""Valida la continuidad conversacional en respuestas de seguimiento."""

from __future__ import annotations

import sys
from pathlib import Path

# ---------------------------------------------------------
# Permite ejecutar este script directamente desde /scripts
# sin depender de una configuración externa de PYTHONPATH.
# ---------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from core.conversation_continuity_guard import ConversationContinuityGuard


def main() -> int:
    """Comprueba que una respuesta pendiente de rutina conserve continuidad."""

    guard = ConversationContinuityGuard()

    # -----------------------------------------------------
    # Resultado previo:
    # neuroguIA había iniciado una rutina de mañana.
    # -----------------------------------------------------

    previous_result = {
        "routine_payload": {
            "routine_type": "morning_organization",
            "routine_name": "Rutina de mañana con baja carga",
        },
        "response_package": {
            "routine_payload": {
                "routine_type": "morning_organization",
                "routine_name": "Rutina de mañana con baja carga",
            }
        },
        "conversation_frame": {
            "functional_category": "rutinas_habitos",
            "last_routine_type": "morning_organization",
        },
    }

    # -----------------------------------------------------
    # Resultado provisional de una nueva interpretación.
    # El guard debe impedir que se pierda la pregunta
    # pendiente de la conversación anterior.
    # -----------------------------------------------------

    result = {
        "response_package": {
            "response": (
                "Estoy contigo. Primero baja una sola señal del cuerpo: "
                "apoya ambos pies y suelta el aire lento una vez."
            )
        },
        "functional_analysis": {
            "functional_category": "regulacion_emocional",
            "functional_category_label": "Regulación emocional",
            "crisis_present": False,
        },
        "conversation_frame": {},
        "state_analysis": {},
    }

    # -----------------------------------------------------
    # Historial inmediato.
    # -----------------------------------------------------

    history = [
        {
            "user": "Necesito una rutina para organizar las mañanas",
            "assistant": (
                "Claro. Vamos a construir una secuencia sencilla.\n\n"
                "**Rutina de mañana con baja carga**\n"
                "¿Esta rutina es para ti, para tu hijo o para toda la familia?"
            ),
        }
    ]

    # -----------------------------------------------------
    # Mensaje que responde directamente a la pregunta
    # pendiente.
    # -----------------------------------------------------

    output = guard.ensure(
        message="Es para mí, pero igual genera una para mi hijo",
        result=result,
        chat_history=history,
        previous_result=previous_result,
    )

    response_package = output.get("response_package") or {}

    response = str(
        response_package.get("response") or ""
    )

    metadata = (
        response_package.get("response_metadata")
        or {}
    )

    # -----------------------------------------------------
    # Validaciones.
    # -----------------------------------------------------

    assert "Rutina de mañana para ti" in response, (
        "No se generó la rutina solicitada para la persona cuidadora."
    )

    assert "Rutina de mañana para tu hijo" in response, (
        "No se generó la rutina solicitada para el hijo."
    )

    assert (
        "Primero baja una sola señal del cuerpo"
        not in response
    ), (
        "La respuesta perdió continuidad y utilizó "
        "una ruta distinta de la pregunta pendiente."
    )

    assert (
        metadata.get("answered_pending_question")
        == "routine_audience"
    ), (
        "No se registró correctamente la resolución "
        "de la pregunta pendiente."
    )

    assert metadata.get("routine_targets") == [
        "self",
        "child",
    ], (
        "Los destinatarios de la rutina no fueron "
        "identificados correctamente."
    )

    # -----------------------------------------------------
    # Resultado.
    # -----------------------------------------------------

    print("CONVERSATION_CONTINUITY_OK")
    print(response)

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
