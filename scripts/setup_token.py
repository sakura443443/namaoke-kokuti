#!/usr/bin/env python3
"""はじめの一回だけ動かします。投稿に使う「鍵」を4つそろえるための道具です。

Meta の画面で取った短い有効期限のトークンを、期限のない長いトークンに交換し、
Facebook ページのID と Instagram のID もまとめて調べます。

  python3 scripts/setup_token.py

聞かれるのは3つです（セットアップ手順.md の 4 に、どこで取るかが書いてあります）。
  ・アプリID
  ・アプリシークレット
  ・ユーザーアクセストークン（短いもの）

★入力した値は画面に出ませんし、どのファイルにも保存しません。
　最後に表示される4つを、GitHub の Secrets に貼ってください。
"""

import getpass
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import meta_api  # noqa: E402


def ask(label, secret=True):
    value = (getpass.getpass(f"{label}: ") if secret else input(f"{label}: ")).strip()
    if not value:
        raise SystemExit(f"{label} が空でした。やり直してください。")
    return value


def main():
    print(__doc__)
    if "--help" in sys.argv or "-h" in sys.argv:
        return  # 説明だけ読みたいときは、ここで終わります
    app_id = ask("アプリID（数字）", secret=False)
    app_secret = ask("アプリシークレット（打っても画面には出ません）")
    short_token = ask("ユーザーアクセストークン（打っても画面には出ません）")

    print("\n1) 期限のない長いトークンに交換しています…")
    long_user = meta_api.get("oauth/access_token", {
        "grant_type": "fb_exchange_token",
        "client_id": app_id,
        "client_secret": app_secret,
        "fb_exchange_token": short_token,
    }, short_token)["access_token"]

    print("2) Facebook ページを探しています…")
    pages = meta_api.get("me/accounts", {"fields": "id,name,access_token"}, long_user).get("data", [])
    if not pages:
        raise SystemExit(
            "Facebook ページが1つも見つかりませんでした。\n"
            "セットアップ手順.md の 1（ページを作る）が済んでいるか、\n"
            "トークンを取るときに pages_show_list の許可を入れたかを確かめてください。"
        )

    if len(pages) == 1:
        page = pages[0]
    else:
        print("\n  どのページに投稿しますか？")
        for i, p in enumerate(pages, 1):
            print(f"    {i}. {p['name']}")
        page = pages[int(ask("  番号", secret=False)) - 1]

    print(f"3) 「{page['name']}」につながった Instagram を探しています…")
    linked = meta_api.get(page["id"], {"fields": "instagram_business_account{id,username}"},
                          page["access_token"]).get("instagram_business_account")
    if not linked:
        raise SystemExit(
            f"「{page['name']}」に Instagram がつながっていません。\n"
            "セットアップ手順.md の 2（プロアカウントに切り替えてページと連携）を先にどうぞ。"
        )

    print("\n" + "=" * 62)
    print("できました。次の4つを GitHub の Secrets に登録してください。")
    print("（登録のしかたは セットアップ手順.md の 5 にあります）")
    print("=" * 62)
    print(f"\nMETA_PAGE_ID\n  {page['id']}")
    print(f"\nIG_USER_ID\n  {linked['id']}      ← @{linked['username']}")
    print(f"\nMETA_PAGE_TOKEN\n  {page['access_token']}")
    print("\nMETA_PLACE_ID\n  → 次に scripts/find_location.py を動かすと出ます")
    print("\n" + "=" * 62)
    print("★ このトークンは、お店の投稿ができる鍵です。")
    print("　 人に見せたり、チャットに貼ったりしないでください。")
    print("　 この画面は、貼り終えたら閉じてください。")
    print("=" * 62)


if __name__ == "__main__":
    try:
        main()
    except meta_api.GraphError as e:
        raise SystemExit(f"\n❌ うまくいきませんでした。\n   {e.detail}")
