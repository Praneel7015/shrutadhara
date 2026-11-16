# Changelog

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
