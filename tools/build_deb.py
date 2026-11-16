"""Build an architecture-independent .deb from a reviewed pure-Python wheel.

Uses Debian's documented ar format; never installs packages or runs maintainer hooks.
"""

import argparse
import gzip
import hashlib
import io
import os
import re
import tarfile
import zipfile
from email.parser import BytesParser
from pathlib import Path, PurePosixPath

DEPENDENCIES = (
    'python3 (>= 3.11), python3-jsonschema (>= 4.10), python3-gi, '
    'gir1.2-gtk-4.0 (>= 4.10), ffmpeg, pulseaudio-utils, pipewire-pulse, wireplumber'
)


def tar_bytes(files, epoch):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w', format=tarfile.GNU_FORMAT) as archive:
        # dpkg requires parent directories to be explicit archive members.
        directories = {str(parent) for name in files for parent in PurePosixPath(name).parents if str(parent) != '.'}
        for name in sorted(directories, key=lambda value: (value.count('/'), value)):
            info = tarfile.TarInfo('./' + name)
            info.type = tarfile.DIRTYPE
            info.mode, info.mtime = 0o755, epoch
            info.uid = info.gid = 0
            info.uname = info.gname = 'root'
            archive.addfile(info)
        for name, (content, mode) in sorted(files.items()):
            info = tarfile.TarInfo('./' + name)
            info.size, info.mode, info.mtime = len(content), mode, epoch
            info.uid = info.gid = 0
            info.uname = info.gname = 'root'
            archive.addfile(info, io.BytesIO(content))
    return gzip.compress(buffer.getvalue(), mtime=epoch)


def ar_member(name, content, epoch):
    header = f'{name + "/":<16}{epoch:<12}{0:<6}{0:<6}{0o100644:<8o}{len(content):<10}`\n'
    return header.encode('ascii') + content + (b'\n' if len(content) % 2 else b'')


def build(wheel, output, epoch):
    files = {}
    with zipfile.ZipFile(wheel) as archive:
        metadata_names = [n for n in archive.namelist() if n.endswith('.dist-info/METADATA')]
        if len(metadata_names) != 1:
            raise ValueError('Expected exactly one wheel metadata file')
        metadata = BytesParser().parsebytes(archive.read(metadata_names[0]))
        version = metadata['Version']
        if metadata['Name'] != 'shrutadhara' or not re.fullmatch(r'\d+\.\d+\.\d+', version):
            raise ValueError('Expected Shrutadhara wheel with a three-part release version')
        if wheel.name != f'shrutadhara-{version}-py3-none-any.whl':
            raise ValueError('Only matching pure Python wheels are supported')
        for name in archive.namelist():
            path = PurePosixPath(name)
            if path.is_absolute() or '..' in path.parts:
                raise ValueError('Unsafe wheel path')
            if name.endswith('/'):
                continue
            if '.data/data/share/' in name:
                dest = 'usr/share/' + name.split('.data/data/share/', 1)[1]
            elif name.startswith('shrutadhara/') or name.startswith(f'shrutadhara-{version}.dist-info/'):
                if path.name == 'RECORD':
                    continue  # Wheel installation layout differs from the Debian layout.
                dest = 'usr/lib/python3/dist-packages/' + name
            else:
                raise ValueError(f'Unexpected wheel member: {name}')
            files[dest] = (archive.read(name), 0o644)
        prefix = f'shrutadhara-{version}.dist-info/licenses/'
        for name in ['LICENSE', 'NOTICE']:
            files['usr/share/doc/shrutadhara/' + name] = (archive.read(prefix + name), 0o644)
    files['usr/share/doc/shrutadhara/copyright'] = files['usr/share/doc/shrutadhara/LICENSE']
    files['usr/bin/shruta'] = (
        b'#!/usr/bin/python3\nfrom shrutadhara.cli import main\nraise SystemExit(main())\n', 0o755
    )
    files['usr/share/doc/shrutadhara/README'] = (
        b'Experimental release. Run shruta doctor before use. Recording requires notice and permission.\n'
        b'No recording, services, configuration, or AI uploads are enabled by installation.\n'
        b'Automatic agy transcription remains unvalidated. See the project VALIDATION.md.\n', 0o644
    )
    installed_size = sum(len(value[0]) for value in files.values()) // 1024 + 1
    control = (
        f'Package: shrutadhara\nVersion: {version}-1\nSection: sound\nPriority: optional\n'
        'Architecture: all\nMaintainer: Praneel7015 <praneelsindhole@gmail.com>\n'
        f'Installed-Size: {installed_size}\nDepends: {DEPENDENCIES}\n'
        'Recommends: libnotify-bin, xdg-utils\n'
        'Homepage: https://github.com/Praneel7015/shrutadhara\n'
        'Description: Experimental local-first meeting recorder and AI assistant\n'
        ' Native GTK controls and CLI with private PipeWire recording and optional agy processing.\n'
    ).encode()
    sums = ''.join(f'{hashlib.md5(content).hexdigest()}  {name}\n' for name, (content, _) in sorted(files.items()))
    members = [('debian-binary', b'2.0\n'),
               ('control.tar.gz', tar_bytes({'control': (control, 0o644), 'md5sums': (sums.encode(), 0o644)}, epoch)),
               ('data.tar.gz', tar_bytes(files, epoch))]
    output.mkdir(parents=True, exist_ok=True)
    destination = output / f'shrutadhara_{version}-1_all.deb'
    destination.write_bytes(b'!<arch>\n' + b''.join(ar_member(name, content, epoch) for name, content in members))
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('wheel', type=Path)
    parser.add_argument('--output', type=Path, default=Path('dist'))
    args = parser.parse_args()
    print(build(args.wheel, args.output, int(os.environ.get('SOURCE_DATE_EPOCH', '0'))))


if __name__ == '__main__':
    main()
