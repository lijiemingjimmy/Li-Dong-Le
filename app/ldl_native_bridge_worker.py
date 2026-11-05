#!/usr/bin/env python3
"""Internal worker for LDL's existing native WindVane/MTOP bridge.

Use ldl_native_bridge.py; this worker connects to its private loopback ADB forward.
Write operations use the reviewed project candidates and retain attempt journals.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import socket
import struct
import sys
import tempfile
import ldl_auth

import mtop_session

RUN_DIR = Path(sys.argv[3]).resolve() if len(sys.argv) > 3 else mtop_session.STATE_DIR
if RUN_DIR != mtop_session.STATE_DIR:
    root = (mtop_session.STATE_DIR / 'automation' / 'runs').resolve()
    if not RUN_DIR.is_relative_to(root) or not RUN_DIR.is_dir():
        raise ValueError('Invalid automation run directory')

def save_result(name, value):
    if Path(name).name != name:
        raise ValueError('Expected state basename')
    if RUN_DIR == mtop_session.STATE_DIR:
        mtop_session.save_private(name, value)
    else:
        fd, temporary = tempfile.mkstemp(prefix='.pending-', dir=RUN_DIR)
        try:
            with os.fdopen(fd, 'w') as stream:
                json.dump(value, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, RUN_DIR / name)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    owner = RUN_DIR.stat()
    if os.geteuid() == 0:
        os.chown(RUN_DIR / name, owner.st_uid, owner.st_gid)


def list_targets(socket_name):
    with socket.socket(socket.AF_INET) as connection:
        connection.settimeout(5)
        connection.connect(('127.0.0.1', int(socket_name)))
        connection.sendall(b'GET /json/list HTTP/1.1\r\nHost: localhost\r\n\r\n')
        raw = b''
        while b'\r\n\r\n' not in raw:
            chunk = connection.recv(4096)
            if not chunk or len(raw) > 65536:
                raise RuntimeError('Invalid target response')
            raw += chunk
        head, _, body = raw.partition(b'\r\n\r\n')
        headers = dict(line.decode().split(':', 1) for line in head.split(b'\r\n')[1:])
        length = int(next(value for key, value in headers.items() if key.lower() == 'content-length'))
        if length > 1048576:
            raise RuntimeError('Target response too large')
        while len(body) < length:
            chunk = connection.recv(65536)
            if not chunk:
                raise RuntimeError('Incomplete target response')
            body += chunk
        return json.loads(body[:length])


operation = sys.argv[2] if len(sys.argv) > 2 else 'user-id'
if operation in ('upload-run', 'submit-course'):
    journal_name = 'native-run-upload-attempt.json' if operation == 'upload-run' else 'native-course-submit-attempt.json'
    if (RUN_DIR / journal_name).exists():
        print(json.dumps({'status': 'already_attempted', 'operation': operation,
                          'journal': journal_name, 'request_sent': False}))
        raise SystemExit(2)
rows = list_targets(sys.argv[1])
save_result('webview-list-current.json', rows)
allowed = ('https://market.m.taobao.com/app/front-end-group/course-tools-student/',
           'https://market.m.taobao.com/app/alisports-fe/sports-data/')
target = next(row for row in rows if row.get('url', '').startswith(allowed))
s = socket.socket(socket.AF_INET)
s.settimeout(30)
s.connect(('127.0.0.1', int(sys.argv[1])))
key = base64.b64encode(os.urandom(16)).decode()
request = (f'GET /devtools/page/{target["id"]} HTTP/1.1\r\nHost: localhost\r\n'
           f'Upgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n'
           'Sec-WebSocket-Version: 13\r\n\r\n')
s.sendall(request.encode())
buf = b''
while b'\r\n\r\n' not in buf:
    chunk = s.recv(4096)
    if not chunk or len(buf) > 65536:
        raise RuntimeError('Invalid WebSocket handshake response')
    buf += chunk
head, _, buf = buf.partition(b'\r\n\r\n')
accept = base64.b64encode(hashlib.sha1((key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest())
if not head.startswith(b'HTTP/1.1 101') or accept not in head:
    raise RuntimeError('WebSocket handshake failed')
operations = {
    'user-id': ('LeWVJSBridge', 'getUserId', {}, 'ldl-user-id-bridge.json'),
}
if operation == 'homework':
    token = ldl_auth.require_account()['credentials']['sso_token']
    operations[operation] = ('MtopWVPlugin', 'send', {
        'api': 'mtop.alisports.course.tool.user.homework.get', 'v': '1.0',
        'method': 'POST', 'param': {'bizType': 2}, 'dataType': 'json',
        'timeout': 20000, 'needLogin': False,
        'ext_headers': {'ssoToken': token, 'alty_sso_token': token},
    }, 'native-homework-response.json')
if operation == 'upload-run':
    token = ldl_auth.require_account()['credentials']['sso_token']
    candidate = json.loads((RUN_DIR / 'run-upload-candidate.json').read_text())
    payload = candidate['payload']
    uid = json.loads((RUN_DIR / 'ldl-user-id.json').read_text())
    if not uid.get('verified_current_account') or payload.get('ldluid') != uid['ldluid']:
        raise ValueError('Current user ID must match the upload candidate')
    save_result('native-run-upload-attempt.json', {'startTime': payload['startTime'],
                'payload_sha256': hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()})
    operations[operation] = ('MtopWVPlugin', 'send', {
        'api': 'mtop.alisports.ldl.run.activity.upload', 'v': '1.0',
        'method': 'POST', 'param': payload, 'dataType': 'json',
        'timeout': 20000, 'needLogin': False,
        'ext_headers': {'ssoToken': token, 'alty_sso_token': token},
    }, 'native-run-upload-response.json')
if operation == 'submit-course':
    token = ldl_auth.require_account()['credentials']['sso_token']
    uploaded = json.loads((RUN_DIR / 'native-run-upload-response.json').read_text())
    if not ldl_auth.gateway_ok(uploaded) or uploaded.get('data', {}).get('data') != 'success':
        raise ValueError('Running summary upload not confirmed')
    candidate = json.loads((RUN_DIR / 'course-submit-candidate.json').read_text())
    run = json.loads((RUN_DIR / 'run-upload-candidate.json').read_text())['payload']
    model = json.loads(candidate['model'])
    if model['startTime'] != run['startTime'] or model['ldluid'] != run['ldluid']:
        raise ValueError('Course association must match uploaded record')
    journal = RUN_DIR / 'native-course-submit-attempt.json'
    if journal.exists():
        raise ValueError('Course submission already attempted; inspect saved result before retry')
    run_journal = json.loads((RUN_DIR / 'native-run-upload-attempt.json').read_text())
    if run_journal['payload_sha256'] != hashlib.sha256(json.dumps(run, sort_keys=True).encode()).hexdigest():
        raise ValueError('Upload journal does not match current record')
    save_result(journal.name, {'startTime': run['startTime'], 'taskId': candidate['taskId']})
    operations[operation] = ('MtopWVPlugin', 'send', {
        'api': 'mtop.alisports.course.tool.user.homework.score.update', 'v': '1.0',
        'method': 'POST', 'param': candidate, 'dataType': 'json',
        'timeout': 20000, 'needLogin': False,
        'ext_headers': {'ssoToken': token, 'alty_sso_token': token},
    }, 'native-course-submit-response.json')
if operation not in operations:
    raise ValueError('Unsupported bridge operation')
plugin, action, parameters, output_file = operations[operation]
expression = '''new Promise((resolve,reject)=>{
 const t=setTimeout(()=>reject(new Error('bridge timeout')),25000);
 if(!window.WindVane){clearTimeout(t);reject(new Error('bridge missing'));return;}
 window.WindVane.call(PLUGIN,ACTION,PARAMETERS,v=>{clearTimeout(t);resolve(v)},
 e=>{clearTimeout(t);resolve({bridge_failure:true,response:e})});
})'''.replace('PLUGIN', json.dumps(plugin)).replace('ACTION', json.dumps(action)).replace('PARAMETERS', json.dumps(parameters))
raw = json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {
    'expression': expression, 'awaitPromise': True, 'returnByValue': True}}).encode()
mask = os.urandom(4)
length = len(raw)
prefix = bytes([0x81, 0x80 | length]) if length < 126 else b'\x81\xfe' + struct.pack('!H', length)
s.sendall(prefix + mask + bytes(c ^ mask[i % 4] for i, c in enumerate(raw)))

def take(n):
    global buf
    while len(buf) < n:
        chunk = s.recv(65536)
        if not chunk:
            raise RuntimeError('WebSocket closed')
        buf += chunk
    result, buf = buf[:n], buf[n:]
    return result

try:
    while True:
        a, b = take(2)
        length = b & 127
        if length == 126:
            length = struct.unpack('!H', take(2))[0]
        elif length == 127:
            length = struct.unpack('!Q', take(8))[0]
        if length > 1048576 or b & 128 or a & 15 != 1 or not a & 128:
            raise RuntimeError('Unsupported WebSocket frame')
        reply = json.loads(take(length))
        if reply.get('id') != 1:
            continue
        if reply.get('error') or reply.get('result', {}).get('exceptionDetails'):
            raise RuntimeError('Native bridge evaluation failed')
        value = reply['result']['result'].get('value')
        save_result(output_file, value)
        data = value.get('data', {}) if isinstance(value, dict) else {}
        model = ldl_auth.object_value(data.get('model')) or {}
        print(json.dumps({'saved': True, 'operation': operation,
                          'ret_codes': ldl_auth.ret_codes(value),
                          'completed': model.get('completeNum') if operation == 'homework' else None,
                          'result_keys': list(value) if isinstance(value, dict) else [],
                          'result_type': type(value).__name__}))
        break
finally:
    s.close()
