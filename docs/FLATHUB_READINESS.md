# Flathub readiness

Checked against Flathub's published requirements on 2026-11-17. This is project planning documentation, not a submission manifest, PR draft or acceptance claim.

The standalone development Flatpak is not currently eligible for submission as-is.

## Human ownership and AI policy

Flathub's [generative AI policy](https://docs.flathub.org/docs/for-app-authors/requirements#generative-ai-policy) prohibits AI-generated or AI-assisted manifests, as well as agents opening/automating submission PRs or writing their commit messages, descriptions or review interactions. It also requires disclosure of known AI-generated application code, documentation, packaging and other material, identifying the affected parts and approximate extent. Acceptance of disclosed material is at reviewers' discretion.

The existing experimental manifest and substantial application/documentation material were produced with AI assistance. A human maintainer needs to independently author the Flathub manifest, understand and maintain it, supply an accurate disclosure, and personally handle submission and review. Merely reviewing, renaming or relabeling our generated manifest does not remove its provenance. Research and debugging assistance remain allowed under the stated policy.

## Technical work before human submission

- Select a stable tagged release that includes the Flatpak runtime support. The current v0.1.1 release predates these changes; the tested bundle comes from development commit `95f5ac6`. Flathub does not accept new submissions directly into beta or distribute development snapshots.
- Replace the local source archive reference with an immutable public source URL and checksum for that release.
- Build all available-source dependencies from source, including the Rust-backed Python dependency; the development recipe currently downloads precompiled wheels. Supply the required offline build inputs.
- Add real screenshots of the application, hosted at immutable URLs, and accurate release metadata. Do not fabricate meeting content or use screenshots containing private meeting/device information.
- Run Flathub's manifest, repository and AppStream linters. Our standalone AppStream validation is not equivalent to Flathub-specific validation.
- Complete live capture, Stop/finalization and window-lifetime checks, device changes, file-opening/notification behavior and cross-distribution testing. Record evidence of real use and ongoing maintenance; Flathub also evaluates development history.
- Review the recording-only scope against Flathub's functionality and host-dependency rules. Optional native agy features must not be advertised as available in this Flatpak.
- Have the human maintainer justify each permission, review architecture support and handle the submission using the official process.

Official references: [requirements](https://docs.flathub.org/docs/for-app-authors/requirements), [submission](https://docs.flathub.org/docs/for-app-authors/submission), [metadata](https://docs.flathub.org/docs/for-app-authors/metainfo-guidelines).

Until then, distribute explicitly experimental standalone bundles and keep their limitations visible. No Flathub submission PR has been opened.
