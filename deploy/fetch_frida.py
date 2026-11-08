"""Fetch the unmodified, pinned upstream Android compatibility runtime."""
import hashlib
import lzma
import os
from pathlib import Path
import sys
import urllib.request

assets = {
    'arm64': ('arm64', '36ec3d7474b1ac69c4e7ec985612fae771d37ffb71cb94858bc6978f69f5e581'),
    'amd64': ('x86_64', '4bc938db27cbe1fec859e28f6bd34d269995a719de2f10e97e28c1bdcd9416c7'),
}
if sys.argv[1] not in assets:
    raise SystemExit('Supported Docker architectures: arm64, amd64.')
abi, checksum = assets[sys.argv[1]]
version = '16.7.19'
filename = f'frida-server-{version}-android-{abi}.xz'
base = os.environ.get('FRIDA_ASSET_BASE', f'https://github.com/frida/frida/releases/download/{version}').rstrip('/')
license_override = os.environ.get('FRIDA_LICENSE_BASE')
license_base = (license_override or f'https://raw.githubusercontent.com/frida/frida/{version}').rstrip('/')


def fetch(url):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({})) if url.startswith('http://127.0.0.1:') else urllib.request.build_opener()
    with opener.open(url, timeout=120) as stream:
        return stream.read()


archive = fetch(base + '/' + filename)
if hashlib.sha256(archive).hexdigest() != checksum:
    raise SystemExit('Upstream Frida server checksum mismatch')
binary = Path('/work/frida-server')
binary.write_bytes(lzma.decompress(archive))
binary.chmod(0o755)
licenses = Path('/work/frida-licenses')
licenses.mkdir()
for name in ('COPYING', 'COPYING.LIB'):
    url = license_base + '/' + name
    if name == 'COPYING.LIB' and not license_override:
        url = 'https://raw.githubusercontent.com/spdx/license-list-data/main/text/LGPL-2.0-or-later.txt'
    text = fetch(url)
    expected = b'wxWindows Library Licence' if name == 'COPYING' else b'GNU LIBRARY GENERAL PUBLIC LICENSE'
    if expected not in text:
        raise SystemExit('Unexpected upstream license text')
    (licenses / name).write_bytes(text)
(licenses / 'SOURCE.txt').write_text(f'Unmodified Frida {version}: https://github.com/frida/frida/tree/{version}\n')
