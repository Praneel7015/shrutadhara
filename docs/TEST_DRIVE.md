# Test-drive Shrutadhara

Start with a short, explicitly authorized recording before relying on the app for meetings. Recording captures your microphone independently of Teams' mute button and does not trigger Teams' native recording announcement. Keep the recording indicator visible and obtain any required participant permission.

## Record and listen

```bash
shruta doctor
shruta show
```

In the window, choose a test title and click **Start recording**. Speak a few sentences, optionally play permitted audio through Teams, then click **Stop recording** after about 30 seconds. Closing the window leaves recording running; `shruta stop` also stops it.

For a known speech reference, say: “This is a Shrutadhara test. Maya will send the report on Friday. We decided to keep daily backups.” Do not include confidential content in a sample you might later approve for a hosted AI test.

```bash
shruta status
shruta list
shruta open
```

The latest session folder contains `audio/microphone.wav`, `audio/participants.wav`, `audio/combined.wav` and immutable originals. Listen to each source separately. For mpv:

```bash
mpv --force-window=yes /path/to/session/audio/microphone.wav
mpv --force-window=yes /path/to/session/audio/participants.wav
```

Space pauses, arrow keys seek, and `q` quits. Check that your voice is clear, Teams audio is present when played, and unrelated desktop audio is absent from the participants track. A silent participants track is expected if Teams did not play anything. Review any clipping, missing-device or gap warnings before recording a real meeting.

## Prepare locally

```bash
shruta process --prepare-only
```

This validates and chunks audio without uploading it. Original recordings are retained. No transcription or notes are invented when an AI backend is unavailable.

## Validate optional AI separately

Native agy transcription has failed a previous accuracy test, so its capability gate is currently blocked. First review an approved 1–30 second sample and write down exactly what it says. A complete 30-second recording may run slightly longer due to startup/finalization; use an approved shorter derivative if needed, preserving the original.

The following command explicitly sends that sample through your agy account and may consume quota:

```bash
shruta doctor --probe-ai --sample /path/to/approved-short-sample.wav --expected 'Exact spoken words.'
```

Compare recognition with the recording. Do not bypass a failed gate or rely on plausible output. Only after a representative successful test and consent for the actual meeting data:

```bash
shruta configure --allow-hosted
shruta process
shruta transcript
shruta notes
shruta summary
shruta actions
shruta decisions
shruta ask 'What decisions were made?'
```

Transcription, notes and Q&A remain AI drafts. Check dialogue, technical terms, owners, deadlines and evidence links against the audio. Two-hour, Bluetooth/USB, suspend and broader desktop acceptance testing remains outstanding.
