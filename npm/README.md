# Shrutadhara npm launcher — experimental

This MIT-licensed Linux package starts the native Python/GTK application. It bundles a small version-matched Python wheel, not Electron, an audio fixture or a speech engine. It has no install/lifecycle hooks, automatic application downloads, recording or service setup. Node is required for this convenience wrapper only; prefer native Arch/Debian packages where available.

Until registry publication, install the reviewed release tarball with `npm install --global ./shrutadhara-0.1.0.tgz --ignore-scripts`. After publication use `npm install --global shrutadhara@experimental --ignore-scripts`. Registry availability is not implied by this README.

Install Python >=3.11 with venv/pip support, jsonschema, GTK >=4.10/PyGObject, FFmpeg, pactl and a running PipeWire/Pulse compatibility stack first. On Debian13/Ubuntu24.04 or newer these correspond to `python3 python3-venv python3-pip python3-jsonschema python3-gi gir1.2-gtk-4.0 ffmpeg pulseaudio-utils pipewire-pulse wireplumber`; on Arch see the native PKGBUILD dependencies. Review audio-stack package changes yourself.

Then explicitly run:

```bash
shruta setup-native
shruta doctor
shruta show
```

Setup checks the bundled wheel against its packaged SHA256 manifest, creates a private user-local venv with system packages visible for GTK, and installs that wheel. The hash is a consistency check; trust comes from the reviewed npm/GitHub release, not an independent signature. pip may fetch Python dependency wheels. System packages/services remain managed by you. Runtime location: `${XDG_DATA_HOME:-$HOME/.local/share}/shrutadhara/npm-runtime`.

An explicitly reviewed local wheel can instead be supplied: `shruta setup-native /absolute/path/to/shrutadhara-0.1.0-py3-none-any.whl`. This option checks version/name but cannot authenticate arbitrary local bytes; review them first. Source-tree launchers require this explicit path because release staging adds the bundled wheel. Build a release with `tools/prepare_npm.py` before `npm pack` or publishing.

For an existing native installation set `SHRUTA_NATIVE_EXECUTABLE` to its absolute executable path; do not point it at this wrapper. Desktop integration is separately explicit: `shruta install-desktop`. `shruta shortcuts` documents manual compositor bindings. Recording and hosted AI use require their ordinary explicit actions. agy transcription remains unvalidated; installation does not enable it.

Repeated explicit setup reinstalls the same matching wheel. Setup uses prebuilt dependency wheels, bounded network retries and three-minute subprocess deadlines; no compiler build is launched. Normal recording/GUI commands have no setup deadline. Use your distribution package if Python dependency wheels are unavailable.

`npm uninstall --global shrutadhara` removes the wrapper. After stopping recording and processing, remove only its managed npm-runtime directory and any explicitly installed user desktop entry if desired. Recordings/configuration are retained separately. Never remove a native package manager's files.
