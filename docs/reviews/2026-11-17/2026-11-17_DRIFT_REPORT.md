# Document/code differences — 2026-11-17

Baseline `b3af550669b41ca3d2364099f2c245970bb17e42`. Applied skill: installed Google EGM `egm-drift-report`. This file lists differences, not matching behavior. Findings are expanded in [the consolidated review](consolidated_review_report.md). Historical proposals and explicitly disclosed experimental limitations are not treated as implemented promises.

## README.md

- Unsupported native audio is documented as stopping processing, but ordinary validation errors allow later chunks to be submitted (F11).
- A ten-minute deadline is described without saying each of three attempts receives that allowance (F22).
- Suspend is described as an explicit gap, but its detector uses a Linux clock that excludes suspended time (F05).
- Multiple Teams processes require selection at startup, but later streams can evade that rule when startup had no bound PID (F06).
- Authoritative status does not account for the age of the saved supervisor snapshot (F10).
- Source GUI requirements say GTK4 without the4.10 minimum needed by confirmation dialogs (F18).
- Optional service and Hyprland examples assume a user-local executable even when native packages install the system executable (F20).

## SECURITY.md

- The broad established-integrity-baseline policy covers cached artifacts in prose, but accepted model-output caches have input fingerprints without an independent output baseline (F16). Audio baselines and model-output baselines must be described separately until both are implemented.

## OPEN_SOURCE_PLAN.md

- Pinned wrapper/runtime compatibility and dual-version diagnostics are planned, but normal npm launches do not verify the installed native version (F17). This remains an unimplemented plan item, not a claim that the historical plan is current implementation documentation.

## VALIDATION.md

- The distribution section retains the earlier host Arch `--nodeps` evidence and describes installation workflows without their subsequently verified successful run reference. Actual Ubuntu/Arch install/import/help/remove checks succeeded in run43935549226. Record that evidence while keeping desktop activation, upgrades, live capture and two-hour acceptance separate.
- The default125-test result does not include the two Arch preparation cases. State explicit-suite results until collection is fixed (F21).

## CONTRIBUTING.md

- The required dependency/check instructions omit the GUI GTK4.10 minimum and do not collect Arch metadata tests through the default command (F18/F21).
- The broad mocked/offline CI description should distinguish synthetic runtime tests from package-install jobs that use disposable runner system package managers. Neither performs hosted AI or live audio acceptance.

## docs/ARCH_PACKAGING.md

- No new document/code drift detected. Full native install smoke evidence exists separately; clean-chroot reproducibility, desktop and live-device acceptance remain distinct tests.

## docs/DISTRIBUTION.md

- Its tag-driven release procedure is the intended workflow, but the first tag's publication step failed on nested Arch artifact paths. The validated first release was published separately without changing its tag/assets. The flattening correction is in the reviewed main baseline; record this first-release exception instead of implying that tag publication succeeded automatically.

## docs/RELEASE_NOTES.md

- No new drift detected. Experimental capture/AI limitations and separate registry/repository publication remain explicitly stated.

## docs/TEST_DRIVE.md

- No new drift detected. Instructions are manual acceptance steps, not evidence those steps have already passed.

## npm/README.md

- Setup-time matching wheel validation is implemented, but the shared native runtime can later diverge from an upgraded wrapper (F17). Add upgrade/version-mismatch instructions alongside the launch guard.

## ASTRA_REVIEW.md

- No new drift detected. This is historical review evidence; its fixed earlier defects are not reclassified as currently unresolved.

## CHANGELOG.md

- No new drift detected. Packaging changes are present; experimental status does not establish registry or distribution-repository inclusion.

## .github/PULL_REQUEST_TEMPLATE.md

- No drift detected in its contributor requirements. The no-coauthor and no-sensitive-data instructions continue to apply.
