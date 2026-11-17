# Signed APT repository

Shrutadhara's independently maintained experimental APT repository is hosted at:

`https://praneel7015.github.io/shrutadhara/apt/`

This is separate from Debian/Ubuntu's official archives. Initial support is Debian13/Ubuntu24.04 or newer on amd64, using the published architecture-independent package. Installation pulls distribution Python/GTK≥4.10, FFmpeg and the PipeWire/Pulse compatibility stack. Review the package manager transaction if your desktop audio stack is customized. Recognition accuracy and live-device/long-meeting acceptance remain experimental.

## Install

Download the public key and verify its complete fingerprint:

```bash
curl -fsSL https://praneel7015.github.io/shrutadhara/apt/shrutadhara-archive-keyring.gpg -o /tmp/shrutadhara-archive-keyring.gpg
gpg --show-keys --with-fingerprint /tmp/shrutadhara-archive-keyring.gpg
```

Expected fingerprint:

```text
030DFDDC2CC010060580D9C6744FE7EF7F6C41CC
```

It is also recorded in `packaging/apt/KEY_FINGERPRINT` alongside the public key in the source repository. Matching a fingerprint from a separately reviewed source matters; a key downloaded from the repository itself is not an independent trust anchor.

```bash
sudo install -m 644 /tmp/shrutadhara-archive-keyring.gpg /usr/share/keyrings/shrutadhara-archive-keyring.gpg
echo 'deb [arch=amd64 signed-by=/usr/share/keyrings/shrutadhara-archive-keyring.gpg] https://praneel7015.github.io/shrutadhara/apt experimental main' | sudo tee /etc/apt/sources.list.d/shrutadhara.list
sudo apt update
sudo apt install shrutadhara
shruta doctor
shruta show
```

The key is scoped to this source with `signed-by`; no `apt-key` or globally trusted key installation is used. The repository indexes only Shrutadhara. `NotAutomatic` avoids treating experimental packages as normal distribution candidates, while `ButAutomaticUpgrades` permits updates once explicitly installed. No recording, app service, consent or hosted upload is enabled by package installation.

To remove the application, use `sudo apt remove shrutadhara`. Recordings/configuration are retained. To remove this repository, remove only `/etc/apt/sources.list.d/shrutadhara.list` and `/usr/share/keyrings/shrutadhara-archive-keyring.gpg`, then run `sudo apt update`.

## Maintainer publishing

The `Publish signed APT repository` workflow downloads one existing released `.deb` and SHA256SUMS, verifies exact package bytes, generates indexes and signed Release/InRelease metadata, and deploys the public site through GitHub Pages. It does not rebuild or replace published package bytes. Signing keys are never part of the site or source archive.

The workflow uses the dedicated `APT_SIGNING_KEY` GitHub Actions secret and `APT_SIGNING_FINGERPRINT` variable. The public fingerprint must also match the checked-in value. Private signing material is imported into a temporary GnuPG home and removed before artifact upload. GitHub Pages must be configured to deploy through Actions.

Run manually with:

```bash
gh workflow run apt-publish.yml --repo Praneel7015/shrutadhara --ref main --field tag=v0.1.1
```

Later releases explicitly dispatch this workflow, because events generated using GITHUB_TOKEN do not generally trigger other workflows. A weekly refresh selects the newest published release and renews the signed metadata. Metadata expires after30days; if schedules are disabled or fail, repair the workflow and refresh it rather than disabling APT signature/expiry checks.

The dedicated private GnuPG home is kept outside the checkout under `~/.local/share/shrutadhara-publish/gnupg` on the maintainer workstation. Back it up privately; do not commit it or reuse an unrelated personal signing key. The signing key expires after two years. Renew/re-export its public key and update the Actions secret before expiry; clients may need the renewed public key. A different signing fingerprint requires an explicit trust/rotation announcement and client keyring update.

## Validation

Unit tests verify package identity, release checksums, index hashes, signing, independent gpgv verification and signature rejection after metadata tampering. Real APT tests use disposable Ubuntu runners: signed HTTP repository update, package fetch, installation, help/version and removal. `tools/test_apt_repository.sh` refuses to run unless explicitly marked as a disposable test. It must never be run against a user's ordinary workstation as a diagnostics command.

No APT source or trusted key is added to the CachyOS development workstation.
