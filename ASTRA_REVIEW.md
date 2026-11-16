# Independent release-readiness review

**Follow-up:** the findings below describe the audited prototype. All four now have implementation fixes and regression tests. Astra independently retested the original reproductions and a 90-test suite successfully, including correction of a corrupt-cache follow-up and improved merge scaling. See VALIDATION.md for current status. AI accuracy/live acceptance and public release prerequisites remain outstanding.

Reviewed 2026-11-16 against the current working tree. **Recommendation: fix the four correctness issues below before an experimental public release; do not advertise reliable daily transcription.** Recording remains a useful experimental local feature, but long-duration, device-transition and human-speech acceptance remain outstanding.

## Scope and evidence

Read README.md, VALIDATION.md, implementation and existing tests. Ran `.venv/bin/python -m pytest -q`: **60 passed in 0.31 seconds**. Ran additional isolated Python checks with temporary sessions, mocked provider calls and generated PCM/tone audio. No live audio capture, routing changes, hosted AI, meeting-content access, user-configuration changes or implementation edits occurred. The existing seven-minute recording was not inspected.

Reproduction scripts are `/tmp/shruta_astra_checks.py` and `/tmp/shruta_astra_recovery.py` (temporary artifacts, not committed tests). Re-run from this project with `.venv/bin/python SCRIPT`. All test state uses fresh temporary SHRUTA_ROOT, XDG_CONFIG_HOME and XDG_RUNTIME_DIR values. Scripts contain only synthetic data. Recovery test mocks export, but uses actual FFmpeg generation/validation and the actual recovery/manifest code.

## Findings

### 1. High: boundary ownership can silently delete recognized speech

`shrutadhara/processing.py:375` discards each segment whose estimated midpoint lies outside that chunk's core before comparing neighboring readings. Approximate timestamps can put the two readings on opposite sides of the boundary, so both are discarded. The later overlap review never sees either reading.

Reproduction: core A `[0,10)`, audio A `[0,12)` with “Boundary speech” at `[9.5,11]`; core B `[10,20)`, audio B `[8,20)` with the same text at local `[0.5,2]`. Both inputs validate. `merge()` returns **zero segments and `coverage_complete=True`**. This is application-induced omission, independent of the known provider recognition failure.

Minimal fix: reconcile adjacent overlap candidates before applying ownership; retain one matching reading, and retain/flag unmatched or ambiguous boundary content. Add this opposite-midpoint regression test and partial/unequal segmentation cases.

### 2. High: recovery silently replaces the original integrity baseline

`shrutadhara/recorder.py:110` unconditionally rebuilds the archive manifest. `shrutadhara/audio.py:450` hashes current bytes and `:538` overwrites the existing manifest without comparing recorded original hashes.

Reproduction: create a valid two-track 440 Hz synthetic archive and persist its manifest, replace it with a valid 880 Hz archive, then recover an interrupted session. Output: **changed original hash=True, invalid_segments=0, recovery_finalized=True**. Thus an existing original hash mismatch that would stop `prepare()` can be erased by recovery; `start()` also calls recovery automatically. This contradicts the documented recovery hash check.

Minimal fix: preserve and verify existing manifest entries before salvage/export; treat changed original bytes as an integrity failure requiring explicit investigation. Newly discovered/unfinalized segments can receive their first hash without replacing old trusted entries. Test changed-but-decodable originals as well as damaged containers.

### 3. Medium: a corrected manual import is ignored

`shrutadhara/processing.py:728` checks cached result identity before `import_path`. The signature contains chunk/adapter identity but no imported content. A second supplied result for the same chunk therefore never replaces the first.

Reproduction: import “Incorrect old text”, then import “Corrected new text” with the same valid source fingerprint and chunk ID. Both operations succeed, but the generated transcript still contains **“Incorrect old text”**. This prevents the documented local handoff from accepting corrected provider exports.

Minimal fix: explicitly supplied import results take precedence over cached results; validate them and replace that chunk's result. Reuse existing results only for omitted chunks if that resume behavior is intentional and documented. Add correction/re-import coverage.

### 4. Medium: cached processing audio is trusted without checking its bytes

`shrutadhara/processing.py:164` checks only the resampling input fingerprint, and `:205` checks only the chunk's input fingerprint. `:222` then hashes whatever chunk bytes exist and publishes that as the current source. Neither cache metadata records/verifies the expected output digest.

Reproduction: prepare synthetic WAVs, replace a generated chunk with different valid PCM while leaving input.json unchanged, prepare again. The altered bytes are accepted and their digest replaces the manifest digest. The source audio has not changed. Similarly, a changed 16 kHz derivative is not rebuilt when its sidecar fingerprint matches.

Minimal fix: persist and verify digests for both cached derivatives and chunks; stop with an integrity diagnostic, or rebuild disposable cache outputs from validated parents with explicit invalidation of dependent results. Add a tampered-cache regression test.

## Release assessment

The existing tests provide useful checks for consent, tool-error rejection, routing identities, session states and mocked processing. Passing them does not cover the four reproduced cases. There is no demonstrated unauthorized upload in this review; consent remains explicit and known capability failure is disclosed. Existing private-directory protections and provider diagnostics separation are positive controls, not proof of a comprehensive security audit.

A public experimental release should first fix the issues above, include their regression tests, retain prominent accuracy/experimental notices, and provide public distribution essentials. The current tree has no LICENSE; pyproject.toml has no license declaration. README installation starts with a workstation-specific absolute path, and desktop integration is generated by install.py rather than shipped as a distribution asset. Choose licensing and establish a portable source/package installation path before distributing; this review did not publish or install anything.

Daily use remains unvalidated: representative human/code-switched/technical recognition, unrelated-audio exclusion, device/profile reconnection, suspend/PipeWire recovery, D-Bus transitions, two-hour capture/processing soak, timeline drift and sustained GUI resource use are still outstanding. The known synthetic integration recognition failure blocks any claim of accurate hosted transcription even after the local correctness fixes. A brief passing probe is insufficient acceptance evidence.
