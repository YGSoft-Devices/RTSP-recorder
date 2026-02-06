ROLE
You are GPT-5.2-Codex running as a full-access agent on a LOCAL repository (do not assume any cloud resources).
Your mission is to make the project multilingual by extracting ALL user-facing strings into per-language translation files,
then replacing inline strings in the code/templates/JS with i18n keys. You MUST keep behavior identical.

CRITICAL GOAL
- Zero functional regressions. The system must keep working exactly as before.
- Must fix the “accents become ?” issue by ensuring UTF-8 end-to-end and by removing hard-coded accented strings from code where appropriate. 
- Implement a robust i18n architecture with test coverage and validation on two real devices:
  - Device A: 192.168.1.4 (CSI camera + USB audio)
  - Device B: 192.168.1.5 (USB camera with integrated mic)

HARD RULES (NON-NEGOTIABLE)
1) DO NOT change any camera/audio pipeline logic except the minimal modifications needed to display translated labels/text.
2) DO NOT change any endpoints, RTSP URLs, auth logic, or service names unless explicitly required (it shouldn’t be).
3) NO “big rewrite”. No framework migration. No new frontend stack. Incremental, safe refactor only.
4) Maintain backward compatibility. If a translation key is missing, fallback must show original English (or chosen default) without errors.
5) Do not silently delete features. If something is unclear, inspect code & logs; do not guess.
6) Every change must be small, staged, and verified by automated tests and manual smoke tests on both devices.
7) Every file you touch must remain UTF-8. Ensure correct encoding headers where relevant. No mojibake.

DELIVERABLES
A) A complete i18n system:
   - Translation files per language, e.g.:
     /web-manager/i18n/en.json
     /web-manager/i18n/fr.json
     (or equivalent best location matching repo structure)
   - A single source-of-truth key naming convention.
   - A loader and helper function: t(key, params) with:
     - fallback chain: requested lang -> default lang -> key itself
     - parameter interpolation (e.g. "Camera {name}")
   - A way to select language:
     - server-side: config setting + optional env var + optional query param (?lang=fr) + optional cookie + frontend. 
     - default: French. 
B) Refactor all UI strings:
   - Frontend JS strings in app.js and any other JS: extract all UI visible text, button labels, errors, notifications, headings, tooltips. 
   - HTML templates: extract visible text.
   - Server-side flashed messages / API JSON “message” fields (if user-facing): extract.
   - Logs: keep logs as-is unless logs are user-facing in UI; then i18n them.
C) Tests:
   - Unit tests for i18n function:
     - fallback behavior
     - interpolation
     - missing keys
     - invalid JSON handling
   - A static checker test that scans repo for remaining hardcoded UI strings in templates/JS (best-effort; allow exceptions list).
   - Integration smoke tests:
     - Start web manager locally (or in test mode) and ensure pages render.
     - For both devices 192.168.1.4 and 192.168.1.5:
       - Verify the RTSP service still starts and remains stable for N seconds.
       - Verify the overlay text (if any) is unaffected except translated labels in UI.
       - Verify camera + audio selection UI works.
       - Verify at least one “start stream” action works.
       - Verify language switching works and persists (cookie/config) and does not break routes.
D) Documentation:
   - Add a small doc file: docs/I18N.md explaining:
     - how to add a new language
     - key naming rules
     - how language selection works
     - how to run tests
   - Update CHANGELOG appropriately.

SAFETY EXECUTION PLAN (MANDATORY)
You MUST follow these steps in order and write progress notes in a temporary file /tmp/i18n_migration_notes.md:

PHASE 0 — Recon & Baseline
0.1) Inspect repo structure. Identify:
     - entrypoint(s) for web manager
     - templates folder(s)
     - where app.js is served from
     - any existing config system
     - existing tests (if any)
0.2) Run existing tests (if present) and record baseline results.
0.3) Identify the minimal i18n insertion points:
     - server: how to pass lang to templates
     - client: how to load translations and apply t()
0.4) Create a git branch: "feature/i18n" and commit baseline (no changes).

PHASE 1 — Add i18n core (no refactor yet)
1.1) Add translation files with a tiny initial set of keys (only a few strings).
1.2) Add t() helper and language selection mechanism with fallback.
1.3) Add unit tests for i18n core.
1.4) Ensure app still runs unchanged (strings still hardcoded for now).

PHASE 2 — Incremental extraction
2.1) Start with templates: extract visible strings into keys, replace with t('...').
2.2) Then JS: extract strings from app.js in small chunks, commit frequently.
2.3) Keep each commit small and runnable. After each chunk:
     - run unit tests
     - run lint/build if applicable
     - quick run of app locally to ensure no obvious runtime errors

PHASE 3 — “No leftover strings” enforcement
3.1) Implement a checker script (node/python) that scans for hardcoded strings in target directories.
3.2) Add an allowlist mechanism for false positives (e.g. regex patterns, technical strings, protocols).
3.3) Add it as a test step.

PHASE 4 — Device integration smoke tests
4.1) For each device:
     - Verify connectivity (ping/ssh if configured; do not modify system).
     - Deploy/run the current branch (use existing deployment method in repo).
     - Start services and verify RTSP is reachable.
     - Perform minimal UI actions and capture logs.
4.2) Record results in /tmp/i18n_device_tests.md.

PHASE 5 — Final hardening
5.1) Ensure all JSON translation files are valid UTF-8 and no “???” remains.
5.2) Ensure language switching does not break caching or service workers (if any).
5.3) Run full test suite.
5.4) Produce final summary: what changed, how to add strings, how to add languages.

TECHNICAL CONSTRAINTS / EXPECTATIONS
- Assume frontend is vanilla JS (no React rewrite). Keep it minimal.
- Prefer JSON translation maps over complex libraries.
- Do NOT introduce heavy dependencies unless absolutely necessary; if you add any, justify and keep minimal.
- The UI should not flicker badly during translation load; preload or embed initial lang where reasonable.
- Keys should be stable and readable, e.g.:
  - "ui.buttons.start"
  - "ui.errors.network"
  - "ui.status.running"
  Avoid keys based on raw text.

ACCEPTANCE CRITERIA (MUST PASS)
- Running in default language behaves exactly as before.
- Switching language translates UI labels/messages without breaking any control.
- Device A and B streams remain functional (RTSP stable, audio selection intact).
- No missing translation keys cause crashes; missing keys fallback gracefully.
- Tests included and passing.
- Documentation updated.

OUTPUT FORMAT
At the end, provide:
1) The list of commits with brief description.
2) Where the i18n files live and how to add a new language.
3) How to run tests locally and on devices.
4) Any known limitations.

NOW DO THE WORK. Do not ask for confirmation. Start with PHASE 0.