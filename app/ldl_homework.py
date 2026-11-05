#!/usr/bin/env python3
"""Read the signed-in user's course requirements using the shipped H5 contract."""
import argparse
import json
from datetime import datetime, timezone
import ldl_auth
import mtop_session

API = 'mtop.alisports.course.tool.user.homework.get'


def user_value(model, key):
    value = model.get(key)
    return value.get('user') if isinstance(value, dict) else value


def summarize(model):
    minimum_pace = user_value(model, 'maxSpeed')
    maximum_pace = user_value(model, 'minSpeed')
    fence = model.get('geoFence') or {}
    return {
        'name': model.get('name'),
        'school': (model.get('school') or {}).get('schoolName'),
        'class': (model.get('classInfo') or {}).get('className'),
        'class_homework_id': model.get('classHomeworkId'),
        'task_id': model.get('taskId'),
        'start_date': model.get('startDate'), 'end_date': model.get('endDate'),
        'minimum_distance_m': user_value(model, 'minDistance'),
        # Frontend formats these values /60 and %60 as minutes and seconds/km.
        'fastest_pace_seconds_per_km': minimum_pace,
        'slowest_pace_seconds_per_km': maximum_pace,
        'total_required': model.get('totalTimes'), 'completed': model.get('completeNum'),
        'daily_max': user_value(model, 'dayMaxTimes'),
        'weekly_max': user_value(model, 'weekMaxTimes'),
        'valid_time_windows': [
            {'begin': x.get('beginTime'), 'end': x.get('endTime')}
            for x in model.get('validTimeList', [])
        ],
        'geofence_required': fence.get('enabled'),
        'allowed_venues': [
            {'id': x.get('id'), 'name': x.get('name')}
            for x in fence.get('geoFenceList', [])
        ],
        'ai_exchange': {
            'enabled': (model.get('exchangeScheme') or {}).get('enabled'),
            'completed': model.get('completeExchangeNum'),
        },
    }


def read_requirements(session=None):
    token = ldl_auth.require_account()['credentials']['sso_token']
    session = session or mtop_session.MtopSession()
    body = session.call(API, '1.0', {'bizType': 2},
                        headers={'ssoToken': token, 'alty_sso_token': token})
    if not ldl_auth.gateway_ok(body):
        raise ldl_auth.AuthError('homework_query_rejected:' + ','.join(ldl_auth.ret_codes(body)))
    model = ldl_auth.object_value((body.get('data') or {}).get('model'))
    if not model or not model.get('taskId'):
        raise ldl_auth.AuthError('homework_model_missing')
    mtop_session.save_private('homework-current.json', body)
    summary = summarize(model)
    summary['queried_at'] = datetime.now(timezone.utc).isoformat()
    mtop_session.save_private('homework-requirements.json', summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cached', action='store_true', help='Summarize last stored response without network')
    args = parser.parse_args()
    try:
        if args.cached:
            path = mtop_session.STATE_DIR / 'homework-current.json'
            result = summarize(json.loads(path.read_text())['data']['model'])
        else:
            result = read_requirements()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except ldl_auth.AuthError as error:
        print(json.dumps({'status': 'failed', 'reason': str(error)}))
    except Exception as error:
        print(json.dumps({'status': 'failed', 'error_type': type(error).__name__}))
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
