#!/usr/bin/env python3
"""GitHub の Issue を使って、投稿前の承認をやりとりします。

  open      木曜：下書きを Issue として立てる
  approval  金曜：承認のコメントがあるか調べる（あれば exit 0、無ければ exit 3）
  comment   結果をコメントする（--close で閉じる）

承認できるのは、このリポジトリの持ち主だけです。
公開リポジトリなので、他の人のコメントは承認として扱いません。
"""

import argparse
import datetime as dt
import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
LABEL = "告知"

# 「OK」は、告知文の中にも出てきます（例：手ぶらでOK）。
# 語として単独で書かれたときだけ承認と見なすため、区切りを見ています。
APPROVE_RE = re.compile(r"\bapprove\b|承認|\bok\b", re.I)

# 一度 approve したあとで気が変わることもあります。
# 新しいコメントに取りやめの言葉があれば、そちらを優先します。
CANCEL_RE = re.compile(r"やめ|中止|取り消|取消|キャンセル|\bcancel\b|\bstop\b", re.I)


def api(path, method="GET", body=None):
    token = os.environ["GITHUB_TOKEN"]
    url = f"https://api.github.com{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "namaoke-kokuti",
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as res:
            return json.loads(res.read().decode("utf-8") or "null")
    except urllib.error.HTTPError as e:
        raise SystemExit(f"GitHub API {path} で失敗しました: {e.code} {e.read().decode('utf-8', 'replace')}")


def repo():
    return os.environ["GITHUB_REPOSITORY"]


def owner():
    return repo().split("/")[0]


def title_for(draft):
    d = dt.date.fromisoformat(draft["開催日"])
    return f"{d.month}/{d.day}（水）の告知 — 承認をお願いします"


def find_issue(draft):
    """この開催日の Issue を探します（開いていても閉じていても）。"""
    for issue in api(f"/repos/{repo()}/issues?state=all&labels={urllib.parse.quote(LABEL)}&per_page=50"):
        if issue["title"] == title_for(draft):
            return issue
    return None


def cmd_open(draft, draft_path):
    if find_issue(draft):
        print("この日の Issue はもうあります。作りません。")
        return

    cfg = json.loads((ROOT / "data" / "config.json").read_text(encoding="utf-8"))
    base = cfg["image_base_url"].rstrip("/")
    d = dt.date.fromisoformat(draft["開催日"])
    miss = draft["アカウント未登録"]["instagram"]
    tags = draft.get("user_tags") or []

    body = f"""**{d.month}月{d.day}日（水）の生バンドカラオケ**の告知です。
明日の**金曜11時**に、Instagram と Facebook へ投稿します。

## 投稿してよければ

このページの下のコメント欄に **`approve`** と書いて送ってください。
（このお知らせメールに、そのまま返信しても届きます）

**承認がないと投稿しません。** うっかり古い内容が出てしまうのを防ぐためです。

## 直したいところがあるとき

直した**全文**を ``` で囲んでコメントし、同じコメントに `approve` も書いてください。
その文で投稿します。1つ目の枠が Instagram 用、2つ目が Facebook 用です
（1つだけなら、両方にその文を使います）。

---

## 今回のメンバー（第{draft['第何週']}水曜）

{chr(10).join('- ' + m['name'] + '（' + m['instrument'] + '）' + ('　@' + m['ig'] if m.get('ig') else '　※アカウント未登録') for m in draft['メンバー'])}

タグ付け：{'、'.join('@' + t['username'] for t in tags) if tags else '（今回はなし）'}
{('' if not miss else chr(10) + '> ℹ️ ' + '、'.join(miss) + ' さんの Instagram がわかったら、`data/hosts.json` に書き足してください。次回から自動でタグが付きます。')}

## 出る画像

| フィード | ストーリー |
|---|---|
| <img src="{base}/feed-1.jpg" width="200"> | <img src="{base}/story-1.jpg" width="120"> |
| <img src="{base}/feed-2.jpg" width="200"> | <img src="{base}/story-2.jpg" width="120"> |

## Instagram の本文

```
{draft['captions']['instagram']}
```

## Facebook の本文

```
{draft['captions']['facebook']}
```

<!-- draft: {draft_path} -->
"""
    issue = api(f"/repos/{repo()}/issues", "POST",
                {"title": title_for(draft), "body": body, "labels": [LABEL]})
    print(f"Issue を立てました: {issue['html_url']}")


def set_output(key, value):
    """GitHub Actions の次の手順に、結果を渡します。"""
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{key}={value}\n")


def cmd_approval(draft):
    issue = find_issue(draft)
    if not issue:
        set_output("approved", "false")
        raise SystemExit("この日の Issue が見つかりません。木曜の下書きが作られなかったようです。")

    comments = api(f"/repos/{repo()}/issues/{issue['number']}/comments?per_page=100")
    for c in reversed(comments):  # 新しいコメントから順に見ます
        if c["user"]["login"].lower() != owner().lower():
            continue
        body = c["body"] or ""
        # 差し替え本文には「OK」などが含まれるので、判定からは外します。
        stripped = re.sub(r"```.*?```", "", body, flags=re.S)

        if CANCEL_RE.search(stripped):
            print(f"取りやめのコメントがありました（{c['user']['login']} さん）。今週は投稿しません。")
            set_output("approved", "false")
            sys.exit(3)

        if not APPROVE_RE.search(stripped):
            continue

        blocks = [b.strip("\n") for b in re.findall(r"```(?:[a-zA-Z]*\n)?(.*?)```", body, flags=re.S)]
        print(f"承認を確認しました（{c['user']['login']} さん）")
        result = {"issue": issue["number"], "override": {}}
        if blocks:
            result["override"]["instagram"] = blocks[0]
            result["override"]["facebook"] = blocks[1] if len(blocks) > 1 else blocks[0]
            print(f"本文の差し替えが {len(blocks)} つ入っていました。")
        pathlib.Path(".approval.json").write_text(
            json.dumps(result, ensure_ascii=False), encoding="utf-8")
        set_output("approved", "true")
        return

    # 承認が無いのは、故障ではありません。「今週は出さない」というだけです。
    print("承認のコメントがまだありません。今週は投稿を見送ります。")
    set_output("approved", "false")
    sys.exit(3)


def cmd_comment(draft, text, close):
    issue = find_issue(draft)
    if not issue:
        print("Issue が見つからないので、コメントできませんでした。")
        return
    api(f"/repos/{repo()}/issues/{issue['number']}/comments", "POST", {"body": text})
    if close:
        api(f"/repos/{repo()}/issues/{issue['number']}", "PATCH", {"state": "closed"})
    print(f"Issue #{issue['number']} にコメントしました。")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=["open", "approval", "comment"])
    ap.add_argument("--draft", required=True)
    ap.add_argument("--file", help="comment のとき、この中身をコメントします")
    ap.add_argument("--close", action="store_true")
    args = ap.parse_args()

    draft = json.loads(pathlib.Path(args.draft).read_text(encoding="utf-8"))

    if args.command == "open":
        cmd_open(draft, args.draft)
    elif args.command == "approval":
        cmd_approval(draft)
    else:
        text = pathlib.Path(args.file).read_text(encoding="utf-8") if args.file else "（内容なし）"
        cmd_comment(draft, text, args.close)


if __name__ == "__main__":
    main()
