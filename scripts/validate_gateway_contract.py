# -*- coding: utf-8 -*-
"""Valida que el gateway y el guard de continuidad sean compatibles."""

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


from core.llm_gateway import LLMGateway
from core.conversation_continuity_guard import ConversationContinuityGuard


def main() -> int:
    """Ejecuta las comprobaciones mínimas del contrato del gateway."""

    gateway = LLMGateway()

    # -----------------------------------------------------
    # Verifica que el método utilizado por continuidad
    # conversacional siga disponible.
    # -----------------------------------------------------

    method = getattr(
        gateway,
        "rewrite_conversational_followup",
        None,
    )

    assert callable(method), (
        "LLMGateway no contiene "
        "rewrite_conversational_followup. "
        "Revisa la compatibilidad entre "
        "core/llm_gateway.py y "
        "core/conversation_continuity_guard.py."
    )

    # -----------------------------------------------------
    # Verifica que ConversationContinuityGuard utilice
    # un gateway compatible.
    # -----------------------------------------------------

    guard = ConversationContinuityGuard()

    guard_method = getattr(
        guard.llm_gateway,
        "rewrite_conversational_followup",
        None,
    )

    assert callable(guard_method), (
        "ConversationContinuityGuard no dispone de "
        "un LLMGateway compatible."
    )

    # -----------------------------------------------------
    # Verifica que el gateway pueda reportar su estado
    # sin realizar una llamada al modelo.
    # -----------------------------------------------------

    status = gateway.get_openai_writer_status()

    assert isinstance(status, dict), (
        "get_openai_writer_status() debe devolver un diccionario."
    )

    assert "model" in status, (
        "El estado del gateway no informa el modelo configurado."
    )

    assert "enabled" in status, (
        "El estado del gateway no informa si la API está habilitada."
    )

    # -----------------------------------------------------
    # Resultado
    # -----------------------------------------------------

    print("GATEWAY_CONTRACT_OK")

    print(
        "Modelo configurado en el entorno:",
        status.get("model"),
    )

    print(
        "API habilitada:",
        status.get("enabled"),
    )

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
