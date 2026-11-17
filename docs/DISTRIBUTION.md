# Distribution and release plan

Shrutadhara is experimental. Local recording is useful independently of optional AI; reliable agy transcription remains unvalidated. Package installation never starts recording, enables a service, changes user consent, or uploads data.

## Install released artifacts

Use assets from https://github.com/Praneel7015/shrutadhara/releases only after reviewing the release and its source. Download SHA256SUMS and the chosen asset, then run `sha256sum --check --ignore-missing SHA256SUMS`. Matching hashes detect changed/download-corrupted assets; hashes from the same release are not an independent signature. GitHub account/release trust remains necessary.

Arch/CachyOS: download the `.pkg.tar.zst`, then `sudo pacman -U ./shrutadhara-*.pkg.tar.zst`. Dependencies are handled by pacman. Once an AUR entry is submitted, `yay -S shrutadhara` and `paru -S shrutadhara` build the same project; these commands are not available merely because this source or a GitHub release exists. AUR submission steps are in [ARCH_PACKAGING.md](ARCH_PACKAGING.md).

Debian 13 / Ubuntu 24.04 or newer: download the `.deb`, then `sudo apt install ./shrutadhara_*-1_all.deb`. It requires Python >=3.11, GTK >=4.10, distribution jsonschema >=4.10, FFmpeg, Pulse compatibility utilities, PipeWire Pulse and WirePlumber. Older distributions may fail dependency resolution and are unsupported by this native package. The Ubuntu CI checks actual install/import/help/removal; the independently maintained [signed APT repository](APT_REPOSITORY.md) also provides updates. This is separate from Debian/Ubuntu official archive admission. Review APT's dependency transaction on a customized audio stack.

npm: version 0.1.1 is published. Use `npm install --global shrutadhara@experimental --ignore-scripts`. Install system dependencies first, then run `shruta setup-native` explicitly. The matching application wheel is bundled and checked; pip may fetch Python dependency wheels. See [npm README](../npm/README.md). Never install two competing `shruta` launchers into the same PATH location. Prefer the native package on Arch/Debian.

Run `shruta doctor`, then `shruta show`. Do not interpret a successful installation as transcription capability validation. Test live capture using [TEST_DRIVE.md](TEST_DRIVE.md).

## Maintainer release sequence

1. Update Python and npm versions together. Keep release filenames synchronized; the latest published release is 0.1.1, experimental. Run tests, Ruff and package checks. Do not ship meetings, fixtures, configuration, credentials or generated notes.
2. Push reviewed source. The Distribution packages workflow builds source/wheel, an npm tarball containing that exact wheel, and a reproducible architecture-independent `.deb`. A disposable Arch runner generates PKGBUILD/.SRCINFO from the exact source hash, runs makepkg tests, and installs/removes the resulting package. A disposable Ubuntu24.04 runner installs/removes the `.deb`. Neither workflow records or calls AI.
3. Only after those checks pass, tag that commit `vVERSION` and push the tag. Experimental release workflow repeats the package checks, verifies tag/source/npm versions, generates SHA256SUMS for all assets, and publishes a GitHub **prerelease**. It fails rather than replacing an existing release. Do not move published tags or replace package bytes under an existing version. There is no automatic npm or AUR publication.
4. Initial npm publication needs the package owner's npm account and interactive authentication: download and verify the exact release tarball; `npm login`; `npm publish ./shrutadhara-VERSION.tgz --access public --tag experimental --ignore-scripts`. npm may require 2FA. Never send tokens/passwords through chat. The package name must still be available when published.
5. After package creation configure npm trusted publishing for GitHub owner `Praneel7015`, repository `shrutadhara`, workflow `npm-publish.yml`, allowing direct publish. Then manually dispatch Publish npm experimental package with the validated release tag. It downloads the existing tarball, verifies its release checksum and publishes using OIDC/provenance, without a stored npm token. Never dispatch for a version already published. See https://docs.npmjs.com/trusted-publishers/.
6. Review and submit the generated AUR recipe using the maintainer's AUR account/SSH key. Use a separate AUR git checkout, not this application's `.git`. Only PKGBUILD/.SRCINFO belong in that submission; do not commit build products. Keep checksums pinned. See https://wiki.archlinux.org/title/AUR_submission_guidelines.
7. Once usage and reliability justify it, request CachyOS repository inclusion through its GitHub/forum process: https://wiki.cachyos.org/cachyos_basic/faq/#submitting-package-requests-to-cachyos. `pacman -S shrutadhara` requires a configured repository containing the package. A signed custom pacman repository is a separate optional deployment.
8. The [signed APT repository](APT_REPOSITORY.md) is deployed through GitHub Pages using an independently maintained signing key. No repository/key is automatically added by this application. Official Debian/Ubuntu inclusion requires their review; a PPA is Ubuntu-specific.
9. The [experimental Flatpak](FLATPAK.md) workflow builds a recording/local-preparation-only bundle for x86_64. It is not listed on Flathub. Review its manual acceptance checklist before recommending it for daily use. AUR account registration is temporarily closed; use the released native Arch package meanwhile.

The PyPI upload guard stays enabled: this phase distributes Python assets through GitHub, not PyPI. Native packages avoid npm/Node entirely. Optional agy remains separately installed and configured; no replacement speech engine is bundled.

## Local builds

```bash
uv build --out-dir /tmp/shrutadhara-dist
python tools/prepare_npm.py /tmp/shrutadhara-dist/*.whl /tmp/shrutadhara-npm-stage
npm pack --ignore-scripts --pack-destination /tmp/shrutadhara-dist /tmp/shrutadhara-npm-stage
SOURCE_DATE_EPOCH=$(git log -1 --format=%ct) python tools/build_deb.py /tmp/shrutadhara-dist/*.whl --output /tmp/shrutadhara-dist
python tools/check_release.py /tmp/shrutadhara-dist
```

Use new staging directories. The `.deb` builder uses Debian's documented ar format without executing the application or requiring root/dpkg on the build host. CI uses real dpkg/APT to validate it. No maintainer scripts or audio-service units are installed. Existing recordings and configuration are outside package-owned paths and retained on removal.

## Upgrade and removal

Stop recording and processing before changing the installation. Keep only one intended `shruta` executable first in PATH (`command -v shruta`). No removal command below deletes meetings or configuration.

| Channel | Upgrade | Remove application |
|---|---|---|
| Source checkout | Pull reviewed source, rerun `bash install.sh`; rebuild the venv after a Python ABI upgrade | Remove only the managed `~/.local/bin/shruta` and user desktop entry; then remove the checkout/venv if desired |
| Arch/AUR | Install the reviewed newer package with pacman/AUR helper | `sudo pacman -R shrutadhara` |
| Debian/Ubuntu | `sudo apt install ./shrutadhara_VERSION-1_all.deb` | `sudo apt remove shrutadhara` |
| npm | Upgrade the wrapper, then explicitly `shruta setup-native` for its bundled matching wheel | `npm uninstall --global shrutadhara`; remove only the managed npm-runtime separately after stopping work |

Native packages own `/usr/bin/shruta` and their system desktop entry; never delete these manually or add a shadow launcher to work around a user-service template. If you explicitly ran `install-desktop`, inspect its managed user files separately. A source or npm user launcher can shadow a native installation after migration; resolve that PATH ownership explicitly.

For the optional user call-monitor unit, copy the source template and review `ExecStart` before enabling: source default `%h/.local/bin/shruta`, native `/usr/bin/shruta`, npm the absolute wrapper path from `command -v shruta`. For uninstall, first `systemctl --user disable --now shrutadhara-call-monitor.service`, remove only the unit you installed and run `systemctl --user daemon-reload`. Do not remove unrelated user services.

Version0.1.1 is being prepared as a reliability patch. The published v0.1.0 tag remains unchanged. Its first release used separately verified tag artifacts after an artifact-directory aggregation error; the flattening fix is on main. A new tag/release is a separate publication step.

## Cross-distribution coverage

| Route | Availability | Scope |
|---|---|---|
| Arch/CachyOS native package | Published GitHub release | Native recording and optional configured agy |
| AUR / yay / paru | Submission blocked by account registration closure | Prepared recipe; no AUR listing yet |
| Debian/Ubuntu APT | Signed experimental repository | amd64 Debian 13 / Ubuntu 24.04 or newer |
| npm | Published experimental package | Linux launcher; system Python/GTK/audio tools required |
| Flatpak | Development build workflow | x86_64 recording/local preparation; shared GNOME runtime |
| Source/wheel | Published GitHub release | Linux with supported native dependencies |
| RPM / AppImage / Nix | Not implemented | Candidates after Flatpak acceptance and maintainer testing |

Flatpak is the first route intended to span distributions without rebuilding native packages. Its runtime must still work with the desktop's audio and display services. Package format portability does not establish audio compatibility on every distribution. It is not a Windows/macOS package. Fedora/openSUSE can eventually use the validated Flatpak rather than requiring an RPM immediately. A Flathub listing and official distro repository admission each require separate review.
