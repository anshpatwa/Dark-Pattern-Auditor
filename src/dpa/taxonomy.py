"""The dark-pattern taxonomy used to guide and constrain detection.

The categories follow the academic taxonomy of Mathur et al. (2019), "Dark Patterns
at Scale", combined with the pattern vocabulary catalogued by Harry Brignull on
deceptive.design. Keeping this in one place means the AI prompt, the heuristic engine,
the scoring model and the UI all share a single source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PatternType:
    """A specific, named dark pattern."""

    key: str
    name: str
    category: str
    definition: str
    example: str
    default_severity: str  # low | medium | high | critical


@dataclass(frozen=True)
class Category:
    key: str
    name: str
    description: str
    patterns: list[PatternType] = field(default_factory=list)


# --- High-level categories (Mathur et al., 2019) --------------------------

CATEGORY_META: dict[str, str] = {
    "sneaking": "Hiding, disguising or delaying information the user would object to.",
    "urgency": "Imposing a real or fake deadline to rush the user into acting.",
    "misdirection": "Steering attention toward or away from a choice using framing or visuals.",
    "social_proof": "Using others' (often fabricated) behaviour to influence a decision.",
    "scarcity": "Signalling limited supply or demand to increase perceived value.",
    "obstruction": "Making a desired action needlessly hard ('roach motel').",
    "forced_action": "Requiring an unrelated action to complete the task at hand.",
}


PATTERNS: list[PatternType] = [
    # --- Sneaking ---------------------------------------------------------
    PatternType(
        "sneak_into_basket", "Sneak into Basket", "sneaking",
        "An item the user did not choose is added to their cart, often via a pre-checked add-on.",
        "An insurance or 'priority support' add-on silently appears at checkout.",
        "high",
    ),
    PatternType(
        "hidden_costs", "Hidden Costs", "sneaking",
        "Unexpected charges (fees, taxes, shipping) are only revealed at the last checkout step.",
        "A $9 'service fee' that only appears on the final payment screen.",
        "high",
    ),
    PatternType(
        "hidden_subscription", "Hidden Subscription", "sneaking",
        "A one-off-looking purchase silently enrolls the user in a recurring charge.",
        "'Free trial' that converts to a paid monthly plan with no clear disclosure.",
        "critical",
    ),
    PatternType(
        "bait_and_switch", "Bait and Switch", "sneaking",
        "The user sets out to do one thing, but a different, undesirable thing happens.",
        "Clicking an 'X' to close triggers the very action it appeared to dismiss.",
        "high",
    ),
    # --- Urgency ----------------------------------------------------------
    PatternType(
        "countdown_timer", "Fake Urgency / Countdown Timer", "urgency",
        "A countdown implies an offer expires, but it resets or is not real.",
        "'Offer ends in 09:59' that restarts on every page load.",
        "medium",
    ),
    PatternType(
        "limited_time_message", "Limited-Time Message", "urgency",
        "A deadline is asserted without evidence to pressure an immediate decision.",
        "'Today only!' banners with no actual expiry.",
        "medium",
    ),
    # --- Misdirection -----------------------------------------------------
    PatternType(
        "confirmshaming", "Confirmshaming", "misdirection",
        "The opt-out option is worded to shame or guilt the user for declining.",
        "Decline link reads 'No thanks, I don't like saving money.'",
        "high",
    ),
    PatternType(
        "visual_interference", "Visual Interference", "misdirection",
        "Styling makes the manipulative choice prominent and the honest choice hard to find.",
        "A bright 'Accept All' button beside a greyed, tiny 'Manage settings' link.",
        "high",
    ),
    PatternType(
        "trick_wording", "Trick Wording / Trick Questions", "misdirection",
        "Confusing language, double negatives or inverted toggles obscure the real choice.",
        "'Uncheck if you do not want to not receive emails.'",
        "medium",
    ),
    PatternType(
        "pressured_selling", "Pressured Selling", "misdirection",
        "A more expensive option is pre-selected or defaulted to nudge a costlier choice.",
        "The premium plan is pre-selected and styled as 'recommended' with no basis.",
        "medium",
    ),
    # --- Social proof -----------------------------------------------------
    PatternType(
        "fake_activity", "Fake Activity Messages", "social_proof",
        "Notifications claim recent activity by others that cannot be verified.",
        "'Sarah from London just bought this' pop-ups on a loop.",
        "medium",
    ),
    PatternType(
        "fake_testimonials", "Fake Testimonials", "social_proof",
        "Reviews or endorsements are fabricated or unverifiable.",
        "Five-star quotes attributed to stock-photo avatars.",
        "medium",
    ),
    # --- Scarcity ---------------------------------------------------------
    PatternType(
        "low_stock_message", "Low-Stock Message", "scarcity",
        "A claim of limited inventory pressures the user, often without being real.",
        "'Only 2 left in stock!' that never decreases.",
        "medium",
    ),
    PatternType(
        "high_demand_message", "High-Demand Message", "scarcity",
        "A claim that an item is in high demand to imply it may sell out.",
        "'18 people are looking at this right now.'",
        "low",
    ),
    # --- Obstruction ------------------------------------------------------
    PatternType(
        "hard_to_cancel", "Hard to Cancel (Roach Motel)", "obstruction",
        "Signing up is easy but cancelling is deliberately difficult or hidden.",
        "Cancellation requires a phone call during limited hours.",
        "critical",
    ),
    PatternType(
        "comparison_prevention", "Comparison Prevention", "obstruction",
        "The page makes it hard to compare prices or options with competitors.",
        "Prices shown per different units to block apples-to-apples comparison.",
        "medium",
    ),
    PatternType(
        "obstruction_nagging", "Nagging", "obstruction",
        "Repeated, interruptive requests redirect the user away from their intent.",
        "Persistent 'enable notifications?' prompts on every visit.",
        "low",
    ),
    # --- Forced action ----------------------------------------------------
    PatternType(
        "forced_enrollment", "Forced Enrollment", "forced_action",
        "Completing a task forces the user to create an account or accept terms.",
        "Cannot view content without signing up for marketing emails.",
        "high",
    ),
    PatternType(
        "preselection", "Preselection", "forced_action",
        "Options that benefit the business (consent, add-ons) are checked by default.",
        "A pre-ticked 'subscribe to newsletter' box at checkout.",
        "high",
    ),
    PatternType(
        "forced_continuity", "Forced Continuity", "forced_action",
        "A free trial silently becomes a paid plan unless the user actively cancels.",
        "Card charged automatically after a trial with no reminder.",
        "high",
    ),
]


PATTERNS_BY_KEY: dict[str, PatternType] = {p.key: p for p in PATTERNS}

VALID_CATEGORIES: tuple[str, ...] = tuple(CATEGORY_META.keys())

VALID_PATTERN_KEYS: tuple[str, ...] = tuple(PATTERNS_BY_KEY.keys())


def categories() -> list[Category]:
    """Return categories with their patterns nested, in a stable order."""
    out: list[Category] = []
    for key, desc in CATEGORY_META.items():
        pats = [p for p in PATTERNS if p.category == key]
        out.append(Category(key=key, name=key.replace("_", " ").title(), description=desc, patterns=pats))
    return out


def taxonomy_prompt_block() -> str:
    """A compact, model-friendly description of the taxonomy for the system prompt."""
    lines: list[str] = []
    for cat in categories():
        lines.append(f"## {cat.name} — {cat.description}")
        for p in cat.patterns:
            lines.append(
                f"- `{p.key}` ({p.name}, default severity: {p.default_severity}): "
                f"{p.definition} e.g. {p.example}"
            )
        lines.append("")
    return "\n".join(lines).strip()
