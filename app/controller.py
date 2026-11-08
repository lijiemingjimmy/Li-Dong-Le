#!/usr/bin/env python3
"""Container CLI and private browser console. Secrets remain in the data volume."""
import argparse
from datetime import datetime, timedelta
import json
import math
import os
from pathlib import Path
import random
import struct
import subprocess
import sys
import threading
import time
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import adb_backend as device
import ldl_auth
import ldl_automation as workflow
import ldl_homework
import ldl_native_bridge
import ldl_runtime
import mtop_session
import net_compat

LOCK = threading.Lock()
CACHE = (0, b'')
KEYS = {'back': 4, 'home': 3, 'recent': 187, 'enter': 66, 'delete': 67, 'wake': 224}
APP_ACTIVITIES = {
    'open-wechat': 'com.tencent.mm/.ui.LauncherUI',
    'open-ldl': 'cn.ledongli.ldl/.activity.SplashScreenActivity',
}
WEB = Path('/web')
CONFIG = workflow.BASE / 'config.json'


def compatibility():
    device.wait_boot()
    device.shell('cmd', 'alarm', 'set-timezone', 'Asia/Shanghai')
    metadata = device.shell('dumpsys', 'package', 'cn.ledongli.ldl')
    import re
    match = re.search(r'(?:userId|appId)=(\d+)', metadata)
    if not match or 'versionCode=10092 ' not in metadata:
        raise RuntimeError('install_supported_ldl_apk_first')
    uid = match.group(1)
    directory = '/data/user/0/cn.ledongli.ldl/files/windvane/config'
    filename = directory + '/WindVane_wv_main_configcommonwv-data'
    try:
        value = json.loads(device.shell('cat', filename))
    except (ValueError, RuntimeError):
        value = {}
    value['v'] = value.get('v') or '0'
    value['useSystemWebView'] = True
    device.shell('mkdir', '-p', directory)
    device.shell('sh', '-c', 'umask 077; printf %s "$1" > "$2"',
                 'sh', json.dumps(value, separators=(',', ':')), filename)
    device.shell('chown', '-R', uid + ':' + uid, directory)
    mtop_session.save_private('network-compat.json', {'enabled': True})
    return {'status': 'compatibility_enabled', 'network_compat_waits_for_app': True}


def setup(enable_schedule=False):
    device.wait_boot()
    device.adb('root')
    device.connect()
    # Only the user's own newly logged-in Android instance is read.
    text = device.shell('cat', '/data/user/0/cn.ledongli.ldl/shared_prefs/XIAOBAI_SP.xml')
    root = ET.fromstring(text)
    values = {x.get('name'): x.text for x in root}
    credentials = ldl_auth.clean_credentials({
        'access_token': values.get('alisports_accesstoken'),
        'sso_token': values.get('alisports_ssotoken')})
    mtop_session.save_private(ldl_auth.ACCOUNT_FILE, {
        'schema_version': 1, 'source': 'own_android_session',
        'credentials': credentials, 'student_query_succeeded_at': None})
    ldl_auth.verify()
    requirements = ldl_homework.read_requirements()
    ldl_runtime.prepare()
    if ldl_native_bridge.main(['user-id']) != 0:
        raise RuntimeError('native_identity_unavailable')
    uid = str(json.loads((mtop_session.STATE_DIR / 'ldl-user-id-bridge.json').read_text())['uid'])
    if not uid.isdigit() or int(uid) <= 0:
        raise RuntimeError('native_login_required')
    mtop_session.save_private('ldl-user-id.json', {'ldluid': uid, 'verified_current_account': True})
    config = {'task_id': requirements['task_id'], 'class_homework_id': requirements['class_homework_id'],
        'ldluid': uid, 'distance_m': [3050, 3300], 'pace_seconds_per_km': [330, 420],
        'duration_seconds': [1050, 1110], 'scheduled_hour': 15,
        'submission_jitter_seconds': 1200, 'timezone': 'Asia/Shanghai',
        'https_proxy': os.environ.get('LDL_HTTPS_PROXY', ''), 'schedule_enabled': enable_schedule}
    # Validate parameters without creating or submitting a record.
    check_time = datetime.now(ZoneInfo('Asia/Shanghai')).replace(hour=15, minute=30, second=0)
    workflow.plan(config, requirements, check_time)
    workflow.save(CONFIG, config)
    return {'status': 'configured', 'schedule_enabled': enable_schedule,
            'completed': requirements['completed'], 'required': requirements['total_required']}


def scheduler():
    while True:
        try:
            if not CONFIG.exists() or not workflow.read(CONFIG).get('schedule_enabled'):
                time.sleep(15)
                continue
            config = workflow.read(CONFIG)
            now = datetime.now(ZoneInfo(config['timezone']))
            path = workflow.BASE / 'schedule-state.json'
            saved = workflow.read(path) if path.exists() else {}
            today = now.date().isoformat()
            if saved.get('date') != today:
                target = now.replace(hour=config['scheduled_hour'], minute=0, second=0, microsecond=0)
                target += timedelta(seconds=random.SystemRandom().randint(0, config['submission_jitter_seconds']))
                saved = {'date': today, 'target': target.isoformat(), 'attempted': False}
                workflow.save(path, saved)
            if not saved['attempted'] and now >= datetime.fromisoformat(saved['target']):
                # Mark before dispatch: restart cannot cause an automatic replay.
                saved['attempted'] = True
                workflow.save(path, saved)
                result = subprocess.run([sys.executable, '/app/ldl_automation.py', 'run', '--now'], timeout=300)
                print(json.dumps({'event': 'scheduled_run_finished', 'exit_code': result.returncode}), flush=True)
        except Exception as error:
            print(json.dumps({'event': 'scheduler_error', 'error_type': type(error).__name__}), flush=True)
        time.sleep(15)


def connect_android():
    while True:
        try:
            device.connect()
            return
        except Exception:
            time.sleep(5)


def screen():
    global CACHE
    with LOCK:
        if time.monotonic() - CACHE[0] > 0.8:
            frame = device.binary('screencap', '-p')
            if not frame.startswith(b'\x89PNG\r\n\x1a\n'):
                raise RuntimeError('android_screen_unavailable')
            CACHE = (time.monotonic(), frame)
        return CACHE[1]


def coordinate(value, limit):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('invalid_coordinate')
    return str(round(max(0, min(limit - 1, value))))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, status, data, kind='application/json; charset=utf-8'):
        self.send_response(status)
        for name, value in [('Content-Type', kind), ('Content-Length', str(len(data))),
            ('Cache-Control', 'no-store'), ('X-Content-Type-Options', 'nosniff'),
            ('Referrer-Policy', 'no-referrer'), ('Content-Security-Policy',
             "default-src 'self'; img-src 'self' blob:; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")]:
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(data)

    def local(self):
        host = self.headers.get('Host', '')
        try:
            valid = urlsplit('http://' + host).hostname in ('localhost', '127.0.0.1')
        except ValueError:
            return False
        return (valid and self.headers.get('Sec-Fetch-Site') != 'cross-site' and
                self.headers.get('Origin', 'http://' + host) == 'http://' + host)

    def error(self, status):
        self.reply(status, b'{"error":"request_failed"}')

    def do_GET(self):
        if not self.local():
            return self.error(403)
        path = urlsplit(self.path).path
        static = {'/': ('index.html', 'text/html; charset=utf-8'),
                  '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                  '/style.css': ('style.css', 'text/css; charset=utf-8')}
        try:
            if path in static:
                name, kind = static[path]
                self.reply(200, (WEB / name).read_bytes(), kind)
            elif path == '/screen':
                self.reply(200, screen(), 'image/png')
            elif path == '/health':
                self.reply(200, b'{"ok":true}')
            else:
                self.error(404)
        except Exception:
            self.error(503)

    def do_POST(self):
        global CACHE
        if not self.local() or urlsplit(self.path).path != '/input':
            return self.error(403)
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 4096:
                raise ValueError('input_size')
            value = json.loads(self.rfile.read(size))
            action = value.get('action')
            frame = screen()
            width, height = struct.unpack('>II', frame[16:24])
            if action in APP_ACTIVITIES:
                device.shell('input', 'keyevent', 'KEYCODE_WAKEUP')
                args = ['am', 'start', '-W', '-n', APP_ACTIVITIES[action]]
            elif action == 'tap':
                args = ['input', 'tap', coordinate(value['x'], width), coordinate(value['y'], height)]
            elif action == 'swipe':
                args = ['input', 'swipe', coordinate(value['x'], width), coordinate(value['y'], height),
                    coordinate(value['endX'], width), coordinate(value['endY'], height),
                    coordinate(value.get('duration', 350), 1501)]
            elif action in KEYS:
                args = ['input', 'keyevent', str(KEYS[action])]
            elif action == 'text':
                text = value['text']
                if not isinstance(text, str) or not 1 <= len(text) <= 256 or '%s' in text or any(ord(c) < 32 or ord(c) > 126 for c in text):
                    raise ValueError('unsupported_text')
                args = ['input', 'text', text.replace(' ', '%s')]
            else:
                raise ValueError('unsupported_input')
            with LOCK:
                device.shell(*args)
                CACHE = (0, b'')
            self.reply(200, b'{"ok":true}')
        except (ValueError, TypeError, KeyError):
            self.error(400)
        except Exception:
            self.error(503)


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('serve', 'install-apks', 'compatibility', 'open-app',
        'setup', 'status', 'run', 'check', 'plan', 'schedule-on', 'schedule-off'))
    parser.add_argument('--enable-schedule', action='store_true')
    parser.add_argument('--now', action='store_true')
    args = parser.parse_args()
    mtop_session.private_dir()
    try:
        if args.command == 'serve':
            threading.Thread(target=connect_android, daemon=True).start()
            threading.Thread(target=net_compat.guardian, daemon=True).start()
            threading.Thread(target=scheduler, daemon=True).start()
            server = ThreadingHTTPServer(('0.0.0.0', 6080), Handler)
            server.daemon_threads = True
            server.serve_forever()
        elif args.command in ('run', 'check', 'plan'):
            return workflow.main([args.command] + (['--now'] if args.now else []))
        elif args.command == 'install-apks':
            print(json.dumps({'installed': device.install_apks()}))
        elif args.command == 'compatibility':
            device.connect()
            print(json.dumps(compatibility()))
        elif args.command == 'open-app':
            device.wait_boot()
            device.shell('input', 'keyevent', 'KEYCODE_WAKEUP')
            device.shell('am', 'start', '-n', 'cn.ledongli.ldl/.activity.SplashScreenActivity')
            if net_compat.enabled():
                deadline = time.monotonic() + 20
                while time.monotonic() < deadline:
                    path = mtop_session.STATE_DIR / 'network-compat-status.json'
                    if path.exists():
                        network = json.loads(path.read_text())
                        try:
                            current = device.shell('pidof', 'cn.ledongli.ldl').split()
                        except RuntimeError:
                            current = []
                        if current and network.get('ready') and network.get('app_pid') == max(map(int, current)):
                            break
                    time.sleep(1)
                else:
                    raise RuntimeError('network_compat_not_ready')
            print('{"status":"app_opened"}')
        elif args.command == 'setup':
            print(json.dumps(setup(args.enable_schedule)))
        elif args.command.startswith('schedule-'):
            config = workflow.read(CONFIG)
            config['schedule_enabled'] = args.command == 'schedule-on'
            workflow.save(CONFIG, config)
            print(json.dumps({'schedule_enabled': config['schedule_enabled']}))
        else:
            configured = CONFIG.exists()
            print(json.dumps({'configured': configured,
                'schedule_enabled': workflow.read(CONFIG).get('schedule_enabled', False) if configured else False,
                'network_compat': workflow.read(mtop_session.STATE_DIR / 'network-compat-status.json') if (mtop_session.STATE_DIR / 'network-compat-status.json').exists() else None,
                'last_result': workflow.read(workflow.BASE / 'last-result.json') if (workflow.BASE / 'last-result.json').exists() else None}))
        return 0
    except Exception as error:
        print(json.dumps({'status': 'failed', 'error_type': type(error).__name__}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
