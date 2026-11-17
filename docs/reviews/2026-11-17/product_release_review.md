# product release review

Completed fresh-context reviewer. Findings normalized by the Elephant; original IDs preserved. Full qualifications, disagreements and evidence are in the consolidated report.

## RT-07; PR-01: Automatic call transitions are dropped while busy

Mapped to F04, Major, Source verified. `shrutadhara/teams.py:47; shrutadhara/teams.py:76`.

worker returns when another start/stop action is running. A call-end debounce can fire during slow startup and be discarded permanently.

Opt-in automatic recording can continue after a short call ends, or miss the next call during finalization.

Recommendation: Keep latest desired call state and reconcile it after every operation. Preserve owned-session checks and explicit unknown-state behavior. Do not use an unbounded event queue.

Test: Block mocked startup, deliver call end, release startup and require owned-session stop. Also deliver a new call during blocked stop and simulate bus loss.

## PR-03: npm wrapper upgrades silently run the old runtime

Mapped to F17, Major, Source verified; future-version trigger. `npm/launcher.js:40; npm/launcher.js:55`.

Version matching occurs during setup only; ordinary launch uses any existing shared npm-runtime.

A future wrapper B can launch native A without an actionable compatibility warning. Only version0.1.0 is currently declared; no real upgrade was executed.

Recommendation: Persist/check native version and runtime installation identity before launch; require explicit setup on mismatch. Define the override executable compatibility policy too.

Test: Newer staged wrapper plus older synthetic native runtime: recording commands must fail with explicit setup guidance. Same-version reinstall remains valid.

## PR-04: Source GUI installation lacks its GTK minimum guard

Mapped to F18, Major, Source + upstream API contract. `README.md:29; shrutadhara/gui.py:49; shrutadhara/gui.py:225; shrutadhara/cli.py:339`.

Native packages require GTK>=4.10, but source/wheel startup and doctor accept any GTK4. AlertDialog exists only since4.10.

GTK4.8 source installations fail at required confirmation instead of reporting an actionable dependency error.

Recommendation: Check GTK>=4.10 before window construction and state it consistently in source installation/contributor docs.

Test: Mock4.8: dependency exit3 before constructing window; accept4.10. Native dependency metadata remains versioned.

## PR-02: Folder stays disabled after the first GUI session

Mapped to F19, Nit, Source verified. `shrutadhara/gui.py:406; shrutadhara/gui.py:414`.

Empty history disables all output buttons; subsequent state updates restore notes/transcript only.

A first-session user cannot open its folder without reopening the application.

Recommendation: Set every output button sensitivity from current state on every update.

Test: Empty→recording→recorded without recreating the window; Folder becomes enabled.

## PR-05: Service and shortcut examples assume a source launcher

Mapped to F20, Nit, Source verified. `desktop/shrutadhara-call-monitor.service:8; README.md:232; README.md:242`.

Examples use ~/.local/bin/shruta, whereas native packages install /usr/bin/shruta.

Following these examples after native installation can produce a failed service or inactive shortcut.

Recommendation: Document channel-specific executable paths or generate an explicitly installed unit from a resolved owned executable. Avoid shadow launchers.

Test: Check source/native/npm unit and shortcut commands, including paths containing spaces.

## PR-06: Arch metadata regression tests are omitted from normal CI

Mapped to F21, Major, Collection verified. `pyproject.toml:30; packaging/arch/test_prepare.py; .github/workflows/offline.yml:17; .github/workflows/packages.yml:21`.

Default testpaths contains tests only. The two Arch generator tests ran only when explicitly named.

Traversal and source-pinning regressions can pass ordinary CI.

Recommendation: Move the suite under tests or include its path explicitly in every required test job. Prefer one collection convention.

Test: pytest --collect-only must include both Arch metadata cases; unsafe archive fixtures must still be rejected.

