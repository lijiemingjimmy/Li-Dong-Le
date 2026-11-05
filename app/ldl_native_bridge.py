#!/usr/bin/env python3
"""Invoke the signed-in app's native bridge over a loopback ADB forward."""
import argparse
import fcntl
import os
from pathlib import Path
import subprocess
import sys

import adb_backend as device
import mtop_session


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('user-id', 'homework', 'upload-run', 'submit-course'))
    parser.add_argument('--run-dir', type=Path)
    args = parser.parse_args(argv)
    mtop_session.private_dir()
    with (mtop_session.STATE_DIR / 'bridge.lock').open('a') as lock:
        os.chmod(mtop_session.STATE_DIR / 'bridge.lock', 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            device.connect()
            device.shell('input', 'keyevent', 'KEYCODE_WAKEUP')
            pids = device.shell('pidof', 'cn.ledongli.ldl').split()
            sockets = device.shell('cat', '/proc/net/unix')
            name = next('webview_devtools_remote_' + pid for pid in pids
                        if '@webview_devtools_remote_' + pid + '\n' in sockets + '\n')
            device.adb('forward', 'tcp:9223', 'localabstract:' + name)
            worker = Path(__file__).with_name('ldl_native_bridge_worker.py')
            extra = [str(args.run_dir.resolve())] if args.run_dir else []
            return subprocess.run([sys.executable, '-B', str(worker), '9223', args.operation, *extra],
                                  timeout=40).returncode
        except (OSError, RuntimeError, subprocess.SubprocessError, StopIteration) as error:
            print('{"status":"native_bridge_unavailable","error_type":"' + type(error).__name__ + '"}')
            return 3
        finally:
            try:
                device.adb('forward', '--remove', 'tcp:9223', timeout=5)
            except Exception:
                pass


if __name__ == '__main__':
    raise SystemExit(main())
