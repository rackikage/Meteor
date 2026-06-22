from __future__ import annotations

import sys

from app.bootstrap import bootstrap
from app.runtime.contract import RuntimeRequest
from app.runtime.orchestrator import build_orchestrator


def cmd_health() -> None:
    result = bootstrap()
    orchestrator = build_orchestrator()
    health = orchestrator.health()
    print(f"App: {result.config.app.name} v{result.config.app.version}")
    print(f"Local-first: {result.config.app.local_first}")
    print(f"Model profile: {result.config.models.default_profile}")
    print(f"Model path: {result.default_model_path}")
    print(f"Model path exists: {result.default_model_path.exists()}")
    print(f"Runtime wired: {health['runtime_wired']}")
    print(f"Model execution wired: {health['model']['wired']}")
    print(f"Retrieval wired: {health['retrieval']['wired']}")
    print(f"Memory wired: {health['memory']['wired']}")
    print(f"Ready: {result.ready}")
    if result.warnings:
        print("Warnings:")
        for warning in result.warnings:
            print(f"  - {warning}")


def cmd_run(prompt_parts: list[str]) -> None:
    if not prompt_parts:
        print("Usage: python3 -m app.main run <prompt>")
        sys.exit(1)
    prompt = " ".join(prompt_parts)
    orchestrator = build_orchestrator()
    response = orchestrator.handle(RuntimeRequest(prompt=prompt))
    print(f"Status: {response.status.value}")
    print(response.response_text)


def cmd_serve() -> None:
    print("API server not yet wired. Runtime can be invoked with: python3 -m app.main run <prompt>")
    sys.exit(1)


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print("Usage: python3 -m app.main [health|run|serve]")
        sys.exit(1)

    command = args[0]
    if command == "health":
        cmd_health()
    elif command == "run":
        cmd_run(args[1:])
    elif command == "serve":
        cmd_serve()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
