# runtime review

Completed fresh-context reviewer. Findings normalized by the Elephant; original IDs preserved. Full qualifications, disagreements and evidence are in the consolidated report.

## RT-orphan: Detached capture survives a killed supervisor

Mapped to F01, Major, Reproduced. `shrutadhara/recorder.py:195; shrutadhara/recorder.py:299`.

A supervisor killed with SIGKILL releases its lock without reliably terminating its FFmpeg child. Synthetic segmented capture continued from three to five files after parent death.

Capture can continue beyond the visible controller; recovery may inspect archives still being written. The reproduction uses lavfi, not a microphone; actual fallback-session end-to-end capture was not run.

Recommendation: Give the child a verified parent-death lifetime and durable PID/start-identity ownership. Recovery must establish that every owned writer has stopped before validating/exporting archives. Prefer existing systemd cgroup supervision where available, with a tested fallback.

Test: Kill a synthetic fallback parent; require child termination, no new segments and safe recovery. Cover startup races, PID reuse and normal graceful stop.

## RT-05: Storage failures can bypass shutdown

Mapped to F02, Major, Source verified. `shrutadhara/recorder.py:551; shrutadhara/recorder.py:571; shrutadhara/recorder.py:580`.

Metadata reads/writes occur before halt_capture and route cleanup inside finalization. An I/O exception can escape before teardown.

A full/unwritable filesystem can leave recording/routing resources running or unrecovered.

Recommendation: Place child termination, routing restoration and socket closure in independent finally blocks; make failure reporting best-effort after teardown.

Test: Inject ENOSPC, failed fsync/rename and corrupt metadata at each finalization boundary. All cleanup attempts must occur and originals must remain.

## RT-03: Failed unload forgets the owned audio module

Mapped to F03, Major, Reproduced. `shrutadhara/audio.py:142`.

unload pops the module ID, swallows pactl failure and saves the empty ownership journal. A mocked failure reproduced the loss in memory and on disk.

An old loopback can remain active while replacements load and recovery no longer knows it.

Recommendation: Delete ownership only after successful unload or verified absence; retain failed historical IDs separately when replacing a labeled module.

Test: Fail unload, create a replacement, then retry cleanup. Both owned IDs must stay tracked until verified gone; unrelated modules remain untouched.

## RT-07; PR-01: Automatic call transitions are dropped while busy

Mapped to F04, Major, Source verified. `shrutadhara/teams.py:47; shrutadhara/teams.py:76`.

worker returns when another start/stop action is running. A call-end debounce can fire during slow startup and be discarded permanently.

Opt-in automatic recording can continue after a short call ends, or miss the next call during finalization.

Recommendation: Keep latest desired call state and reconcile it after every operation. Preserve owned-session checks and explicit unknown-state behavior. Do not use an unbounded event queue.

Test: Block mocked startup, deliver call end, release startup and require owned-session stop. Also deliver a new call during blocked stop and simulate bus loss.

## RT-01: Suspend detection uses the wrong clock

Mapped to F05, Major, Source + platform contract. `shrutadhara/recorder.py:357; shrutadhara/recorder.py:449; shrutadhara/recorder.py:561; shrutadhara/sessions.py:132`.

Linux monotonic time excludes suspended time, but it drives the suspend-gap detector, epoch offsets and final duration. Display elapsed time uses wall time.

Suspend can be omitted from the promised gap timeline; saved and displayed durations can disagree. FFmpeg offset consequences still need integration measurement.

Recommendation: Define one elapsed session timeline with CLOCK_BOOTTIME and detect suspend from boottime/monotonic delta differences. Keep wall timestamps only as presentation anchors.

Test: Inject independently advancing clocks, verify gap/offset/duration agreement, then run an authorized real suspend acceptance test.

## RT-02: Late Teams instances bypass ambiguity checks

Mapped to F06, Major, Source verified. `shrutadhara/audio.py:50; shrutadhara/audio.py:80; shrutadhara/audio.py:182`.

Starting without Teams playback leaves teams_pid unset; later routing matches every Teams PID without rechecking ambiguity.

Unrelated Teams profiles/calls can be mixed into one recording.

Recommendation: Persist an explicit selection policy; bind an initially unbound recording only to an unambiguous process. Surface ambiguity before moving any newly ambiguous streams.

Test: Empty startup inventory followed by two different Teams PIDs; assert neither is silently routed. Cover explicit selection and process replacement.

## RT-04: Recovery and processing can race on exports

Mapped to F07, Major, Source verified. `shrutadhara/recorder.py:90; shrutadhara/recorder.py:119; shrutadhara/processing.py:736; shrutadhara/audio.py:635`.

Recovery takes a global recording lock while processing takes a different session processing lock. Both can export the same session into identical temporary paths.

Concurrent recovery/preparation can corrupt or replace derivatives during use and leave inconsistent metadata.

Recommendation: Use one shared per-session audio-artifact lock for repair, export and preparation, with a documented lock order.

Test: Synchronize two processes at export creation; one must wait/refuse. Verify final hashes, metadata and retained originals.

## RT-06: A blocked export read has no deadline

Mapped to F08, Major, Source verified. `shrutadhara/audio.py:665; shrutadhara/audio.py:685`.

stdout.read can block before proc.wait(timeout=30) is reached.

Stop/finalization can hold the recording lock indefinitely.

Recommendation: Use selectable streaming reads with an overall deadline and guaranteed child termination; reuse a shared bounded subprocess primitive.

Test: A synthetic child emits a short block and holds stdout open. Require bounded interruption, released locks and preserved archives.

## RT-08: Connected health does not verify the capture route

Mapped to F09, Major, Source verified. `shrutadhara/recorder.py:370; shrutadhara/recorder.py:428; shrutadhara/audio.py:151`.

Private sink and physical-device checks do not validate owned loopback existence/endpoints or same-name device recreation.

The GUI can show a connected microphone while its loopback is absent and the archive contains silence.

Recommendation: Track device/module incarnation and verify route endpoints. Expose physical presence, route health and capture progress separately.

Test: Remove a loopback while keeping devices and sinks unchanged; require warning/gap/repair. Recreate a device with the same name and new identity.

## RT-09: Health remains green when the supervisor snapshot is stale

Mapped to F10, Major, Source verified. `shrutadhara/recorder.py:35; shrutadhara/recorder.py:272; shrutadhara/gui.py:355`.

Status accepts a live PID and merges the last snapshot without recalculating its age; saved progress age freezes when the worker stalls.

A stalled worker can continue to appear healthy.

Recommendation: Compute snapshot age at read time and expose stale/unknown status after a documented threshold. Distinguish process existence from progress.

Test: Advance a fake clock against a frozen snapshot and matching PID; require stale health in CLI and GUI.

