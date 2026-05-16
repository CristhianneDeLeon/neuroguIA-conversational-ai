import argparse
import sys
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.orchestrator_v2 import NeuroGuiaOrchestratorV2


CASES: List[Dict[str, List[str]]] = [
    {
        "name": "crisis",
        "messages": [
            "Está ocurriendo una crisis y necesito ayuda para manejarla",
            "ok, por donde empiezo?",
            "que le digo?",
            "si, que le digo??",
        ],
    },
    {
        "name": "ansiedad",
        "messages": [
            "Me siento muy ansiosa y no se como calmarme",
            "no lo se",
            "no tengo una idea clara",
            "no tengo ninguna",
        ],
    },
    {
        "name": "bloqueo",
        "messages": [
            "No puedo organizarme ni empezar lo que tengo pendiente",
            "si",
            "no comprendo",
            "no entiendo",
        ],
    },
    {
        "name": "cambio_contexto",
        "messages": [
            "Tengo demasiados pendientes y me da ansiedad pensar en todo",
            "ademas no estoy durmiendo bien y el cansancio me esta pegando mucho",
        ],
    },
    {
        "name": "meta_preguntas",
        "messages": [
            "quien eres?",
            "que puedes hacer?",
        ],
    },
    {
        "name": "followup_largo",
        "messages": [
            "Tengo demasiados pendientes y me da ansiedad pensar en todo",
            "ademas se me junto que no estoy durmiendo bien, estoy cansada y aun asi tengo que sacar algo del trabajo hoy porque si no se me acumula mas",
        ],
    },
]


def run_case(orch: NeuroGuiaOrchestratorV2, use_llm_stub: bool) -> None:
    print("=" * 100)
    print("MODE", "stub" if use_llm_stub else "auto")
    print("=" * 100)
    for case in CASES:
        print(f"\nCASE {case['name']}")
        chat_history = []
        previous_conversation_frame = {}
        for message in case["messages"]:
            result = orch.process_message(
                message=message,
                chat_history=chat_history,
                extra_context={"conversation_frame": previous_conversation_frame},
                auto_save_case=False,
                auto_store_system_response=False,
                auto_store_curated_llm_response=False,
                use_llm_stub=use_llm_stub,
            )
            response = result["response_package"]["response"]
            llm_result = result.get("llm_result") or {}
            response_goal = result["decision_payload"].get("response_goal", {})
            conversation_frame = result.get("conversation_frame", {}) or {}
            conversation_control = result.get("conversation_control", {}) or {}
            print("- user:", message)
            print("  domain:", conversation_frame.get("conversation_domain"))
            print("  phase:", conversation_frame.get("conversation_phase"))
            print("  turn_family:", conversation_control.get("turn_family"))
            print("  response_goal:", response_goal.get("goal"))
            print("  shape:", response_goal.get("response_shape"))
            print("  form_variant:", response_goal.get("form_variant"))
            print("  mode:", result["response_package"].get("mode"))
            print("  provider:", llm_result.get("provider"))
            print("  used_stub_fallback:", llm_result.get("used_stub_fallback"))
            print("  response:", response.replace("\n", " | "))
            previous_conversation_frame = result.get("conversation_frame", {}) or {}
            chat_history.append({"user": message, "assistant": response})


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate conversational behavior for key NeuroGuIA scenarios.")
    parser.add_argument("--db-path", default="neuroguia_validation.db", help="SQLite DB path to reuse during validation.")
    parser.add_argument(
        "--mode",
        choices=["stub", "auto", "both"],
        default="both",
        help="Validation mode. 'auto' uses the configured LLM path and may still fall back to the local stub.",
    )
    args = parser.parse_args()

    orch = NeuroGuiaOrchestratorV2(db_path=args.db_path)
    try:
        if args.mode in {"stub", "both"}:
            run_case(orch, use_llm_stub=True)
        if args.mode in {"auto", "both"}:
            run_case(orch, use_llm_stub=False)
    finally:
        orch.close()


if __name__ == "__main__":
    main()
