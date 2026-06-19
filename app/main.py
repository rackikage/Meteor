from __future__ import annotations

import sys

from app.bootstrap import bootstrap


def cmd_health() -> None:
    result = bootstrap()
    print(f"App: {result.config.app.name} v{result.config.app.version}")
    print(f"Local-first: {result.config.app.local_first}")
    print(f"Model profile: {result.config.models.default_profile}")
    print(f"Model path: {result.default_model_path}")
    print(f"Model path exists: {result.default_model_path.exists()}")
    print(f"Runtime wired: False")
    print(f"Model execution wired: False")
    print(f"Ready: {result.ready}")
    if result.warnings:
        print("Warnings:")
        for w in result.warnings:
            print(f"  - {w}")


def cmd_serve() -> None:
    print("API server not yet wired. See feat/api-contracts-and-health-runtime-entrypoints-v1.")
    sys.exit(1)


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print("Usage: python3 -m app.main [health|serve]")
        sys.exit(1)

    command = args[0]
    if command == "health":
        cmd_health()
    elif command == "serve":
        cmd_serve()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
