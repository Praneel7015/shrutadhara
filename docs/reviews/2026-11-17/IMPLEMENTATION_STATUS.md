# Reliability patch implementation status

Development version: **0.1.1**, experimental. The published v0.1.0 tag is unchanged. This implements the programmatic fixes from the EGM review, not a claim that live capture or recognition acceptance has passed.

## Implemented and regression-tested

| Review finding | Change | Commit |
|---|---|---|
| F01–F03 | Parent-bound capture child, trusted writer identity, teardown despite metadata failure, retained unload ownership | `2aa0fbf` |
| F04 | Desired call-state reconciliation and owned-session Stop verified at dispatch | `d264d9a` |
| F05–F06, F09–F10 | Boottime timeline/suspend detection, persisted unambiguous Teams selection, exact route/device checks and stale health | `ab18554` |
| F07–F08 | Shared session audio lock and bounded streaming export reads | `3099834` |
| F11–F12 | Native refusal stops submissions; cancellation tears down provider groups | `525c299` |
| F12 hard parent-death follow-up | Parent-bound watchdog cleans provider leader and same-group descendants, including TERM-ignoring processes | `704b2d7` |
| F13–F16 | Q&A evidence snapshots, literal Markdown, serialized UTF-8 bounds, accepted-output snapshots and independent ledger | `50dd2ed`, `de76574` |
| F17–F19 | npm/native version match, GTK4.10 startup guard, restored first-session Folder control | `4c822f3` |
| F20 | Channel-specific service/shortcut, upgrade and removal guidance | patch preparation |
| F21 | Arch metadata tests collected by default | `13ad659` |
| F22 | Deadline documented per attempt and across retries | patch preparation |

Additional compact GUI improvements: recent-session selection, individual audio-track actions, local prepare-only action, resize/scroll support and mnemonic labels (`6253fec`). A peer review found a selection/target mismatch; `f6b8ee2` keeps the currently selected or active meeting represented and synchronized even outside the recent-history window.

The parent and parallel agents added synthetic fault, lifecycle, routing, timeline and output-integrity regressions. Independent peer review also caught the hard-death descendant gap and unsafe already-reaped group signaling; both were corrected before considering the lifecycle work complete. Agents subsequently hit usage limits, so the parent completed the remaining review/integration directly; that is not an additional independent clean-review round.

## Local evidence

- Default suite: **210 passed**, plus two unittest subtests. Arch metadata cases are now part of this collection.
- Python3.11 with jsonschema4.10.3: **209 passed, one GTK availability skip**, plus two subtests.
- Ruff, Python compilation and Node syntax checks passed.
- Python wheel/sdist, bundled npm tarball and Debian0.1.1 package build checks passed; generated Arch source SHA verification passed. A fresh npm prefix/runtime installed the bundled wheel, reported0.1.1, loaded system GTK and launched a parent-bound child from `/tmp` with test PYTHONPATH removed.
- Synthetic FFmpeg tests check real segmented signals, sample alignment, hanging export deadlines and cross-process locks.
- Process tests check parent SIGKILL, normal provider exit with leftover descendants, cancellation, ignored signals, startup races, PID identity and safe group escalation.
- Fault tests cover metadata/storage errors, changed accepted outputs, snapshot/ledger write failures and unchanged Markdown after rejected acceptance.
- Tests use approved synthetic tones/local fake programs only. No microphone, Teams routing, real meeting data or hosted AI was used.

The minimum-dependency run caught a test-infrastructure assumption: subprocesses launched from private working directories depended on an editable install. Test fixtures now explicitly put the reviewed source tree on test-only PYTHONPATH. Installed-wheel/npm smoke checks run separately with that variable removed so source imports cannot hide installation problems.

## Compatibility and failure behavior

- Existing originals and old published artifacts are not rewritten. New captures use the guarded lifetime and durable identity record; a pre-upgrade orphan without a trusted identity journal cannot retroactively be proven absent.
- New Q&A answers link to their own evidence snapshot. Historical answers are not silently relinked or rewritten.
- Legacy unbaselined transcript/output caches are not silently trusted. Q&A refuses them without submitting data; reprocess or explicitly import reviewed results to establish an accepted revision.
- Snapshots are written before replacing an accepted cache. A crash or I/O failure between cache replacement and ledger commit fails closed; the prior accepted snapshot remains for explicit restoration. The JSON is authoritative if a later Markdown-projection write fails.
- Hash baselines detect accidental/local changes; they do not authenticate against someone who can rewrite every baseline.
- The provider watchdog guarantees lifetime for its owned process group. A program deliberately escaping into an independent session requires separate supervision; the helper is not a sandbox.
- Hosted CLI calls use main-thread cancellation handling; a library invocation from another thread cannot install main-thread signal handlers, while parent lifetime remains supervised.
- No new provider, silent fallback, automatic recording default, service enablement, or hosted-consent change was introduced.

## Still requires acceptance or a later milestone

1. Authorized real Teams playback plus microphone and unrelated-desktop-audio exclusion.
2. Bluetooth/USB switching, actual suspend/resume, PipeWire restart and real desktop behavior.
3. Two-hour CPU/RSS/disk/finalization soak and dynamic export-space forecasting.
4. Native GTK visual/screen-reader/keyboard/200% font acceptance. The UI code and state regressions do not establish this acceptance.
5. Representative approved human-speech benchmark, measured recognition/notes accuracy, and actual native permission-boundary validation. The previously failed agy accuracy gate remains unchanged.
6. Broader installed upgrade/desktop/service matrix, exact build-input provenance and stronger independent reproducibility evidence.
7. npm/AUR account publication, CachyOS inclusion and a maintained signed APT repository remain separate distribution steps. No new release tag or registry publication is performed merely by preparing this patch.

Provider expansion, portal hotkeys and SaaS remain demand-gated. The useful next validation is the live two-track test followed by a measured long recording; neither should be inferred from the unit-test count.
