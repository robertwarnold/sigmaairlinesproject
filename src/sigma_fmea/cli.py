import argparse
import json
from pathlib import Path
import sys

from .models import EngineeringContext, FMEADraft
from .methodology import get_profile, registry, scope_assessment
from .providers import MockProvider, generate
from .conversion import convert, import_records
from .export import export, verify_bundle
from .integrity import load_json


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline FMEA drafts; engineering review required")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("profiles")
    commands.add_parser("doctor", help="Report provider credential presence without revealing values")
    draft = commands.add_parser("draft", help="Research generation with execution/evaluation records")
    draft.add_argument("--system", type=Path, required=True)
    draft.add_argument("--profile", choices=("general", "dfmea", "pfmea", "aerospace"), required=True)
    draft.add_argument("--provider", choices=("mock", "auto", "openai", "anthropic", "gemini"), default="mock")
    draft.add_argument("--model")
    draft.add_argument("--condition", choices=("baseline", "improved"), default="improved")
    draft.add_argument("--output", type=Path, required=True)
    draft.add_argument("--max-output-tokens", type=int, default=5000)
    draft.add_argument("--temperature", type=float)
    draft.add_argument("--allow-paid", action="store_true")
    evaluation = commands.add_parser("evaluate")
    evaluation.add_argument("bundle", type=Path)
    evaluation.add_argument("--reference", type=Path)
    evaluation.add_argument("--output", type=Path, required=True)
    experiment = commands.add_parser("experiment")
    experiment.add_argument("--config", type=Path, required=True)
    experiment.add_argument("--output", type=Path, required=True)
    experiment.add_argument("--mode", choices=("plan", "smoke", "batch"), default="plan")
    experiment.add_argument("--provider", choices=("mock", "auto", "openai", "anthropic", "gemini"))
    experiment.add_argument("--model")
    experiment.add_argument("--allow-paid", action="store_true")
    experiment.add_argument("--max-calls", type=int, default=1)
    analysis = commands.add_parser("analyze")
    analysis.add_argument("experiment", type=Path)
    analysis.add_argument("--output", type=Path, required=True)
    analysis.add_argument("--no-plots", action="store_true")
    scope = commands.add_parser("scope", help="Inspect profile-specific scope gaps without generating a draft")
    scope.add_argument("--context", type=Path, required=True)
    scope.add_argument("--profile", choices=("general", "dfmea", "pfmea", "aerospace"), required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("input", type=Path)
    for name in ("generate", "convert"):
        command = commands.add_parser(name)
        command.add_argument("--context", type=Path, required=True)
        command.add_argument("--profile", choices=("general", "dfmea", "pfmea", "aerospace"), required=True)
        command.add_argument("--output", type=Path, required=True)
        if name == "convert":
            command.add_argument("--input", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "profiles":
            print(json.dumps(registry(), indent=2, ensure_ascii=False))
        elif args.command == "doctor":
            from .llm import credential_status
            print(json.dumps({"python": sys.version.split()[0], "credentials_present": credential_status(),
                              "paid_calls_default": "disabled", "real_network_smoke": "not_performed"}, indent=2))
        elif args.command == "draft":
            from .research import execute_run
            result = execute_run(args.system, args.profile, args.condition, args.provider, args.model or "offline-mock", args.output,
                                 args.allow_paid, args.max_output_tokens, args.temperature)
            print(json.dumps(result, indent=2))
            return 0 if result["state"] == "success" else 2
        elif args.command == "evaluate":
            from .evaluation import evaluate
            from .export import json_bytes
            result = evaluate(verify_bundle(args.bundle), load_json(args.reference) if args.reference else None)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("xb") as stream:
                stream.write(json_bytes(result))
            print(json.dumps(result, indent=2))
        elif args.command == "experiment":
            from .research import run_experiment
            result = run_experiment(args.config, args.output, args.mode, args.provider, args.model, args.allow_paid, args.max_calls)
            print(json.dumps(result, indent=2))
            return 2 if result.get("failed", 0) or result.get("uncertain", 0) or (args.mode == "batch" and result.get("remaining", 0)) else 0
        elif args.command == "analyze":
            from .analysis import summarize
            print(json.dumps(summarize(args.experiment, args.output, not args.no_plots), indent=2))
        elif args.command == "scope":
            context = EngineeringContext(**load_json(args.context))
            print(json.dumps(scope_assessment(context, get_profile(args.profile)), indent=2, ensure_ascii=False))
        elif args.command == "validate":
            if args.input.is_dir():
                verify_bundle(args.input)
                print("Valid artifact bundle; engineering approval is unauthenticated.")
            else:
                FMEADraft.from_dict(load_json(args.input))
                print("Valid FMEA draft schema only; validate its directory to check the full bundle.")
        else:
            context = EngineeringContext(**load_json(args.context))
            profile = get_profile(args.profile)
            report = None
            if args.command == "generate":
                draft = generate(context, profile, MockProvider())
            else:
                draft, report = convert(import_records(args.input), context, profile)
            export(draft, args.output, report)
            print(f"Exported review-required FMEA draft to {args.output}")
        return 0
    except (ValueError, TypeError, KeyError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
