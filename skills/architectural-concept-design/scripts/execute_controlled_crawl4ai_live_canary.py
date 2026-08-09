"""Launch the reviewed Crawl4AI transport only after the existing canary gates pass."""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import bootstrap_external_skills as runtime_bootstrap
import controlled_crawl4ai_live_canary_worker as canary_worker
import execute_controlled_crawl_live_canary as canary
from check_source_access import load_json_object
from execute_crawl4ai_local_health_probe import PROBE_OUTPUT_MAX_LENGTH


JsonObject = Mapping[str, Any]
SKILL_ROOT = Path(__file__).resolve().parents[1]
REFERENCES = SKILL_ROOT / "references"
WORKER = Path(__file__).with_name("controlled_crawl4ai_live_canary_worker.py")
TRANSPORT_TIMEOUT_SECONDS = 60

ProcessRunner = Callable[[Sequence[str], int | None], str | bytes]


def _mapping(value: object) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _transport_failure(kind: str) -> Mapping[str, object]:
    """Return a safe internal observation after an invoked worker fails.

    The launcher deliberately omits paths, command output, and error text.  An
    invoked worker is counted conservatively by the gate, so it never creates
    an implicit safe retry path.
    """

    return {
        "transport_failure": kind,
        "robots": "unavailable",
        "terms": "unavailable",
        "checked_at": "",
        "page": None,
    }


def _transport_exit_envelope(reason: str) -> Mapping[str, object]:
    """Forward one validated worker exit-envelope token to the gate mapping."""

    return {
        "transport_failure": "worker_exit_envelope",
        "worker_exit_reason": reason,
        "robots": "unavailable",
        "terms": "unavailable",
        "checked_at": "",
        "page": None,
    }


def _worker_exit_envelope_reason(error: subprocess.CalledProcessError) -> str | None:
    """Accept only the strict, sanitized one-line worker exit envelope.

    The guard reuses the ARCH-063/064 fixed bounded-output and network-intent
    protections: a missing, oversized, multi-line, malformed, unknown, or
    network-shaped stdout returns ``None`` so the caller keeps the existing
    conservative worker-execution result.  Stderr is never read.
    """

    if error.returncode != canary_worker.WORKER_EXIT_STATUS:
        return None
    output = error.output
    if isinstance(output, str):
        try:
            raw = output.encode("utf-8")
        except UnicodeEncodeError:
            return None
    elif isinstance(output, bytes):
        raw = output
    else:
        return None
    if not raw or len(raw) > PROBE_OUTPUT_MAX_LENGTH:
        return None
    try:
        line = raw.decode("utf-8").strip()
    except UnicodeDecodeError:
        return None
    if not line or "\n" in line or "\r" in line:
        return None
    if "http" in line.lower():
        return None
    try:
        envelope = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(envelope, Mapping) or set(envelope) != set(canary_worker.WORKER_EXIT_ENVELOPE_KEYS):
        return None
    if envelope.get("worker_exit_envelope") != canary_worker.WORKER_EXIT_ENVELOPE_VERSION:
        return None
    reason = envelope.get("exit_reason")
    if not isinstance(reason, str) or reason not in canary_worker.WORKER_EXIT_REASONS:
        return None
    return reason


def _exit_status_observation(error: subprocess.CalledProcessError) -> Mapping[str, object]:
    """Map one nonzero worker exit to a fixed, non-retaining transport signal.

    ARCH-067: only the fixed envelope exit status may carry an ARCH-066
    envelope.  Any other exit status becomes a fixed unexpected-exit signal
    without echoing the status value, and a non-conforming envelope line
    becomes a fixed output-boundary signal.  The envelope validation itself
    is unchanged and never loosened; stderr is never read.
    """

    if error.returncode != canary_worker.WORKER_EXIT_STATUS:
        return _transport_failure("worker_unexpected_exit_status")
    reason = _worker_exit_envelope_reason(error)
    if reason is None:
        return _transport_failure("worker_exit_output_invalid")
    return _transport_exit_envelope(reason)


def _worker_runner(command: Sequence[str], timeout: int | None) -> str | bytes:
    """Capture noisy worker stdout as bytes; success uses its private result file."""

    return runtime_bootstrap._run_supervised_process(command, timeout, binary_stdout=True)


def _read_worker_result(path: Path) -> Mapping[str, object] | None:
    """Read only the bounded atomic success result from the private directory."""

    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if not raw or len(raw) > canary_worker.WORKER_RESULT_MAX_BYTES:
        return None
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if "\n" in text or "\r" in text:
        return None
    try:
        observation = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(observation, Mapping) or set(observation) != {"robots", "terms", "checked_at", "page"}:
        return None
    return observation


def _worker_observation(
    request: Mapping[str, object],
    runtime_root: str,
    runner: ProcessRunner,
    temporary_directory: Callable[..., object] = tempfile.TemporaryDirectory,
) -> Mapping[str, object]:
    """Run the isolated worker and return only a schema-shaped safe observation."""

    root = Path(runtime_root)
    python = root / ".venv" / "Scripts" / "python.exe"
    worker_request = {
        "seed_url": request.get("seed_url"),
        "terms_url": request.get("terms_url"),
        "robots_url": request.get("robots_url"),
        "runtime_root": runtime_root,
        "minimum_delay_ms": request.get("minimum_delay_ms"),
    }
    try:
        with temporary_directory(prefix="architecture-live-canary-", dir=root.parent) as directory:
            path = Path(directory) / "request.json"
            result_path = path.with_name(canary_worker.WORKER_RESULT_FILENAME)
            path.write_text(json.dumps(worker_request, ensure_ascii=False, sort_keys=True, separators=(",", ":")), encoding="utf-8")
            try:
                output = runner([str(python), "-I", str(WORKER), "--request", str(path)], TRANSPORT_TIMEOUT_SECONDS)
            except (TimeoutError, subprocess.TimeoutExpired):
                return _transport_failure("worker_timeout")
            except subprocess.CalledProcessError as error:
                return _exit_status_observation(error)
            except FileNotFoundError:
                # ARCH-067: the exact locked interpreter or worker could not
                # be started at all; no worker process ever ran.
                return _transport_failure("worker_spawn_failed")
            except OSError:
                # ARCH-067: the controlled process/job supervision could not
                # be established or awaited; no result boundary was reached.
                return _transport_failure("worker_supervision_failed")
            except UnicodeDecodeError:
                # The supervised process drains both pipes as bytes.  Its
                # stdout is the only accepted UTF-8 observation boundary, so
                # malformed bytes never escape or become a retry path.
                return _transport_failure("worker_output_malformed")
            except Exception:
                return _transport_failure("worker_execution_failed")
            if isinstance(output, bytes):
                observation = _read_worker_result(result_path)
                return observation if observation is not None else _transport_failure("worker_output_malformed")
    except (TimeoutError, subprocess.TimeoutExpired):
        return _transport_failure("worker_timeout")
    except OSError:
        # ARCH-067: request staging or supervised cleanup failed locally.
        return _transport_failure("worker_supervision_failed")
    except Exception:
        return _transport_failure("worker_execution_failed")
    if not isinstance(output, str) or len(output) > 4096:
        return _transport_failure("worker_output_malformed")
    try:
        observation = json.loads(output)
    except json.JSONDecodeError:
        return _transport_failure("worker_output_malformed")
    if not isinstance(observation, Mapping):
        return _transport_failure("worker_output_malformed")
    if set(observation) != {"robots", "terms", "checked_at", "page"}:
        return _transport_failure("worker_output_malformed")
    return observation


def execute_controlled_crawl4ai_live_canary(
    payload: JsonObject,
    plan_schema: JsonObject,
    dry_run_schema: JsonObject,
    canary_schema: JsonObject,
    registry: JsonObject,
    lock: JsonObject,
    *,
    runner: ProcessRunner = _worker_runner,
) -> canary.LiveCanaryResult:
    """Reuse the existing gate and inject only the exact locked-runtime transport."""

    runtime_input = _mapping(payload.get("runtime_dry_run_input")) or {}
    runtime_root = runtime_input.get("runtime_root")
    if not isinstance(runtime_root, str):
        transport = None
    else:
        transport = lambda request: _worker_observation(request, runtime_root, runner)
    return canary.execute_controlled_crawl_live_canary(payload, plan_schema, dry_run_schema, canary_schema, registry, lock, transport)


def _explicit_execution_required(payload: JsonObject, canary_schema: JsonObject) -> canary.LiveCanaryResult:
    runtime_input = _mapping(payload.get("runtime_dry_run_input")) or {}
    plan = _mapping(runtime_input.get("plan")) or {}
    return canary._finalize(canary._result(plan, ok=False, outcome="blocked", codes=["LIVE_CANARY_EXPLICIT_EXECUTION_FLAG_REQUIRED"]), canary_schema)


def _authority_load_failure() -> canary.LiveCanaryResult:
    return {
        "contract_version": "1.0.0",
        "ok": False,
        "outcome": "blocked",
        "plan_id": None,
        "source_domain": None,
        "registry_version": None,
        "attempt_count": 0,
        "retry_count": 0,
        "reason_codes": ["LIVE_CANARY_AUTHORITY_LOAD_FAILED"],
        "runtime_diagnostic": None,
        "records": [],
    }


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--execute-live", action="store_true")
    arguments = parser.parse_args(argv[1:])
    try:
        payload = load_json_object(arguments.input)
        plan_schema = load_json_object(canary.PLAN_SCHEMA)
        dry_run_schema = load_json_object(canary.DRY_RUN_SCHEMA)
        canary_schema = load_json_object(canary.CANARY_SCHEMA)
        registry = load_json_object(canary.REGISTRY)
        lock = load_json_object(canary.LOCK)
        result = execute_controlled_crawl4ai_live_canary(payload, plan_schema, dry_run_schema, canary_schema, registry, lock) if arguments.execute_live else _explicit_execution_required(payload, canary_schema)
    except (OSError, ValueError, json.JSONDecodeError):
        result = _authority_load_failure()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv))
