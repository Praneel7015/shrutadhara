#!/usr/bin/env bash
# Real signed-APT install test for a disposable Ubuntu/Debian runner only.
set -euo pipefail
if [[ "${SHRUTA_DISPOSABLE_APT_TEST:-}" != 1 ]]; then
    echo 'Run only in a disposable Debian/Ubuntu runner with SHRUTA_DISPOSABLE_APT_TEST=1.' >&2
    exit 2
fi
repo_code="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
release_deb="$(realpath -- "$1")"
apt_test_root="$(mktemp -d /tmp/shruta-apt-ci.XXXXXX)"
chmod 755 "$apt_test_root"
key_home="$apt_test_root/gnupg"
mkdir -m 700 "$key_home"
gpg --homedir "$key_home" --batch --pinentry-mode loopback --passphrase '' --quick-generate-key 'Shrutadhara disposable APT integration' ed25519 sign 1d
fingerprint="$(gpg --homedir "$key_home" --with-colons --list-secret-keys | awk -F: '$1=="fpr" {print $10; exit}')"
python3 - "$release_deb" "$apt_test_root/SHA256SUMS" <<'PY'
import hashlib,sys
from pathlib import Path
p=Path(sys.argv[1]);Path(sys.argv[2]).write_text(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n')
PY
python3 "$repo_code/tools/build_apt_repository.py" "$release_deb" --checksums "$apt_test_root/SHA256SUMS" --output "$apt_test_root/site/apt" --gpg-home "$key_home" --fingerprint "$fingerprint"
keyring="/usr/share/keyrings/shrutadhara-ci-$$.gpg"
source_file="/etc/apt/sources.list.d/shrutadhara-ci-$$.list"
server_pid=''
cleanup() {
    if [[ -n "$server_pid" ]]; then kill "$server_pid" 2>/dev/null || true; fi
    sudo rm -f -- "$source_file" "$keyring"
    gpgconf --homedir "$key_home" --kill gpg-agent || true
}
trap cleanup EXIT
sudo install -m 644 "$apt_test_root/site/apt/shrutadhara-archive-keyring.gpg" "$keyring"
python3 -m http.server 18765 --bind 127.0.0.1 --directory "$apt_test_root/site" > "$apt_test_root/http.log" 2>&1 &
server_pid=$!
python3 - <<'PY'
import time,urllib.request
for attempt in range(50):
 try:
  with urllib.request.urlopen('http://127.0.0.1:18765/apt/dists/experimental/InRelease',timeout=1):break
 except OSError:
  if attempt==49:raise
  time.sleep(.1)
PY
printf 'deb [arch=amd64 signed-by=%s] http://127.0.0.1:18765/apt experimental main\n' "$keyring" | sudo tee "$source_file" > /dev/null
sudo apt-get update
apt-cache policy shrutadhara
apt-cache policy shrutadhara | grep -F 'http://127.0.0.1:18765/apt'
sudo rm -f /var/cache/apt/archives/shrutadhara_*.deb
sudo apt-get install -y shrutadhara
/usr/bin/shruta --version
/usr/bin/shruta --help > /dev/null
grep -F 'GET /apt/pool/main/s/shrutadhara/' "$apt_test_root/http.log"
sudo apt-get remove -y shrutadhara
test ! -e /usr/bin/shruta
echo 'Signed repository update, package fetch, installation and removal passed.'
