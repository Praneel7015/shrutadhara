# Improvement plan after the EGM review

Baseline: `b3af550669b41ca3d2364099f2c245970bb17e42`. This is a proposed implementation sequence; no production fixes were applied by this review. Finding IDs refer to [the consolidated report](consolidated_review_report.md).

## Order and release decisions

Prepare `0.1.1` as a reliability patch. Address P0 lifecycle, cleanup and submission-control defects first, then evidence presentation and core state consistency. Keep recording manual by default, automatic processing off by default, agy as the only AI provider, existing original audio immutable, and hosted processing behind explicit consent/capability gates. Do not broaden daily-use claims until the relevant acceptance tests pass.

Use several cohesive changes, each with targeted regressions and a buildable end state. The scopes below are proposed file boundaries, not permission to apply unrelated refactoring. Do not move the published `v0.1.0` tag or replace its assets; publish new bytes under a new version. Keep commit messages free of co-author trailers.

## Phase 1: stop recording and requests reliably

Findings: F01–F04, F11–F12. Highest priority. Relative effort: several focused small/medium changes; no new application framework or provider spending is needed.

Modify:

- `shrutadhara/recorder.py`: make teardown independent of every metadata operation; persist capture-child identity; refuse recovery while an owned writer remains active; retain current graceful SIGINT finalization. Validate detached fallback lifetime and process identity before signaling.
- `shrutadhara/audio.py`: preserve module ownership until successful unload or verified absence. Keep failed previous module IDs attributable during reconnect. Do not unload unrelated modules.
- `shrutadhara/teams.py`: replace dropped-work behavior with latest desired-state reconciliation. After each start/stop, reevaluate confirmed call state, owned session and unknown-state policy. Keep automatic recording opt-in.
- `shrutadhara/agy.py` and `shrutadhara/cli.py`: share signal/cancellation handling for process, ask and explicit capability probes; terminate the owned provider group on cancellation and mark private attempts cancelled. Verify parent-death behavior too.
- `shrutadhara/processing.py` and, only if needed for common failure categories, `shrutadhara/providers.py`: separate session-fatal native-audio refusal from recoverable chunk-local errors. Stop further submissions on refusal; preserve existing explicit provider-limit bisection and accepted chunks.

Create `tests/test_recording_failures.py`, `tests/test_teams_automation.py`, and `tests/test_ai_cancellation.py`; extend `tests/test_audio.py` and `tests/test_processing.py`.

Acceptance:

1. Synthetic FFmpeg child stops when its fallback supervisor dies; no new archive segments appear; owned-child identity is checked against PID reuse. No microphone is used.
2. ENOSPC/fsync/rename/read errors at every finalization boundary cannot bypass child, route and socket cleanup.
3. Failed unload plus replacement keeps both IDs recoverable until removal; unrelated IDs survive.
4. True→False during blocked Start eventually stops only the monitor's recording; False→True during blocked Stop starts the subsequent recording. Bus loss is explicit and conservative.
5. Fake agy children terminate when each hosted parent receives SIGINT/SIGTERM; locks release and cancellation diagnostics persist.
6. Native refusal on chunk one produces one adapter call, blocked/incomplete state and explicit unprocessed coverage.

Tradeoffs: parent-death supervision is Linux-specific and must avoid races in a multithreaded parent; choose a tested mechanism rather than an unreviewed `preexec_fn` shortcut. Systemd cgroups remain useful where available, but cannot substitute for validating the detached fallback. A desired-state reconciler adds a few explicit states, not an unbounded queue.

## Phase 2: keep evidence stable and rendered text literal

Findings: F13–F16. Modify `shrutadhara/questions.py`, `shrutadhara/processing.py`, and existing `tests/test_questions.py`/`tests/test_processing.py`. Create `tests/test_output_integrity.py` only if separating the regressions improves clarity.

- Store a versioned transcript or minimal cited evidence snapshot per question; historical links must resolve to the originally cited text after corrected imports, deletions and reordered segments. Preserve existing request/source hashes.
- Add one shared text-escaping helper for transcript and notes Markdown. Leave application-generated anchors/links controlled by the renderer. Preserve exact plain dialogue in JSON; escape raw HTML and provider-authored links/images rather than dropping dialogue. Treat code through controlled literal/fenced rendering.
- Define a single UTF-8 serialized-request byte limit and check the entire prompt immediately before every notes adapter call. Include instructions and JSON overhead. The first patch should reject an oversized individual segment with an actionable message; splitting into stable subspans can follow when needed. Keep completed intermediate records resumable.
- Establish accepted-output digests/revisions before reusing cached transcripts, intermediate records or notes. Explicit correction import must remain a deliberate new revision, not an unexplained cache mutation. Clarify that these checks detect accidental/local changes and are not cryptographic authenticity against an actor who controls all files.

Acceptance: historical Q&A evidence remains unchanged; hostile Markdown renders literally; every prompt fits its bound for multibyte and single-large-segment cases; valid-schema cached-output mutations are rejected or explicitly invalidated; approved imports still work. All tests use synthetic content and local provider stubs.

Tradeoffs: snapshots and output baselines consume modest disk and need a clear compatibility policy. Reusing current JSON/hash helpers avoids a database or search service. Literal rendering may reduce rich formatting, so preserve structured code separately when justified.

## Phase 3: reconcile timelines, routes and shared artifacts

Findings: F05–F10. Modify `shrutadhara/recorder.py`, `shrutadhara/audio.py`, `shrutadhara/sessions.py`; extend session/audio/recorder tests and create `tests/test_media_integration.py` for real synthetic FFmpeg checks.

- Define session elapsed time with Linux boottime; retain UTC for display timestamps. Detect suspended intervals by comparing boottime with monotonic deltas. Document migration behavior for old sessions; never reinterpret their audio silently.
- Persist Teams selection policy. If initially unbound, bind after one unambiguous process appears; if several candidates appear, expose ambiguity before changing remote routes.
- Use a shared session audio-artifact lock around repair/export/preparation. Choose and document one lock acquisition order so recovery, processing and the global recorder cannot deadlock.
- Bound streaming export reads with an aggregate deadline and child termination, not only a final wait timeout.
- Verify loopback identity/endpoints and same-name device replacement. Separate physical-device presence, route connection, capture progress and snapshot freshness.
- Compute stale snapshot age when status is read. Show unknown/stale health when the control worker cannot demonstrate recent progress.

Acceptance: fake suspend clocks produce accurate gaps/offsets/durations; dynamic two-PID ambiguity never silently mixes calls; concurrent recovery/preparation serializes cleanly; a child holding stdout open is terminated within the bound; lost loopbacks and stale snapshots produce visible warnings and recoverable state.

Tradeoffs: additional route inventory work can delay control responses. Keep one bounded reconciliation interval and reuse one inventory snapshot per cycle. Avoid solving this with a second always-running daemon before measurements show it is needed.

## Phase 4: make installed daily use predictable

Findings: F17–F22 plus product recommendations PR-09–PR-11. Primarily small changes, except the session-history and upgrade test work.

Modify:

- `npm/launcher.js`, `tools/prepare_npm.py`, `tests/test_shortcuts_packaging.py`, `tests/test_distribution.py`: check installed native version/identity against the wrapper before normal launch; fail with explicit setup guidance on mismatch. Cover newer-wrapper/older-runtime and override behavior. Do not silently download or replace a runtime at launch.
- `shrutadhara/gui.py`, `shrutadhara/cli.py`, `README.md`, `CONTRIBUTING.md`: check/document GTK>=4.10 consistently; update every output button on every state change, including Folder.
- `desktop/shrutadhara-call-monitor.service`, `docs/DISTRIBUTION.md`, `README.md`: make service/shortcut instructions installation-specific; document source/native/npm upgrade, desktop entry ownership, removal and retained user data.
- `pyproject.toml` or the location of `packaging/arch/test_prepare.py`: bring Arch tests into the default suite with one collection convention. Update workflow commands only where necessary; require collection evidence.
- `shrutadhara/agy.py` and README only if changing rather than clarifying the retry budget: distinguish per-attempt and total deadlines.
- `shrutadhara/gui.py` and existing session/CLI interfaces: add recent-session selection, source-track playback/open actions and a local preparation action in a secondary view. Keep the main recorder small.

Acceptance: source GTK4.8 fails clearly before creating a window; first-session Folder works; npm version mismatch is visible before recording; default pytest collects Arch regressions; service commands resolve correctly for every supported install channel; upgrade/removal preserves recordings/configuration. Keyboard-only controls, accessible labels and 200% text scaling remain usable on a small display.

Tradeoffs: a runtime version check adds launch work and needs invalidation after interpreter ABI upgrades. A secondary history surface adds controls; use standard GTK widgets rather than Electron/web infrastructure. Channel-specific manual removal instructions are cheaper and safer initially than an automatic cleanup command with uncertain ownership.

## Phase 5: earn measured capture and AI support claims

This phase is a validation plan, not permission to capture audio or upload a corpus. Live recording and hosted tests require their ordinary explicit authorization and approved samples.

Create or extend test-drive/validation documentation, not a second backend:

- Thirty-second local/Teams two-track test with known playback, microphone speech and unrelated desktop playback. Listen to both source tracks; require unrelated audio exclusion. The previous mic-only sample did not validate the remote track.
- Bluetooth/USB changes, default-output changes, same-name device recreation, PipeWire restart, stop during startup, process kill, suspend/resume and low-space finalization.
- A two-hour soak with CPU/RSS, free-disk trend, archive count, gap durations and finalization time recorded. Compare exported signal markers with archive timing. Report measured support boundaries instead of inferring reliability from test count.
- A versioned, licensed/approved speech reference set covering languages, code-switching, technical terms, boundaries, repeated phrases, silence, noise and speaker bleed. Keep it outside public packages unless separately cleared.
- Measure WER/CER, technical-token exact match, omissions/hallucinations, timestamp error, false decisions/actions, citation support, abstention and processing latency/quota. Establish explicit release thresholds with the project owner before evaluating a hosted model; do not invent thresholds or claim a single exact probe proves accuracy.
- Verify native provider restrictions using only synthetic files: sibling-file reads, commands, URLs, plugins and subagents should be denied before execution/access. Current response parsing is not a substitute for testing the actual permission boundary.

Approximate raw storage for two hours at the current rates: two 48 kHz, 16-bit mono archive tracks about 1.38 GB; three mono WAV exports about 2.07 GB; two 16 kHz derivatives about 0.46 GB; chunk copies about 0.47 GB with overlap. This is about 4.38 GB decimal before metadata, temporary/recovered files and reserve. Derive actual budgeting from required artifacts and available space; do not treat this estimate as measured free-space acceptance.

Tradeoffs: smaller chunks increase calls and overlap reconciliation; a second semantic verifier adds quota and can still agree with an incorrect first model. Adopt it only after human-labeled evaluation shows an improvement. No additional hosted service is needed for the local-capture reliability work.

## Later, only with demonstrated demand

- Retain agy as the only adapter now. Factor provider-neutral schemas, typed errors, declared limits and identity only as existing bugs require; add one explicitly chosen second provider later with separate destination consent and credentials. Never implement silent fallback.
- Add portal shortcuts only after capability checks across the supported Wayland desktops establish a reliable path; keep documented compositor bindings usable.
- Improve CI supply-chain provenance and record build inputs before promising bit-for-bit reproducible source/wheel/Arch builds. Current fixed-wheel Debian archive determinism is narrower and useful.
- Ask for CachyOS inclusion after reliability and AUR maintenance are established; host a signed APT repository only after choosing its owner, domain, signing-key lifecycle and supported distributions.
- Treat SaaS as a separate demand-tested product decision. Accounts, tenant isolation, retention/deletion and operations do not belong in a lightweight recorder merely to make installation easier. Support, documentation and contribution quality can grow without a backend.

## Completion criteria for this review

Three fresh Goldfish reviews completed; parent reproductions and evidence are saved; confirmed findings are separated from source-only risks and outstanding acceptance. Implementation, new live tests, registry publication and a second EGM convergence round are not part of this completed review. No architectural change should be described as approved merely because it appears in this plan.
