Shrutadhara is an experimental native Linux meeting recorder with optional agy transcription and notes.

- CLI `shruta` and compact GTK4 controls; separate microphone and Teams playback recordings.
- Native Arch package, AUR recipe, Debian package, Python wheel/source and npm convenience launcher.
- npm bundles the matching wheel; `shruta setup-native` explicitly installs the user runtime. No install hooks.
- Installation enables no recording, services or AI uploads. Obtain participant permission and follow organizational rules.

Known limits: a microphone smoke test passed, but live Teams playback, long meetings and device switching still need acceptance testing. agy speech-recognition reliability failed synthetic integration validation; automatic transcription remains blocked until a representative probe passes. This is not a daily-use reliability claim.

See docs/DISTRIBUTION.md for package installation and source/checksum verification, docs/TEST_DRIVE.md for testing, and VALIDATION.md for current evidence. npm/AUR registry listings require separate publication; attached packages do not imply inclusion in CachyOS, Arch, Debian or Ubuntu repositories.
