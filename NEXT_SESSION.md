# NEXT_SESSION — tandc

> Handoff note for the next session after a `/compact`. Once you've
> read this, it has served its purpose — delete it (and re-create at
> the next session-end).

## Current state

Stage 1 v1 (CLI) + v2 (local web UI) both shipped. Public repo live at
<https://github.com/nborwankar/tandc>, MIT-licensed, GitHub Actions
configured as manual-only.

- Branch: `main`, in sync with `origin/main`.
- Working tree: clean.
- Tests: 126 unit (`pytest -m "not slow"`) — all green at last run.
- 6-vendor live smoke (`pytest -m slow`) — last full run was green;
  costs ~$0.06 each.

## Most recent work

Post-publish polish round: README install instructions tightened
(clone step, working example URLs, API-key console link, prerequisites,
user-vs-dev install, venv alternative, "How it works" section, `.env`
note, linkified paths), MIT LICENSE added with matching `pyproject.toml`
metadata, GitHub Actions workflow added as manual-only, 12 GitHub topics
set, and a sweep that removed all pre-rebuild SHA references and
historical narrative from `DONE.md` / `PLAN.md` / `CLAUDE.md`.

## Immediate next step (when you resume)

**Stage 2 brainstorm — Chrome extension.** Open question is whether to
build a fresh extension that calls `localhost:8765/analyze`, or extend
the official Claude for Chrome extension if it exposes a plug-in
surface (would need research). Either way the backend is the v2
`POST /analyze` endpoint — no new server-side work required.

Recommended kick-off: `/brainstorm` (superpowers brainstorming skill)
with the prompt: *"Stage 2 — Chrome extension for tandc. Two
candidate paths to compare: fresh extension vs extending Claude for
Chrome. Backend is `POST /analyze` on `localhost:8765`."*

## Things deliberately not done

- README badges (build status, license) — pending; would benefit from
  CI being non-manual first.
- CHANGELOG.md — pending; not urgent for a pre-v1.0 personal project.
- Screenshots/GIFs of the web UI — would require a manual capture pass.
- Stage 2 implementation — gated on the brainstorm above.

## Standing constraints to keep in mind

- Local commits unless explicitly told otherwise — but the repo IS now
  public, so `git push` to `origin/main` is fine when the user approves.
- Paid Claude calls (anything that triggers a real `tandc analyze`
  against a URL/file/paste) need explicit per-call confirmation.
- Test-log rule: `docs/test_runs/*` is gitignored; never commit raw
  pytest output to that path without a manual secret grep.
- `~/.env` holds the canonical key; this session may have stale
  `$ANTHROPIC_API_KEY` from before the 2026-05-21 rotation. New shells
  pick up the rotated key from `~/.zshrc`.
