# Test Log — tandc

| datetime | task | command | passed | failed | skipped | deselected | duration_sec | commit | raw_output |
|----------|------|---------|--------|--------|---------|------------|--------------|--------|------------|
| 2026-05-20 | t01 | pytest --collect-only | 0 | 0 | 0 | 0 | 0 | <pending> | docs/test_runs/2026-05-20_t01_scaffold.txt |
| 2026-05-20 | t02 | pytest tests/test_paths.py | 13 | 0 | 0 | 0 | 0.02 | <pending> | docs/test_runs/2026-05-20_t02_paths.txt |
| 2026-05-20 | t03 | pytest tests/test_schema.py | 9 | 0 | 0 | 0 | 0.18 | <pending> | docs/test_runs/2026-05-20_t03_schema.txt |
| 2026-05-20 | t04 | pytest tests/test_cache.py | 9 | 0 | 0 | 0 | 0.05 | <pending> | docs/test_runs/2026-05-20_t04_cache.txt |
| 2026-05-20 | t05 | pytest tests/test_extract.py | 7 | 0 | 0 | 0 | 1.87 | <pending> | docs/test_runs/2026-05-20_t05_extract.txt |
| 2026-05-20 | t06 | pytest tests/test_loader.py | 7 | 0 | 0 | 0 | 0.31 | <pending> | docs/test_runs/2026-05-20_t06_loader.txt |
| 2026-05-20 | t07 | pytest tests/test_prompt.py | 7 | 0 | 0 | 0 | 0.05 | <pending> | docs/test_runs/2026-05-20_t07_prompt.txt |
| 2026-05-20 | t08 | pytest tests/test_analyzer.py | 6 | 0 | 0 | 0 | 0.06 | <pending> | docs/test_runs/2026-05-20_t08_analyzer.txt |
| 2026-05-20 | t09 | pytest tests/test_render.py | 7 | 0 | 0 | 0 | 0.05 | <pending> | docs/test_runs/2026-05-20_t09_render.txt |
| 2026-05-20 | t10 | pytest -v (full suite) | 69 | 0 | 0 | 0 | 0.59 | 5cf31ac | docs/test_runs/2026-05-20_t10_core_init.txt |
| 2026-05-20 | t11 | pytest tests/test_cli.py -v | 10 | 0 | 0 | 0 | 0.46 | 5bbd801 | docs/test_runs/2026-05-20_t11_cli.txt |
| 2026-05-20 | t11 | pytest -v (full suite) | 85 | 0 | 0 | 0 | 0.64 | 5bbd801 | docs/test_runs/2026-05-20_t11_full.txt |
| 2026-05-20 | t13 | pytest -v (default, smoke skipped by fixture) | 86 | 0 | 6 | 0 | 0.70 | bdd466c | docs/test_runs/2026-05-20_t13_default.txt |
| 2026-05-20 | t13 | pytest --collect-only -q -m slow (6 collected, none run) | 0 | 0 | 0 | 0 | 0.42 | bdd466c | docs/test_runs/2026-05-20_t13_collect.txt |
| 2026-05-20 | t14 | pytest -m "not slow" -q (unit suite, no live calls) | 86 | 0 | 0 | 6 | 0.70 | 16b2e69 | docs/test_runs/2026-05-20_t14_e2e_anthropic.txt |
| 2026-05-20 | t14 | tandc analyze https://www.anthropic.com/legal/consumer-terms (live) | n/a | 0 | n/a | n/a | n/a | 16b2e69 | docs/test_runs/2026-05-20_t14_e2e_anthropic.txt |
| 2026-05-20 | t14 | tandc analyze (cached re-run) | n/a | 0 | n/a | n/a | n/a | 16b2e69 | docs/test_runs/2026-05-20_t14_e2e_cached.txt |
| 2026-05-20 | t14 | tandc analyze - (stdin) | n/a | 0 | n/a | n/a | n/a | 16b2e69 | docs/test_runs/2026-05-20_t14_e2e_stdin.txt |
| 2026-05-20 | t14 | tandc analyze --json (json mode, cached) | n/a | 0 | n/a | n/a | n/a | 16b2e69 | docs/test_runs/2026-05-20_t14_e2e_json.txt |
| 2026-05-20 | t14 | tandc analyze bad-domain (fetch fail, exit=2) | n/a | 0 | n/a | n/a | n/a | 16b2e69 | docs/test_runs/2026-05-20_t14_fetch_fail.txt |
| 2026-05-20 | t14 | tandc cache clear (no --yes, exit=1) | n/a | 0 | n/a | n/a | n/a | 16b2e69 | docs/test_runs/2026-05-20_t14_cache_clear.txt |
| 2026-05-21 | v2-t2 | pytest tests/test_schema.py::test_fetch_meta_accepts_{paste,file}_source (pre-fix, expect fail) | 0 | 2 | 0 | 0 | 1.21 | e2cd027 | docs/test_runs/2026-05-21_stage1v2_t2_fail.txt |
| 2026-05-21 | v2-t2 | pytest tests/test_schema.py (post-fix, full suite) | 11 | 0 | 0 | 0 | 0.44 | <pending> | docs/test_runs/2026-05-21_stage1v2_t2_pass.txt |
| 2026-05-21 | v2-t3 | pytest tests/test_loader.py -k text_to_meta (pre-impl, expect ImportError) | 0 | 5 | 0 | 7 | 0.49 | <pending> | docs/test_runs/2026-05-21_stage1v2_t3_fail.txt |
| 2026-05-21 | v2-t3 | pytest tests/test_loader.py (post-impl, full suite) | 12 | 0 | 0 | 0 | 0.54 | <pending> | docs/test_runs/2026-05-21_stage1v2_t3_pass.txt |
| 2026-05-21 | v2-t3 | pytest tests/test_loader.py (post-cleanup hoist imports) | 12 | 0 | 0 | 0 | 0.55 | <pending> | docs/test_runs/2026-05-21_loader_cleanup.txt |
| 2026-05-21 | v2-t4 | pytest tests/test_core_analyze.py -k AnalyzePrepared (pre-impl, expect ImportError) | 0 | 3 | 0 | 6 | 0.51 | <pending> | docs/test_runs/2026-05-21_stage1v2_t4_fail.txt |
| 2026-05-21 | v2-t4 | pytest tests/test_core_analyze.py (post-impl) | 9 | 0 | 0 | 0 | 0.47 | <pending> | docs/test_runs/2026-05-21_stage1v2_t4_pass.txt |
| 2026-05-21 | v2-t4 | pytest tests/ -m "not slow" (full unit suite) | 98 | 0 | 0 | 6 | 0.76 | <pending> | docs/test_runs/2026-05-21_stage1v2_t4_full.txt |
| 2026-05-21 | v2-t6 | pytest tests/web/test_pdf.py -v (pre-impl, expect ImportError) | 0 | 0 | 0 | 0 | 0.06 | <pending> | docs/test_runs/2026-05-21_stage1v2_t6_fail.txt |
| 2026-05-21 | v2-t6 | pytest tests/web/test_pdf.py -v (post-impl) | 5 | 0 | 0 | 0 | 0.48 | <pending> | docs/test_runs/2026-05-21_stage1v2_t6_pass.txt |
| 2026-05-21 | v2-t8 | pytest tests/web/test_api.py -v (post-impl, fixed UploadFile isinstance bug) | 14 | 0 | 0 | 0 | 0.63 | <pending> | docs/test_runs/2026-05-21_stage1v2_t8_api.txt |
| 2026-05-21 | v2-t8 | pytest tests/ -m "not slow" (full unit suite) | 117 | 0 | 0 | 6 | 0.85 | <pending> | docs/test_runs/2026-05-21_stage1v2_t8_full.txt |
| 2026-05-21 | v2-t9 | pytest tests/ -m "not slow" (post vanilla-JS frontend) | 117 | 0 | 0 | 6 | 0.85 | <pending> | docs/test_runs/2026-05-21_task9_vanilla_js_frontend.txt |
| 2026-05-21 | v2-t10 | pytest tests/web/test_serve.py -v (pre-impl, expect ImportError) | 0 | 0 | 0 | 0 | 0.06 | <pending> | docs/test_runs/2026-05-21_stage1v2_t10_fail.txt |
| 2026-05-21 | v2-t10 | pytest tests/web/test_serve.py -v (post-impl) | 4 | 0 | 0 | 0 | 0.56 | <pending> | docs/test_runs/2026-05-21_stage1v2_t10_pass.txt |
| 2026-05-21 | v2-t11 | pytest tests/web/test_cli_serve.py -v (pre-impl, expect _serve_run AttributeError) | 0 | 4 | 0 | 0 | 0.72 | <pending> | docs/test_runs/2026-05-21_stage1v2_t11_fail.txt |
| 2026-05-21 | v2-t11 | pytest tests/web/test_cli_serve.py -v (post-impl) | 4 | 0 | 0 | 0 | 0.57 | <pending> | docs/test_runs/2026-05-21_stage1v2_t11_pass.txt |
| 2026-05-21 | v2-t11 | pytest tests/ -m "not slow" (full unit suite, post serve subcommand) | 125 | 0 | 0 | 6 | 0.85 | <pending> | docs/test_runs/2026-05-21_stage1v2_t11_pass.txt |
| 2026-05-21 | v2-cache-hit-fix | pytest tests/ -m "not slow" (cache_hit threaded through analyze/_prepared to /analyze response) | 126 | 0 | 0 | 6 | 0.89 | <pending> | docs/test_runs/2026-05-21_v2_cache_hit_fix.txt |
| 2026-05-21 | s1v2-t12 | manual e2e (curl 3 modes + errors + cache hit) | n/a | 0 | 0 | 0 | 108 | eb7f6c2 | docs/test_runs/2026-05-21_v2_curl_*.txt |
| 2026-05-21 | s1v2-t14 | pytest -m "not slow" (final) | 126 | 0 | 0 | 6 | 0.88 | df0e8e8 | docs/test_runs/2026-05-21_v2_final_unit.txt |
| 2026-05-21 | s1v2-t14 | pytest -m slow (regression) | 5 | 1 | 0 | 126 | 388 | df0e8e8 | docs/test_runs/2026-05-21_v2_final_slow.txt |
| 2026-05-21 | s1v2-t14 | pytest -m slow -k dropbox (post-fixture-fix) | 1 | 0 | 0 | 5 | 47 | (pending) | docs/test_runs/2026-05-21_v2_dropbox_recheck.txt |
