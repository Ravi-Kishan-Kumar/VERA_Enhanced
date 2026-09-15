# Codex round-two notes — 2026-09-14

## Ownership and scope

Read `CODEX_TASKS_ROUND2.md` completely and performed its six tasks in order. Worked on
`feat/training-and-release` without branch switching, stash/reset/rebase/clean, or push.
Claude's live labeling/training processes were not started, stopped, or signaled. No edits were
made to training, ML modules, notebooks, live data/reports/artifacts, `.env`, `HANDOFF.md`, or
`DECISIONS.md`. Existing training diffs and untracked input/data/report files remain outside this
commit. This document replaces a HANDOFF update while that file is owned by Claude.

## Changes

1. `deploy/huggingface-space/`: source-only Docker package, UID 1000, port 7860, local Redis,
   migrations, solo worker, bounded child shutdown and failure propagation. Separate Space
   checkout instructions include `.dockerignore`; no image was built or run locally.
2. API: sanitized request IDs on responses/logs; JSON request logs use route templates and avoid
   bodies/query strings. Rate limiting is bounded, process-local, and proxy-aware only with
   explicit trust configuration. Body cap applies before handlers persist side effects. Security
   headers cover rejection/error responses. `/ready` checks only the DB; `/health` remains liveness.
3. Demo importer: CSV/JSONL validation before submission, explicit dry-run, 429 backoff, safe
   polling, and done/failed/unconfirmed summaries. Ambiguous POST failures are not resubmitted.
   Parsing, mock HTTP requests, dry-run isolation, and timeout behavior are unit-tested.
4. CI: browser smoke and Space image-build jobs; pip-audit/npm audit produce artifacts for
   manual triage, without automatic fixes. Dependabot is weekly. Existing dependency pins remain.
5. Docs: deployment path, operating boundaries/runbook, model-card skeleton, environment examples.
   `human_validated=false`; no claimed model metrics or invented gate outcomes.
6. Frontend: stronger typography/contrast, aligned brand mark, finite CSS transitions, focus and
   touch targets, reduced motion, clearer ranking copy, and no readiness-success layout shift.
   The existing-project redesign skill guided targeted improvements with the current Next/React,
   local fonts, and CSS stack; no new UI dependencies or decorative image downloads were added.
   429 cooldown honors Retry-After without auto-submitting; DB-unavailable checks preserve drafts.
   Static metadata, branded social image/favicon, robots, sitemap, and canonical-origin validation
   do not need a trained backend. Removed redundant decoding of Next's decoded ASIN parameter.

## Verification

Passed locally (source/test checks, not model evaluation):

```powershell
.\.venv\Scripts\python.exe -m ruff check backend/app/api backend/app/main.py backend/app/config.py backend/scripts/seed_demo.py backend/tests/test_hardening.py backend/tests/test_seed_demo.py backend/tests/conftest.py
.\.venv\Scripts\python.exe -m black --check backend/app/api backend/app/main.py backend/app/config.py backend/scripts/seed_demo.py backend/tests/test_hardening.py backend/tests/test_seed_demo.py backend/tests/conftest.py
.\.venv\Scripts\python.exe -m mypy backend/app/api backend/app/main.py backend/app/config.py backend/scripts/seed_demo.py --follow-imports=silent
.\.venv\Scripts\python.exe -m pytest backend/tests -k "not pipeline" --ignore=backend/tests/test_pipeline.py -q
# From frontend/:
npm run test:e2e -- --workers=1
```

The final `npm run lint`, `npm run typecheck`, and `npm run build` sequence passed. The production
build ran once, with prerender concurrency limited to one worker and Rust worker threads limited
to two. No trained backend was required during prerendering.

Also passed: YAML parsing of CI/Dependabot/Render and `sh -n` syntax validation of the Space
entrypoint using Git's shell (not execution). Reviewed desktop/mobile screenshots and static
accessibility on analyzer, rankings, detail, and methodology. Browser tests cover narrow layout,
keyboard skip navigation, reduced motion, metadata, successful results, pagination failure, rate
limits, and readiness recovery. All browser `/api/**` calls are intercepted, including defaults
for missing fixtures; none reach the shared worker. Initial new recovery tests used an ambiguous
alert selector matching Next's route announcer; scoped it to main content and reran successfully.
No Lighthouse audit, remote dependency scan, Docker runtime test, or trained-model check was run.

## Exact next steps / unresolved release work

1. Claude continues the active runs. Do not restart, relabel, retrain, regenerate reports, or alter
   frozen paths until the user explicitly says **"training released"**.
2. Claude provides accepted gate evidence and a complete compatible artifact manifest. Check
   `reports/experience_export.json` and `reports/evaluation_report.json`; publish authoritative
   agreement evidence under reports before quoting G1. Preserve non-human reference provenance.
3. Once a PR/approved CI run exists, inspect Playwright, Space build, and dependency scan outputs.
   The scanner jobs are report-only: green CI alone does not prove no vulnerabilities. Triage
   findings manually and document any required pin updates. The pre-existing full-project mypy
   issues in frozen labeling code remain for its owner, not this patch.
4. Obtain user approval before creating Supabase/HF/Vercel/monitor resources or uploading/pushing.
   Verify proxy CIDRs in the actual deployment; until then peer-based buckets may group users.
   Production scaling requires a shared/edge limiter; this process-local limiter is for one instance.
5. After artifact acceptance and on an approved target, build/run the Space, verify migrations,
   cold start, worker crash/restart, queue recovery, memory headroom, health/readiness, and a
   controlled non-sensitive review through completion. `/ready` alone is not model readiness.
6. Configure `API_URL` and `SITE_URL` for the frontend, confirm canonical/share URLs, and test
   deployed 429/503/proxy behavior. Define public-demo retention/deletion and contact procedures.
7. Only after that, run the demo importer first with `--dry-run`, then on approved fixtures.
   Investigate any unconfirmed submission before rerunning; the public API has no idempotency key.

No claim is made that the remaining model or deployment gates have passed.

## UI round 3 audit — 2026-09-15

### Before-state evidence

Captured the analyzer, rankings, product detail, methodology, not-found, route error, and loading
states in light and dark themes at 375, 768, and 1440 CSS pixels. The 42 baseline images are in
`frontend/test-results/audit-before/`. All API calls were intercepted; no request reached the live
backend, worker, data, reports, or training processes. The capture ran sequentially in one browser.

### Findings to correct

1. **Aspect evidence is misleading when nothing is detected.** Product detail renders all ten
   aspects as “Not mentioned”, even though the task and API semantics require showing only evidence
   actually mentioned by reviews. This is especially noisy on 375 px screens.
2. **The Round 1 benchmark table over-compresses at 375 px.** Its three columns remain in one narrow
   row layout, shrinking labels and values below the otherwise comfortable reading scale. It needs
   a mobile presentation that preserves comparison context without inventing data.
3. **Benchmark content cannot represent an unfinished round.** It is a single object whose every
   field requires a metric. A typed discriminated list is needed so Round 2 can be honestly marked
   `pending` with no numeric placeholders.
4. **Analyzer polling is heavier and less resilient than the API permits.** It repeatedly fetches
   the full review every two seconds. The lightweight `/reviews/{id}/status` contract should drive
   bounded exponential backoff, with the full record fetched only after completion.
5. **Validation and degraded states are incomplete.** Empty/short/long text needs explicit inline
   feedback independent of browser-native messages. Queue failure, network failure, 429 retry,
   database readiness, and missing-model/worker failure need distinct, truthful copy; `/ready`
   proves database readiness only and must not be presented as model readiness.
6. **Elevated styling has multiple sources of truth.** Navigation, command palette, status notice,
   and score result repeat one-off translucent fills, borders, blur, radii, and literal shadows.
   They need shared semantic surface/radius/shadow/type/spacing tokens plus a solid fallback when
   `backdrop-filter` is unavailable.
7. **Some responsive controls and spacing are inefficient.** Ranking density controls remain visible
   above the mobile card layout even though density does not affect those cards. The 375 px analyzer
   also spends excessive vertical space between the floating navigation and the hero; this pushes
   the primary task farther below the fold.
8. **Typography needs systematic numeric treatment.** Most scores use the mono face, but tabular
   numeral behavior is not guaranteed globally for metrics. Display wrapping is locally balanced
   rather than defined once, leaving avoidable heading-orphan risk.

The sampled declared token pairs pass WCAG AA contrast by calculation: light body 17.10:1, light
muted 6.54:1, light primary link 4.77:1, light primary button 4.84:1; dark body 18.45:1, dark muted
6.99:1, dark primary link/button 6.62:1. The palette therefore needs no speculative contrast shift.
The existing `@axe-core/playwright` package is not installed; per the brief it will not be added as
a new dependency, and an automated axe pass remains a follow-up.

### Round 3 changes

- Centralized semantic colour, control/card/shell radius, elevated blur/fallback fill, shadow,
  responsive page spacing, display type, and metric-number behavior in `globals.css`. Navigation,
  command palette, service notice, and result surfaces now share the elevated-surface contract.
- Reduced the narrow-screen gap above page heroes, hid desktop-only density controls on mobile,
  and replaced the compressed 375 px benchmark table with structured comparison cards. The same
  data remains a table from the `sm` breakpoint upward.
- Aspect views now render only detected evidence. A truthful empty-evidence explanation replaces
  the previous ten-row “Not mentioned” list; no empty category is plotted.
- Analyzer validation now gives inline empty, short, over-10,000-character, and rating-contract
  errors. Drafts survive every failure. Readiness copy explicitly describes database availability,
  not worker/model readiness.
- Polling now uses `/reviews/{id}/status` with bounded 1.5× backoff from 1.5 to 8 seconds and a
  three-minute client wait window. It fetches the full review once only after `done`, or once after
  `failed` to classify a safe worker/model message. Internal artifact paths are never rendered.
- Replaced artificial internal-stage progression with only states the API actually confirms:
  submission, queue, processing, and final retrieval. Scores, intervals, aspects, and explanations
  appear only from a completed API response.
- Refactored benchmark content into a typed discriminated list. Round 1 retains only brief-approved
  figures; Round 2 has `status: "pending"`, no metric properties, and renders “Evaluation in
  progress”. Its TODO names `evaluation_report.json`, `cv_comparison.json`,
  `aspect_detector.json`, and `calibration.json` as the only future sources.
- Fixed a server/client motion-path mismatch by making the initial SVG path state deterministic;
  reduced motion still resolves immediately.

### Round 3 verification

All checks ran from `frontend/` without the live backend, trained models, Python, or GPU work:

```powershell
npm run lint
npm run typecheck
$env:NEXT_PRIVATE_BUILD_WORKER='1'; $env:RAYON_NUM_THREADS='2'; npm run build
npm run test:e2e -- --workers=1
```

Final results: ESLint passed with zero warnings; Next route type generation and `tsc --noEmit`
passed; the production build completed with one page-data/static-generation worker and generated
all nine routes; Playwright passed **24/24** tests across desktop Chromium and mobile Chromium in
one worker. The suite exercises empty/short/long validation, queue-to-processing-to-success with
three lightweight status requests and one full-result request, 429 Retry-After, network failure,
database-unavailable recovery, sanitized missing-model failure, pending benchmarks, keyboard and
reduced-motion behavior, chart text alternatives, and horizontal overflow at 375/768/1024/1440 px.

The first extended browser pass was 20/22 because a new text locator also matched an accessible
`sr-only` table caption; the product behavior was correct. The locator was made exact, the full
suite was rerun after the fix, and the final 24/24 result above is authoritative.

The persisted comparison galleries contain 42 files each in
`frontend/test-results/audit-before/` and `frontend/test-results/audit-after/`: seven route/states ×
three widths × two themes, with every API call mocked. Representative visual comparison confirmed
the fixed hero spacing, mobile benchmark cards, pending-round state, empty aspect state, solid glass
fallback styling, and unchanged legibility in both themes. These artifacts are intentionally
gitignored.

A transient Lighthouse 12.8.2 CLI run against the local production build was saved to
`frontend/test-results/lighthouse-mobile.json`; it did not alter project dependencies or lockfiles.
Mobile scores were Performance **89**, Accessibility **100**, Best Practices **96**, SEO **100**.
Lab metrics were FCP 0.9 s, LCP 3.7 s, TBT 80 ms, CLS 0, Speed Index 0.9 s. This localhost run used
Lighthouse throttling and had no backend on port 8000, so it is diagnostic evidence rather than a
deployed-production claim.

### Known limitations and next steps

1. Round 2 remains deliberately pending. Populate a completed entry only after Claude supplies and
   accepts all four named reports; do not estimate interim values.
2. No live model, worker, backend, training result, or production deployment was exercised. After
   the user says **“training released”**, run a controlled end-to-end review against accepted model
   artifacts and confirm real queue recovery and failure copy.
3. Add per-route axe automation only if the project later accepts `@axe-core/playwright`; the package
   was absent and the task prohibited adding it. Lighthouse accessibility covered the local home
   route, while Playwright covers landmarks, labels, keyboard focus, and text alternatives.
4. Repeat Lighthouse on the deployed origin with its real cache/CDN/backend conditions. The local
   mobile LCP (3.7 s, with 0 layout shift) is the main remaining performance investigation; capture
   multiple production runs before choosing any further optimization.

## Follow-up: prompt cleanup

At the user's explicit request, deleted the tracked `CODEX_PROMPT.md` and untracked
`CODEX_TASKS_ROUND2.md` from the workspace. Removed the tracked prompt from the current Git
snapshot and added root-level prompt/task ignore patterns. Updated README's live-boundary link;
the training freeze remains in force. Kept these operational notes because they are not a prompt.
Verified file absence, ignore rules, and staged whitespace. This documentation-only cleanup does
not require rerunning application tests. No push or history rewrite was performed: the tracked
prompt is recoverable from older commits; the untracked task file has no Git recovery copy.
