"""Per-process Ethernet compatibility for the supported client's login preflight.

Only NetStatus.isNetworkEnable is adjusted, and only for a connected Ethernet
network. The APK, account authorization, TLS and native signing stay intact.
"""
import json
import os
import threading
import time

import adb_backend as device
import mtop_session

SOURCE = r'''
Java.perform(function () {
  try {
    const Status=Java.use('cn.ledongli.ldl.utils.NetStatus');
    const Thread=Java.use('android.app.ActivityThread');
    const CM=Java.use('android.net.ConnectivityManager');
    const original=Status.isNetworkEnable.overload();
    original.implementation=function () {
      try {
        const app=Thread.currentApplication();
        const cm=Java.cast(app.getSystemService('connectivity'),CM);
        const net=cm.getActiveNetworkInfo();
        if(net!==null && net.getType()===9 && net.isConnected()) return true;
      } catch (_) {}
      return original.call(Status);
    };
    send({kind:'ready'});
  } catch (_) { send({kind:'unsupported'}); }
});
'''


def enabled():
    path = mtop_session.STATE_DIR / 'network-compat.json'
    try:
        return json.loads(path.read_text()).get('enabled', False)
    except (OSError, ValueError):
        return False


def status(ready, pid=None, error=None):
    mtop_session.save_private('network-compat-status.json',
                              {'ready': ready, 'app_pid': pid, 'error_type': error})


def guardian():
    session = script = None
    current = None
    detached = threading.Event()
    status(False)
    while True:
        try:
            if not enabled():
                if session is not None:
                    session.detach()
                session = script = None
                current = None
                time.sleep(2)
                continue
            import frida
            device.connect(timeout=10)
            device.shell('setprop', 'ctl.start', 'ldl-netcompat')
            pids = device.shell('pidof', 'cn.ledongli.ldl').split()
            if not pids:
                time.sleep(1)
                continue
            pid = max(map(int, pids))
            if session is not None and current == pid and not detached.is_set():
                time.sleep(1)
                continue
            if 'versionCode=10092 ' not in device.shell('dumpsys', 'package', 'cn.ledongli.ldl'):
                status(False, pid, 'UnsupportedAppVersion')
                time.sleep(15)
                continue
            if session is not None:
                try:
                    session.detach()
                except Exception:
                    pass
            status(False, pid)
            remote = frida.get_device_manager().add_remote_device(os.environ.get('FRIDA_TARGET', 'android:27042'))
            session = remote.attach(pid)
            detached = threading.Event()
            session.on('detached', lambda *args, marker=detached: marker.set())
            ready = threading.Event()
            def message(event, data):
                if event.get('type') == 'send' and event.get('payload', {}).get('kind') == 'ready':
                    ready.set()
            script = session.create_script(SOURCE)
            script.on('message', message)
            script.load()
            if not ready.wait(12):
                raise RuntimeError('network_compat_method_unavailable')
            current = pid
            status(True, pid)
        except Exception as error:
            status(False, error=type(error).__name__)
            if session is not None:
                try:
                    session.detach()
                except Exception:
                    pass
            session = script = None
            current = None
            time.sleep(3)
