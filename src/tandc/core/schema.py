"""Pydantic v2 models for the analysis report."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

SCHEMA_VERSION = "1"
TAXONOMY_VERSION = "v1"

CORE_CATEGORIES = (
    "personal_data",
    "pii_protection",
    "continuity",
    "liability_dispute",
)

FLAG_CATEGORIES = (
    "content_licensing",
    "account_access",
    "payment_subscription",
    "jurisdictional",
)

Severity = Literal["low", "medium", "high", "critical"]
CoreCategory = Literal[
    "personal_data",
    "pii_protection",
    "continuity",
    "liability_dispute",
]
FlagCategory = Literal[
    "content_licensing",
    "account_access",
    "payment_subscription",
    "jurisdictional",
]
Presence = Literal["present", "absent", "unclear"]


class FetchMeta(BaseModel):
    source: Literal["url", "stdin", "paste", "file"]
    url: str | None = None
    fetched_at: datetime
    http_status: int | None = None
    content_type: str | None = None
    content_type_was_plain: bool = False
    extractor: Literal["trafilatura", "raw"] | None = None
    raw_bytes: int
    extracted_chars: int


class Evidence(BaseModel):
    quote: str
    char_start: int
    char_end: int


class CoreFinding(BaseModel):
    category: CoreCategory
    severity: Severity
    summary: str
    why_it_matters: str
    evidence: list[Evidence] = Field(min_length=1)


class FlagFinding(BaseModel):
    category: FlagCategory
    presence: Presence
    note: str


class AnalysisReport(BaseModel):
    schema_version: str = SCHEMA_VERSION
    taxonomy_version: str = TAXONOMY_VERSION
    model: str
    analyzed_at: datetime
    input_hash: str
    fetch_meta: FetchMeta
    overall_risk: Severity
    headline: str
    core_findings: list[CoreFinding]
    flags: list[FlagFinding]
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_core_coverage(self) -> "AnalysisReport":
        cats = [f.category for f in self.core_findings]
        if sorted(cats) != sorted(CORE_CATEGORIES):
            raise ValueError(
                f"core_findings must contain exactly one of each {CORE_CATEGORIES}, "
                f"got {cats}"
            )
        return self

    @model_validator(mode="after")
    def _check_flag_coverage(self) -> "AnalysisReport":
        cats = [f.category for f in self.flags]
        if sorted(cats) != sorted(FLAG_CATEGORIES):
            raise ValueError(
                f"flags must contain exactly one of each {FLAG_CATEGORIES}, "
                f"got {cats}"
            )
        return self
