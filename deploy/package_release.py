#!/usr/bin/env python3
"""Package committed source only; never package an arbitrary workspace directory."""
import argparse
import hashlib
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_DIRS = {'data', 'state', 'runtime', 'private', 'logs', 'screenshots', 'test-results', 'dist'}
BINARY_SUFFIXES = {'.apk', '.so', '.dex', '.jar', '.img', '.pem', '.key', '.db', '.sqlite', '.sqlite3'}


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    files = git('ls-tree', '-rz', '--name-only', 'HEAD').decode().split('\0')
    for name in filter(None, files):
        path = Path(name)
        if (path.parts[0] in PRIVATE_DIRS or path.suffix.lower() in BINARY_SUFFIXES
                or (path.name.startswith('.env') and path.name != '.env.example')
                or path.name == 'compose.override.yaml'):
            raise SystemExit('Refusing to publish private/binary path: ' + name)
    print('Committed source inventory: OK')
    if args.check_only:
        return
    if git('status', '--porcelain', '--untracked-files=normal').strip():
        raise SystemExit('Commit or remove outstanding source changes before packaging')
    version = git('show', 'HEAD:VERSION').decode().strip()
    output = ROOT / 'dist'
    output.mkdir(exist_ok=True)
    basename = 'Li-Dong-Le-v' + version
    lines = []
    for suffix, format_name in (('.tar.gz', 'tar.gz'), ('.zip', 'zip')):
        path = output / (basename + suffix)
        subprocess.run(['git', '-C', str(ROOT), 'archive', '--format=' + format_name,
                        '--prefix=' + basename + '/', '--output=' + str(path), 'HEAD'], check=True)
        lines.append(hashlib.sha256(path.read_bytes()).hexdigest() + '  ' + path.name)
    (output / 'SHA256SUMS').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
