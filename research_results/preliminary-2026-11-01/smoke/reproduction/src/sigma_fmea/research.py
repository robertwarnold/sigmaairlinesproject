"""Prototype run records, smoke gate, immutable experiment plan, and duplicate prevention."""
from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import random
import time
import platform

from .evaluation import evaluate
from .evaluation import reference_coverage
from .export import export, json_bytes, verify_bundle
from .guidance import GUIDANCE, GUIDANCE_VERSION
from .integrity import digest, load_json
from .llm import LLMProvider, ProviderError, build_prompt, credential_status, resolve_provider, PROMPT_VERSION
from .methodology import get_profile
from .models import EngineeringContext
from .providers import generate, MockProvider


def now():
    return datetime.now(timezone.utc).isoformat()


def write_record(path, data):
    """Replace a run-state record atomically. Never includes authorization headers."""
    path = Path(path)
    raw = json_bytes(data).decode("utf-8")
    for variable in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"):
        secret = os.environ.get(variable)
        if secret and len(secret) >= 8:
            raw = raw.replace(secret, "[REDACTED]")
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def load_system(path):
    path = Path(path)
    if any(part.casefold() in {"benchmarks", "fixtures", "reference_materials"} for part in path.parts):
        raise ValueError("Generation input cannot be loaded from reference/benchmark/fixture directories")
    document = load_json(path)
    if not isinstance(document, dict) or any(k in document for k in ("reference_modes", "ground_truth", "benchmark_answers")):
        raise ValueError("Generation input must contain engineering context only, never reference answers")
    if "context" in document:
        if set(document) - {"context", "description", "input_version", "classification"}:
            raise ValueError("Unsupported engineering input envelope keys")
        context = EngineeringContext(**document["context"])
        description = document.get("description", context.scope)
    else:
        context = EngineeringContext(**document)
        description = context.scope
    if not isinstance(description, str) or not description.strip():
        raise ValueError("Engineering description must be nonempty text")
    return context, description, {"sha256": digest(document), "input_version": document.get("input_version", "unversioned"),
                                  "classification": document.get("classification", "user_supplied_context"), "document": document}


def execute_run(system_path, profile_id, condition, provider_name, model, output, allow_paid=False,
                max_output_tokens=5000, temperature=None, reference=None, provider_override=None):
    if condition not in {"baseline", "improved"}:
        raise ValueError("Invalid experimental condition")
    context, description, input_record = load_system(system_path)
    profile = get_profile(profile_id)
    name = resolve_provider(provider_name)
    if name != "mock" and (not isinstance(model, str) or not model.strip() or model == "offline-mock" or model.startswith("SET_")):
        raise ProviderError("Set an explicit accessible real model ID; no request made")
    if name != "mock" and not allow_paid:
        raise ProviderError("Paid API calls require explicit approval and --allow-paid")
    if name != "mock" and not credential_status().get(name):
        raise ProviderError(f"No {name} API credential configured; no request made")
    provider = provider_override or (MockProvider() if name == "mock" else LLMProvider(name, model, description, condition, allow_paid, max_output_tokens, temperature))
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir()  # exclusive claim before a possible paid request; never automatic retry
    prompt = build_prompt(context, profile, description, condition)
    settings = {"provider": name, "model": model, "temperature": temperature, "max_output_tokens": max_output_tokens}
    state = {"state": "running", "system_id": context.system_id, "condition": condition, "profile_id": profile_id,
             "profile_version": profile.version, "input_sha256": input_record["sha256"], "input_version": input_record["input_version"],
             "classification": input_record["classification"], "settings": settings, "prompt_version": PROMPT_VERSION,
             "prompt_sha256": prompt["sha256"], "guidance_sha256": prompt["guidance"]["sha256"],
             "started_at": now(), "data_kind": "offline_mock_rehearsal" if name == "mock" else "real_llm_generation",
             "actual_model": None, "usage": None, "generation_seconds": None}
    state["runtime"] = {"python": platform.python_version(), "implementation": platform.python_implementation(), "os": platform.system()}
    fingerprint = digest({"input": input_record, "prompt": prompt, "settings": settings})
    write_record(output / "state.json", state)
    write_record(output / "input.json", input_record)
    write_record(output / "prompt.json", prompt)
    started = time.perf_counter()
    try:
        draft = generate(context, profile, provider)
        draft.metadata["research_execution_sha256"] = fingerprint
        draft.validate()
        state["generation_seconds"] = time.perf_counter() - started
        execution = getattr(provider, "last_execution", {})
        state.update(actual_model=execution.get("actual_model", model if name == "mock" else None), usage=execution.get("usage"))
        export(draft, output / "bundle")
        # Reference answers are only used here, after generation. Never in prompt or provider interface.
        metrics = evaluate(draft, reference)
        write_record(output / "metrics.json", metrics)
        state.update(state="success", artifact_id=draft.artifact_id, execution_sha256=fingerprint)
    except Exception as error:
        execution = getattr(provider, "last_execution", {})
        state.update(state="failed", generation_seconds=time.perf_counter() - started,
                     usage=execution.get("usage"), actual_model=execution.get("actual_model"),
                     error_type=type(error).__name__, error=str(error))
        write_record(output / "metrics.json", {"schema_valid": False, "validation_errors": [str(error)], "validation_error_count": 1,
                     "structural_completeness_pct": None, "missed_failure_modes_pct": None,
                     "generated_failure_modes": execution.get("raw_row_count"), "unresolved_review_flag_count": None,
                     "coverage_status": "generation_or_evaluation_failed"})
    finally:
        write_record(output / "execution.json", getattr(provider, "last_execution", {}))
        state["finished_at"] = now()
        write_record(output / "state.json", state)
    return state


def build_plan(config_path, provider=None, model=None):
    config_path = Path(config_path).resolve()
    config = load_json(config_path)
    if not isinstance(config, dict):
        raise ValueError("Experiment config must be an object")
    provider_name = provider or config.get("provider", "mock")
    blockers = []
    try:
        name = resolve_provider(provider_name)
    except ProviderError:
        name = "auto"
        blockers.append("No supported provider credential configured")
    if name not in {"mock", "openai", "anthropic", "gemini", "auto"}:
        raise ValueError("Unknown provider")
    model_id = model or config.get("model")
    if name == "mock":
        model_id = "offline-mock"
    if name != "mock" and (not isinstance(model_id, str) or not model_id.strip() or model_id.startswith("SET_")):
        blockers.append("An explicit accessible model ID is required")
    if name in {"openai", "anthropic", "gemini"} and not credential_status()[name]:
        blockers.append(f"{name} credential not configured")
    repetitions = config.get("repetitions", 3)
    if type(repetitions) is not int or not 1 <= repetitions <= 25:
        raise ValueError("repetitions must be 1–25")
    conditions = config.get("conditions", ["baseline", "improved"])
    if conditions != ["baseline", "improved"]:
        raise ValueError("This prototype requires baseline and improved conditions in a fixed pair")
    max_tokens = config.get("max_output_tokens", 5000)
    if type(max_tokens) is not int or not 1 <= max_tokens <= 16000:
        raise ValueError("max_output_tokens must be 1–16000")
    temperature = config.get("temperature")
    if temperature is not None and (type(temperature) not in (int, float) or not 0 <= temperature <= 1):
        raise ValueError("temperature must be null or 0–1")
    systems = []
    for entry in config.get("systems", []):
        path = (config_path.parent / entry["path"]).resolve()
        context, description, record = load_system(path)
        profile = get_profile(entry.get("profile", "general"))
        systems.append({"system_id": context.system_id, "path": str(path), "profile": profile.profile_id, "profile_version": profile.version,
                        "input_sha256": record["sha256"], "input_version": record["input_version"], "classification": record["classification"]})
    if not systems or len({s["system_id"] for s in systems}) != len(systems):
        raise ValueError("Require at least one system and unique system IDs")
    references = {}
    for system_id, relative_path in config.get("references", {}).items():
        if system_id not in {s["system_id"] for s in systems}:
            raise ValueError("Reference names an unavailable system")
        path = (config_path.parent / relative_path).resolve()
        references[system_id] = {"path": str(path), "sha256": digest(load_json(path))}
        # Validate reviewed-reference contracts before reserving any possible paid call.
        system_record = next(s for s in systems if s["system_id"] == system_id)
        context, _, _ = load_system(system_record["path"])
        check_draft = generate(context, get_profile(system_record["profile"]), MockProvider())
        reference_coverage(check_draft, load_json(path))
    jobs = []
    rng = random.Random(config.get("order_seed", 5300))
    for repetition in range(1, repetitions + 1):
        for system_index, system in enumerate(systems):
            order = list(conditions)
            if rng.randrange(2):
                order.reverse()
            for condition in order:
                jobs.append({"job_id": f"s{system_index+1:02d}-r{repetition:02d}-{condition}", "system_index": system_index,
                             "repetition": repetition, "condition": condition})
    plan = {"plan_version": "research-plan-1", "provider": name, "model": model_id or "offline-mock",
            "temperature": temperature, "max_output_tokens": max_tokens, "systems": systems,
            "references": references, "jobs": jobs, "total_generations": len(jobs), "repetitions": repetitions,
            "conditions": conditions, "order_seed": config.get("order_seed", 5300),
            "prompt_version": PROMPT_VERSION, "guidance_version": GUIDANCE_VERSION, "guidance_corpus_sha256": digest(GUIDANCE),
            "schema_version": "0.2", "blockers": blockers,
            "sample_note": "four author-created research scenarios" if len(systems) == 4 else f"reduced/changed sample: {len(systems)} systems"}
    plan["implementation_sha256"] = digest({name: (Path(__file__).parent / name).read_text(encoding="utf-8") for name in ("research.py", "providers.py", "llm.py", "models.py", "methodology.py", "guidance.py", "evaluation.py", "integrity.py", "export.py")})
    plan["plan_sha256"] = digest(plan)
    return plan


def run_experiment(config_path, output, mode="plan", provider=None, model=None, allow_paid=False, max_calls=1):
    plan = build_plan(config_path, provider, model)
    if mode == "plan":
        return plan
    if plan["blockers"]:
        raise ProviderError("; ".join(plan["blockers"]))
    if plan["provider"] != "mock" and not allow_paid:
        raise ProviderError("Paid experiment requires explicit approval and --allow-paid")
    if type(max_calls) is not int or max_calls < 1:
        raise ValueError("max_calls must be a positive integer")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    lock = output / ".experiment.lock"
    lock.mkdir()
    try:
        plan_path = output / "plan.json"
        if plan_path.exists():
            if load_json(plan_path) != plan:
                raise ValueError("Experiment plan changed; use a new output directory")
        else:
            if any(p.name != ".experiment.lock" for p in output.iterdir()):
                raise ValueError("Output contains unrelated files")
            write_record(plan_path, plan)
        runs = output / "runs"
        runs.mkdir(exist_ok=True)
        if mode == "batch":
            smoke = runs / plan["jobs"][0]["job_id"] / "state.json"
            if not smoke.exists() or load_json(smoke).get("state") != "success":
                raise ValueError("Run one successful smoke generation before the batch")
        jobs = plan["jobs"][:1] if mode == "smoke" else plan["jobs"]
        actual_models = set()
        for path in runs.glob("*/state.json"):
            previous = load_json(path)
            if "Actual model identity changed" in previous.get("error", ""):
                raise ValueError("Experiment previously halted for model identity change; use a new frozen campaign")
            if previous.get("state") == "success" and previous.get("actual_model"):
                actual_models.add(previous["actual_model"])
        for job in jobs:
            path = runs / job["job_id"]
            if path.exists():
                continue  # includes failed or uncertain outcomes: never rebill automatically
            if plan["provider"] != "mock" and len([p for p in runs.iterdir() if p.is_dir()]) >= max_calls:
                break
            system = plan["systems"][job["system_index"]]
            reference_record = plan["references"].get(system["system_id"])
            reference = load_json(reference_record["path"]) if reference_record else None
            result = execute_run(system["path"], system["profile"], job["condition"], plan["provider"], plan["model"], path,
                                 allow_paid, plan["max_output_tokens"], plan["temperature"], reference)
            result.update(job_id=job["job_id"], repetition=job["repetition"], plan_sha256=plan["plan_sha256"])
            if result.get("actual_model") and result["state"] == "success":
                actual_models.add(result["actual_model"])
            if len(actual_models) > 1:
                result.update(state="failed", error="Actual model identity changed within experiment; comparison halted")
            write_record(path / "state.json", result)
            if len(actual_models) > 1 or (result["state"] == "failed" and ("HTTP 40" in result.get("error", "") or "HTTP 429" in result.get("error", ""))):
                break
        states = [load_json(p) for p in sorted(runs.glob("*/state.json"))]
        summary = {"planned_generations": plan["total_generations"], "attempted": len(list(runs.iterdir())),
                   "successful": sum(s["state"] == "success" for s in states), "failed": sum(s["state"] == "failed" for s in states),
                   "uncertain": sum(s.get("state") == "running" for s in states) + len([p for p in runs.iterdir() if p.is_dir() and not (p / "state.json").exists()]),
                   "data_kind": "offline_mock_rehearsal" if plan["provider"] == "mock" else "real_llm_generation",
                   "plan_sha256": plan["plan_sha256"]}
        summary["remaining"] = plan["total_generations"] - summary["attempted"]
        write_record(output / "progress.json", summary)
        return summary
    finally:
        lock.rmdir()
