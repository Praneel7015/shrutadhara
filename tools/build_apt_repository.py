"""Build a signed single-package APT archive from verified release .deb bytes.

No installation or system configuration occurs here. The caller owns an isolated
GnuPG home and supplies its exact signing fingerprint. Use the experimental
channel until live capture and recognition acceptance justify broader claims.
"""

import argparse
import gzip
import hashlib
import io
import os
import re
import shutil
import subprocess
import tarfile
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path, PurePosixPath

SUITE = 'experimental'


def control_from_deb(path):
    data = path.read_bytes()
    if not data.startswith(b'!<arch>\n'):
        raise ValueError('Expected Debian ar archive')
    offset, control = 8, None
    while offset < len(data):
        header = data[offset:offset + 60]
        if len(header) != 60 or header[58:60] != b'`\n':
            raise ValueError('Invalid Debian ar member')
        size = int(header[48:58])
        if size < 0 or offset + 60 + size > len(data):
            raise ValueError('Invalid Debian member size')
        name = header[:16].decode('ascii').strip().rstrip('/')
        body = data[offset + 60:offset + 60 + size]
        if name.startswith('control.tar'):
            if control is not None:
                raise ValueError('Duplicate Debian control archive')
            with tarfile.open(fileobj=io.BytesIO(body)) as archive:
                entries = [m for m in archive.getmembers() if m.name in {'control', './control'}]
                if len(entries) != 1 or not entries[0].isfile():
                    raise ValueError('Expected regular Debian control file')
                control = archive.extractfile(entries[0]).read().decode('utf-8')
        offset += 60 + size + size % 2
    if control is None:
        raise ValueError('Missing Debian control archive')
    fields = {}
    for line in control.splitlines():
        if not line or line[0].isspace():
            continue
        key, separator, value = line.partition(':')
        if not separator or key in fields:
            raise ValueError('Invalid or duplicate Debian control field')
        fields[key] = value.strip()
    if fields.get('Package') != 'shrutadhara' or fields.get('Architecture') != 'all':
        raise ValueError('Only architecture-independent Shrutadhara packages are accepted')
    if not re.fullmatch(r'\d+\.\d+\.\d+-\d+', fields.get('Version', '')):
        raise ValueError('Unsupported package version')
    if any(key in fields for key in ['Filename', 'Size', 'SHA256', 'SHA512', 'MD5sum']):
        raise ValueError('Control file cannot override repository index fields')
    return control.rstrip() + '\n', fields


def verify_release_checksum(deb, checksums):
    matches = []
    for line in checksums.read_text().splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1] == deb.name:
            matches.append(parts[0])
    if len(matches) != 1 or hashlib.sha256(deb.read_bytes()).hexdigest() != matches[0]:
        raise ValueError('Release package checksum mismatch')


def gpg(args, home, *, data=None):
    result = subprocess.run(['gpg', '--homedir', str(home), '--batch', '--yes', *args],
                            input=data, capture_output=True, timeout=60)
    if result.returncode:
        raise ValueError('GnuPG operation failed; repository was not approved for publication')
    return result.stdout


def sign_and_export(root, home, fingerprint):
    if not re.fullmatch(r'[A-Fa-f0-9]{40}', fingerprint):
        raise ValueError('Supply the full 40-character signing fingerprint')
    public = gpg(['--export', fingerprint], home)
    if not public:
        raise ValueError('Signing public key is unavailable')
    (root / 'shrutadhara-archive-keyring.gpg').write_bytes(public)
    (root / 'shrutadhara-archive-keyring.asc').write_bytes(gpg(['--armor', '--export', fingerprint], home))
    (root / 'FINGERPRINT').write_text(fingerprint.upper() + '\n')
    release = root / 'dists' / SUITE / 'Release'
    options = ['--pinentry-mode', 'loopback', '--passphrase', '', '--local-user', fingerprint, '--digest-algo', 'SHA256']
    gpg([*options, '--armor', '--output', str(release.with_name('InRelease')), '--clearsign', str(release)], home)
    gpg([*options, '--armor', '--output', str(release.with_name('Release.gpg')), '--detach-sign', str(release)], home)
    gpg(['--verify', str(release.with_name('InRelease'))], home)
    gpg(['--verify', str(release.with_name('Release.gpg')), str(release)], home)


def build(deb, output, timestamp, *, checksum_file, gpg_home, fingerprint):
    verify_release_checksum(deb, checksum_file)
    control, fields = control_from_deb(deb)
    if deb.name != f"shrutadhara_{fields['Version']}_all.deb":
        raise ValueError('Package filename and control version disagree')
    if output.exists() and any(output.iterdir()):
        raise ValueError('Use an empty output directory; publication must replace a complete archive')
    output.mkdir(parents=True, exist_ok=True)
    relative = PurePosixPath('pool/main/s/shrutadhara') / deb.name
    if Path(deb.name).name != deb.name or not re.fullmatch(r'shrutadhara_\d+\.\d+\.\d+-\d+_all\.deb', deb.name):
        raise ValueError('Unexpected release package filename')
    target = output / str(relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(deb, target)
    raw = target.read_bytes()
    index = (control + f'Filename: {relative}\nSize: {len(raw)}\n'
             f'SHA256: {hashlib.sha256(raw).hexdigest()}\nSHA512: {hashlib.sha512(raw).hexdigest()}\n\n').encode()
    suite = output / 'dists' / SUITE
    binary = suite / 'main/binary-amd64'
    binary.mkdir(parents=True)
    (binary / 'Packages').write_bytes(index)
    (binary / 'Packages.gz').write_bytes(gzip.compress(index, mtime=int(timestamp.timestamp())))
    release = (
        'Origin: Shrutadhara\nLabel: Shrutadhara experimental\n'
        f'Suite: {SUITE}\nCodename: {SUITE}\n'
        f'Date: {format_datetime(timestamp)}\n'
        f'Valid-Until: {format_datetime(timestamp + timedelta(days=30))}\n'
        'Architectures: amd64\nComponents: main\n'
        'Description: Experimental local-first meeting assistant\n'
        'NotAutomatic: yes\nButAutomaticUpgrades: yes\nSHA256:\n'
    )
    for path in sorted(binary.iterdir()):
        payload = path.read_bytes()
        release += f' {hashlib.sha256(payload).hexdigest()} {len(payload)} {path.relative_to(suite).as_posix()}\n'
    (suite / 'Release').write_text(release)
    sign_and_export(output, gpg_home, fingerprint)
    (output / 'PACKAGE_VERSION').write_text(fields['Version'] + '\n')
    template = Path(__file__).resolve().parents[1] / 'packaging/apt/index.html.in'
    if template.exists():
        page = template.read_text().replace('@FINGERPRINT@', fingerprint.upper()).replace('@VERSION@', fields['Version'])
        (output / 'index.html').write_text(page)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('deb', type=Path)
    parser.add_argument('--checksums', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--gpg-home', required=True, type=Path)
    parser.add_argument('--fingerprint', required=True)
    args = parser.parse_args()
    timestamp = datetime.fromtimestamp(int(os.environ.get('SOURCE_DATE_EPOCH', datetime.now(timezone.utc).timestamp())), timezone.utc)
    try:
        print(build(args.deb, args.output, timestamp, checksum_file=args.checksums, gpg_home=args.gpg_home, fingerprint=args.fingerprint))
    except (ValueError, OSError, tarfile.TarError, subprocess.SubprocessError) as exc:
        parser.exit(1, f'APT archive build failed: {exc}\n')


if __name__ == '__main__':
    main()
