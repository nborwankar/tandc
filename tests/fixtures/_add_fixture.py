"""Download a policy URL and save the four fixture files. Run manually."""

from __future__ import annotations

import sys
from pathlib import Path

import httpx

from tandc.core.extract import extract_text, is_plain_text_content_type
from tandc.core.loader import _USER_AGENT  # type: ignore[attr-defined]
from tandc.core.schema import FetchMeta
from datetime import datetime, timezone


def main():
    if len(sys.argv) != 3:
        print("Usage: python _add_fixture.py <url> <slug>", file=sys.stderr)
        sys.exit(2)
    url, slug = sys.argv[1], sys.argv[2]
    out = Path(__file__).parent / slug
    out.mkdir(parents=True, exist_ok=True)

    resp = httpx.get(
        url, headers={"User-Agent": _USER_AGENT}, timeout=30.0, follow_redirects=True
    )
    resp.raise_for_status()
    ct = resp.headers.get("content-type")
    body = resp.text
    text, extractor = extract_text(body, ct)
    if text is None:
        print(
            f"WARNING: extraction empty for {url}; saving raw body only",
            file=sys.stderr,
        )
        text = ""

    (out / "input.html").write_text(body, encoding="utf-8")
    (out / "extracted.txt").write_text(text, encoding="utf-8")
    meta = FetchMeta(
        source="url",
        url=url,
        fetched_at=datetime.now(timezone.utc),
        http_status=resp.status_code,
        content_type=ct,
        content_type_was_plain=is_plain_text_content_type(ct),
        extractor=extractor,
        raw_bytes=len(resp.content),
        extracted_chars=len(text),
    )
    (out / "fetch_meta.json").write_text(
        meta.model_dump_json(indent=2), encoding="utf-8"
    )
    (out / "expected_findings.yaml").write_text(
        "# Edit this file with curated expectations for the smoke test.\n"
        "overall_risk_min: medium\n"
        "core:\n"
        "  personal_data: { severity_min: low }\n"
        "  pii_protection: { severity_min: low }\n"
        "  continuity: { severity_min: low }\n"
        "  liability_dispute: { severity_min: low }\n"
        "flags:\n"
        "  content_licensing: { presence: any }\n"
        "  account_access: { presence: any }\n"
        "  payment_subscription: { presence: any }\n"
        "  jurisdictional: { presence: any }\n",
        encoding="utf-8",
    )
    print(f"wrote {out}/")


if __name__ == "__main__":
    main()
