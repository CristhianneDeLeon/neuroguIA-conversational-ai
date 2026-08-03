# -*- coding: utf-8 -*-
"""Valida que una rutina explícita sea visible aunque la ruta base sea genérica."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.routine_response_guard import RoutineResponseGuard


def generic_result() -> dict:
    return {
        "response_package": {
            "response": (
                "Estoy contigo. Primero baja una sola señal del cuerpo: "
                "apoya ambos pies y suelta el aire lento una vez."
            ),
            "text": (
                "Estoy contigo. Primero baja una sola señal del cuerpo: "
                "apoya ambos pies y suelta el aire lento una vez."
            ),
            "response_metadata": {
                "route_id": "ansiedad",
                "support_mode": "guided_support_flow",
            },
        },
        "state_analysis": {
            "primary_state": "emotional_dysregulation",
            "emotional_intensity": 0.62,
            "caregiver_capacity": 0.60,
        },
        "category_analysis": {"detected_category": "apoyo_general"},
        "conversation_frame": {"turn_family": "new_request"},
        "conversation_control": {"turn_family": "new_request"},
        "stage_result": {},
        "memory_payload": {},
    }


def assert_routine(message: str, expected_type: str, chat_history=None) -> dict:
    guard = RoutineResponseGuard()
    result = guard.ensure(
        message=message,
        result=generic_result(),
        previous_frame={},
        active_profile={},
        chat_history=chat_history or [],
    )
    routine = result.get("routine_payload") or {}
    response = str((result.get("response_package") or {}).get("response") or "")

    assert routine.get("routine_type") == expected_type, result
    assert routine.get("routine_name") in response, response
    assert "1." in response, response
    assert (result.get("response_package") or {}).get("routine_generated") is True
    return result


def main() -> int:
    first = assert_routine(
        "Necesito una rutina para organizar las mañanas",
        "morning_organization",
    )
    followup = assert_routine(
        "Listo, ahora genera la rutina que te pedí",
        "morning_organization",
        chat_history=[{
            "user": "Necesito una rutina para organizar las mañanas",
            "assistant": "Estoy contigo. Primero baja una sola señal del cuerpo.",
        }],
    )

    print("ROUTINE_DELIVERY_OK")
    print((first.get("response_package") or {}).get("response"))
    print("---")
    print((followup.get("response_package") or {}).get("response"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
