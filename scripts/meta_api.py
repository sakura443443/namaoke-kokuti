"""Meta Graph API の、いちばん薄い包み。

外から入れるライブラリは使いません（urllib と json だけ）。
入れるものが増えるほど、動かなくなる原因も増えるためです。

エラーが起きたら、Meta が返した説明をそのまま持ち回ります。
「なぜ投稿できなかったか」が後から必ずわかるようにするためです。
"""

import json
import urllib.error
import urllib.parse
import urllib.request

API_VERSION = "v25.0"
BASE = f"https://graph.facebook.com/{API_VERSION}"

TIMEOUT = 120  # Meta が画像を取りに行くので、少し長めに待ちます


class GraphError(Exception):
    """Meta が返したエラー。message に日本語の説明を足して持ちます。"""

    def __init__(self, path, payload):
        self.path = path
        self.payload = payload
        err = (payload or {}).get("error", {})
        self.code = err.get("code")
        self.subcode = err.get("error_subcode")
        self.detail = err.get("message", str(payload))
        super().__init__(f"{path} でエラー（code={self.code}）: {self.detail}")


def _request(method, path, params, token):
    params = {k: v for k, v in (params or {}).items() if v not in (None, "", [])}
    params["access_token"] = token

    url = f"{BASE}/{path.lstrip('/')}"
    data = None
    if method == "POST":
        data = urllib.parse.urlencode(params).encode("utf-8")
    else:
        url = f"{url}?{urllib.parse.urlencode(params)}"

    req = urllib.request.Request(url, data=data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
            return json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            payload = json.loads(body)
        except ValueError:
            payload = {"error": {"message": body}}
        raise GraphError(path, payload) from None
    except urllib.error.URLError as e:
        raise GraphError(path, {"error": {"message": f"通信できませんでした: {e.reason}"}}) from None


def get(path, params, token):
    return _request("GET", path, params, token)


def post(path, params, token):
    return _request("POST", path, params, token)


def check_token(token):
    """トークンが生きているか調べます。生きていれば名前を返します。"""
    return get("me", {"fields": "id,name"}, token)
