"""Small MTOP session client. Cookie state is private, not proof of app login."""
import http.cookiejar
import json
import os
from pathlib import Path
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from mtop_probe import HOST, NoRedirect, build_url, token_for

STATE_DIR = Path(os.environ.get("LDL_STATE_DIR", "/data/state"))
# WindVane WVAppParams.appKey in the supplied APK (formal environment is ONLINE).
LDL_H5_APP_KEY = "24827819"

def private_dir():
    STATE_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    if STATE_DIR.is_symlink():
        raise RuntimeError("Refusing symlink state directory")
    STATE_DIR.chmod(0o700)
    return STATE_DIR

def save_private(name, data):
    if Path(name).name != name:
        raise ValueError("State filename must be a basename")
    directory = private_dir()
    fd, temporary = tempfile.mkstemp(prefix=".pending-", dir=directory)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, directory / name)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

class MtopSession:
    def __init__(self):
        directory = private_dir()
        self.cookie_path = directory / "h5-cookies.txt"
        if self.cookie_path.is_symlink():
            raise RuntimeError("Refusing symlink cookie file")
        self.jar = http.cookiejar.MozillaCookieJar(str(self.cookie_path))
        if self.cookie_path.exists():
            self.cookie_path.chmod(0o600)
            self.jar.load(ignore_discard=True, ignore_expires=False)
        handlers = [NoRedirect(), urllib.request.HTTPCookieProcessor(self.jar)]
        # Explicit per-process routing; leaves host and Android proxy settings alone.
        proxy = os.environ.get("LDL_HTTPS_PROXY")
        if proxy:
            handlers.append(urllib.request.ProxyHandler({"https": proxy}))
        self.opener = urllib.request.build_opener(*handlers)

    def save(self):
        fd, temporary = tempfile.mkstemp(prefix=".cookies-", dir=private_dir())
        os.close(fd)
        try:
            self.jar.save(temporary, ignore_discard=True, ignore_expires=False)
            os.chmod(temporary, 0o600)
            os.replace(temporary, self.cookie_path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def call(self, api, version, payload, *, app_key=LDL_H5_APP_KEY, headers=None,
             method="GET"):
        method = method.upper()
        if method not in ("GET", "POST"):
            raise ValueError("Unsupported request method")
        endpoint = f"https://{HOST}/h5/{api}/{version}/"
        for attempt in range(2):
            before = token_for(self.jar, endpoint)
            url = build_url(api, version, payload, before, int(time.time() * 1000), app_key=app_key)
            request_headers = {
                "User-Agent": "Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36",
                "Accept": "application/json",
                "Referer": "https://market.m.taobao.com/",
                "Origin": "https://market.m.taobao.com",
            }
            if headers:
                request_headers.update(headers)
            request_body = None
            if method == "POST":
                # Sign the same compact JSON as GET, but send data in the form body.
                parts = urllib.parse.urlsplit(url)
                query = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
                request_body = urllib.parse.urlencode(
                    [(key, value) for key, value in query if key == "data"]
                ).encode("ascii")
                url = urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(
                    [(key, value) for key, value in query if key != "data"]
                )))
                request_headers["Content-Type"] = "application/x-www-form-urlencoded;charset=UTF-8"
            req = urllib.request.Request(url, data=request_body,
                                         headers=request_headers, method=method)
            try:
                response = self.opener.open(req, timeout=20)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                raw = response.read(1048577)
                if len(raw) > 1048576:
                    raise RuntimeError("Response exceeded one MiB")
                body = json.loads(raw)
            if not isinstance(body, dict):
                raise RuntimeError("Unexpected response shape")
            self.save()
            ret = str(body.get("ret", []))
            after = token_for(self.jar, endpoint)
            if attempt == 0 and after and before != after and any(
                text in ret for text in ("TOKEN_EMPTY", "TOKEN_EXOIRED", "TOKEN_EXPIRED")
            ):
                continue
            return body
        raise RuntimeError("Retry limit reached")
