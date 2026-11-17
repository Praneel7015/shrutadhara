"""Archive checks use synthetic packages and disposable signing keys."""

import hashlib
import importlib.util
import io
import shutil
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def tool(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tools' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


apt = tool('build_apt_repository')
deb_builder = tool('build_deb')


@pytest.fixture
def package(tmp_path):
    def make(control_extra='', symlink=False):
        control = ('Package: shrutadhara\nVersion: 0.1.1-1\nArchitecture: all\n'
                   'Depends: python3 (>= 3.11)\nDescription: Synthetic test only\n' + control_extra).encode()
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode='w:gz') as archive:
            entry = tarfile.TarInfo('./control')
            if symlink:
                entry.type, entry.linkname = tarfile.SYMTYPE, '/outside'
                archive.addfile(entry)
            else:
                entry.size = len(control)
                archive.addfile(entry, io.BytesIO(control))
        data = b'!<arch>\n' + deb_builder.ar_member('debian-binary', b'2.0\n', 0) + deb_builder.ar_member('control.tar.gz', buffer.getvalue(), 0)
        path = tmp_path / 'shrutadhara_0.1.1-1_all.deb'
        path.write_bytes(data)
        sums = tmp_path / 'SHA256SUMS'
        sums.write_text(hashlib.sha256(data).hexdigest() + '  ' + path.name + '\n')
        return path, sums
    return make


@pytest.fixture(scope='module')
def signing_key(tmp_path_factory):
    if not shutil.which('gpg') or not shutil.which('gpgv'):
        pytest.skip('GnuPG tools unavailable')
    root = tmp_path_factory.mktemp('apt-gnupg')
    root.chmod(0o700)
    subprocess.run(['gpg', '--homedir', str(root), '--batch', '--pinentry-mode', 'loopback', '--passphrase', '', '--quick-generate-key', 'Shruta disposable archive test', 'ed25519', 'sign', '1d'], capture_output=True, check=True, timeout=30)
    result = subprocess.run(['gpg', '--homedir', str(root), '--with-colons', '--list-secret-keys'], capture_output=True, text=True, check=True)
    fingerprint = next(line.split(':')[9] for line in result.stdout.splitlines() if line.startswith('fpr:'))
    yield root, fingerprint
    subprocess.run(['gpgconf', '--homedir', str(root), '--kill', 'gpg-agent'], capture_output=True, timeout=10)


def test_signed_archive_hashes_dependencies_and_independent_verification(package, signing_key, tmp_path):
    deb, sums = package()
    home, fingerprint = signing_key
    root = apt.build(deb, tmp_path / 'repo', datetime.now(timezone.utc), checksum_file=sums, gpg_home=home, fingerprint=fingerprint)
    index = root / 'dists/experimental/main/binary-amd64/Packages'
    text = index.read_text()
    assert 'Depends: python3 (>= 3.11)' in text
    assert f'SHA256: {hashlib.sha256(deb.read_bytes()).hexdigest()}' in text
    assert 'Filename: pool/main/s/shrutadhara/' + deb.name in text
    release = (root / 'dists/experimental/Release').read_text()
    assert f'{hashlib.sha256(index.read_bytes()).hexdigest()} {index.stat().st_size} main/binary-amd64/Packages' in release
    assert 'Valid-Until:' in release and 'NotAutomatic: yes' in release
    public = root / 'shrutadhara-archive-keyring.gpg'
    signed = root / 'dists/experimental/InRelease'
    subprocess.run(['gpgv', '--keyring', str(public), str(signed)], capture_output=True, check=True)
    signed.write_bytes(signed.read_bytes().replace(b'Origin: Shrutadhara', b'Origin: Tampered'))
    assert subprocess.run(['gpgv', '--keyring', str(public), str(signed)], capture_output=True).returncode != 0
    assert (root / 'shrutadhara-archive-keyring.asc').read_text().startswith('-----BEGIN PGP PUBLIC KEY BLOCK-----')
    assert not list(root.rglob('*private*'))


def test_changed_release_package_refused_before_signing(package, tmp_path, monkeypatch):
    deb, sums = package()
    deb.write_bytes(deb.read_bytes() + b'changed')
    monkeypatch.setattr(apt, 'sign_and_export', lambda *_: pytest.fail('Must not sign unverified bytes'))
    with pytest.raises(ValueError, match='checksum'):
        apt.build(deb, tmp_path / 'repo', datetime.now(timezone.utc), checksum_file=sums, gpg_home=tmp_path, fingerprint='0' * 40)
    assert not (tmp_path / 'repo').exists()


@pytest.mark.parametrize('extra,symlink', [('Filename: ../../other.deb\n', False), ('', True), ('Version: 9.9.9-1\n', False)])
def test_invalid_control_cannot_override_index_or_read_symlink(package, extra, symlink):
    deb, _ = package(extra, symlink)
    with pytest.raises(ValueError):
        apt.control_from_deb(deb)


def test_malformed_ar_is_rejected(tmp_path):
    path = tmp_path / 'invalid.deb'
    path.write_bytes(b'!<arch>\ntruncated')
    with pytest.raises(ValueError, match='member'):
        apt.control_from_deb(path)
