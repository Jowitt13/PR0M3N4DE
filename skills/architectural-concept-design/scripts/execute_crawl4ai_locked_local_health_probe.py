"""Wire the fixed locked-runtime worker into the gated local health probe boundary."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import bootstrap_external_skills as runtime_bootstrap
import execute_crawl4ai_local_health_probe as probe_gate
from check_source_access import load_json_object

JsonObject = Mapping[str, Any]
WORKER = Path(__file__).with_name("crawl4ai_local_health_probe_worker.py")

ProcessRunner = Callable[[Sequence[str], int | None], str]


def _mapping(value: object) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _locked_probe_runner(
    runtime_root: str,
    runner: ProcessRunner,
    temporary_directory: Callable[..., object] | None = None,
) -> probe_gate.ProbeRunner:
    """Build the only permitted invocation: exact locked python, fixed worker.

    The command is a fixed argument list: the receipt-validated runtime's own
    ``.venv/Scripts/python.exe`` in isolated ``-I`` mode plus this repository's
    worker and one request file.  There is no shell, PATH lookup, relative
    path, argument concatenation, page locator, or environment injection.
    """

    def _invoke(request: Mapping[str, object], timeout_seconds: int) -> str:
        if set(request) != probe_gate.PROBE_REQUEST_KEYS:
            raise RuntimeError("unexpected probe request shape")
        root = Path(runtime_root)
        python = root / ".venv" / "Scripts" / "python.exe"
        directory_factory = temporary_directory or tempfile.TemporaryDirectory
        with directory_factory(prefix="architecture-local-health-probe-", dir=root.parent) as directory:
            path = Path(directory) / "request.json"
            path.write_text(json.dumps({"runtime_root": runtime_root}, ensure_ascii=False, sort_keys=True, separators=(",", ":")), encoding="utf-8")
            try:
                return runner([str(python), "-I", str(WORKER), "--request", str(path)], timeout_seconds)
            except subprocess.TimeoutExpired as error:
                raise TimeoutError from error

    return _invoke


def execute_crawl4ai_locked_local_health_probe(
    payload: JsonObject,
    plan_schema: JsonObject,
    dry_run_schema: JsonObject,
    canary_schema: JsonObject,
    probe_schema: JsonObject,
    registry: JsonObject,
    lock: JsonObject,
    *,
    execute_local_probe: bool = False,
    runner: ProcessRunner = runtime_bootstrap._run_supervised_process,
) -> probe_gate.ProbeResult:
    """Reuse the ARCH-063 gate unchanged and inject only the locked worker runner."""

    runtime_input = _mapping(payload.get("runtime_dry_run_input")) or {}
    runtime_root = runtime_input.get("runtime_root")
    probe_runner = _locked_probe_runner(runtime_root, runner) if isinstance(runtime_root, str) and runtime_root else None
    return probe_gate.execute_crawl4ai_local_health_probe(
        payload,
        plan_schema,
        dry_run_schema,
        canary_schema,
        probe_schema,
        registry,
        lock,
        execute_local_probe=execute_local_probe,
        probe_runner=probe_runner,
    )


def main(argv: Sequence[str]) -> int:
    """Run the gated boundary with the locked runner; the flag gates still apply."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--execute-local-probe", action="store_true")
    arguments = parser.parse_args(argv[1:])
    try:
        payload = load_json_object(arguments.input)
        result = execute_crawl4ai_locked_local_health_probe(
            payload,
            load_json_object(probe_gate.PLAN_SCHEMA),
            load_json_object(probe_gate.DRY_RUN_SCHEMA),
            load_json_object(probe_gate.CANARY_SCHEMA),
            load_json_object(probe_gate.PROBE_SCHEMA),
            load_json_object(probe_gate.REGISTRY),
            load_json_object(probe_gate.LOCK),
            execute_local_probe=arguments.execute_local_probe,
        )
    except (OSError, ValueError, json.JSONDecodeError):
        result = probe_gate._authority_load_failure()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
