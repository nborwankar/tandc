# tandc test fixtures

Each subdirectory is a saved real-world T&C / privacy policy used by
unit and smoke tests.

## Layout

```
<vendor>/
├── input.html            # original HTML (or text/plain body) as fetched
├── extracted.txt         # trafilatura output, committed for stability
├── fetch_meta.json       # FetchMeta as JSON
└── expected_findings.yaml # human-curated expectations for the smoke test
```

`expected_findings.yaml` is a tolerance file:

```yaml
overall_risk_min: medium   # lowest acceptable severity for overall_risk
core:
  personal_data:
    severity_min: medium
    must_mention: ["data", "collect"]    # case-insensitive substring match
  pii_protection:
    severity_min: low
  continuity:
    severity_min: medium
  liability_dispute:
    severity_min: medium
flags:
  content_licensing: { presence: present }     # or absent | unclear | any
  account_access:    { presence: any }
  payment_subscription: { presence: any }
  jurisdictional:    { presence: any }
```

## Adding a fixture

Use the helper script `tests/fixtures/_add_fixture.py <url> <slug>`
(written in Task 12, Step 3).
