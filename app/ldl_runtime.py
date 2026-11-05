"""Prepare the original app through its versioned WebView activity contract."""
import json
from pathlib import Path
import re
import subprocess
import sys
import time

import adb_backend as device
import mtop_session

ROOT = Path(__file__).resolve().parent
PACKAGE = 'cn.ledongli.ldl'
URL = 'https://market.m.taobao.com/app/front-end-group/course-tools-student/home.html?hideTitleBar=true'


def prepare():
    device.connect()
    deadline = time.monotonic() + 90
    while device.shell('getprop', 'sys.boot_completed') != '1':
        if time.monotonic() > deadline:
            raise RuntimeError('android_boot_timeout')
        time.sleep(2)
    device.shell('input', 'keyevent', 'KEYCODE_WAKEUP')
    device.shell('wm', 'dismiss-keyguard')
    metadata = device.shell('dumpsys', 'package', PACKAGE)
    version = re.search(r'versionCode=(\d+)', metadata)
    if not version or version.group(1) != '10092':
        raise RuntimeError('unsupported_ldl_version_expected_10092')
    device.shell('am', 'start', '-W', '-n', PACKAGE + '/.activity.SplashScreenActivity')
    opened = device.shell('am', 'start', '-W', '-n', PACKAGE + '/.webview.LeWVUCWebViewActivity',
                          '--es', 'WEB_URL', URL)
    if any(x in opened for x in ('Error', 'Exception', 'Permission Denial')):
        raise RuntimeError('native_activity_unavailable')
    for _ in range(3):
        call = subprocess.run([sys.executable, str(ROOT / 'ldl_native_bridge.py'), 'homework'],
                              capture_output=True, text=True, timeout=45)
        if call.returncode == 0:
            response = json.loads((mtop_session.STATE_DIR / 'native-homework-response.json').read_text())
            if (response.get('ret') or [''])[0].split('::')[0] == 'SUCCESS' and response.get('data', {}).get('model'):
                return
        time.sleep(1)
    raise RuntimeError('homework_page_or_login_unavailable')
