> Distribution update: implementation and current publication procedure are in docs/DISTRIBUTION.md. Earlier approval/publication gates below describe the historical planning stage.

# Native Linux recorder: product and engineering plan

**Naming decision:** the owner selected **Shrutadhara (श्रुतधर)**, executable **`shruta`**, and repository/Python package **`shrutadhara`**. CLI branding and migration support are implemented. Summary, action, decision and transcript-Q&A commands extend the original roadmap. The philosophy is “Hear everything. Preserve knowledge. Remember what matters.”

**Implementation progress:** P0's four correctness fixes are implemented and independently retested. The tree now also has portable desktop/source packaging, a private npm local-wheel launcher, configurable GTK shortcuts/manual compositor setup, contributor/CI scaffolding and an agy-only provider interface. Additional providers, portal shortcuts, public publication and SaaS remain future work. Current validation is in VALIDATION.md; this roadmap's original starting-point assessment is historical.

The owner subsequently selected MIT and the `shrutadhara` name. License/NOTICE files are included, and the voice fixture with unclear generator licensing is excluded from packages. Source repository: https://github.com/Praneel7015/shrutadhara. Registry publication remains pending; the license discussion below records the earlier planning options.

Prepared 2026-11-16 from README.md, VALIDATION.md, pyproject.toml, install.py and the capture, GUI, CLI, configuration, processing and agy code. Read ASTRA_REVIEW.md; its reproductions remain the source of detail for correctness defects. This document proposes work; it does not enable processing, change configuration, or promise features already exist.

## Recommendation

Keep the Python/GTK 4/PipeWire architecture. Ship an excellent local recorder first, then optional AI processing through explicit provider profiles. Make Arch/CachyOS the first supported platform, with documented compositor shortcuts and a real npm convenience installer alongside native packaging. Do not rewrite this as Electron, embed a browser, or build a server to render the desktop UI.

The useful first public promise is: **record selected meeting-app playback and microphone locally, recover interruption safely, and export understandable artifacts; optionally process using a separately configured and validated provider.** Present Teams-for-Linux as the supported capture integration initially. “Linux meeting recorder” must not imply that Zoom, arbitrary browsers, all distributions or all compositors are tested.

“Unobtrusive” means a small background worker and compact visible controls. Recording must remain discoverable, with elapsed time and a stop action. Do not implement covert modes, hide recording indicators, bypass desktop permissions or suggest that participants receive a native Teams notification. They currently do not. Keep the microphone-versus-Teams-mute disclosure visible at first use.

## Starting point and release gates

The current application already has the hard foundation: segmented two-track capture, private session storage, supervised workers, crash recovery, CLI/GTK control, explicit hosted consent, prepare/import, resumable processing and evidence-linked notes. It is a working prototype, not yet an installable open-source release. The tree is not currently a Git repository, has no LICENSE, CI, published identity or portable package installation assets. Its source installer relies on a checkout and system PyGObject. The current model selector is one global agy slug; providers and API-key settings do not exist.

The coordinating review built wheel/sdist successfully under `/tmp/meeting-release-audit-build`. Its wheel has the GUI module and synthetic sample but no desktop entry or license; the source archive omits install.py/install.sh even though its README recommends them. Fix distribution file inclusion and test the README from an extracted release archive, not only from this checkout.

An offline rerun of `.venv/bin/python -m pytest -q` passed **60 tests in 0.28 seconds**. This supplies no new live-capture or AI-accuracy evidence. No hosted calls, real recording inspection, audio-routing changes or user configuration edits were performed for this plan.

Before an experimental release, fix the four independently reproduced issues in ASTRA_REVIEW.md: boundary speech omitted despite complete coverage; recovery overwriting original hash baselines; corrected imports losing to cached results; cached derivative/chunk changes silently accepted. Each needs its own regression test. These protect core trust and take priority over UI polish, additional providers and distribution. Retain the existing AI accuracy warning: a short successful attachment probe does not establish accurate meeting transcription.

## A compact native interface

Keep one GTK application with a reusable command/service layer; GUI callbacks must not become a second implementation of session or consent policy. Prefer standard GTK theme styles, symbolic icons, system light/dark preferences, keyboard navigation and accessible labels. A native header bar and restrained spacing can achieve the intended Wayland desktop appearance without a custom theme engine. Libadwaita is optional: adopt it only if its widgets justify another required dependency and its GNOME styling is acceptable on Hyprland/KDE.

Proposed navigation and behavior:

| Surface | Concrete behavior |
| --- | --- |
| Recorder | Title, selected app/source, microphone state, elapsed time, live health and a prominent Start/Stop control. Distinguish recording, finalizing and device gap states using text as well as color. |
| Compact recording window | Small always-available recording indicator, elapsed time, stop and reopen controls; no claim that Wayland permits forcing a window above others. Clearly state that closing the main window leaves capture running. |
| Sessions | Recent recordings with duration, interrupted/gap badges, transcript/notes status, open folder, playback/export and resume processing. Never equate accepted chunk coverage with accurate recognition. |
| Settings | Devices, storage, shortcut help, AI profiles, privacy and optional automation; advanced diagnostics stay collapsed. |
| Processing confirmation | Show session, exact provider endpoint/account profile, audio versus transcript upload, chosen models and expected cost/quota uncertainty. Local prepare/export remains available if processing is blocked. |

Reuse the existing worker/socket ownership model. Expose one action dispatcher for GUI, CLI and shortcuts. Add idempotent `shruta show`, `shruta start` and `shruta stop` actions before offering a toggle; a repeated key event must not immediately stop a newly started capture. If a toggle is added, debounce it and expose the resulting state. Add stop/open actions to notifications when supported, but never rely on notifications being persistent: desktop policies can dismiss or suppress them. An optional panel/tray integration is a later enhancement, not a prerequisite or the only recording indicator.

## Wayland shortcuts

First ship copyable commands and instructions for Hyprland, Sway, KDE and GNOME settings. Bind explicit show/start/stop actions to the installed executable; let users choose unused combinations. Do not edit compositor files automatically. Display the command and test result in a “Shortcuts” settings page. Existing README Hyprland examples are a useful seed, not cross-desktop support.

Optionally add the GlobalShortcuts portal after the command surface is stable. Detect the actual interface and supported version, create a session, bind named actions, handle user denial and session loss, and display the binding actually returned by the desktop. Merely finding xdg-desktop-portal is insufficient. The portal requires a living application session; compositor command bindings can start the app when it is closed. Test those as separate experiences. Missing support should yield clear manual setup instructions, never raw keyboard interception or elevated access. The official [GlobalShortcuts API](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.GlobalShortcuts.html) defines session creation, shortcut binding and activation signals; implement only the version available at runtime.

## AI profiles without changing the user's default

Keep agy as this user's default and preserve its existing authentication path; it does not need a newly invented API key. Separate provider selection from the capture engine and separate transcription from notes. A text-capable model must not appear as eligible for native audio simply because it can return JSON. Do not select alternative providers silently when agy fails.

Proposed internal boundary:

```text
ProviderAdapter.identity(profile) -> reproducible endpoint/model/adapter identity
ProviderAdapter.capabilities(profile) -> declared formats, limits, operations
ProviderAdapter.probe(approved_sample, expected_text) -> observed result
ProviderAdapter.transcribe(chunk, request_context) -> validated transcript result
ProviderAdapter.generate_notes(transcript, request_context) -> validated notes
ProviderAdapter.classify_error(error) -> auth/blocked/limit/transient/unsupported
```

Move the present agy implementation behind that interface while preserving its read_file restrictions, executable identity checks, bounded retries and provider-error rejection. Keep schemas, merging, evidence checks, source integrity and consent outside adapters. Start with built-in adapters rather than arbitrary downloaded plugins. Add one direct API adapter only after choosing a documented native-audio API and testing approved representative speech; “OpenAI-compatible” describes some HTTP shapes, not guaranteed audio, structured output, timestamps or retention behavior.

Profiles should store a schema version, provider kind, endpoint, transcription model, notes model, non-secret credential reference and per-operation limits. Capabilities need both declared and observed state. Key probes/caches by provider, normalized endpoint, model, account reference, adapter version and input format; bind accepted results to that identity and source bytes. Profile changes create a new processing run identity so old and new results cannot be silently mixed. Keep previous artifacts/provenance reviewable. Migrate the current global model into an agy profile without enabling uploads or resetting consent.

Proposed CLI additions are `shruta providers list`, `shruta providers add`, `shruta providers probe PROFILE`, and `shruta configure --transcription-profile PROFILE --notes-profile PROFILE`. These are proposed names, not available commands. Model entry should allow a manual ID and optional provider discovery; list refreshes are explicit network requests and reveal no meeting content. Avoid a hard-coded promise that every model listed by a service supports audio.

Replace the single global hosted boolean with scoped grants covering endpoint/provider/account and operations/data classes. A model change invalidates its capability probe; endpoint/provider changes require a fresh upload disclosure and explicit consent. Explain model changes before saving. If another notes provider would receive a transcript, obtain its own grant. Synthetic probe permission does not authorize meeting uploads. If failover is later offered, show the destination and data involved and require explicit approval before switching; default is stop and resume later. Provider refusal, authentication errors and unsupported input must not trigger a covert workaround.

For API credentials, prefer a desktop keyring through a supported Secret Service client; config stores an opaque reference. Mask inputs; show status and “replace/remove,” never raw values. When a keyring is absent/locked, offer an explicitly selected environment-variable source or an explicitly disclosed private credential file with ownership/mode checks. Never silently downgrade to plaintext. Do not accept secrets in ordinary CLI arguments, write them into session artifacts, expose them in `doctor --json`, log request headers, or pass every configured provider's credentials to child processes. Existing agy subprocesses should receive only their required environment. Use stdin or an interactive hidden prompt for key entry. Keyring availability and unlocking must be tested on the supported desktops; see the [Secret Service specification](https://specifications.freedesktop.org/secret-service/latest/).

## Installation: native first, npm included

| Channel | Role and tradeoff |
| --- | --- |
| Python wheel/sdist | Canonical versioned application artifact. Easy to inspect and share across packaging channels, but GTK/PyGObject, FFmpeg and PipeWire tools remain system dependencies. An isolated pipx/uv environment will not automatically see distro PyGObject; document and test the chosen solution rather than promise `pip install` alone. |
| Arch/AUR PKGBUILD | Best first daily-use install for CachyOS/Arch. Let the package manager own Python dependencies, desktop entry, icon and application files; no checkout path or user venv. Build from tagged source archives with checksums, generate `.SRCINFO`, test in a clean chroot and handle Python ABI rebuilds. AUR submission and maintainership are separate from creating a PKGBUILD. Follow the [Arch Python packaging guidance](https://wiki.archlinux.org/title/Python_package_guidelines). |
| npm convenience package | An explicit supported discovery/setup path for users who prefer npm, while launching the same native Python app. Node is installer/launcher tooling only; no browser runtime, resident JS service or second recorder. |
| Flatpak/AppImage/deb/rpm | Evaluate later. Existing pactl routing, host FFmpeg and CLI integration need real packaging/sandbox experiments. A Flatpak package is not automatically compatible with the present host-control design. Avoid committing to all channels before two are maintained well. |

For npm, use a small Linux-only package with `os: ["linux"]`, a `bin` launcher and a tight `files` allowlist. Package name/scope availability remains undecided. Prefer an explicit setup command over `postinstall`: npm install must not install system packages, enable services, start capture, fetch agy or send data. The [npm package manifest documentation](https://docs.npmjs.com/cli/v11/configuring-npm/package-json/) supports executable mappings and platform constraints; [npm install documentation](https://docs.npmjs.com/cli/install/) makes clear that lifecycle scripts can be disabled, so reliable setup cannot depend on them.

Concrete npm experience after publication: installing the wrapper gives `meeting` plus an explicit native-setup subcommand. If a compatible native installation is found, launch it using an absolute resolved path and verify its version; never recurse into the npm wrapper itself. Otherwise explain missing system dependencies and offer explicit user-local setup using the distribution Python with system packages visible. Bundle the matching wheel or download only an exact release artifact whose digest is embedded in that wrapper version. Install under an application-owned XDG data path, not the npm package directory or a movable checkout. No `sudo` and no unmanaged writes into system Python. Dependency installation remains an explicit command the user reviews. If full setup cannot work on a distro, fail with a useful native-install path instead of pretending npm can supply GTK.

Pin wrapper and application release compatibility; display both versions in diagnostics. Test installation with scripts disabled, spaces in paths, missing dependencies, existing unrelated `meeting` executables, upgrades, offline behavior after setup and uninstall. npm uninstall removes the wrapper; provide an explicit way to remove its managed runtime/desktop entry while retaining recordings and config. Do not let it delete an AUR-owned installation. Publish wheel/AUR/npm from the same tagged source, not three divergent copies.

## Make contributions safe and reviewable

Before publishing, choose the owner/repository/name and a license with the copyright holders. MIT/Apache-2.0 suit permissive reuse; GPL/AGPL impose different redistribution/network-use obligations and warrant a deliberate decision, especially if a SaaS is contemplated. No license is selected by this plan. Verify the bundled SAM-derived sample's licensing/provenance and include dependency notices; source-code licensing alone does not settle audio assets.

Initialize Git with a reviewed ignore list excluding recordings, configuration, credentials, private logs, venvs, caches and generated egg-info. Audit the initial tracked tree and examples before pushing; do not upload existing private artifacts. Add LICENSE, portable README quickstart, CONTRIBUTING.md, SECURITY.md, code-of-conduct choice, changelog, issue templates, PR validation checklist and a dependency/support matrix. Bug templates should request redacted doctor output and synthetic reproductions, never real meeting audio or keys by default. Document storage schemas, consent rules, adapter contracts and manual acceptance procedures so contributors can work without access to this workstation or an agy account. Use small issues with acceptance criteria for the four bugs, packaging, accessibility, shortcuts and adapters.

CI should run the offline mocked tests, lint/compile checks, wheel/sdist build and installation smoke test. Add real FFmpeg synthetic integration in an isolated job without microphone or network access, plus manifest/import/tamper regressions. GTK import/headless smoke tests catch packaging mistakes; actual Wayland/window/device acceptance remains a documented manual matrix. Keep CI independent of hosted accounts and real audio. Never expose release secrets to untrusted PR jobs. Tagged releases should produce checksummed source/wheel artifacts and draft release notes with support/accuracy limitations. Publishing credentials/accounts and a signing/provenance policy require the owner's decision; do not embed a token or invented registry URL.

## Phased delivery and acceptance

| Priority | Deliverable | Exit criteria |
| --- | --- | --- |
| P0: trust | Fix Astra's four defects and clarify coverage language. | All four exact reproductions become regression tests; changed original hashes cannot be erased by recovery; corrected imports take effect; boundary text survives or is flagged; tampered caches cannot silently acquire new trusted identity. Existing tests pass. |
| P1: local alpha | Portable source install, native assets, license/ownership decisions, GitHub contribution setup, compact GTK/session UX, manual shortcuts. | Fresh Arch/CachyOS install and uninstall work without checkout-specific paths or data deletion. Clear indicator/Stop survives window reopen. Approved live two-track and unrelated-audio checks pass; no upload occurs during install/start. Publish only as experimental, with remaining matrix explicit. |
| P2: repeatable distribution | Wheel/sdist, tested PKGBUILD and npm wrapper from one release. | Clean-environment native/npm install, upgrade, version and uninstall checks pass; npm works with install scripts disabled; missing dependencies explain a remedy; no privileged/automatic routing/config changes occur. |
| P3: optional AI | agy behind profile interface, secret handling, scoped consent, one deliberately selected additional provider. | Recording works with no provider/key/network. Profile migration preserves disabled consent. Provider/model/endpoint changes cannot bypass probes/consent. Transcription and notes capabilities are separate. Representative approved human speech is compared to reference, with omissions/technical/code-switch errors documented. |
| P4: daily-use beta | Device resilience, shortcuts portal where available, broader packaging/support. | Two-hour capture and approved processing soak report drift, gaps, recovery, disk use and sustained resource measurements. USB/Bluetooth, suspend/PipeWire restart and call transitions tested. Portal denial/loss/absence behave safely. Meet measured targets of <100 MiB idle GUI RSS and <1% one-core idle CPU, or revise claims with evidence. |

P1 does not require AI accuracy to be solved: recorder/export can ship experimentally while processing remains blocked. P3 passing a short probe is not enough to label processing reliable. Do not use schedules in place of these exit criteria.

## Local OSS and a possible SaaS

Keep capture, recovery, export, manual handoff and provider configuration fully local and useful without login, subscription, telemetry or cloud availability. Retain stable open artifact formats. A future cloud offering can be a separately selected destination/adapter for team sharing, managed processing or search, with explicit per-session upload and deletion/retention controls. It must not quietly become the default endpoint or route users' BYOK traffic through a company server.

A SaaS adds identity, tenant isolation, billing, server-side secret storage, authorization, retention/deletion, abuse handling and operational reliability; those are separate requirements, not a small extension of this desktop worker. Validate demand for a specific shared workflow before implementing a backend. If users only want personal notes with their existing agy account, local OSS already meets that need. Keep any future sync queue visible and opt-in, and define deletion behavior for local, server and downstream provider copies before launch.

## Decisions the owner must make

1. Public product/repository name, GitHub owner, npm scope/name and who maintains releases. Existing local paths are not public URLs.
2. License and copyright/asset rights; desired permissive versus reciprocal contribution terms.
3. Initial support promise: recommend Arch/CachyOS + Teams-for-Linux first, with other desktops/distributions labeled untested until validated.
4. First additional AI service, if any, and its approved budget/data policy. Keep agy default now; this plan does not authorize hosted tests or substitute providers.
5. Whether the optional npm setup may download pinned application artifacts when explicitly invoked, and whether libadwaita's style/dependency is desired. Both can be implemented without changing the native architecture.
6. Whether future revenue is hosted team services, support, or another product. No backend or licensing strategy should be justified by an unspecified SaaS goal.

These decisions need not delay P0 corrections or preparing portable packaging, documentation and offline tests. They do gate choosing public identities/licenses and publishing artifacts. No publication is authorized or performed by this plan.
