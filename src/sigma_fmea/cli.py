import argparse
import json
from pathlib import Path
import sys

from .models import EngineeringContext, FMEADraft
from .methodology import get_profile, registry
from .providers import MockProvider, generate
from .conversion import convert, import_records
from .export import export, verify_bundle
from .integrity import load_json


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline FMEA drafts; engineering review required")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("profiles")
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
