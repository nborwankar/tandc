# tandc — Terms & Conditions risk analyzer

Surfaces what's risky for users in a website or software T&C /
privacy policy: personal-data use, missing PII protections,
unilateral changes, arbitration / class-action waivers, and more.

## Status

Stage 1 v1 (CLI) and v2 (local web UI) shipped 2026-05-2x on
`main`. See `PLAN.md` for the roadmap, `DONE.md` for the ship log,
and `docs/superpowers/specs/` for the design history.

## Setup

```bash
conda create -n tandc python=3.11 -y
conda activate tandc
pip install -e ".[dev]"
export ANTHROPIC_API_KEY=sk-...   # add to ~/.zshrc / ~/.zprofile
```

## Usage — CLI (v1)

```bash
tandc analyze https://openai.com/policies/terms-of-use/
cat policy.txt | tandc analyze -
tandc analyze https://example.com/terms --opus
tandc cache list
```

Reports are written under `./reports/<host-slug>-<date>/`.

## Usage — local web UI (v2)

The recommended way to start the server is the launcher script — it
sets up the conda PATH, checks the API key, and execs `tandc serve`:

```bash
./scripts/serve.sh                       # 127.0.0.1:8765 (default)
./scripts/serve.sh --port 9000
./scripts/serve.sh --host 0.0.0.0        # LAN-accessible (opt-in)
./scripts/serve.sh --reload --debug      # dev mode
```

Then open `http://127.0.0.1:8765/` in any browser. Submit a URL,
pasted text, or upload an HTML / TXT / PDF file; the rendered
report appears inline. FastAPI-generated API docs live at
`/docs`.

Exit codes (matches the CLI):

| Code | Meaning |
|------|---------|
| 0 | clean shutdown |
| 4 | `ANTHROPIC_API_KEY` not set |
| 5 | port already in use |

### Hitting the API directly

```bash
curl -X POST http://127.0.0.1:8765/analyze \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://example.com/terms","use_cache":true}'

curl -X POST http://127.0.0.1:8765/analyze \
  -H 'Content-Type: application/json' \
  -d '{"text":"...policy body...","source_url":"https://..."}'

curl -X POST http://127.0.0.1:8765/analyze \
  -F "file=@policy.pdf;type=application/pdf"
```

Web mode writes the same `./reports/<slug>-<date>/` bundle the CLI
does. The response JSON includes `report_dir` (absolute path) and
`cache_hit` (bool).
