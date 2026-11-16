"""Stage an npm release with its exact version-matched native wheel bundled."""

import argparse
import hashlib
import json
import shutil
import zipfile
from pathlib import Path


def prepare(wheel, destination):
    source = Path(__file__).resolve().parents[1] / 'npm'
    manifest = json.loads((source / 'package.json').read_text())
    expected = f'shrutadhara-{manifest["version"]}-py3-none-any.whl'
    if wheel.name != expected:
        raise ValueError(f'Expected {expected}')
    with zipfile.ZipFile(wheel) as archive:
        if not any(n.startswith('shrutadhara/') for n in archive.namelist()):
            raise ValueError('Wheel lacks application package')
    if destination.exists():
        raise ValueError('Use a new staging directory')
    destination.mkdir(parents=True)
    for name in ['package.json', 'launcher.js', 'README.md', 'LICENSE', 'NOTICE']:
        shutil.copyfile(source / name, destination / name)
    (destination / 'native').mkdir()
    shutil.copyfile(wheel, destination / 'native' / wheel.name)
    (destination / 'native' / 'manifest.json').write_text(json.dumps({
        'filename': wheel.name, 'sha256': hashlib.sha256(wheel.read_bytes()).hexdigest()
    }, indent=2) + '\n')
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('wheel', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    print(prepare(args.wheel, args.destination))


if __name__ == '__main__':
    main()
