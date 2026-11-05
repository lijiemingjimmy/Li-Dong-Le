#!/usr/bin/env python3
"""Experimental LDL auth client, based on supplied APK evidence.

status: local credential metadata only, no network.
login: prompt for a valid WeChat code (or --code-stdin), exchange once.
verify: read student information with the saved SSO; never submit a score.
refresh: explicitly request a new SSO using saved access_token.

This does not obtain a WeChat code or generate an authorization QR. The native
APIs' authenticated compatibility with the H5 transport is not yet verified.
Credentials stay in project/state with mode 0600. No secrets are printed.
"""
import argparse
from datetime import datetime, timezone
import getpass
import json
import re
import sys
import warnings

import mtop_session
from mtop_probe import ALISP_APP_KEY, WECHAT_APP_ID

ACCOUNT_FILE = "ldl-account.json"
PENDING_FILE = "wechat-binding-pending.json"
FIELDS = ("access_token", "sso_token", "alitoken", "aliuid", "appuid", "token")


class AuthError(Exception):
    """Message must be a fixed local diagnostic, never raw server content."""


def now():
    return datetime.now(timezone.utc).isoformat()


def object_value(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            return None
    return value if isinstance(value, dict) else None


def ret_codes(body):
    values = body.get("ret", []) if isinstance(body, dict) else []
    if not isinstance(values, list) or not values:
        return []
    codes = []
    for value in values:
        if not isinstance(value, str):
            return []
        code = value.split("::", 1)[0]
        # Never print arbitrary server text, including echoed credentials.
        codes.append(code if re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", code) else "UNRECOGNIZED")
    return codes


def gateway_ok(body):
    return ret_codes(body) == ["SUCCESS"]


def business_data(body):
    if not gateway_ok(body):
        raise AuthError("gateway_rejected")
    data = object_value(body.get("data"))
    if data is None:
        raise AuthError("missing_business_data")
    code = data.get("alispCode")
    if isinstance(code, bool) or not isinstance(code, (int, str)):
        raise AuthError("missing_business_code")
    if str(code) not in ("200", "21", "102"):
        raise AuthError("business_rejected")
    return int(code), object_value(data.get("alispData"))


def clean_credentials(value):
    if not isinstance(value, dict):
        raise AuthError("missing_credentials")
    result = {}
    for name in FIELDS:
        item = value.get(name)
        if isinstance(item, int) and not isinstance(item, bool) and name in ("aliuid", "appuid"):
            item = str(item)
        if isinstance(item, str) and item and item.strip() == item and not any(ord(c) < 32 or ord(c) == 127 for c in item):
            result[name] = item
    if not result.get("access_token") or not result.get("sso_token"):
        raise AuthError("incomplete_credentials")
    return result


def read_account():
    path = mtop_session.STATE_DIR / ACCOUNT_FILE
    if path.is_symlink():
        raise AuthError("symlink_account_file")
    if not path.exists():
        return None
    if path.stat().st_size > 1048576:
        raise AuthError("oversized_account_file")
    try:
        account = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError):
        raise AuthError("invalid_account_file") from None
    if not isinstance(account, dict) or account.get("schema_version") != 1:
        raise AuthError("unsupported_account_file")
    clean_credentials(account.get("credentials"))
    return account


def require_account():
    account = read_account()
    if account is None:
        raise AuthError("authorization_required")
    return account


def accept_exchange(body):
    code, data = business_data(body)
    if code in (21, 102):
        token = data.get("bindtoken") if data else None
        if not isinstance(token, str) or not token:
            raise AuthError("missing_bindtoken")
        mtop_session.save_private(PENDING_FILE, {
            "schema_version": 1, "received_at": now(), "business_code": code,
            "bindtoken": token,
        })
        return {"status": "phone_binding_required" if code == 102 else "account_conflict",
                "business_code": code, "credentials_saved": False}
    credentials = clean_credentials(data)
    account = {"schema_version": 1, "received_at": now(),
               "source": "wechat_code_exchange", "credentials": credentials,
               "exchange_succeeded": True, "student_query_succeeded_at": None}
    mtop_session.save_private(ACCOUNT_FILE, account)
    return {"status": "credentials_saved_unverified", "credentials_saved": True,
            "credential_fields": sorted(credentials)}


def login(code, session=None):
    if not isinstance(code, str) or not code or len(code) > 4096 or any(c.isspace() or ord(c) < 32 for c in code):
        raise AuthError("invalid_authorization_code")
    session = session if session is not None else mtop_session.MtopSession()
    body = session.call("mtop.alisports.passport.oauth.weixingrant", "2.0", {
        "alisp_app_key": ALISP_APP_KEY, "weixin_appid": WECHAT_APP_ID,
        "weixin_code": code,
    })
    return accept_exchange(body)


def status():
    account = read_account()
    if account is None:
        return {"status": "authorization_required", "credentials_present": False,
                "network_checked": False,
                "gateway_cookie_file_present": (mtop_session.STATE_DIR / "h5-cookies.txt").is_file()}
    return {"status": "credentials_present_validity_unknown", "credentials_present": True,
            "network_checked": False, "received_at": account.get("received_at"),
            "last_student_query_succeeded_at": account.get("student_query_succeeded_at"),
            "credential_fields": sorted(clean_credentials(account["credentials"]))}


def verify(session=None):
    account = require_account()
    credentials = clean_credentials(account["credentials"])
    session = session if session is not None else mtop_session.MtopSession()
    body = session.call("mtop.alisports.ldl.company.member.simple.get", "1.0", {},
                        headers={"ssoToken": credentials["sso_token"]})
    if not gateway_ok(body):
        raise AuthError("student_query_gateway_rejected")
    data = object_value(body.get("data"))
    model = object_value(data.get("model")) if data else None
    # A non-empty model follows PersonDataProvider's observed response contract.
    # This does not establish the task list or the account's current run rules.
    if not model:
        raise AuthError("student_query_model_missing")
    account["student_query_succeeded_at"] = now()
    mtop_session.save_private(ACCOUNT_FILE, account)
    return {"status": "student_query_succeeded", "network_checked": True,
            "checked_at": account["student_query_succeeded_at"],
            "homework_access_verified": False}


def refresh(session=None):
    account = require_account()
    credentials = clean_credentials(account["credentials"])
    session = session if session is not None else mtop_session.MtopSession()
    body = session.call("mtop.alisports.passport.account.ssotokenrefresh", "2.0",
                        {"secret": credentials["access_token"]})
    code, data = business_data(body)
    if code != 200 or not data:
        raise AuthError("refresh_rejected")
    token = data.get("sso_token")
    # Validate the replacement before overwriting the previously saved state.
    if not isinstance(token, str) or not token:
        raise AuthError("refresh_token_missing")
    replacement = dict(credentials, sso_token=token)
    validated = clean_credentials(replacement)
    account["credentials"] = validated
    account["sso_refreshed_at"] = now()
    account["student_query_succeeded_at"] = None
    mtop_session.save_private(ACCOUNT_FILE, account)
    return {"status": "sso_refreshed_unverified", "refreshed_at": account["sso_refreshed_at"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status", help="Read local metadata; no network")
    command = commands.add_parser("login", help="Exchange a user-authorized WeChat code")
    command.add_argument("--code-stdin", action="store_true", help="Read one code from stdin, never shell arguments")
    commands.add_parser("verify", help="Read student information with saved SSO")
    commands.add_parser("refresh", help="Refresh SSO with saved access_token")
    args = parser.parse_args(argv)
    try:
        if args.command == "login":
            if args.code_stdin:
                code = sys.stdin.readline(4098).strip()
            else:
                with warnings.catch_warnings():
                    warnings.simplefilter("error", getpass.GetPassWarning)
                    code = getpass.getpass("微信授权 code（输入隐藏）: ").strip()
            result = login(code)
        else:
            result = {"status": status, "verify": verify, "refresh": refresh}[args.command]()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if result["status"] in ("authorization_required", "phone_binding_required", "account_conflict") else 0
    except AuthError as error:
        print(json.dumps({"status": "failed", "reason": str(error)}))
        return 2
    except (Exception, KeyboardInterrupt) as error:
        # urllib exceptions may embed a URL containing code/tokens. Never echo it.
        print(json.dumps({"status": "failed", "reason": "local_or_transport_error",
                          "error_type": type(error).__name__}))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
