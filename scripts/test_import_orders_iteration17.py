"""Import-order characterization for core/package_service/case_views after dotenv load."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path


def load_backend_env() -> None:
    env_path = Path("/app/backend/.env")
    if not env_path.exists():
        raise RuntimeError("/app/backend/.env missing")
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip().strip('"').strip("'")


def clear_modules() -> None:
    for name in ("core", "package_service", "case_views"):
        if name in sys.modules:
            del sys.modules[name]


def run_order(order: list[str]) -> None:
    clear_modules()
    for module in order:
        importlib.import_module(module)


def main() -> int:
    load_backend_env()
    run_order(["core", "package_service", "case_views"])
    run_order(["package_service", "case_views", "core"])
    print("PASS: both import orders succeeded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
