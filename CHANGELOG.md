# Changelog

## Unreleased

- Report delayed health-monitor polls separately from audio-gap warnings; a scheduling delay alone does not establish missing capture audio.

- Add an experimental x86_64 Flatpak for recording and local preparation, with explicit AI/background-command restrictions and window lifetime protection.
- Build and test the installed Flatpak runtime with pinned audio/Python dependencies and synthetic codec checks.
- Publish a signed experimental APT archive with integrity verification, expiry refresh and disposable installation tests.
- Document currently available npm/native/APT channels and the AUR registration blocker.

## 0.1.1 — experimental

- Bind capture children and hosted provider groups to parent lifetime; terminate owned descendants on cancellation and hard parent death.
- Guarantee teardown despite metadata failure; retain failed module ownership and serialize repair/export/preparation.
- Reconcile Teams transitions without dropping events and verify owned-session Stop at control dispatch.
- Track suspend-aware timelines, fresh worker status, exact route/device identity and unambiguous Teams selection.
- Preserve historical Q&A evidence, verify accepted output revisions, render model text literally, and bound serialized notes prompts.
- Reject mismatched npm runtimes, enforce GTK4.10, collect Arch regressions, and add recent-session/local audio controls.

Live acceptance and recognition accuracy remain outstanding; this is not a daily-use reliability claim.

## 0.1.0 — experimental

- Added pinned-source Arch/AUR packaging and native Debian package builds.
- Added disposable Ubuntu/Arch installation checks and tagged GitHub prereleases.
- Bundled matching native wheel in npm release with explicit setup and integrity checks.
- Added manual npm trusted-publishing workflow; no automatic registry or AUR publication.

- Introduce Shrutadhara (श्रुतधर), the `shruta` CLI and native GTK recording controls.
- Preserve separate microphone/participants audio, segmented originals, recovery metadata and explicit processing gaps.
- Fix overlap speech loss, recovery integrity baselines, corrected imports and cached-audio verification.
- Add detailed notes, summary, action, decision and evidence-linked transcript Q&A commands.
- Add configurable window shortcuts and manual Wayland desktop shortcut instructions.
- Introduce an agy-only provider interface, MIT licensing, contributor/CI scaffolding and local wheel/npm installation.
- Preserve pre-rename settings, consent, capability failures, recordings and managed launcher compatibility.

Known limitations: native agy recognition failed a full synthetic accuracy test and remains gated. Representative human speech, device transitions and two-hour live reliability still require manual validation. GlobalShortcuts portal integration, additional providers and a hosted service are not implemented.
