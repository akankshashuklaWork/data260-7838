# HW7 Requirement Audit

This checklist was reviewed against `DATA260_HW7_final.docx` on 2026-10-23.
`PASS` means the item is implemented or saved in the repository. `MANUAL` is
an item that cannot be verified from a local checkout.

## Submission and configuration

| Requirement | Status | Evidence |
|---|---|---|
| Shared `data260-7838` repository, with application code in shared root-level folders | PASS | `code/hw4_backend/`, `code/hw7/` |
| PDF named `{last_name}_HW7.pdf` in `reports/hw07/` and repository link at top | PASS | `Shukla_HW7.pdf` and page 1 |
| Six personal values, hardware, local model, and tagged commit at top | PASS | PDF page 1; `code/hw7/config.py` |
| `RUN_LOG.txt`, `raw/`, `METRICS.md`, `AI_USE.md`, `Report.pdf`, and `verification.json` | PASS | `reports/hw07/` |
| Objective self-check records homework, SID4, commit, model/config, seeds, checks, and pass/fail | PASS | `code/hw7/verify_hw7.py`, `verification.json` |
| Submitted source state tagged `hw7` | PASS after final audit commit | local Git tag `hw7` |
| Both named collaborators have repository access | MANUAL | Verify in GitHub repository settings before submission. |
| Short snippets followed immediately by labelled evidence images; no duplicate screenshots | PASS | `Report.pdf`, `screenshots/` |

## Part 1 — JWT, roles, and linting

| Requirement | Status | Evidence |
|---|---|---|
| JWT `POST /auth/login`, 200 valid and 401 invalid | PASS | `code/hw4_backend/main.py`; `raw/part1_jwt_results.json`; `screenshots/part1_auth.png` |
| JWT `GET /auth/me`, authenticated identity/role, missing/invalid/expired token 401 | PASS | same evidence image and JSON |
| Existing rental domain routes: authenticated read, writer/moderator create, moderator delete | PASS | `main.py`; Part 1 evidence image |
| MySQL `users` fields use unique username, password hash, and role | PASS | `models.py`, `crud.py`, `migrate_hw7.py` |
| Ruff and pre-commit show failure, fix, hook, and successful commit | PASS | `.pre-commit-config.yaml`; `raw/lint_hook_before.txt`; `raw/lint_hook_after.txt`; `screenshots/part1_lint.png` |

## Part 2 — Agent loop and reliability

| Requirement | Status | Evidence |
|---|---|---|
| HW1-style model adapter, three domain tools, tool-role messages, bounded loop | PASS | `code/hw7/agent.py` |
| One specific repair for unknown tool, malformed arguments, or schema validation failure | PASS | `agent.py`; raw attempt traces |
| Tool name/input logs and total tool-call count | PASS | `RUN_LOG.txt`; `raw/part2_attempts.json` |
| Tasks A, B, C each complete without follow-up prompt and have at least two tool calls | PASS | `raw/part2_attempts.json`; `screenshots/part2_tasks.png` |
| Nonexistent ID returns useful result without a crash | PASS | `raw/part2_impossible_id.json`; `screenshots/part2_recovery.png` |
| Twenty fixed attempts with before/after well-formed rates and four failure classes | PASS | `raw/part2_attempts.json`; `raw/part2_summary.json`; `METRICS.md` |
| Same-settings live local-model record retained without replacing failures | PASS | `raw/part2_live_model_attempts.json`; `raw/part2_live_model_summary.json` |

## Part 3 — Reflexion

| Requirement | Status | Evidence |
|---|---|---|
| At most two retries, hard call/token budgets, and clean stop reason | PASS | `code/hw7/reflexion.py`; `raw/part3_reflexion.json` |
| Concise stored failed-run evidence and reflection without chain-of-thought | PASS | `raw/part3_reflexion.json`; `screenshots/part3_reflexion.png` |
| Reflections isolated to a run and cannot alter tools, permissions, or safety gates | PASS | `reflexion.py` and report explanation |
| Original vs Reflexion comparison: success, unsupported claims, retries, calls, tokens, latency, false rejections | PASS | PDF Part 3 table; `raw/part3_reflexion.json` |
| Note about incorrect verifier rejection | PASS | PDF states 0 observed false rejections. |

## Part 4 — Citi Bike ReAct/MRKL exercise

| Requirement | Status | Evidence |
|---|---|---|
| One Citi Bike agent with pure `csv_sql`, `policy_retriever`, and `calculator` tools | PASS | `code/hw7/bike_agent.py` |
| Input/output JSON schemas and common result envelope | PASS | `TOOL_SCHEMAS` and `envelope()` in `bike_agent.py` |
| Read-only SELECT, captured official-pricing snippets, and no-eval calculator whitelist | PASS | `bike_agent.py`; pricing snapshot |
| CSV upload, URL field, Run button, timeline, results, citation, metrics, stop reason | PASS | `code/hw7/bike_ui.py`; Part 4 evidence images |
| Exact decision choices, 3–6 sentence rationale, cost breakdown, break-even, weekly data, caveat | PASS | scenario summary JSON files and PDF Part 4 |
| Two scenarios with at least 500 trips and opposite decisions | PASS | 620-row membership case and 520-row pay-per-ride case in `raw/` |
| Pricing text snapshot, URL, access date, SHA-256 for each run | PASS | `pricing/` and each scenario summary's citation object |

## Part 5 — Prompt injection and tool security

| Requirement | Status | Evidence |
|---|---|---|
| Three-goal threat model and local hostile pricing fixture | PASS | PDF Part 5; `fixtures/hostile_pricing_fixture.txt` |
| Override, non-SELECT, and CSV-exfiltration attempts before/after defenses | PASS | `raw/part5_attack_before_after.json`; `screenshots/part5_attacks.png` |
| Retrieved text is untrusted and SQL boundary is enforced | PASS | `bike_agent.py`; PDF explanation |

## Part 6 — File tools and safety gate

| Requirement | Status | Evidence |
|---|---|---|
| Six tools, `max_lines`, short edit diff, and `file_pattern` | PASS | `code/hw7/file_tools.py` |
| Module-level allow-list plus independent destructive-command check | PASS | `SAFE_PREFIXES`, `is_destructive`, `confirm_bash` |
| Temporary sandbox glob → search → read integration | PASS | `raw/part6_safety_results.json`; `screenshots/part6_safety.png` |
| Five pass and five blocked safety-gate tests, with a false allow fixed | PASS | same raw JSON and evidence image |

## Assumptions and manual confirmation

- The prompt contains both `Report.pdf` and `{last_name}_HW7.pdf`; both files are intentionally identical.
- The pricing source is a saved local snapshot of the official Citi Bike URL so the numbers used by the reproducible test runs do not change later.
- Only GitHub collaborator access remains a manual pre-submission check; the local repository cannot inspect account permissions.
