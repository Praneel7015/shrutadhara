# Arch/CachyOS package preparation

The v0.1.1 native package and AUR recipe are available as GitHub release assets. AUR submission is pending: new account registration is temporarily closed. Do not automate registration retries or request a bypass; use `sudo pacman -U ./shrutadhara-0.1.1-1-any.pkg.tar.zst` with the checksum-verified released package meanwhile. `yay -S shrutadhara` will work only after a maintained AUR entry is actually published.

This is release packaging tooling, not an AUR publication or an availability claim. The experimental application is `shrutadhara`; the executable is `shruta`. Build a package only after reviewing the source and the capture/AI limitations in VALIDATION.md. agy is optional, externally installed and authenticated; recording/export do not require it. No fake package dependency or silent provider fallback is introduced.

The release owner must first build the final Python source archive named `shrutadhara-0.1.1.tar.gz`, with root `shrutadhara-0.1.1/`, and upload those exact bytes as the GitHub `v0.1.1` release asset when publication is authorized. Generate Arch metadata *after* the source is final:

```sh
python packaging/arch/prepare.py /absolute/path/to/shrutadhara-0.1.1.tar.gz --output /tmp/shrutadhara-aur
cd /tmp/shrutadhara-aur
makepkg --verifysource
makepkg --cleanbuild --check
```

The generator performs no network calls. It validates the archive layout/required assets, computes its real SHA256, renders PKGBUILD and asks local `makepkg --printsrcinfo` to produce `.SRCINFO`. It copies the archive beside the PKGBUILD so checksum verification/build can use local bytes before the release URL exists. There is no `SKIP`, floating Git source, automatic installation or enabled service. Do not run `makepkg -i` unless you explicitly intend to install the package. Missing build dependencies must be installed separately by the user; the tooling does not elevate privileges.

For release verification, use Arch `devtools` and `extra-x86_64-build` from the generated directory in a clean chroot. A host build is not equivalent. Run `namcap` on PKGBUILD and the resulting package if available. Inspect the resulting archive for `/usr/bin/shruta`, the desktop entry, Python modules, license and notice. Test CLI/import/desktop launch from the installed package on a disposable supported system. GTK/device/Wayland acceptance still requires the documented manual checks; mocked tests do not exercise live capture. The package's `check()` runs only the offline isolated tests.

The runtime intentionally declares distribution Python/PyGObject, GTK4, FFmpeg, libpulse tools, PipeWire Pulse compatibility and WirePlumber. This first package targets the tested PipeWire desktop stack rather than claiming support for arbitrary PulseAudio setups. Python build/installer/setuptools/wheel are build dependencies; pytest is a check dependency. Desktop notification/open tools are optional. The optional call-monitor service is documentation, never automatically installed/enabled as a user unit. The wheel installs its desktop entry through standard packaging; `shruta install-desktop` is unnecessary for this package-manager installation and must not overwrite a different launcher.

For a proposed AUR submission, review and commit only `PKGBUILD` and `.SRCINFO` into the separately authorized AUR repository; do not commit the source tarball, build directories or package binary. Verify the public release URL resolves to the same checksum before submission. AUR naming availability, maintainer identity/account and submission remain owner responsibilities. If release bytes change, regenerate metadata and increment the release appropriately; never preserve a stale checksum or publish different bytes under an existing release without explicit versioning review.

Reference: [Arch Python package guidelines](https://wiki.archlinux.org/title/Python_package_guidelines), [AUR submission guidelines](https://wiki.archlinux.org/title/AUR_submission_guidelines). The live Wiki returned access denial during this implementation; local makepkg is the authoritative metadata validator used here.
