# -*- coding: utf-8 -*-
from __future__ import annotations

from core.conversation_continuity_guard import ConversationContinuityGuard


def main() -> int:
    guard = ConversationContinuityGuard()
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

    output = guard.ensure(
        message="Es para mí, pero igual genera una para mi hijo",
        result=result,
        chat_history=history,
        previous_result=previous_result,
    )
    response = str((output.get("response_package") or {}).get("response") or "")
    metadata = (output.get("response_package") or {}).get("response_metadata") or {}

    assert "Rutina de mañana para ti" in response
    assert "Rutina de mañana para tu hijo" in response
    assert "Primero baja una sola señal del cuerpo" not in response
    assert metadata.get("answered_pending_question") == "routine_audience"
    assert metadata.get("routine_targets") == ["self", "child"]

    print("CONVERSATION_CONTINUITY_OK")
    print(response)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
