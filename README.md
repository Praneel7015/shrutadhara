# Shrutadhara (श्रुतधर)

**Hear everything. Preserve knowledge. Remember what matters.**

Shrutadhara is a Sanskrit-inspired name meaning “one who retains what has been heard”: an AI-powered meeting assistant that records conversations, preserves transcripts, and extracts meaningful insights. The application is **Shrutadhara**, the CLI is **`shruta`**, and the repository and Python package are **`shrutadhara`**.

A small native GTK 4 window and Python CLI for private Teams-for-Linux recording on PipeWire. Audio capture works independently of optional hosted `agy` processing. The GUI uses the GTK/Python bindings already installed on CachyOS; it has no bundled browser, Electron runtime, web server, or tray dependency.

**Current validation:** this is experimental software. Capture, local processing, GUI, and mocked tests are implemented. The four application correctness defects found in the independent review have regression fixes. A short native `agy` probe passed, but the full synthetic integration misrecognized known speech. The capability cache remains revoked, so automated meeting transcription remains blocked pending representative validation. See [VALIDATION.md](VALIDATION.md) for evidence and outstanding checks. The source is MIT licensed; package-registry distribution and broader live acceptance testing remain pending.

## Install and open

```bash
git clone https://github.com/Praneel7015/shrutadhara.git
cd shrutadhara
bash install.sh
shruta doctor
shruta gui
```

For a hands-on recording, playback and optional AI validation workflow, see the [test-drive guide](docs/TEST_DRIVE.md).

`shruta show` also opens or focuses the window. `shruta start` returns the current active session when already recording, and repeated `shruta stop` is safe. Keep user-facing recording notices enabled.

For an installed Python wheel, `shruta install-desktop` explicitly installs a user launcher and application-menu entry using that installation. The source installer is no longer required after a wheel install. Experimental native Arch/Debian artifacts and the npm launcher are described in the [distribution guide](docs/DISTRIBUTION.md) and [npm README](npm/README.md). npm/AUR listings and distribution repository inclusion require separate publication; source availability alone does not provide them.

The installer creates an isolated venv using `/usr/bin/python3` with system packages visible for GTK, a `~/.local/bin/shruta` launcher, and an application-menu entry. It does not enable recording, a login service, or hosted processing. Keep this project directory in place; the launcher points into it. Re-run the installer after moving it.

Required system tools: `ffmpeg`/`ffprobe`, `pactl` (Arch package `libpulse`), running PipeWire/Pulse compatibility and WirePlumber, Python ≥3.11. GUI: GTK ≥4.10 (`gtk4`) and `python-gobject`. Optional: `notify-send` (`libnotify`), `xdg-open` (`xdg-utils`), systemd user services, and `agy`.

If dependencies are missing, review `shruta doctor`; install only those you need using your usual package manager. The application never installs audio engines or changes system audio configuration files.

Manual installation without uv:

```bash
/usr/bin/python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install -e .
.venv/bin/python install.py
```

This alternative requires the distribution's Python venv/pip support. Rebuild the venv after an Arch Python ABI upgrade so PyGObject remains compatible.

## Daily use

```bash
shruta start --title 'Engineering sync'
shruta status
shruta stop
shruta process
shruta notes
shruta summary
shruta actions
shruta decisions
shruta transcript
shruta ask 'What decisions were made?'
shruta list
shruta open
```

`notes` displays detailed notes; `summary`, `actions`, and `decisions` display their corresponding outputs. Each supports session selection and opening in a desktop application. `shruta ask --session SESSION_ID 'Question'` answers from an accepted transcript with segment-level evidence links. Without a question argument it reads an interactive question, or stdin when piped. Q&A requires hosted consent, accepts incomplete transcripts only with `--allow-partial`, rejects stale/oversized source context rather than truncating it, and preserves private request/answer artifacts in the session's `questions/` directory. It does not upload audio or create a missing transcript.

The compact window offers the same recording controls, elapsed time, device health, processing, and output buttons. Device selection and diagnostics are collapsed initially. It attaches to an active recording when reopened. **Closing the window does not stop recording.** Processing launched from the GUI also continues in a separate process.

Provide participant notice and obtain required permission before capture. **Local recording does not trigger Teams' native recording notification.** Organizational restrictions still apply. The microphone is captured continuously, including speech while muted inside Teams. System and hardware mute remain effective; the application never unmutes a device automatically. A system-muted microphone causes startup to fail unless explicitly accepted with `--allow-muted-mic` or the GUI checkbox.

CLI device overrides:

```bash
shruta start --microphone SOURCE_NAME --output SINK_NAME
shruta start --teams-pid AUDIO_STREAM_PID
shruta start --foreground
shruta status --json
shruta process --session SESSION_ID
```

Use source/sink names from `shruta doctor`. By default, microphone selection follows Teams' capture source where identifiable, then the desktop default; listening follows the desktop default sink. Multiple Teams audio processes require `--teams-pid`. The recorder captures the selected Teams application's playback, which may include notification sounds. It does not isolate individual remote participants.

## Audio and recovery

Only identified Teams playback streams are moved into a private virtual sink. A loopback forwards that audio to the listening output. Another private sink carries microphone audio to the recorder. Desktop defaults remain unchanged. FFmpeg captures two mono PCM tracks at 48 kHz/16-bit into 60-second Matroska archive segments. The supervisor tracks new Teams streams and device changes and restores moved streams at stop.

On this workstation, a transient systemd user service supervises capture; a detached worker is the fallback. It is not enabled at login. A private Unix socket, checked against the peer UID, carries CLI/GUI control messages.

Completed archives survive worker crashes. Recovery checks archive hashes, validates decodability, and retains damaged originals. Recording does not automatically restart after reboot. Missing devices, scheduling interruptions/suspend, and capture restarts create explicit gap records. Silence is an observation rather than proof of failure. Listening-output loss does not itself mean the remote audio archive is lost.

```bash
shruta recover
shruta process --session SESSION_ID --prepare-only
```

If interrupted finalization left WAV derivatives missing, processing rebuilds them from valid archives. Existing derivative hash mismatches stop processing for investigation. Do not edit original archives or chunk manifests in place. No command deletes recordings.

Startup reserves 4 GiB plus 512 MiB safety headroom for a two-hour meeting, derivatives, and processing; this is an estimate, not a hard maximum duration. Capture stops before the safety reserve is exhausted. Some temporary exports can require additional room. Use a larger storage filesystem for repeated long meetings.

## Hosted processing is opt-in

`shruta providers` lists available adapters without contacting a service. The new provider interface currently supports **only agy**, preserving its model, authentication, capability checks and consent. Additional APIs, API keys, profiles and provider failover are not enabled. An unknown configured provider is rejected rather than silently substituted.

`agy` is a hosted AI interface. Local-first means recording, storage, chunk preparation, and recovery are local. AI processing sends audio/transcripts to Google through your account, may consume quota, and may retain data in `agy` conversation history. This application cannot control Google's retention. Private AI diagnostics and intermediate responses may contain meeting content; routine status/errors do not include dialogue.

First validate native audio processing using known **synthetic or otherwise approved** speech:

```bash
# Explicitly permits uploading this approved 1–30 second sample only:
shruta doctor --probe-ai --sample /path/to/sample.wav --expected 'Exact spoken words.'
```

The expected text is compared locally; it is never included in the model prompt. No speech fixture is bundled: the earlier development sample's generator had unclear upstream licensing, so that sample is retained locally outside release artifacts. Supply speech you have permission to process and upload. A clean, exact result is required. A failed probe leaves audio processing blocked. Do not keep retrying provider blocks. Verify representative English/Indian-language and technical speech separately before trusting daily output.

Then, only for meetings you are permitted to upload:

```bash
shruta configure --allow-hosted
shruta process
shruta configure --deny-hosted
```

The GUI offers the same disclosure before enabling meeting-data processing. Synthetic probe consent does not enable meeting uploads. The capability gate is keyed by CLI executable hash/version, model, audio format and adapter version. Application-managed CLI invocations set `AGY_CLI_DISABLE_AUTO_UPDATE=true`; other independently launched `agy` sessions can still update it. A version/model change requires another clean probe.

```bash
shruta configure --model gemini-3.8-flash-high
shruta configure --chunk-seconds 120
shruta configure --allow-hosted --auto-process
shruta configure --no-auto-process
```

### Capability findings from this workstation

- `agy` was 1.5.8 at initial inspection and automatically became 1.5.9.
- Plain `-p '@audio.wav'` did not attach audio. Manually typed file mentions are text.
- ACP negotiation reported `audio: false`.
- The native `read_file` tool returned recognizable WAV speech without another speech engine, but the initial result had a wrong word and embedded provider filter errors. **It did not qualify as a clean capability test.**
- JSON-schema output worked. The adapter rejects provider errors even when exit code and terminal status claim success.
- Release notes list WAV, MP3, M4A, AAC, FLAC, OPUS attachment recognition. Only WAV/native reading was exercised. Audio size/duration limits remain unverified; desktop attachment limits must not be assumed to apply.

References: [headless and structured output](https://antigravity.google/docs/cli/headless/), [mentions](https://antigravity.google/docs/at-mentions/), [CLI release notes](https://antigravity.google/docs/changelog), [Teams D-Bus API](https://ismaelmartinez.github.io/teams-for-linux/development/dbus-control/).

### Processing behavior

The pipeline validates both tracks, preserves the originals, and makes unnormalized 16 kHz mono PCM WAV derivatives. Default chunks contain five minutes of core audio plus two seconds of boundary context, with a conservative **application** ceiling of 16 MiB. Exact sample offsets, hashes, chronological order, and overlap boundaries are persisted. Explicit provider size/context failures bisect chunks to a minimum 30-second core; other failures never trigger arbitrary splitting.

Native processing uses `read_file` only; commands, file writes, plugins, and URL access are denied. The application never uses Whisper, another transcription engine, external API credentials, or a fallback provider. Intermediate results are private and retained. Three attempts are allowed for transient transport errors with bounded backoff and a ten-minute deadline per attempt (up to about thirty minutes per chunk plus cleanup/backoff); provider blocks, authentication failures, contaminated output, and unsupported input stop processing. Rerun `shruta process` to resume accepted chunks rather than repeat them.

Local and remote tracks are transcribed separately. Speaker labels represent track provenance, not verified identity; speaker names are not invented. Acoustic bleed from speakers into a microphone can appear on both tracks—use a headset for the best separation. Model timestamps are approximate. Unintelligible speech is marked. Ambiguous chunk boundaries retain both readings and prevent a claim of complete coverage.

The transcript JSON includes segment IDs, start/end offsets, track identity, uncertainty, and source/chunk provenance. Markdown exposes missing intervals and review items. **Coverage means all expected chunks were accepted, not certified recognition accuracy.** Review the audio before relying on exact wording.

Notes are generated separately after transcript validation. Every item cites transcript segment IDs; action owners/deadlines must occur explicitly in their evidence. Schema/link validation cannot prove semantic truth, so review consequential notes. Oversized transcripts use resumable evidence-linked intermediate topic records; if the final records exceed the application context budget, processing stops rather than truncates them. Partial notes require `shruta process --allow-partial` and are prominently labeled.

### Manual handoff

```bash
shruta process --prepare-only
```

This writes per-chunk audio, prompts, and `transcript/chunks/manifest.json` without AI calls. In an interactive `agy` session, select/attach each audio file using the supported interface; a typed `@path` alone is insufficient. Interactive transcription remains unverified until your own sample succeeds. Do not automate terminal keystrokes or use another transcription backend.

Save results as the following JSON, using the current manifest's `source_fingerprint` and chunk IDs. Export only actual `agy` results; never fill missing dialogue yourself to pass validation.

```json
{
  "source_fingerprint": "COPY_FROM_MANIFEST",
  "results": {
    "microphone-00000": {
      "audio_received": true,
      "fully_processed": true,
      "limitation": "",
      "segments": [
        {"start": 1.0, "end": 2.5, "text": "Actual recognized speech.", "uncertain": false}
      ]
    }
  }
}
```

```bash
shruta process --import /path/to/results.json
```

Imports are local. Notes still require separate hosted consent. Missing chunks remain incomplete. If native and interactive audio transcription both fail, keep recording/export available and report processing blocked.

## Files and states

Configuration is stored in `${XDG_CONFIG_HOME:-~/.config}/shrutadhara/config.json`, capability results alongside it, and control sockets under `$XDG_RUNTIME_DIR/shrutadhara`. `SHRUTA_ROOT` overrides the meeting storage directory; the default remains `~/Meetings`.

On upgrade from the early prototype, configuration and capability metadata are copied from `~/.config/meeting` only when the corresponding new file does not exist. Consent flags and a failed capability test are preserved; originals remain intact. An active legacy recorder remains controllable until it finishes. The explicit desktop installer forwards only the old managed `meeting` launcher and backs up its managed desktop entry; unrelated commands are untouched. The old `MEETING_ROOT` override is recognized only for compatibility, with `SHRUTA_ROOT` taking precedence.

```text
~/Meetings/YYYY-MM-DD_HHMMSS_title_uuid/
  session.json
  audio/
    originals/epoch-000/000000.mkv
    manifest.json
    routing.json
    microphone.wav
    participants.wav
    combined.wav
  transcript/
    full-transcript.md
    transcript.json
    chunks/manifest.json
    chunks/microphone-00000/...
  notes/
    summary.md
    detailed-notes.md
    action-items.md
    decisions.md
  logs/
    recording.log
    processing.log
```

Recording: `starting → recording → stopping → recorded`, with `interrupted` and `failed` outcomes. Transcription and notes independently use `pending/running/partial/complete/blocked/failed`. Locks prevent concurrent capture or duplicate processing. Metadata updates use atomic replacement. Session directories/files use `0700`/`0600`; sharing/syncing them is your explicit choice.

Predictable exit codes: `0` success, `2` arguments, `3` unavailable dependency/capability, `4` state conflict, `5` audio/recording failure, `6` incomplete/failed processing, `7` consent required, `130` interruption.

## Optional call detection and shortcuts

The installed Teams 2.32.1 supports a disabled-by-default local D-Bus service. To use it, add `"dbusControl": {"enabled": true}` to the appropriate Teams configuration and restart Teams yourself. The recorder does not edit Teams internals or enable this setting.

```bash
shruta watch                          # call notifications only
shruta watch --auto-record --validated # explicit opt-in, only after testing transitions
```

Detection uses `GetState`/`InCallChanged` on `com.github.IsmaelMartinez.teams_for_linux.Control`, not presence or stream activity. It is an observed selected-profile state, not server-confirmed. Meeting title/calendar metadata is not exposed. Initial state does not start an existing call automatically. Call end is debounced and rechecked. Bus loss means unknown state and leaves active capture running; stop it manually. Profile switching, upstream Teams changes, or suspend can invalidate the observation—test before enabling automation. The experimental `meetingStarted` pulse is not used. MQTT is unnecessary.

Optional notification-only login service:

```bash
mkdir -p ~/.config/systemd/user
cp desktop/shrutadhara-call-monitor.service ~/.config/systemd/user/
# Check the executable for your installation, then edit ExecStart if needed:
command -v shruta
systemctl --user edit --full shrutadhara-call-monitor.service
systemctl --user daemon-reload
systemctl --user enable --now shrutadhara-call-monitor.service
# Undo:
systemctl --user disable --now shrutadhara-call-monitor.service
```

The copied unit defaults to the source launcher `%h/.local/bin/shruta`. For native packages use `/usr/bin/shruta`; for npm use the absolute wrapper path reported by `command -v shruta`. Quote paths containing spaces in `ExecStart`, and double any literal percent signs. The template is in the source release; native package users need not create a shadow launcher.

Hyprland examples (add manually, choosing unused bindings; use the absolute installed path if its PATH differs):

```ini
bind = SUPER SHIFT, R, exec, shruta show
bind = SUPER SHIFT, S, exec, shruta stop
```

`shruta shortcuts` shows setup commands for Hyprland, Sway, KDE and GNOME. In the window, the defaults are **Ctrl+Shift+R** to start and **Ctrl+Shift+S** to stop. Change them with `shruta shortcuts --start '<Control><Alt>r' --stop '<Control><Alt>s'`, then reopen the window. Identical bindings, including reordered modifier aliases, are refused. These accelerators are window-local; desktop-wide shortcuts require your compositor/settings bindings. GlobalShortcuts portal integration is deferred.

Keep a visible GUI/notification indicator while recording. `shruta status` shows active state and warns when the worker status is stale; a live process alone is not proof that audio is arriving.

Recording-start notifications request no expiry and use a replacement tag where the notification server supports it. The desktop can still suppress or dismiss them; keep the window visible when a persistent indicator is required.

## Tests and manual acceptance

```bash
uv pip install --python .venv/bin/python -e '.[test]'
.venv/bin/python -m pytest -q
```

Unit tests isolate storage and mock external audio/AI tools. They cover session lifecycle, concurrency, routing identities, command construction, recovery, exact chunk offsets, overlap merging, provider errors with exit zero, bounded retries, resume, evidence validation, consent and GUI button states. They do not record your microphone or upload data.

Manual daily-use acceptance checklist:

1. Obtain permission; record 30 seconds, playing distinct speech through Teams and speaking locally.
2. Play unrelated browser audio; verify it is absent from the participants track.
3. Stop and listen to both tracks; check timing, Teams mute versus system mute, silence and clipping.
4. Close/reopen the GUI during capture and confirm continuity.
5. Run the explicit clean capability probe, enable hosted processing if permitted, process, and compare dialogue/technical terms/code-switching/timestamps to audio. Check note evidence and owners/deadlines.
6. Test USB and Bluetooth disconnect/reconnect, Teams stream recreation, default-device switching, suspend, worker interruption, and processing interruption/resume.
7. Run a two-hour soak test; measure timeline drift, disk use, gaps, recovery and memory/CPU. Target idle GUI overhead: <100 MiB RSS and <1% of one CPU core, excluding FFmpeg/agy.

An optional short **live** capture diagnostic is `shruta doctor --test-recording`; it explicitly records three seconds and retains the test session. It is not run by default. Passing unit tests does not establish two-hour or Bluetooth reliability.

For a source installation, remove only its managed launcher and desktop entry after stopping active work. Native packages must be removed through pacman/APT; npm has a separate wrapper and user runtime. See the [channel-specific upgrade/removal guide](docs/DISTRIBUTION.md#upgrade-and-removal). Recordings and configuration are retained; remove any explicitly installed user service separately.

## License

The application source is available under the [MIT License](LICENSE). See [NOTICE](NOTICE) for the excluded development fixture and dependency notes. Experimental GitHub package releases use the public project identity. npm and AUR publication remain separate steps; see the [distribution guide](docs/DISTRIBUTION.md).

## Reliability patch development

The 0.1.1 development version addresses the [EGM project review](docs/reviews/2026-11-17/README.md). See [implementation status](docs/reviews/2026-11-17/IMPLEMENTATION_STATUS.md) for completed regressions and remaining acceptance. New Q&A answers keep their own evidence snapshot. Accepted output caches and transcript JSON are verified before reuse; old unbaselined transcripts require reprocessing or explicit reviewed import before Q&A. Historical answer links are not retroactively rewritten.

The window includes recent meetings, separate microphone/participants audio, and **Prepare audio locally (no AI upload)** under Recordings and local tools. `shruta open --artifact microphone` and `shruta open --artifact participants` select the individual tracks. Source GUI installations require GTK4.10 or newer; the window can resize/scroll for larger text.
