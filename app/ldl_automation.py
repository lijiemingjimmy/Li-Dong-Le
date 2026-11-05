#!/usr/bin/env python3
"""Run the pinned LDL homework workflow, with daily guards and private receipts."""
import argparse
from datetime import datetime, timedelta
import fcntl
import json
import math
import os
from pathlib import Path
import random
import re
import subprocess
import sys
import tempfile
import time
from zoneinfo import ZoneInfo

import ldl_auth
import ldl_homework
import ldl_runtime
import mtop_session

ROOT = Path(__file__).resolve().parent
BASE = mtop_session.STATE_DIR / 'automation'
ZONE = ZoneInfo('Asia/Shanghai')
RNG = random.SystemRandom()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(prefix='.pending-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def read(path):
    return json.loads(path.read_text())


def report(status, **values):
    result = {'status': status, 'at': datetime.now(ZONE).isoformat(), **values}
    save(BASE / 'last-result.json', result)
    print(json.dumps(result, ensure_ascii=False))
    return result


def api(session, name, payload):
    token = ldl_auth.require_account()['credentials']['sso_token']
    result = session.call(name, '1.0', payload,
                          headers={'ssoToken': token, 'alty_sso_token': token})
    if not ldl_auth.gateway_ok(result):
        raise ldl_auth.AuthError('read_rejected:' + ','.join(ldl_auth.ret_codes(result)))
    return result


def check_homework_binding(binding, requirements):
    # The server may rotate taskId while keeping the class assignment.
    pinned_class = binding.get('class_homework_id')
    if pinned_class not in (None, '', 0, '0'):
        if str(requirements.get('class_homework_id')) != str(pinned_class):
            raise RuntimeError('homework_class_changed')
    elif str(requirements['task_id']) != str(binding['task_id']):
        # Older configurations without a class assignment cannot follow a new task.
        raise RuntimeError('homework_task_changed')


def eligibility(session, config):
    # Only read requests are retried after a confirmed SSO rejection.
    for attempt in range(2):
        try:
            requirements = ldl_homework.read_requirements(session)
            check_homework_binding(config, requirements)
            check = api(session, 'mtop.alisports.course.tool.user.homework.check', {
                'bizType': 2, 'type': 2, 'taskId': requirements['task_id']})
            model = ldl_auth.object_value(check.get('data', {}).get('model')) or {}
            return requirements, model
        except ldl_auth.AuthError as error:
            if attempt or 'SSOTOKEN' not in str(error).upper():
                raise
            ldl_auth.refresh(session)


def plan(config, requirements, now, rng=RNG):
    check_homework_binding(config, requirements)
    minimum, maximum = config['distance_m']
    if minimum < int(requirements['minimum_distance_m']):
        raise ValueError('configured_distance_below_requirement')
    fastest, slowest = config['pace_seconds_per_km']
    if fastest < int(requirements['fastest_pace_seconds_per_km']) or slowest > int(requirements['slowest_pace_seconds_per_km']):
        raise ValueError('configured_pace_outside_requirement')
    distance = rng.randint(minimum, maximum)
    minimum_duration = math.ceil(distance * fastest / 1000)
    maximum_duration = math.floor(distance * slowest / 1000)
    if 'duration_seconds' in config:
        minimum_duration = max(minimum_duration, config['duration_seconds'][0])
        maximum_duration = min(maximum_duration, config['duration_seconds'][1])
    if minimum_duration > maximum_duration:
        raise ValueError('duration_and_pace_constraints_conflict')
    duration = rng.randint(minimum_duration, maximum_duration)
    end = int(now.timestamp())
    start = datetime.fromtimestamp(end - duration, ZONE)
    today = now.strftime('%Y%m%d')
    if not str(requirements['start_date']) <= today <= str(requirements['end_date']):
        raise ValueError('outside_homework_dates')
    if start.date() != now.date():
        raise ValueError('record_crosses_midnight')
    valid = any(window['begin'] <= start.strftime('%H:%M:%S') and
                now.strftime('%H:%M:%S') <= window['end']
                for window in requirements['valid_time_windows'])
    if not valid:
        raise ValueError('outside_homework_time_window')
    pace = duration * 1000 / distance
    if not int(requirements['fastest_pace_seconds_per_km']) <= pace <= int(requirements['slowest_pace_seconds_per_km']):
        raise ValueError('rounded_pace_outside_requirement')
    return {'distance_m': distance, 'duration_s': duration,
            'start_time': end - duration, 'end_time': end,
            'pace_seconds_per_km': pace}


def candidates(record, requirements, uid):
    distance, duration = record['distance_m'], record['duration_s']
    speed = distance / duration
    first_km = duration * 1000 / distance
    payload = {'ldluid': str(uid), 'startTime': str(record['start_time']),
        'endTime': str(record['end_time']), 'type': '80',
        'steps': str(round(duration * 170 / 60)), 'speed': str(speed),
        'calorie': '0.0', 'distance': str(float(distance)), 'weatherCode': '0',
        'duration': str(float(duration)), 'cityName': '', 'facticity': '1',
        'fakeProbability': '-1.0', 'platform': 'android',
        'oneKilometerDuration': str(first_km), 'fiveKilometerDuration': '0',
        'tenKilometerDuration': '0', 'halfMarathonDuration': '0',
        'fullMarathonDuration': '0'}
    parts = []
    left = distance
    while left:
        segment = min(1000, left)
        parts.append({'distance': float(segment), 'duration': duration * segment / distance})
        left -= segment
    parts[-1]['duration'] = duration - sum(x['duration'] for x in parts[:-1])
    venues = requirements['allowed_venues']
    if requirements['geofence_required'] and not venues:
        raise ValueError('homework_venue_missing')
    model = dict(payload, geoFenceId=str(venues[0]['id']) if venues else '',
        inPeriodDistance=0, outPeriodDistance=0, stepDistanceRatio='1.0000',
        isRunAbnormal=0, speeds=json.dumps(parts, separators=(',', ':')),
        invalidCodeList=[], status=1)
    course = {'bizType': '2', 'type': '2', 'taskId': str(requirements['task_id']),
              'model': json.dumps(model, ensure_ascii=False, separators=(',', ':'))}
    return {'origin': 'script_generated', 'payload': payload}, course


def bridge(operation, directory):
    subprocess.run([sys.executable, str(ROOT / 'ldl_native_bridge.py'),
                    operation, '--run-dir', str(directory)], check=True, timeout=90)


def confirm(session, directory, receipt, requirements):
    submitted_task = receipt.get('task_id')
    if submitted_task is None:
        # Older receipts did not store the ID; the candidate records what was sent.
        candidate = directory / 'course-submit-candidate.json'
        if candidate.is_file():
            submitted_task = read(candidate).get('taskId')
        if submitted_task is None:
            return None
    detail = api(session, 'mtop.alisports.course.tool.user.homework.score.record.detail',
                 {'sportsStartTime': receipt['record']['start_time'] * 1000})
    save(directory / 'record-detail.json', detail)
    model = ldl_auth.object_value(detail.get('data', {}).get('model')) or {}
    latest = ldl_homework.read_requirements(session)
    try:
        check_homework_binding({
            'task_id': submitted_task,
            'class_homework_id': receipt.get('class_homework_id', requirements.get('class_homework_id')),
        }, latest)
    except RuntimeError:
        return None
    if (str(model.get('taskId')) == str(submitted_task) and
            int(model.get('score', 0)) == receipt['record']['distance_m'] and
            int(model.get('useTime', 0)) == receipt['record']['duration_s'] * 1000 and
            int(latest['completed']) >= int(receipt['progress_before']) + 1):
        return latest
    return None


def run(config, *, check_only=False, immediate=False):
    os.environ.setdefault('LDL_HTTPS_PROXY', config['https_proxy'])
    session = mtop_session.MtopSession()
    requirements, allowed = eligibility(session, config)
    if int(requirements['completed']) >= int(requirements['total_required']):
        return report('all_homework_completed', completed=requirements['completed'])
    if allowed.get('success') not in (True, 'true'):
        return report('skipped_today' if allowed.get('code') == 1 else 'server_not_permitted',
                      reason_code=allowed.get('code'), completed=requirements['completed'])
    if check_only:
        return report('eligible', completed=requirements['completed'])
    now = datetime.now(ZONE)
    day_file = BASE / 'days' / (now.date().isoformat() + '.json')
    if day_file.exists():
        prior = read(day_file)
        if prior['status'] == 'completed':
            return report('already_completed_locally', completed=requirements['completed'])
        directory = BASE / 'runs' / prior['run_id']
        if prior.get('record') and confirm(session, directory, prior, requirements):
            prior['status'] = 'completed'
            save(day_file, prior)
            return report('reconciled_completed')
        return report('needs_review', reason='prior_attempt_not_confirmed', run_id=prior['run_id'])
    if not immediate:
        delay = RNG.randint(0, config['submission_jitter_seconds'])
        print(json.dumps({'status': 'waiting_to_submit', 'delay_seconds': delay,
                          'planned_at': (now + timedelta(seconds=delay)).isoformat()}), flush=True)
        time.sleep(delay)
        requirements, allowed = eligibility(session, config)
        if allowed.get('success') not in (True, 'true'):
            return report('skipped_after_delay', reason_code=allowed.get('code'))
        if datetime.now(ZONE).date() != now.date():
            return report('skipped_date_changed')
    ldl_runtime.prepare()
    now = datetime.now(ZONE)
    record = plan(config, requirements, now)
    run_id = now.strftime('%Y%m%dT%H%M%S') + '-' + str(requirements['task_id'])
    (BASE / 'runs').mkdir(exist_ok=True, mode=0o700)
    directory = BASE / 'runs' / run_id
    directory.mkdir(mode=0o700)
    bridge('user-id', directory)
    uid = str(read(directory / 'ldl-user-id-bridge.json')['uid'])
    if uid != config['ldluid']:
        raise RuntimeError('native_account_changed')
    save(directory / 'ldl-user-id.json', {'ldluid': uid, 'verified_current_account': True})
    payload, course = candidates(record, requirements, uid)
    save(directory / 'run-upload-candidate.json', payload)
    save(directory / 'course-submit-candidate.json', course)
    receipt = {'status': 'pending', 'run_id': run_id, 'record': record,
               'task_id': requirements['task_id'], 'class_homework_id': requirements.get('class_homework_id'),
               'progress_before': int(requirements['completed'])}
    # Persist before the first write. A lost response cannot create a second run.
    save(day_file, receipt)
    try:
        bridge('upload-run', directory)
        uploaded = read(directory / 'native-run-upload-response.json')
        if not ldl_auth.gateway_ok(uploaded) or uploaded.get('data', {}).get('data') != 'success':
            raise RuntimeError('running_upload_rejected')
        bridge('submit-course', directory)
        submitted = read(directory / 'native-course-submit-response.json')
        model = ldl_auth.object_value(submitted.get('data', {}).get('model')) or {}
        if not ldl_auth.gateway_ok(submitted) or model.get('success') not in (True, 'true'):
            raise RuntimeError('course_association_rejected')
        latest = confirm(session, directory, receipt, requirements)
        receipt['status'] = 'completed' if latest else 'awaiting_confirmation'
        save(day_file, receipt)
        return report(receipt['status'], run_id=run_id, distance_m=record['distance_m'],
                      duration_s=record['duration_s'], completed=latest['completed'] if latest else None)
    except Exception:
        receipt['status'] = 'uncertain'
        save(day_file, receipt)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('run', 'check', 'plan', 'status'))
    parser.add_argument('--now', action='store_true', help='Skip the manual random delay')
    args = parser.parse_args(argv)
    BASE.mkdir(parents=True, exist_ok=True, mode=0o700)
    config = read(BASE / 'config.json')
    if args.command == 'status':
        print(json.dumps(read(BASE / 'last-result.json') if (BASE / 'last-result.json').exists()
                         else {'status': 'not_run'}, ensure_ascii=False, indent=2))
        return 0
    if args.command == 'plan':
        result = plan(config, read(mtop_session.STATE_DIR / 'homework-requirements.json'), datetime.now(ZONE))
        print(json.dumps({'preview_only': True, **result}, ensure_ascii=False, indent=2))
        return 0
    with (BASE / 'run.lock').open('a') as lock:
        os.chmod(BASE / 'run.lock', 0o600)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('{"status":"another_run_in_progress"}')
            return 0
        try:
            result = run(config, check_only=args.command == 'check', immediate=args.now)
            return 2 if result['status'] in ('needs_review', 'awaiting_confirmation') else 0
        except Exception as error:
            reason = str(error)
            report('failed', error_type=type(error).__name__,
                   reason=reason if re.fullmatch(r'[a-z][a-z0-9_]{1,95}', reason) else None)
            return 2


if __name__ == '__main__':
    raise SystemExit(main())
