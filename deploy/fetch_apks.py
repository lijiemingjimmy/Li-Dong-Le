#!/usr/bin/env python3
"""Fetch pinned, unmodified APKs separately from this source release."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def checksum(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def download(spec, directory, *, verify_only=False):
    name = spec['filename']
    if Path(name).name != name or not name.endswith('.apk'):
        raise ValueError('APK filename must be a basename ending in .apk')
    target = directory / name
    if target.is_file() and checksum(target) == spec['sha256']:
        return 'verified'
    if verify_only:
        raise ValueError(name + ': missing or checksum mismatch')
    directory.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix('.download')
    try:
        print('Downloading ' + name, flush=True)
        with urllib.request.urlopen(spec['url'], timeout=120) as response, temporary.open('wb') as out:
            while chunk := response.read(1024 * 1024):
                out.write(chunk)
        if checksum(temporary) != spec['sha256']:
            raise ValueError(name + ': checksum mismatch; original file retained')
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return 'downloaded and verified'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-only', action='store_true')
    parser.add_argument('--directory', type=Path, default=ROOT / 'apks')
    args = parser.parse_args()
    for spec in json.loads((ROOT / 'apks/manifest.json').read_text()):
        result = download(spec, args.directory, verify_only=args.verify_only)
        print(spec['filename'] + ': ' + result, flush=True)


if __name__ == '__main__':
    main()
