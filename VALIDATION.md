# Validation on this workstation

Date: 2026-11-16. CachyOS, PipeWire 1.6.11, WirePlumber 0.5.19, Teams-for-Linux 2.32.1, FFmpeg 9.0.2, GTK 4.24.1, Python 3.14.10, `agy` 1.5.9.

## Follow-up implementation

The four defects in ASTRA_REVIEW.md now have fixes and regression tests: boundary readings are reconciled before ownership (unmatched/ambiguous speech is retained for review); recovery verifies durable archive baselines before replacing manifests; explicit imported corrections override old caches, even corrupt ones; derivative and chunk caches verify saved digests. Legacy caches without output digests are rebuilt from validated parents rather than trusted in place.

Astra independently reran 90 tests and the original reproductions after these changes; all passed. Its focused merge benchmark measured 1,000/2,000/4,000 nonoverlapping segments at 0.037/0.070/0.140 seconds using the new active-interval sweep. Additional repeat-Stop finalization coverage is included in the current suite. These results address the application defects; they do not change the AI recognition failure below.

The working tree also includes portable desktop installation, source archive assets, an unpublished npm local-wheel launcher, window-local accelerators/manual desktop shortcuts, contributor docs, offline CI and an agy-only provider interface. MIT and the `shrutadhara` name were selected by the owner; repository/registry publication remains pending. No new hosted AI calls, recording or audio-routing changes were made for this follow-up.

The local npm installer was also tested in an isolated HOME/XDG data directory with an actual built wheel and fresh Python dependencies, without relying on the checkout or PYTHONPATH for the installed application. Version, provider listing, shortcut help, desktop setup, GTK and jsonschema imports passed. Dependency setup now has bounded network retries and a three-minute subprocess deadline.

The earlier synthetic SAM fixture is now excluded from Git and release artifacts because its upstream does not specify an open-source license. Its local copy is preserved in `.local-fixtures/legacy-probe.wav`; capability probes now require an explicitly supplied approved sample and reference text. No recordings were deleted.

The project was subsequently named **Shrutadhara (श्रुतधर)**, with CLI `shruta` and Python package/repository `shrutadhara`. Branding migration tests cover preserved settings/consent/capability failures, active-worker control, storage overrides and managed launcher backups. Summary/actions/decisions commands and evidence-linked transcript-only Q&A are tested with mocked providers. New Q&A functionality has not been exercised against a hosted model or private meeting content.

Current local verification: **117 tests passed**, Ruff checks passed, and the final Shrutadhara wheel/source/npm artifacts passed the release-content check. The actual packed npm tarball and wheel were installed into a fresh isolated HOME/XDG environment; version/help/Q&A help/provider listing/shortcut help/desktop installation and installed GTK/jsonschema imports passed without importing application code from the checkout. No co-author trailers are added to commits.

## 2026-11-17 local test drive and source publication

A user-authorized 30-second microphone test completed normally (approximately 31 seconds including startup/finalization), with no recorded gaps or finalization errors. Microphone and combined audio contained sound; the participants track was silent, matching the user's confirmation that no Teams audio was played. All three WAV exports validated. The microphone reached full scale and triggered a possible-clipping warning; gain/playback review remains necessary.

Local `process --prepare-only` produced two ordered chunks without uploads. The session stopped, moved streams were restored and no session routing modules remained. The microphone WAV was opened locally in mpv paused for user review. Recordings, transcripts, configuration and private logs are excluded from source publication.

The complete 117-test suite, Ruff, compilation, desktop-entry validation, release artifact checks and a redacted Git-history secret scan passed before pushing source to https://github.com/Praneel7015/shrutadhara. The repository is experimental; npm/PyPI/AUR publication and broader live/AI acceptance are separate work. No meeting audio was uploaded during this validation.

## Passed

- 60 isolated automated tests, with external audio/AI tools mocked: state transitions, locking, routing ownership, FFmpeg construction, crash recovery, exact splitting/offsets, overlap, parsing, bounded retries/timeouts, resume, imported provenance, evidence, consent and GUI state.
- Ruff import/error checks, Python compilation, and desktop-entry validation.
- The native GUI opened at 430 × 399 logical pixels. Its initial measured RSS was approximately 96.8 MiB; imports were subsequently made lazy to reduce startup overhead. A sustained CPU benchmark remains outstanding.
- Offline FFmpeg integration generated segmented two-track PCM archives and exported three WAVs at the expected duration. A deliberate 100 ms microphone offset survived export.
- A seven-minute capture was initiated through the shared GUI during implementation. It produced eight valid archive segments. An early-build cleanup incompatibility with `pactl`'s JSON module listing was corrected; recovery finalized all three WAVs and restored Teams routing. Original archives remain in `~/Meetings`; the session is truthfully marked interrupted. Possible clipping was flagged on both source tracks. Audio content was not uploaded or manually assessed for speech quality.
- The installed native `agy` file-reader adapter returned a clean, exact known-speech capability result once. This demonstrated native audio perception and structured output without another speech engine.

## Accuracy failure: AI processing remains gated

A subsequent full synthetic integration used the same approved synthetic speech through the archival/export/chunk pipeline. It produced structurally valid transcripts and all four evidence-linked notes files, but comparison with the known source found recognition errors on **both** tracks. Notes carried those errors forward. Coverage of submitted chunks did not establish accurate recognition.

The application capability cache has therefore been explicitly invalidated. The synthetic integration artifacts were marked failed and their transcript/notes labeled for review. Hosted processing for actual meetings remains disabled. No real meeting audio or transcript was sent to Google.

Synthetic failure artifacts, including private provider diagnostics, were retained at `/tmp/meeting-synthetic-integration-035g4ssh/Meetings/2026-11-16_214646_synthetic-integration-sample-only_642f85de`. This temporary directory may disappear after reboot. The robotic SAM sample is a limited quality benchmark; neither its failure nor a short successful probe establishes performance on human speech, code-switching, or technical vocabulary.

Before enabling meeting processing, run an explicitly approved representative known-speech test and compare the result to the recording. Do not treat native file attachment support as production transcription assurance. The application includes manual prepare/import as an alternative and installs no other transcription backend.

## Outstanding manual acceptance

- Representative human English/Indian-language recognition and meaningful technical dialogue.
- Listening checks for unrelated desktop-audio exclusion, acoustic bleed and source gain/clipping.
- USB/Bluetooth device and profile transitions, suspend/resume, and PipeWire restart under live capture.
- Teams D-Bus call transitions before enabling optional automatic capture.
- A real two-hour recording/processing soak and sustained GUI resource measurements.

The recording/CLI/GUI implementation is available for manual use and further acceptance testing. Reliable daily AI transcription has **not** been established on the current `agy` path.
