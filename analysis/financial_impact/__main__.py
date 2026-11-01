"""Run offline financial analysis from repository root, without generation credentials."""
import argparse
from pathlib import Path
from .report import create_report


def main():
    """Parse explicit local datasets and print interpretable costs and missing outcomes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, action="append", required=True)
    parser.add_argument("--output-root", type=Path, default=Path("reports/financial_impacts"))
    parser.add_argument("--assumptions", type=Path)
    parser.add_argument("--sources", type=Path)
    parser.add_argument("--labor", type=Path)
    parser.add_argument("--quality", type=Path)
    parser.add_argument("--invoices", type=Path)
    parser.add_argument("--expenses", type=Path)
    parser.add_argument("--analysis-id")
    parser.add_argument("--tier", default="standard_paid")
    parser.add_argument("--billing-arrangement", default="pay_as_you_go")
    args = parser.parse_args()
    output, metrics = create_report(args.manifest, args.output_root, args.assumptions,
        args.labor, args.quality, args.invoices, args.expenses, args.analysis_id, args.sources,
        args.tier, args.billing_arrangement)
    # Print the evidence distinction rather than a misleading zero-dollar accepted cost.
    observed = metrics["observed"]
    print(f"Report: {output.resolve()}")
    print(f"Attempts: {observed['n_attempts']}; successful generations: {observed['n_successful_generations']}")
    print(f"Known token/invoice subtotal: USD {observed['known_token_estimate_or_invoice_subtotal_usd']:.6f}; unknown billing attempts: {observed['unknown_billing_attempts']}")
    print(f"Illustrative loaded engineering rate: USD {metrics['loaded_labor_rate_usd_per_hour']:.2f}/active hour")
    print(f"Empirical savings interval: {metrics['uncertainty']['status']}. Acceptance is separate from generation success.")


if __name__ == "__main__":
    main()
