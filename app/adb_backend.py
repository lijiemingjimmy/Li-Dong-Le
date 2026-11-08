"""ADB transport to the private Android service; never prints command output."""
import os
from pathlib import Path
import shlex
import subprocess
import time

TARGET = os.environ.get('ADB_TARGET', 'android:5555')


def adb(*args, timeout=30, binary=False):
    result = subprocess.run(['adb', '-s', TARGET, *args], capture_output=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError('adb_command_failed')
    return result.stdout if binary else result.stdout.decode('utf-8', errors='replace').strip()


def connect(timeout=90):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        subprocess.run(['adb', 'connect', TARGET], capture_output=True, timeout=10)
        try:
            if adb('get-state', timeout=5) == 'device':
                return
        except (RuntimeError, subprocess.TimeoutExpired):
            pass
        time.sleep(2)
    raise RuntimeError('android_connection_timeout')


def shell(*args, timeout=30):
    # adb shell uses a guest shell: quote arguments rather than concatenate input.
    return adb('shell', shlex.join(map(str, args)), timeout=timeout)


def wait_boot(timeout=120):
    connect(timeout)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if shell('getprop', 'sys.boot_completed') == '1':
            return
        time.sleep(2)
    raise RuntimeError('android_boot_timeout')


def binary(*args):
    return adb('exec-out', shlex.join(map(str, args)), binary=True)


def install_apks():
    wechat = os.environ.get('LDL_WECHAT_APK', 'wechat.apk')
    if Path(wechat).name != wechat or not wechat.endswith('.apk'):
        raise ValueError('invalid_wechat_apk_filename')
    for name in ('ledongli.apk', wechat):
        if not (Path('/apks') / name).is_file():
            raise FileNotFoundError('required_apk_missing: ' + name)
    wait_boot()
    installed = []
    for name in ('webview.apk', 'ledongli.apk', wechat):
        path = Path('/apks') / name
        if path.is_file():
            result = adb('install', '-r', str(path), timeout=180)
            if 'Success' not in result:
                raise RuntimeError('apk_install_failed')
            installed.append(name)
    return installed
