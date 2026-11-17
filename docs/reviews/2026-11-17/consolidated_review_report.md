# Shrutadhara: Elephant-Goldfish project review

Reviewed commit: `b3af550669b41ca3d2364099f2c245970bb17e42`. Review date: 2026-11-17.

## Decision

Prioritize a `0.1.1` reliability and evidence-integrity release before broadening distribution or adding providers. The native Python/GTK/PipeWire architecture remains an appropriate lightweight foundation. Current tests and packaging successes do not establish safe failure cleanup or reliable AI recognition. This review found concrete lifecycle, routing and evidence-presentation defects; the AI recognition limitation was already disclosed and remains unresolved.

P0 means fix before widening the experimental rollout, particularly automatic recording. P1 means fix before a daily-use reliability claim. P2 means a follow-up improvement; a Major with P2 is a narrower integrity concern, not a remote exploit claim. S is a focused change, M spans several paths/tests; these are relative effort estimates, not delivery promises.

## Method and completion

Google's EGM 0.1.1 was installed as a complete Codex plugin, including personas and standards. The applied skill was `egm-drift-report`, supplemented by three fresh-context Goldfish reviewers and the bundled review personas. Upstream reference: https://github.com/google/elephant-goldfish-model. Upstream checkout inspected: `72d06f52a2482885d9a64bd24b291c6e8628942c`.

This is one project audit and synthesis, not a claim that the five-stage design-spec workflow or the iterative two-clean-round convergence process ran. Every reviewer used `fork_turns: none`, read the installed integration/skill/persona/standard files and returned a completed report. They did not receive the parent conversation or retrieve memory. Shared filesystem and harness instruction-file isolation are not independently verified. Reviewers remained read-only; the parent performed isolated reproductions and wrote these artifacts.

| Reviewer | EGM lens and standard | Coverage | Status |
|---|---|---|---|
| goldfish_runtime | codebase_details; implementation-readiness applied only where relevant | Recorder, routing, sessions, storage, crash/recovery, shared test infrastructure | completed |
| goldfish_ai_privacy | design_critic; feature-spec standard | agy, orchestration, transcripts, notes, questions, consent and provenance | completed |
| goldfish_product_release | zoom_out + inventive_catalyst; zoom-out standard | CLI/GTK, shortcuts, automation, installers, npm, Arch/Debian builders, workflows and docs | completed |

All production Python modules were covered by the combined reviewer reading lists, plus installers, packaging tools, npm, desktop integration and four workflows. Tests and all existing project Markdown documents were inspected; individual reviewers used selected test files rather than claiming line-by-line inspection of every test. Contributor/template documents were also read by the parent. No implementation was changed. No commits, pushes, releases, npm/AUR submissions, live capture, user meeting/configuration reads or hosted AI were performed in this audit. The separately requested plugin installation changed only Codex plugin configuration/cache.

## Verification

- Existing default suite: **125 passed**; Ruff passed.
- Explicit Arch metadata suite: **2 passed**, with two subtests; it is currently outside default collection (F21).
- Seven positive isolated checks: capture-child survival; provider-child survival; failed-unload ownership loss; refusal followed by another mocked submission; preserved active Markdown; oversized notes request; historical Q&A evidence retargeting. The process probes exercise the production subprocess lifetime pattern/adapter, not a full live meeting.
- Real FFmpeg negative control: four retained-timestamp synthetic tone segments exported correctly, approximately 2895 RMS per second on both tracks. The suspected later-segment silence defect was not reproduced and is excluded.
- No actual Markdown viewer/network fetch was tested. No native GTK4.8 session, suspend, full-disk event, real Teams call or two-hour soak ran.
- Existing GitHub package install/remove checks were verified by the parent: https://github.com/Praneel7015/shrutadhara/actions/runs/43935549226 succeeded. Tag package jobs also succeeded before its publication step hit an artifact-layout error. The already-validated tag assets were separately published and downloaded/checksummed in the earlier release task. A reviewer's inability to inspect CI is not evidence that these checks failed.

Machine-readable results: [findings.json](findings.json), [reproduction-results.json](reproduction-results.json). Implementation sequence: [improvement_plan.md](improvement_plan.md). Document differences: [2026-11-17_DRIFT_REPORT.md](2026-11-17_DRIFT_REPORT.md).

## Prioritized findings and traceability

| ID | Goldfish sources | Priority | Evidence | Finding |
|---|---|---|---|---|
| F01 | RT-orphan | P0 | Reproduced | Detached capture survives a killed supervisor |
| F02 | RT-05 | P0 | Source verified | Storage failures can bypass shutdown |
| F03 | RT-03 | P0 | Reproduced | Failed unload forgets the owned audio module |
| F04 | RT-07; PR-01 | P0 | Source verified | Automatic call transitions are dropped while busy |
| F05 | RT-01 | P1 | Source + platform contract | Suspend detection uses the wrong clock |
| F06 | RT-02 | P1 | Source verified | Late Teams instances bypass ambiguity checks |
| F07 | RT-04 | P1 | Source verified | Recovery and processing can race on exports |
| F08 | RT-06 | P1 | Source verified | A blocked export read has no deadline |
| F09 | RT-08 | P1 | Source verified | Connected health does not verify the capture route |
| F10 | RT-09 | P1 | Source verified | Health remains green when the supervisor snapshot is stale |
| F11 | AI-01 | P0 | Reproduced | A native-audio refusal does not stop later submissions |
| F12 | AI-05 | P0 | Reproduced | Terminating Q&A/probe can leave the provider alive |
| F13 | AI-02 | P1 | Reproduced | Historical Q&A links point into a mutable transcript |
| F14 | AI-03 | P1 | Reproduced payload; viewer effect untested | Model text is rendered as active Markdown |
| F15 | AI-04 | P1 | Reproduced | A single large segment bypasses notes request bounds |
| F16 | AI-06 | P2 | Source verified; integrity scope | Cached output has no independent accepted-output digest |
| F17 | PR-03 | P1 | Source verified; future-version trigger | npm wrapper upgrades silently run the old runtime |
| F18 | PR-04 | P1 | Source + upstream API contract | Source GUI installation lacks its GTK minimum guard |
| F19 | PR-02 | P2 | Source verified | Folder stays disabled after the first GUI session |
| F20 | PR-05 | P2 | Source verified | Service and shortcut examples assume a source launcher |
| F21 | PR-06 | P1 | Collection verified | Arch metadata regression tests are omitted from normal CI |
| F22 | AI-07 | P2 | Source verified | The ten-minute deadline is per attempt |

### F01: Detached capture survives a killed supervisor

**P0 / Major — Reproduced**. Source: `shrutadhara/recorder.py:195; shrutadhara/recorder.py:299`. Reviewer references: RT-orphan.

A supervisor killed with SIGKILL releases its lock without reliably terminating its FFmpeg child. Synthetic segmented capture continued from three to five files after parent death.

Impact: Capture can continue beyond the visible controller; recovery may inspect archives still being written. The reproduction uses lavfi, not a microphone; actual fallback-session end-to-end capture was not run.

Change: Give the child a verified parent-death lifetime and durable PID/start-identity ownership. Recovery must establish that every owned writer has stopped before validating/exporting archives. Prefer existing systemd cgroup supervision where available, with a tested fallback.

Acceptance: Kill a synthetic fallback parent; require child termination, no new segments and safe recovery. Cover startup races, PID reuse and normal graceful stop. Effort: M.

### F02: Storage failures can bypass shutdown

**P0 / Major — Source verified**. Source: `shrutadhara/recorder.py:551; shrutadhara/recorder.py:571; shrutadhara/recorder.py:580`. Reviewer references: RT-05.

Metadata reads/writes occur before halt_capture and route cleanup inside finalization. An I/O exception can escape before teardown.

Impact: A full/unwritable filesystem can leave recording/routing resources running or unrecovered.

Change: Place child termination, routing restoration and socket closure in independent finally blocks; make failure reporting best-effort after teardown.

Acceptance: Inject ENOSPC, failed fsync/rename and corrupt metadata at each finalization boundary. All cleanup attempts must occur and originals must remain. Effort: M.

### F03: Failed unload forgets the owned audio module

**P0 / Major — Reproduced**. Source: `shrutadhara/audio.py:142`. Reviewer references: RT-03.

unload pops the module ID, swallows pactl failure and saves the empty ownership journal. A mocked failure reproduced the loss in memory and on disk.

Impact: An old loopback can remain active while replacements load and recovery no longer knows it.

Change: Delete ownership only after successful unload or verified absence; retain failed historical IDs separately when replacing a labeled module.

Acceptance: Fail unload, create a replacement, then retry cleanup. Both owned IDs must stay tracked until verified gone; unrelated modules remain untouched. Effort: S.

### F04: Automatic call transitions are dropped while busy

**P0 / Major — Source verified**. Source: `shrutadhara/teams.py:47; shrutadhara/teams.py:76`. Reviewer references: RT-07; PR-01.

worker returns when another start/stop action is running. A call-end debounce can fire during slow startup and be discarded permanently.

Impact: Opt-in automatic recording can continue after a short call ends, or miss the next call during finalization.

Change: Keep latest desired call state and reconcile it after every operation. Preserve owned-session checks and explicit unknown-state behavior. Do not use an unbounded event queue.

Acceptance: Block mocked startup, deliver call end, release startup and require owned-session stop. Also deliver a new call during blocked stop and simulate bus loss. Effort: M.

### F05: Suspend detection uses the wrong clock

**P1 / Major — Source + platform contract**. Source: `shrutadhara/recorder.py:357; shrutadhara/recorder.py:449; shrutadhara/recorder.py:561; shrutadhara/sessions.py:132`. Reviewer references: RT-01.

Linux monotonic time excludes suspended time, but it drives the suspend-gap detector, epoch offsets and final duration. Display elapsed time uses wall time.

Impact: Suspend can be omitted from the promised gap timeline; saved and displayed durations can disagree. FFmpeg offset consequences still need integration measurement.

Change: Define one elapsed session timeline with CLOCK_BOOTTIME and detect suspend from boottime/monotonic delta differences. Keep wall timestamps only as presentation anchors.

Acceptance: Inject independently advancing clocks, verify gap/offset/duration agreement, then run an authorized real suspend acceptance test. Effort: M.

### F06: Late Teams instances bypass ambiguity checks

**P1 / Major — Source verified**. Source: `shrutadhara/audio.py:50; shrutadhara/audio.py:80; shrutadhara/audio.py:182`. Reviewer references: RT-02.

Starting without Teams playback leaves teams_pid unset; later routing matches every Teams PID without rechecking ambiguity.

Impact: Unrelated Teams profiles/calls can be mixed into one recording.

Change: Persist an explicit selection policy; bind an initially unbound recording only to an unambiguous process. Surface ambiguity before moving any newly ambiguous streams.

Acceptance: Empty startup inventory followed by two different Teams PIDs; assert neither is silently routed. Cover explicit selection and process replacement. Effort: S/M.

### F07: Recovery and processing can race on exports

**P1 / Major — Source verified**. Source: `shrutadhara/recorder.py:90; shrutadhara/recorder.py:119; shrutadhara/processing.py:736; shrutadhara/audio.py:635`. Reviewer references: RT-04.

Recovery takes a global recording lock while processing takes a different session processing lock. Both can export the same session into identical temporary paths.

Impact: Concurrent recovery/preparation can corrupt or replace derivatives during use and leave inconsistent metadata.

Change: Use one shared per-session audio-artifact lock for repair, export and preparation, with a documented lock order.

Acceptance: Synchronize two processes at export creation; one must wait/refuse. Verify final hashes, metadata and retained originals. Effort: M.

### F08: A blocked export read has no deadline

**P1 / Major — Source verified**. Source: `shrutadhara/audio.py:665; shrutadhara/audio.py:685`. Reviewer references: RT-06.

stdout.read can block before proc.wait(timeout=30) is reached.

Impact: Stop/finalization can hold the recording lock indefinitely.

Change: Use selectable streaming reads with an overall deadline and guaranteed child termination; reuse a shared bounded subprocess primitive.

Acceptance: A synthetic child emits a short block and holds stdout open. Require bounded interruption, released locks and preserved archives. Effort: M.

### F09: Connected health does not verify the capture route

**P1 / Major — Source verified**. Source: `shrutadhara/recorder.py:370; shrutadhara/recorder.py:428; shrutadhara/audio.py:151`. Reviewer references: RT-08.

Private sink and physical-device checks do not validate owned loopback existence/endpoints or same-name device recreation.

Impact: The GUI can show a connected microphone while its loopback is absent and the archive contains silence.

Change: Track device/module incarnation and verify route endpoints. Expose physical presence, route health and capture progress separately.

Acceptance: Remove a loopback while keeping devices and sinks unchanged; require warning/gap/repair. Recreate a device with the same name and new identity. Effort: M.

### F10: Health remains green when the supervisor snapshot is stale

**P1 / Major — Source verified**. Source: `shrutadhara/recorder.py:35; shrutadhara/recorder.py:272; shrutadhara/gui.py:355`. Reviewer references: RT-09.

Status accepts a live PID and merges the last snapshot without recalculating its age; saved progress age freezes when the worker stalls.

Impact: A stalled worker can continue to appear healthy.

Change: Compute snapshot age at read time and expose stale/unknown status after a documented threshold. Distinguish process existence from progress.

Acceptance: Advance a fake clock against a frozen snapshot and matching PID; require stale health in CLI and GUI. Effort: S.

### F11: A native-audio refusal does not stop later submissions

**P0 / Major — Reproduced**. Source: `shrutadhara/processing.py:346; shrutadhara/processing.py:842; shrutadhara/processing.py:869`. Reviewer references: AI-01.

A schema-valid audio_received=false result becomes MeetingError, but only AIError breaks the loop. The local stub was called for both chunks after its first refusal.

Impact: The program continues unnecessary data submissions and quota use after capability failure, contrary to its documented stop policy. Existing consent was present; this is not a claim of upload without initial consent.

Change: Introduce provider-neutral session-fatal/capability refusal categories. Stop subsequent calls, persist a blocked reason and retain unprocessed intervals. Keep specific size-limit splitting.

Acceptance: Three mocked chunks, first native-audio refusal: exactly one submission, incomplete coverage and durable diagnostics. Effort: S/M.

### F12: Terminating Q&A/probe can leave the provider alive

**P0 / Major — Reproduced**. Source: `shrutadhara/agy.py:244; shrutadhara/agy.py:256; shrutadhara/cli.py:515; shrutadhara/cli.py:534`. Reviewer references: AI-05.

Only process translates SIGTERM into handled cancellation. Other hosted paths spawn a new provider session; default parent SIGTERM bypasses its cleanup. A harmless fake agy survived parent termination.

Impact: A hosted request may continue after the initiating application exits. No actual provider was contacted in this review.

Change: Wrap every hosted entry point with shared cancellation handling and process-group teardown; restore signal handlers and mark attempts cancelled. Also handle supervisor hard-death lifetime.

Acceptance: Fake agy records PID then waits; terminate ask/probe parents and require no surviving child, released locks and interrupted attempt state. Effort: M.

### F13: Historical Q&A links point into a mutable transcript

**P1 / Major — Reproduced**. Source: `shrutadhara/questions.py:129; shrutadhara/questions.py:176; shrutadhara/processing.py:503; shrutadhara/processing.py:555`. Reviewer references: AI-02.

Answers link to sequential IDs in the overwritten shared transcript. A local stub answer stayed unchanged while its cited anchor was replaced by contradictory synthetic dialogue.

Impact: Retained answers can appear supported by different evidence after correction or retranscription.

Change: Save immutable transcript revisions or minimal evidence snapshots per question, and qualify links with revision identity. Reuse existing source hashes; do not add a database for this.

Acceptance: Ask, correct/reorder/delete source segments, then open historical evidence. It must still show the originally cited text and revision. Effort: M.

### F14: Model text is rendered as active Markdown

**P1 / Major — Reproduced payload; viewer effect untested**. Source: `shrutadhara/processing.py:551; shrutadhara/processing.py:698; shrutadhara/processing.py:705`. Reviewer references: AI-03.

Transcript and notes preserve model-authored images/links/HTML. Synthetic remote-image markup survived both renderers; no viewer was opened.

Impact: Forged links can misrepresent evidence. Remote-resource-capable viewers may make network requests when opened; actual fetching is viewer-dependent and was not tested.

Change: Centralize literal text escaping, keep app-generated evidence links separate and retain exact raw transcript text in JSON. Support code through controlled rendering.

Acceptance: Images, HTML, headings, forged evidence links and table escapes must render literally; generated local evidence links remain usable. Effort: S/M.

### F15: A single large segment bypasses notes request bounds

**P1 / Major — Reproduced**. Source: `shrutadhara/processing.py:625; shrutadhara/processing.py:659; shrutadhara/processing.py:664`. Reviewer references: AI-04.

The splitter checks size only for a nonempty block and counts characters. A 200000-character Devanagari segment reached a local stub as a 601032-byte prompt.

Impact: Large requests can exceed provider limits or consume unintended quota; existing resumable behavior does not impose a bound on every request.

Change: Check complete serialized UTF-8 request size before each call, including instructions. Reject oversized single segments before submission or split them into explicitly linked spans.

Acceptance: Single oversize segment, many ordinary segments and multibyte text; no over-budget prompt may reach the adapter. Effort: S/M.

### F16: Cached output has no independent accepted-output digest

**P2 / Major — Source verified; integrity scope**. Source: `shrutadhara/processing.py:803; shrutadhara/processing.py:837; shrutadhara/processing.py:597; shrutadhara/processing.py:640`. Reviewer references: AI-06.

Input fingerprints do not detect a schema-valid cached transcript/notes edit that preserves its fingerprint.

Impact: Accidental or same-user cached-output changes can silently alter provenance. This is not a remote compromise or protection against an attacker able to rewrite every baseline.

Change: Separate accepted output revisions/digests from disposable input-keyed caches. Explicit imports create an auditable new revision. Align the baseline promise in SECURITY.md with the implemented scope.

Acceptance: Modify valid cached text without changing input fingerprint; require rejection/invalidation. Explicit correction imports remain supported. Effort: M.

### F17: npm wrapper upgrades silently run the old runtime

**P1 / Major — Source verified; future-version trigger**. Source: `npm/launcher.js:40; npm/launcher.js:55`. Reviewer references: PR-03.

Version matching occurs during setup only; ordinary launch uses any existing shared npm-runtime.

Impact: A future wrapper B can launch native A without an actionable compatibility warning. Only version0.1.0 is currently declared; no real upgrade was executed.

Change: Persist/check native version and runtime installation identity before launch; require explicit setup on mismatch. Define the override executable compatibility policy too.

Acceptance: Newer staged wrapper plus older synthetic native runtime: recording commands must fail with explicit setup guidance. Same-version reinstall remains valid. Effort: M.

### F18: Source GUI installation lacks its GTK minimum guard

**P1 / Major — Source + upstream API contract**. Source: `README.md:29; shrutadhara/gui.py:49; shrutadhara/gui.py:225; shrutadhara/cli.py:339`. Reviewer references: PR-04.

Native packages require GTK>=4.10, but source/wheel startup and doctor accept any GTK4. AlertDialog exists only since4.10.

Impact: GTK4.8 source installations fail at required confirmation instead of reporting an actionable dependency error.

Change: Check GTK>=4.10 before window construction and state it consistently in source installation/contributor docs.

Acceptance: Mock4.8: dependency exit3 before constructing window; accept4.10. Native dependency metadata remains versioned. Effort: S.

### F19: Folder stays disabled after the first GUI session

**P2 / Nit — Source verified**. Source: `shrutadhara/gui.py:406; shrutadhara/gui.py:414`. Reviewer references: PR-02.

Empty history disables all output buttons; subsequent state updates restore notes/transcript only.

Impact: A first-session user cannot open its folder without reopening the application.

Change: Set every output button sensitivity from current state on every update.

Acceptance: Empty→recording→recorded without recreating the window; Folder becomes enabled. Effort: S.

### F20: Service and shortcut examples assume a source launcher

**P2 / Nit — Source verified**. Source: `desktop/shrutadhara-call-monitor.service:8; README.md:232; README.md:242`. Reviewer references: PR-05.

Examples use ~/.local/bin/shruta, whereas native packages install /usr/bin/shruta.

Impact: Following these examples after native installation can produce a failed service or inactive shortcut.

Change: Document channel-specific executable paths or generate an explicitly installed unit from a resolved owned executable. Avoid shadow launchers.

Acceptance: Check source/native/npm unit and shortcut commands, including paths containing spaces. Effort: S.

### F21: Arch metadata regression tests are omitted from normal CI

**P1 / Major — Collection verified**. Source: `pyproject.toml:30; packaging/arch/test_prepare.py; .github/workflows/offline.yml:17; .github/workflows/packages.yml:21`. Reviewer references: PR-06.

Default testpaths contains tests only. The two Arch generator tests ran only when explicitly named.

Impact: Traversal and source-pinning regressions can pass ordinary CI.

Change: Move the suite under tests or include its path explicitly in every required test job. Prefer one collection convention.

Acceptance: pytest --collect-only must include both Arch metadata cases; unsafe archive fixtures must still be rejected. Effort: S.

### F22: The ten-minute deadline is per attempt

**P2 / Nit — Source verified**. Source: `README.md:142; shrutadhara/agy.py:209; shrutadhara/agy.py:255; shrutadhara/agy.py:317`. Reviewer references: AI-07.

Each of three attempts gets the full configured600seconds.

Impact: A chunk may take roughly30minutes plus cleanup/backoff, not one ten-minute total deadline.

Change: State per-attempt and total bounds explicitly, or implement one shared overall deadline.

Acceptance: A fake clock verifies retry allocation and total elapsed budget. Effort: S.

## Deduplication and contested observations

- RT-07 and PR-01 are the same call-automation defect (F04); count once.
- RT orphan risk was initially unconfirmed. Parent lavfi reproduction established continued writing after supervisor death (F01).
- The proposed doctor-stops-an-active-recording defect was withdrawn: recorder.start rejects an existing active session; only CLI dispatch adds idempotence.
- Later-segment export silence was not reproduced by real FFmpeg. Do not turn that suspicion into a fix.
- PR-07 is partly an evidence/documentation gap: actual Ubuntu/Arch help/import/install/remove CI already passed. Desktop activation, upgrades, optional service examples and uninstall after user desktop setup remain untested.
- PR-08 is a reproducibility limit, not proof the existing deterministic-deb claim is false: fixed-wheel container determinism does not imply independent reproducibility of every build dependency and rolling Arch input.
- OPEN_SOURCE_PLAN is explicitly historical. Deferred portal shortcuts, extra providers, SaaS and old planning gates are not missing implemented features.
- Recognition accuracy, approximate timestamps, speaker identity limits and unverified live-device/long-meeting acceptance were already disclosed. They remain product release gates, not newly discovered implementation defects.

## Improvements beyond defects

1. Build a small approved speech benchmark before claiming AI reliability: English/Indian-language code-switching, technical identifiers, silence, clipped/quiet speech, overlapping speech and chunk-boundary phrases. Track WER/CER by language, omitted/invented speech, technical-token exact match, timestamp error, unsupported-note rate, action/decision precision and abstention. A short exact probe proves only that sample; it does not validate two-hour meetings. No corpus upload is authorized by this review.
2. Add signal-aware, real-FFmpeg synthetic integration tests with deterministic markers and per-track delays. Mocked command tests cannot establish actual media alignment and shutdown.
3. Expose recent sessions, separate-track playback/opening and local prepare-only in a secondary GTK view. Reuse the existing sessions/CLI functions. Keep Start/Stop and visible status prominent.
4. Test keyboard-only control, screen-reader labels, 200% text scaling and small displays. Associate labels with controls and keep content reachable through ordinary GTK resizing/scrolling.
5. Add measured CPU/RSS/disk usage and a two-hour capture soak. Forecast export headroom instead of relying only on a fixed reserve. Define the duration/container policy before approaching ordinary WAV RIFF limits.
6. Improve contributor onboarding with one test collection convention, small synthetic fixtures generated at runtime, channel-specific upgrade/removal instructions and optional user-unit ownership handling. Continue excluding recordings and credentials.
7. Keep agy as the only provider. When failure classification is repaired, move neutral schemas/errors/limits to the provider boundary so a future explicitly chosen adapter can be added without silently changing destinations. Do not add a plugin downloader or automatic fallback.
8. Delay SaaS until an actual shared-workflow need is established. A separate service requires accounts, tenant isolation, retention/deletion, billing and operations. The current useful scope is a trustworthy local recorder with optional AI; wider distribution does not require a cloud backend.

## Primary platform references

- EGM method and source: https://github.com/google/elephant-goldfish-model
- Suspend-aware CLOCK_BOOTTIME: https://docs.python.org/3/library/time.html#time.CLOCK_BOOTTIME
- Gtk.AlertDialog minimum 4.10: https://docs.gtk.org/gtk4/class.AlertDialog.html
