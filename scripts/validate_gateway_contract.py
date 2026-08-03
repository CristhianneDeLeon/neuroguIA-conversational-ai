# -*- coding: utf-8 -*-
"""Valida que el gateway y el guard de continuidad sean compatibles."""

from __future__ import annotations

from core.llm_gateway import LLMGateway
from core.conversation_continuity_guard import ConversationContinuityGuard


def main() -> int:
    gateway = LLMGateway()
    method = getattr(gateway, "rewrite_conversational_followup", None)

    assert callable(method), (
        "LLMGateway no contiene rewrite_conversational_followup. "
        "Reemplaza core/llm_gateway.py con la versión del mismo paquete."
    )

    guard = ConversationContinuityGuard()
    guard_method = getattr(guard.llm_gateway, "rewrite_conversational_followup", None)
    assert callable(guard_method)

    status = gateway.get_openai_writer_status()
    assert isinstance(status, dict)
    assert "model" in status
    assert "enabled" in status

    print("GATEWAY_CONTRACT_OK")
    print(f"Modelo configurado: {status.get('model')}")
    print(f"API habilitada: {status.get('enabled')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
