from __future__ import annotations

import argparse
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.llm_gateway import LLMGateway
from database import load_env_file


def build_test_request() -> Dict[str, Any]:
    """
    Construye un payload minimo pero realista para probar la capa
    de generacion. La logica central no cambia: solo simulamos el
    contexto ya estructurado que normalmente llegaria al gateway.
    """
    gateway = LLMGateway()
    return gateway.build_request(
        message="Me siento muy saturada y no sé por dónde empezar con todo lo que tengo encima.",
        fallback_payload={
            "use_llm": True,
            "fallback_reason": "manual_gateway_test",
            "prompt_mode": "controlled_support_generation",
            "constraints": {
                "avoid": ["tono clínico", "explicación extensa"],
                "must_include": ["una acción pequeña viable"],
                "should_close_with_followup": True,
            },
        },
        decision_payload={
            "selected_strategy": "vaciar pendientes y elegir solo una prioridad",
            "selected_microaction": "anotar todo y marcar una sola prioridad posible ahora",
            "selected_routine_type": None,
            "intervention_type": "supportive_generation",
        },
        confidence_payload={
            "overall_confidence": 0.41,
            "confidence_level": "medium",
        },
        intent_analysis={
            "detected_intent": "general_support",
            "confidence": 0.48,
        },
        category_analysis={
            "detected_category": "ansiedad_cognitiva",
            "confidence": 0.56,
        },
        state_analysis={
            "primary_state": "cognitive_anxiety",
            "secondary_states": ["general_distress"],
        },
        stage_result={
            "stage": "adaptive_intervention",
            "config": {
                "tone": "warm_clear",
                "length": "short",
                "max_questions": 1,
            },
        },
        support_plan={
            "support_priorities": [
                "bajar carga mental",
                "elegir una sola prioridad posible",
            ],
            "response_alerts": [
                "evitar saturación",
                "no sobrecargar con demasiados pasos",
            ],
        },
        active_profile={
            "alias": "Alex",
            "role": "cuidador",
            "conditions": ["tdah"],
            "sensory_needs": [],
            "emotional_needs": ["claridad", "baja exigencia"],
        },
        routine_payload={
            "routine_name": None,
            "routine_type": None,
            "short_version": [],
            "steps": [],
        },
        memory_payload={
            "recommended_strategies": ["elegir una sola prioridad"],
            "recommended_microactions": ["anotar pendientes"],
        },
        response_memory_payload={},
        case_context={
            "caregiver_capacity": 0.42,
            "emotional_intensity": 0.74,
            "followup_needed": True,
            "conversation_domain": "ansiedad_cognitiva",
            "conversation_phase": "prioritize",
            "speaker_role": "cuidador",
            "conversation_frame": {
                "conversation_domain": "ansiedad_cognitiva",
                "support_goal": "reduce_mental_overload",
                "conversation_phase": "prioritize",
                "speaker_role": "cuidador",
                "continuity_score": 0.62,
            },
            "llm_policy": {
                "reason": "manual_gateway_test",
                "domain": "ansiedad_cognitiva",
                "phase": "prioritize",
                "category": "ansiedad_cognitiva",
                "intent": "general_support",
            },
            "expert_adaptation_plan": {
                "tone_profile": {"warmth": "high"},
                "structure_profile": {"brevity": "high"},
                "language_profile": {"clinical_terms": "avoid"},
                "followup_policy": {"max_questions": 1},
            },
        },
    ).get("request_payload") or {}


@contextmanager
def temporary_env(overrides: Dict[str, Optional[str]]) -> Iterator[None]:
    original_values = {key: os.environ.get(key) for key in overrides}
    try:
        for key, value in overrides.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, value in original_values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def print_section(title: str) -> None:
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def infer_env_source(
    key: str,
    env_file_values: Dict[str, str],
    overrides: Dict[str, Optional[str]],
) -> str:
    if key in overrides:
        return "override"
    if key in env_file_values and os.environ.get(key) == env_file_values.get(key):
        return ".env"
    if key in os.environ:
        return "environment"
    return "default"


def read_env_file_values(env_file: Optional[str]) -> Dict[str, str]:
    values: Dict[str, str] = {}
    if not env_file:
        return values

    env_path = Path(env_file)
    if not env_path.exists():
        return values

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")

    return values


def print_env_debug(
    scenario: str,
    env_file_values: Dict[str, str],
    overrides: Dict[str, Optional[str]],
) -> None:
    print("effective_env:")
    print(
        "  USE_OPENAI_LLM: "
        f"{os.environ.get('USE_OPENAI_LLM')} "
        f"(source={infer_env_source('USE_OPENAI_LLM', env_file_values, overrides)})"
    )
    print(
        "  OPENAI_MODEL: "
        f"{os.environ.get('OPENAI_MODEL', '[unset]')} "
        f"(source={infer_env_source('OPENAI_MODEL', env_file_values, overrides)})"
    )
    api_key_present = bool(str(os.environ.get("OPENAI_API_KEY", "") or "").strip())
    print(
        "  OPENAI_API_KEY: "
        f"{'present' if api_key_present else 'absent'} "
        f"(source={infer_env_source('OPENAI_API_KEY', env_file_values, overrides)})"
    )


def print_result(name: str, result: Dict[str, Any]) -> None:
    print_section(f"ESCENARIO: {name}")
    preview = str(result.get("response_text") or "").strip().replace("\n", " ")
    if len(preview) > 260:
        preview = f"{preview[:257]}..."

    print(f"provider: {result.get('provider')}")
    print(f"model: {result.get('model')}")
    print(f"used_stub_fallback: {result.get('used_stub_fallback')}")
    print(f"fallback_reason: {result.get('fallback_reason')}")
    print(f"llm_enabled: {result.get('llm_enabled')}")
    print("response_text_preview:")
    print(f"  {preview or '[vacío]'}")

    response_structure = result.get("response_structure")
    print("response_structure:")
    if response_structure:
        print(f"  {response_structure}")
    else:
        print("  [no disponible]")

    metadata = result.get("generation_metadata") or {}
    print("generation_metadata:")
    if metadata:
        print(f"  {metadata}")
    else:
        print("  [no disponible]")


def run_scenario(name: str, env_file: Optional[str] = None) -> Dict[str, Any]:
    env_file_values = read_env_file_values(env_file)
    if env_file:
        env_path = Path(env_file)
        if env_path.exists():
            load_env_file(str(env_path))

    gateway = LLMGateway()
    request_payload = build_test_request()

    if name == "stub":
        overrides = {
            "USE_OPENAI_LLM": "false",
        }
    elif name == "missing-key":
        overrides = {
            "USE_OPENAI_LLM": "true",
            "OPENAI_API_KEY": None,
        }
    elif name == "real":
        overrides = {
            "USE_OPENAI_LLM": "true",
        }
    else:
        raise ValueError(f"Escenario no soportado: {name}")

    with temporary_env(overrides):
        print_section(f"DIAGNÓSTICO DE ENTORNO: {name}")
        print_env_debug(name, env_file_values, overrides)
        return gateway.run(request_payload)


def expand_scenarios(selected: str) -> Iterable[str]:
    if selected == "all":
        return ["stub", "missing-key", "real"]
    return [selected]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prueba funcional mínima del llm_gateway de NeuroGuía.",
    )
    parser.add_argument(
        "--scenario",
        choices=["all", "stub", "missing-key", "real"],
        default="all",
        help="Escenario a ejecutar.",
    )
    parser.add_argument(
        "--env-file",
        default=str(PROJECT_ROOT / ".env"),
        help="Ruta opcional a archivo .env para cargar configuración antes de la prueba.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    print_section("TEST LLM GATEWAY - NEUROGUÍA")
    print(f"project_root: {PROJECT_ROOT}")
    print(f"env_file: {args.env_file}")
    print(f"scenario: {args.scenario}")

    for scenario in expand_scenarios(args.scenario):
        result = run_scenario(scenario, env_file=args.env_file)
        print_result(scenario, result)

    print()
    print("Fin de la prueba.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
