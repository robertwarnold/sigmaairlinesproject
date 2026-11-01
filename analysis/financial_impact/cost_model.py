"""Costs in USD: active engineering labor plus all observed workflow expenses."""
from datetime import date
import math
from .data_schema import number


def loaded_rate(labor):
    """Combine wage with benefits once, or use an already burdened override directly."""
    # A company-supplied loaded rate replaces the national-average calculation.
    override = labor.get("fully_burdened_override_usd_per_hour")
    if override is not None:
        return number(override, "loaded rate")
    wage = number(labor["wage_usd_per_hour"], "wage")
    denominator = number(labor["benefit_wage_usd_per_hour"], "benefit wage")
    total = number(labor["benefit_total_usd_per_hour"], "total compensation")
    if denominator <= 0 or total < denominator:
        raise ValueError("Invalid compensation multiplier")
    return wage * total / denominator


def token_cost(usage, price, invoice_usd=None):
    """Estimate uncached text usage; output tokens exclude separately reported thinking."""
    # Invoices take precedence; incomplete usage and cached/tool billing need reconciliation.
    if invoice_usd is not None:
        return {"usd": number(invoice_usd, "invoice"), "basis": "invoice", "billing_uncertain": False}
    if usage is None or any(usage.get(k) is None for k in ("prompt_token_count", "candidates_token_count", "thoughts_token_count")):
        return {"usd": None, "basis": "unavailable_usage", "billing_uncertain": True}
    if usage.get("cached_content_token_count", 0) or usage.get("tool_use_prompt_token_count", 0):
        return {"usd": None, "basis": "requires_cached_or_tool_pricing", "billing_uncertain": True}
    input_tokens = number(usage["prompt_token_count"], "input tokens")
    output_tokens = number(usage["candidates_token_count"], "output tokens")
    thinking_tokens = number(usage["thoughts_token_count"], "thinking tokens")
    if any(value != int(value) for value in (input_tokens, output_tokens, thinking_tokens)):
        raise ValueError("Token counts must be whole numbers")
    # Add thinking exactly once; total_token_count is not another billable bucket.
    usd = (input_tokens * number(price["input_usd_per_million"], "input price") +
           (output_tokens + thinking_tokens) * number(price["output_including_thinking_usd_per_million"], "output price")) / 1_000_000
    return {"usd": usd, "basis": "estimated_standard_paid_tokens", "billing_uncertain": True}


def select_price(prices, model, timestamp, tier, arrangement):
    """Select exactly one effective dated tariff; never substitute model or tier."""
    # Match the observation date, rather than silently repricing an old experiment.
    observed = date.fromisoformat(timestamp[:10])
    matches = [p for p in prices if p["model"] == model and p["tier"] == tier and
               p["billing_arrangement"] == arrangement and
               date.fromisoformat(p["effective_from"]) <= observed <= date.fromisoformat(p["effective_through"])]
    if len(matches) != 1:
        raise ValueError(f"Expected one applicable tariff for {model}, {observed}, {tier}/{arrangement}")
    return matches[0]


def active_minutes(row):
    """Sum mutually exclusive ordinary, review and rework labor; exclude passive waiting."""
    return sum(number(row[k], k) for k in ("active_engineering_minutes", "review_minutes", "rework_minutes"))


def comparison(manual, ai, development_usd=0, annual_maintenance_usd=0, annual_volume=0):
    """Compare accepted unit costs without clipping losses or inventing a break-even."""
    # A nonpositive benefit has no finite break-even for a positive investment.
    if manual is None or ai is None:
        return {key: None for key in ("absolute_savings_usd", "percentage_reduction", "net_annual_savings_usd",
                                      "break_even_fmeas", "net_savings_per_fmea_usd")}
    manual, ai = number(manual, "manual cost"), number(ai, "AI cost")
    investment = number(development_usd, "development")
    maintenance = number(annual_maintenance_usd, "maintenance")
    volume = number(annual_volume, "annual volume")
    savings = manual - ai
    fixed = investment + maintenance
    return {"absolute_savings_usd": savings,
            "percentage_reduction": 100 * savings / manual if manual else None,
            "net_annual_savings_usd": savings * volume - fixed,
            "break_even_fmeas": math.ceil(fixed / savings) if savings > 0 else (0 if fixed == 0 and savings == 0 else None),
            "net_savings_per_fmea_usd": savings - fixed / volume if volume else None}
