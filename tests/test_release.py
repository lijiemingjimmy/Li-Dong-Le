import hashlib
import importlib.util
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from datetime import datetime
from http.server import ThreadingHTTPServer
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
import ldl_automation as flow
import controller

spec = importlib.util.spec_from_file_location('fetch_apks', ROOT / 'deploy/fetch_apks.py')
fetch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch)


class PlanningTests(unittest.TestCase):
    def setUp(self):
        self.config = {'class_homework_id': 'fixture-class', 'task_id': 'fixture-task',
                       'distance_m': [3100, 3100], 'pace_seconds_per_km': [330, 420],
                       'duration_seconds': [1080, 1080]}
        self.requirements = {'class_homework_id': 'fixture-class', 'task_id': 'fixture-task',
            'minimum_distance_m': 3000, 'fastest_pace_seconds_per_km': 330,
            'slowest_pace_seconds_per_km': 420, 'start_date': '20260101', 'end_date': '20261231',
            'valid_time_windows': [{'begin': '08:00:00', 'end': '22:00:00'}]}
        self.now = datetime(2026, 11, 8, 16, 0, tzinfo=flow.ZONE)

    def test_valid_record(self):
        result = flow.plan(self.config, self.requirements, self.now)
        self.assertEqual(result['distance_m'], 3100)
        self.assertEqual(result['end_time'] - result['start_time'], 1080)
        self.assertAlmostEqual(result['pace_seconds_per_km'], 1080 * 1000 / 3100)

    def test_whole_interval_must_fit(self):
        with self.assertRaisesRegex(ValueError, 'outside_homework_time_window'):
            flow.plan(self.config, self.requirements, self.now.replace(hour=8, minute=5))

    def test_changed_class_rejected(self):
        self.requirements['class_homework_id'] = 'another-class'
        with self.assertRaisesRegex(RuntimeError, 'homework_class_changed'):
            flow.plan(self.config, self.requirements, self.now)

    def test_rotated_task_same_class_allowed(self):
        self.requirements['task_id'] = 'rotated-task'
        flow.plan(self.config, self.requirements, self.now)

    def test_distance_and_duration_constraints(self):
        self.config['distance_m'] = [2000, 2000]
        with self.assertRaisesRegex(ValueError, 'configured_distance_below_requirement'):
            flow.plan(self.config, self.requirements, self.now)
        self.config['distance_m'] = [3100, 3100]
        self.config['duration_seconds'] = [1, 2]
        with self.assertRaisesRegex(ValueError, 'duration_and_pace_constraints_conflict'):
            flow.plan(self.config, self.requirements, self.now)


class WriteGuardTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name)
        self.config = {'https_proxy': ''}
        self.requirements = {'completed': 1, 'total_required': 10}

    def run_guard(self, allowed, receipt=None, check_only=False):
        if receipt is not None:
            path = self.base / 'days' / (datetime.now(flow.ZONE).date().isoformat() + '.json')
            path.parent.mkdir()
            path.write_text(json.dumps(receipt))
        with patch.object(flow, 'BASE', self.base), \
             patch.object(flow.mtop_session, 'MtopSession'), \
             patch.object(flow, 'eligibility', return_value=(self.requirements, allowed)), \
             patch.object(flow, 'report', side_effect=lambda status, **kw: {'status': status, **kw}), \
             patch.object(flow.ldl_runtime, 'prepare') as prepare, \
             patch.object(flow, 'bridge') as bridge:
            result = flow.run(self.config, check_only=check_only, immediate=True)
            prepare.assert_not_called()
            bridge.assert_not_called()
            return result

    def test_server_daily_limit_stops_before_write(self):
        self.assertEqual(self.run_guard({'success': False, 'code': 1})['status'], 'skipped_today')

    def test_completed_receipt_stops_duplicate(self):
        self.assertEqual(self.run_guard({'success': True}, {'status': 'completed'})['status'],
                         'already_completed_locally')

    def test_uncertain_receipt_is_not_retried(self):
        result = self.run_guard({'success': True}, {'status': 'uncertain', 'run_id': 'fixture'})
        self.assertEqual(result['status'], 'needs_review')

    def test_read_only_check_does_not_write(self):
        self.assertEqual(self.run_guard({'success': True}, check_only=True)['status'], 'eligible')
        self.assertFalse((self.base / 'days').exists())


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.spec = {'filename': 'fixture.apk', 'url': 'https://example.invalid/app.apk',
                     'sha256': hashlib.sha256(b'expected').hexdigest()}

    def test_valid_download_is_verified(self):
        with patch.object(fetch.urllib.request, 'urlopen', return_value=io.BytesIO(b'expected')):
            self.assertEqual(fetch.download(self.spec, self.root), 'downloaded and verified')
        self.assertEqual(fetch.download(self.spec, self.root, verify_only=True), 'verified')

    def test_bad_download_retains_existing_file(self):
        target = self.root / 'fixture.apk'
        target.write_bytes(b'old')
        with patch.object(fetch.urllib.request, 'urlopen', return_value=io.BytesIO(b'corrupt')):
            with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
                fetch.download(self.spec, self.root)
        self.assertEqual(target.read_bytes(), b'old')
        self.assertFalse(target.with_suffix('.download').exists())

    def test_verify_only_never_fetches(self):
        with patch.object(fetch.urllib.request, 'urlopen') as network:
            with self.assertRaises(ValueError):
                fetch.download(self.spec, self.root, verify_only=True)
            network.assert_not_called()

    def test_path_traversal_rejected(self):
        self.spec['filename'] = '../fixture.apk'
        with self.assertRaises(ValueError):
            fetch.download(self.spec, self.root)


class ConsoleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), controller.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = 'http://127.0.0.1:' + str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def post(self, data, **headers):
        return urllib.request.urlopen(urllib.request.Request(self.url + '/input',
            data=json.dumps(data).encode(), headers={'Content-Type': 'application/json', **headers}), timeout=5)

    def test_launcher_is_allowlisted(self):
        frame = b'\x89PNG\r\n\x1a\n' + b'\0' * 8 + struct.pack('>II', 720, 1280)
        with patch.object(controller, 'screen', return_value=frame), \
             patch.object(controller.device, 'shell') as shell:
            with self.post({'action': 'open-wechat'}) as response:
                self.assertEqual(response.status, 200)
            shell.assert_any_call('am', 'start', '-W', '-n', 'com.tencent.mm/.ui.LauncherUI')
            shell.reset_mock()
            with self.assertRaises(urllib.error.HTTPError) as error:
                self.post({'action': 'open-arbitrary', 'component': 'unknown/.Activity'})
            self.assertEqual(error.exception.code, 400)
            shell.assert_not_called()

    def test_cross_origin_input_rejected(self):
        with patch.object(controller.device, 'shell') as shell:
            with self.assertRaises(urllib.error.HTTPError) as error:
                self.post({'action': 'home'}, Origin='https://example.invalid')
            self.assertEqual(error.exception.code, 403)
            shell.assert_not_called()


if __name__ == '__main__':
    unittest.main()
