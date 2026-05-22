# tandc — Terms & Conditions risk analyzer

Surfaces what's risky for users in a website or software T&C /
privacy policy: personal-data use, missing PII protections,
unilateral changes, arbitration / class-action waivers, and more.

## Status

Stage 1 v1 (CLI) and v2 (local web UI) shipped 2026-05-21 on
`main`. See [PLAN.md](PLAN.md) for the roadmap, [DONE.md](DONE.md)
for the ship log, and [docs/superpowers/specs/](docs/superpowers/specs/)
for the design history.

## Setup

You need: git, Python 3.11+, a virtual-env manager (conda or venv — both shown below), and an Anthropic API key from <https://console.anthropic.com/settings/keys>.

```bash
# 1. Clone
git clone https://github.com/nborwankar/tandc.git
cd tandc

# 2. Create a virtual environment — pick ONE of the two:

# (a) conda (recommended if you have it)
conda create -n tandc python=3.11 -y
conda activate tandc

# (b) venv (stdlib, no extra install needed)
python3.11 -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate

# 3. Install the package
#     Users (just want to run the tool):
pip install -e .
#     Contributors (also need pytest, ruff, etc.):
pip install -e ".[dev]"

# 4. Set your API key (and add this line to ~/.zshrc or your shell rc file)
export ANTHROPIC_API_KEY=sk-ant-...   # get one at https://console.anthropic.com/settings/keys

# 5. Verify
tandc --help
```

## Usage — CLI (v1)

```bash
tandc analyze https://docs.github.com/en/site-policy/github-terms/github-terms-of-service
cat policy.txt | tandc analyze -
tandc analyze https://slack.com/terms-of-service/user --opus
tandc cache list
```

Reports are written under `./reports/<host-slug>-<date>/`.

Three more T&C URLs known to fetch and analyze cleanly, if you want to try the tool against different services:

- Dropbox — <https://www.dropbox.com/terms>
- Discord — <https://discord.com/terms>
- Wikimedia Foundation — <https://foundation.wikimedia.org/wiki/Terms_of_Use/en>

(Some sites — notably OpenAI's policy pages — return HTTP 403 to automated fetches and won't work directly; paste the text via stdin instead.)

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
