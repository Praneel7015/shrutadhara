# Experimental Flatpak

The initial Flatpak targets x86_64 desktops with Flatpak, Wayland or X11, and a working PulseAudio-compatible audio server (including PipeWire). It supports recording and local audio preparation. Transcription, notes, Q&amp;A, automatic Teams monitoring and CLI global shortcut installation require a native installation. No host-command bridge or hosted AI network permission is granted.

An installable development bundle passed the [build and installed-runtime checks](https://github.com/Praneel7015/shrutadhara/actions/runs/44106976357) from commit `95f5ac6`. This is a development bundle, not a published Flathub application. A successful bundle build does not establish live Teams routing, speech recognition accuracy or long-meeting reliability. ARM builds and Flathub submission remain future work.

## Build

Install Flatpak and flatpak-builder using your distribution's packages, and add Flathub following its official installation instructions. The shared GNOME 51 runtime/SDK are substantial downloads; subsequent applications share the runtime. The app itself bundles only its Python code/dependencies, PulseAudio clients and a speech-audio subset of FFmpeg.

From a clean, committed source checkout:

```bash
mkdir -p dist
git archive --format=tar.gz --prefix=shrutadhara/ -o dist/shrutadhara-flatpak-source.tar.gz HEAD
flatpak-builder --user --install-deps-from=flathub --force-clean --repo=flatpak-repo flatpak-build packaging/flatpak/io.github.Praneel7015.Shrutadhara.json
flatpak build-bundle flatpak-repo shrutadhara-experimental-x86_64.flatpak io.github.Praneel7015.Shrutadhara experimental
```

The archive contains tracked files only. Never replace it with a source directory that includes private recordings/configuration. All downloaded dependencies are pinned by SHA256. The current Python dependency wheels target x86_64 Python 3.14/3.15; a runtime Python upgrade needs a dependency refresh and build test. This development recipe uses binary Python wheels; a future Flathub submission needs review against Flathub's source/build requirements.

The `Experimental Flatpak` GitHub Actions workflow builds the same recipe, uploads a development `.flatpak` artifact, installs it and checks the actual runtime. The synthetic smoke test checks JSON validation/PyGObject imports, PCM Matroska segmentation, sound validation and combined audio generation without opening the microphone or uploading data.

## Install and record

Download the tested workflow artifact (requires GitHub CLI authentication), or build locally:

```bash
gh run download 44106976357 --repo Praneel7015/shrutadhara --name shrutadhara-experimental-x86_64-x86_64.flatpak --dir ./shrutadhara-flatpak
cd shrutadhara-flatpak
```

Workflow artifacts expire; if this run is unavailable, build a reviewed source checkout or use a newer passing run. This is not yet an automatically updated Flatpak repository. Then install:

```bash
flatpak install --user ./shrutadhara-experimental-x86_64.flatpak
flatpak run io.github.Praneel7015.Shrutadhara
```

Use Start and Stop in the recording window. Notify participants and obtain required permission first. Teams mute does not mute microphone recording. Stop and wait for finalization before closing: the Flatpak window deliberately stays open during capture/startup/finalization/local preparation, because the window owns the sandbox lifetime. Force-killing the app interrupts recording; original archive segments remain for recovery.

Recordings go under `~/Meetings/Flatpak`. The sandbox has access only to that recording directory, its private app data, audio and display sockets. PulseAudio permission enables audio capture and stream routing; recording is always explicitly started. Native and Flatpak runtime metadata are isolated because PIDs differ across sandboxes. Use one installation for recording at a time; simultaneous native/Flatpak capture is not supported.

The host's `agy` and application configuration are not imported. AI processing fails with a clear native-installation message. To process a stopped recording, use a native installation:

```bash
shruta process --session "$HOME/Meetings/Flatpak/SESSION_DIRECTORY"
```

Native hosted consent and a successful agy capability probe are still required. Do not change Flatpak permissions to run host commands as a workaround.

CLI tools such as `--help` and `list` can run with `flatpak run --command=shruta io.github.Praneel7015.Shrutadhara ...`. Detached `start` is rejected: the sandbox would exit when the command returns. `start --foreground` is available for advanced use (interrupt that foreground command to stop); independently launched Flatpak commands may have different PID namespaces, so use the GUI to control GUI recordings. The native CLI retains its normal behavior.

## Manual acceptance before distribution

Record an explicitly approved 30-second sample with microphone speech and Teams playback. Stop, prepare locally, and listen to both exported tracks using a native audio player. Confirm that closing the window during recording retains it, then stops/closes correctly after finalization. Repeat with a Bluetooth/USB device change and interrupted process recovery. Check Wayland and X11, notification/file-opening portals, different distributions, and a two-hour capture. These remain manual checks until completed; synthetic CI is not a replacement.

Flathub publication additionally needs a reviewed stable manifest, genuine screenshots, suitable dependency sources, a submission review and maintainer ownership. No Flathub listing or automatic-update repository is created by building a standalone bundle.
