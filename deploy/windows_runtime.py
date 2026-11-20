"""Run Li-Dong-Le against a rootable Android 11 x86_64 AVD on Windows."""
import certifi
import hashlib
import lzma
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
SDK = Path(os.environ.get('ANDROID_SDK_ROOT') or os.environ.get('ANDROID_HOME') or
           Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local')) / 'Android/Sdk')
RUNTIME = ROOT / 'runtime'
SERIAL = 'emulator-5556'
AVD = 'ldl_win_x64'
PORT = 16081

os.environ.update(
    PATH=os.pathsep.join([str(SDK / 'platform-tools'), str(SDK / 'emulator'), os.environ.get('PATH', '')]),
    ADB_TARGET=SERIAL, FRIDA_TARGET='127.0.0.1:27042',
    LDL_STATE_DIR=str(ROOT / 'private' / 'state'), LDL_NATIVE_EMULATOR='1',
    LDL_WEB_DIR=str(ROOT / 'web'), LDL_APK_DIR=str(ROOT / 'apks'),
    LDL_WECHAT_APK='wechat.apk', LDL_LISTEN_HOST='127.0.0.1',
    LDL_LISTEN_PORT=str(PORT), PYTHONDONTWRITEBYTECODE='1',
    SSL_CERT_FILE=certifi.where(),
)
sys.path.insert(0, str(ROOT / 'app'))
import adb_backend as device

FRIDA_SHA256 = '4bc938db27cbe1fec859e28f6bd34d269995a719de2f10e97e28c1bdcd9416c7'
FRIDA_URL = 'https://github.com/frida/frida/releases/download/16.7.19/frida-server-16.7.19-android-x86_64.xz'


def health():
    import urllib.error
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{PORT}/health', timeout=2) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError):
        return False


def ensure_frida():
    RUNTIME.mkdir(exist_ok=True)
    binary = RUNTIME / 'ldl-frida-server.exe-guest'
    if binary.exists() and hashlib.sha256(binary.read_bytes()).hexdigest() == FRIDA_SHA256:
        return binary
    archive = RUNTIME / 'frida-server-16.7.19-android-x86_64.xz'
    with urllib.request.urlopen(FRIDA_URL, timeout=120) as response:
        archive.write_bytes(response.read())
    if hashlib.sha256(archive.read_bytes()).hexdigest() != FRIDA_SHA256:
        archive.unlink(missing_ok=True)
        raise RuntimeError('frida_download_checksum_mismatch')
    binary.write_bytes(lzma.decompress(archive.read_bytes()))
    return binary


def start():
    emulator = SDK / 'emulator' / ('emulator.exe' if os.name == 'nt' else 'emulator')
    if not emulator.exists():
        raise RuntimeError('android_emulator_not_found_install_sdk_emulator')
    if not (SDK / 'platform-tools' / ('adb.exe' if os.name == 'nt' else 'adb')).exists():
        raise RuntimeError('adb_not_found_install_platform_tools')
    binary = ensure_frida()
    rows = subprocess.check_output(['adb', 'devices'], text=True, stderr=subprocess.DEVNULL)
    if SERIAL not in rows:
        log = (RUNTIME / 'emulator.log').open('ab')
        flags = getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
        subprocess.Popen([str(emulator), '@' + AVD, '-port', '5556', '-no-snapshot',
                          '-no-boot-anim', '-memory', '4096', '-accel', 'auto'],
                         stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                         creationflags=flags)
        log.close()
    device.wait_boot(timeout=240)
    avd = device.adb('emu', 'avd', 'name').splitlines()[0].strip()
    if avd != AVD:
        raise RuntimeError('reserved_port_used_by_other_avd')
    root_result = subprocess.run(['adb', '-s', SERIAL, 'root'], capture_output=True, text=True)
    if root_result.returncode:
        raise RuntimeError('rootable_google_apis_avd_required')
    time.sleep(2)
    device.connect(timeout=30)
    if device.shell('id', '-u') != '0':
        raise RuntimeError('rootable_google_apis_avd_required')
    try:
        running = device.shell('pidof', 'ldl-frida-server')
    except RuntimeError:
        running = ''
    if not running:
        device.adb('push', str(binary), '/data/local/tmp/ldl-frida-server')
        device.shell('chmod', '700', '/data/local/tmp/ldl-frida-server')
        device.shell('sh', '-c', 'nohup /data/local/tmp/ldl-frida-server --listen=127.0.0.1:27042 >/data/local/tmp/ldl-frida.log 2>&1 </dev/null &')
    device.adb('forward', 'tcp:27042', 'tcp:27042')
    if not health():
        log = (RUNTIME / 'controller.log').open('ab')
        flags = getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
        subprocess.Popen([sys.executable, str(ROOT / 'app' / 'controller.py'), 'serve'],
                         stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                         creationflags=flags, env=os.environ.copy())
        log.close()
        for _ in range(20):
            if health():
                break
            time.sleep(1)
        else:
            raise RuntimeError('controller_not_ready')
    print('{"status":"ready","console":"http://127.0.0.1:16081","avd":"ldl_win_x64","schedule_enabled_by_start":false}')


if __name__ == '__main__':
    if sys.argv[1:] == ['start']:
        start()
    else:
        os.execv(sys.executable, [sys.executable, str(ROOT / 'app' / 'controller.py'), *sys.argv[1:]])
