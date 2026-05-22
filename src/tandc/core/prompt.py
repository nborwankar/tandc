"""System prompt + user message templates for the Claude analyzer."""

from __future__ import annotations

import json
import re

from tandc.core.schema import (
    CORE_CATEGORIES,
    FLAG_CATEGORIES,
    TAXONOMY_VERSION as TAXONOMY_VERSION,  # re-export for callers
    AnalysisReport,
)

# Match any <DOCUMENT> / </DOCUMENT> variant — case-insensitive, with or
# without attributes, self-closing or not. Used to neutralise prompt-injection
# attempts where a malicious T&C body contains literal DOCUMENT tags.
_DOC_TAG_RE = re.compile(r"<\s*/?\s*document\b[^>]*>", re.IGNORECASE)

_CATEGORY_DEFS = {
    "personal_data": "What PII is collected, why, how long retained, who it's shared with, whether it's used for model training.",
    "pii_protection": "Absence of encryption-at-rest claims, breach-notification commitments, deletion rights, portability rights, or processor disclosure.",
    "continuity": "Unilateral right to change terms without notice, service termination without refund, data deletion on account close, sunset clauses.",
    "liability_dispute": "Arbitration mandates, class-action waivers, jury-trial waivers, liability caps, unfavourable choice-of-law.",
    "content_licensing": "Perpetual/irrevocable/worldwide licence to user content, sublicensing, training-data clauses, moral-rights waivers.",
    "account_access": "Termination without cause, suspension procedures, appeal rights, content-removal authority.",
    "payment_subscription": "Auto-renewal, refund policy, price-change notice, cancellation friction, dark-pattern indicators.",
    "jurisdictional": "GDPR / CCPA / HIPAA / COPPA stance, data residency, international transfer mechanism, regulator-cooperation language.",
}


def _category_docs() -> str:
    lines = ["CORE categories (full treatment — one CoreFinding per category, always):"]
    for c in CORE_CATEGORIES:
        lines.append(f"  - {c}: {_CATEGORY_DEFS[c]}")
    lines.append("")
    lines.append(
        "FLAG categories (one FlagFinding per category, always, with presence and note):"
    )
    for c in FLAG_CATEGORIES:
        lines.append(f"  - {c}: {_CATEGORY_DEFS[c]}")
    return "\n".join(lines)


def build_system_prompt() -> str:
    """Build the system prompt. Stable across calls — eligible for prompt caching."""
    schema_json = json.dumps(AnalysisReport.model_json_schema(), indent=2)
    return f"""You analyze website / software Terms & Conditions and privacy policies and surface what is risky for an ordinary user. You are NOT giving legal advice; you are surfacing patterns and clauses that a careful reader would want to know about before accepting.

Taxonomy version: {TAXONOMY_VERSION}

{_category_docs()}

OUTPUT RULES (strict):

1. Return ONLY valid JSON matching the AnalysisReport schema below.
2. core_findings MUST contain exactly one entry for each of the {len(CORE_CATEGORIES)} CORE categories, even if severity is "low".
3. flags MUST contain exactly one entry for each of the {len(FLAG_CATEGORIES)} FLAG categories, with presence in {{present, absent, unclear}}.
4. Every Evidence.quote MUST be a verbatim substring of the DOCUMENT body wrapped in <DOCUMENT>...</DOCUMENT> tags. char_start and char_end are 0-indexed character offsets into that body.
5. If the document is genuinely silent on a topic, set the FlagFinding presence to "absent" and explain in `note`. For CORE categories where silence itself is the risk (e.g. no PII protection language), the CoreFinding severity reflects that.
6. overall_risk is the worst severity across core_findings, biased upward if multiple categories are high/critical.
7. headline is a single sentence a user would screenshot — concrete, not abstract.

JSON SCHEMA (AnalysisReport):

{schema_json}
"""


def build_user_message(document_text: str) -> str:
    """Wrap the document body in tags, neutralising any embedded tag injection.

    The regex strips any `<document...>` / `</document...>` variant (case-
    insensitive, with or without attributes) from the body so the wrapper tags
    we add appear exactly once.
    """
    safe = _DOC_TAG_RE.sub(lambda m: m.group(0).replace("<", "&lt;"), document_text)
    return f"<DOCUMENT>\n{safe}\n</DOCUMENT>"
