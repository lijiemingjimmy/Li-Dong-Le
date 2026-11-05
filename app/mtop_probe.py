#!/usr/bin/env python3
"""Anonymous H5 feasibility probe, not a login client or homework uploader.

Offline: python3 scripts/mtop_probe.py
Live:    python3 scripts/mtop_probe.py --live --output analysis/h5-probe.json
Login gateway preflight (no auth code):
         python3 scripts/mtop_probe.py --api wechat-preflight --live

The H5 signing algorithm/app key come from the supplied APK's bundled mtop.js.
Compatibility of these native APIs with H5 is experimental. A successful HTTP
response is not successful authentication. No credentials are loaded or saved.
Exit 2 means the live probe did not establish business success; exit 3 is a
transport failure. Dry runs exit 0.
"""
import argparse
import datetime
import hashlib
import http.cookiejar
import json
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request

HOST = "h5api.m.taobao.com"
APP_KEY = "12574478"  # Bundled H5 SDK default; not the native app key.
ALISP_APP_KEY = "24765312"  # AliSportsApi.ALISPORTS_APP_KEY, classes.dex.
WECHAT_APP_ID = "wxae0dbef5cffa211e"  # WechatManager.WECHAT_APPID.
APIS = {
    "homework": ("mtop.alisports.course.tool.class.homework.get", "1.0"),
    "wechat-preflight": ("mtop.alisports.passport.oauth.weixingrant", "2.0"),
}

def sdk_md5(text):
    # This bundled SDK encodes UTF-16 code units individually, including surrogates.
    raw = text.replace("\r\n", "\n").encode("utf-16-le", "surrogatepass")
    encoded = b"".join(
        chr(int.from_bytes(raw[i:i + 2], "little")).encode("utf-8", "surrogatepass")
        for i in range(0, len(raw), 2)
    )
    return hashlib.md5(encoded, usedforsecurity=False).hexdigest()

def sign(token, timestamp, app_key, data):
    # Absent browser cookie yields JavaScript undefined, not an empty string.
    token_text = "undefined" if token is None else token
    return sdk_md5(f"{token_text}&{timestamp}&{app_key}&{data}")

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def token_for(jar, endpoint):
    req = urllib.request.Request(endpoint)
    jar.add_cookie_header(req)
    for part in req.get_header("Cookie", "").split(";"):
        name, sep, value = part.strip().partition("=")
        if sep and name == "_m_h5_tk":
            return value.split("_", 1)[0]
    return None

def build_url(api, version, payload, token, timestamp, app_key=APP_KEY):
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    query = {
        "jsv": "2.6.1", "appKey": app_key, "t": str(timestamp),
        "sign": sign(token, timestamp, app_key, data),
        "api": api, "v": version, "type": "originaljson",
        "dataType": "json", "data": data,
    }
    return f"https://{HOST}/h5/{api}/{version}/?" + urllib.parse.urlencode(query)

def request_once(opener, jar, api, version, payload):
    endpoint = f"https://{HOST}/h5/{api}/{version}/"
    token = token_for(jar, endpoint)
    url = build_url(api, version, payload, token, int(time.time() * 1000))
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://market.m.taobao.com/",
        "Origin": "https://market.m.taobao.com",
    })
    started = time.monotonic()
    try:
        response = opener.open(req, timeout=20)
    except urllib.error.HTTPError as exc:
        response = exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        # Do not print URLs, proxy credentials, or raw exception strings.
        return {"transport_error": True, "error_type": type(exc).__name__, "reason_type": type(getattr(exc, "reason", None)).__name__, "elapsed_ms": round((time.monotonic()-started)*1000)}
    with response:
        raw = response.read(65537)
        result = {
            "http_status": response.code,
            "content_type": response.headers.get_content_type(),
            "elapsed_ms": round((time.monotonic()-started)*1000),
            "body_truncated": len(raw) > 65536,
            "body_sha256": hashlib.sha256(raw).hexdigest(),
            "request_had_h5_token": token is not None,
            "cookie_names": sorted({c.name for c in jar}),
        }
        try:
            body = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            result["json_response"] = False
            return result
        if not isinstance(body, dict):
            result["json_response"] = False
            return result
        result["json_response"] = True
        ret = body.get("ret", [])
        result["ret"] = [str(x)[:300] for x in ret[:10]] if isinstance(ret, list) else [str(ret)[:300]]
        data = body.get("data")
        result["data_present"] = bool(data)
        if isinstance(data, dict):
            result["business_code"] = data.get("alispCode")
            message = data.get("alispMsg")
            result["business_message"] = str(message)[:300] if message is not None else None
        return result

def probe(kind, live=False, class_homework_id=None, biz_type=None):
    api, version = APIS[kind]
    payload = {"classHomeworkId": class_homework_id} if kind == "homework" and class_homework_id else {}
    if kind == "wechat-preflight":
        payload = {"alisp_app_key": ALISP_APP_KEY, "weixin_appid": WECHAT_APP_ID}
    if kind == "homework" and biz_type is not None:
        payload["bizType"] = biz_type
    report = {
        "time_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "api": api, "version": version, "endpoint": f"https://{HOST}/h5/{api}/{version}/",
        "transport": "bundled H5 SDK candidate", "h5_app_key": APP_KEY,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "native_app_key_verified": False, "live": live,
        "payload_keys": sorted(payload), "credentials_supplied": False,
        "complete_business_parameters": False,
        "login_verified": False, "homework_read_verified": False,
        "attempts": [],
        "limitations": [
            "Anonymous transport/API compatibility test only.",
            "No WeChat auth code or authenticated user session.",
            "No classHomeworkId unless explicitly supplied; no score submission.",
            "H5 SDK default app key may not be authorized for these APIs.",
        ],
    }
    if not live:
        report["status"] = "dry_run"
        return report
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(NoRedirect(), urllib.request.HTTPCookieProcessor(jar))
    for attempt in range(2):
        before = token_for(jar, report["endpoint"])
        response = request_once(opener, jar, api, version, payload)
        report["attempts"].append(response)
        ret = ",".join(response.get("ret", []))
        after = token_for(jar, report["endpoint"])
        # One fresh-token retry, no challenge solving or repeated access attempts.
        if attempt == 0 and after and after != before and any(
            marker in ret for marker in ("TOKEN_EMPTY", "TOKEN_EXOIRED")
        ):
            continue
        break
    last = report["attempts"][-1]
    if last.get("transport_error"):
        report["status"] = "transport_error"
    elif any(x.startswith("SUCCESS") for x in last.get("ret", [])):
        report["status"] = ("business_rejected" if last.get("business_code") not in (None, 200)
                            else "gateway_success_business_unverified")
    else:
        report["status"] = "request_not_accepted"
    return report

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", choices=APIS, default="homework")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--class-homework-id")
    parser.add_argument("--biz-type", help="Explicit hypothesis for homework query; 2 is observed in the sibling course score API")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.api != "homework" and (args.class_homework_id or args.biz_type):
        parser.error("--class-homework-id / --biz-type are only valid for homework")
    report = probe(args.api, args.live, args.class_homework_id, args.biz_type)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        with args.output.open("x", encoding="utf-8") as output:
            output.write(text + "\n")
    print(text)
    if report["status"] == "transport_error":
        return 3
    return 0 if report["status"] == "dry_run" else 2

if __name__ == "__main__":
    raise SystemExit(main())
