"""Distribution regressions: artifact trust, layout and reproducibility."""

import hashlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import tarfile
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def tool(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tools' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def wheel(tmp_path):
    path = tmp_path / 'shrutadhara-0.1.0-py3-none-any.whl'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('shrutadhara/__init__.py', '')
        archive.writestr('shrutadhara-0.1.0.dist-info/METADATA', 'Name: shrutadhara\nVersion: 0.1.0\n')
        archive.writestr('shrutadhara-0.1.0.dist-info/licenses/LICENSE', 'MIT')
        archive.writestr('shrutadhara-0.1.0.dist-info/licenses/NOTICE', 'No audio bundled')
        archive.writestr('shrutadhara-0.1.0.dist-info/RECORD', 'old wheel paths')
        archive.writestr('shrutadhara-0.1.0.data/data/share/applications/io.github.Praneel7015.Shrutadhara.desktop', '[Desktop Entry]')
    return path


def test_debian_reproducible_layout_and_dependencies(wheel, tmp_path):
    builder = tool('build_deb')
    first = builder.build(wheel, tmp_path / 'a', 123).read_bytes()
    second = builder.build(wheel, tmp_path / 'b', 123).read_bytes()
    assert first == second
    assert first.startswith(b'!<arch>\n')
    offset, members = 8, {}
    while offset < len(first):
        header = first[offset:offset + 60]
        size = int(header[48:58])
        members[header[:16].decode().strip().rstrip('/')] = first[offset + 60:offset + 60 + size]
        offset += 60 + size + size % 2
    assert members['debian-binary'] == b'2.0\n'
    with tarfile.open(fileobj=io.BytesIO(members['control.tar.gz'])) as archive:
        control = archive.extractfile('./control').read().decode()
        assert 'gir1.2-gtk-4.0 (>= 4.10)' in control
        assert 'python3-jsonschema (>= 4.10)' in control
        assert not {'./postinst', './preinst'} & set(archive.getnames())
    with tarfile.open(fileobj=io.BytesIO(members['data.tar.gz'])) as archive:
        preceding_directories = set()
        for member in archive.getmembers():
            if member.isdir():
                preceding_directories.add(member.name)
            else:
                assert str(Path(member.name).parent) in {str(Path(name)) for name in preceding_directories}
        assert archive.getmember('./usr/bin/shruta').mode == 0o755
        assert not any(name.endswith('/RECORD') for name in archive.getnames())
        assert archive.extractfile('./usr/bin/shruta').read().startswith(b'#!/usr/bin/python3')


def test_debian_rejects_wheel_path_escape(wheel, tmp_path):
    with zipfile.ZipFile(wheel, 'a') as archive:
        archive.writestr('../outside', 'untrusted')
    with pytest.raises(ValueError, match='Unsafe wheel path'):
        tool('build_deb').build(wheel, tmp_path / 'out', 0)


@pytest.mark.skipif(not shutil.which('node'), reason='Node unavailable')
def test_npm_tampered_bundle_never_creates_runtime(wheel, tmp_path):
    staged = tool('prepare_npm').prepare(wheel, tmp_path / 'stage')
    manifest = json.loads((staged / 'native/manifest.json').read_text())
    assert manifest['sha256'] == hashlib.sha256(wheel.read_bytes()).hexdigest()
    (staged / 'native' / wheel.name).write_bytes(b'tampered')
    environment = dict(os.environ, XDG_DATA_HOME=str(tmp_path / 'data'))
    environment.pop('SHRUTA_NATIVE_EXECUTABLE', None)
    result = subprocess.run(['node', str(staged / 'launcher.js'), 'setup-native'], env=environment, capture_output=True, text=True)
    assert result.returncode == 3
    assert 'checksum mismatch' in result.stderr
    assert not (tmp_path / 'data').exists()


@pytest.mark.parametrize('name', ['root/notes/summary.md', 'root/questions/answer.json', 'root/config.json', 'root/.env.secret', 'root/clip.ogg'])
def test_release_rejects_private_payloads(name):
    with pytest.raises(ValueError):
        tool('check_release').check_names(['LICENSE', 'NOTICE', name])
