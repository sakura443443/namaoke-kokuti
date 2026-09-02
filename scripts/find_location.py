#!/usr/bin/env python3
"""「ミュージックカフェSAKURA」の場所ID を調べます。はじめの一回だけです。

この ID が、Instagram とFacebook の投稿に付く位置情報になります。

  META_PAGE_TOKEN='さっき取ったトークン' python3 scripts/find_location.py

見つからないときの探し方も、最後に表示します。
"""

import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import meta_api  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent


def main():
    token = os.environ.get("META_PAGE_TOKEN", "").strip()
    if not token:
        raise SystemExit(
            "META_PAGE_TOKEN が設定されていません。こう動かしてください:\n"
            "  META_PAGE_TOKEN='トークン' python3 scripts/find_location.py"
        )

    cfg = json.loads((ROOT / "data" / "config.json").read_text(encoding="utf-8"))
    query = cfg["shop"]["location_search_name"]

    # 日本語の「ミュージックカフェさくら」では出てきません。英字で探します。
    print(f"「{query}」で探しています…\n")
    try:
        found = meta_api.get("pages/search", {
            "q": query, "fields": "id,name,location", "limit": 10,
        }, token).get("data", [])
    except meta_api.GraphError as e:
        found = []
        print(f"⚠ 検索の機能が使えませんでした（{e.detail}）\n")

    for p in found:
        loc = p.get("location", {})
        where = "、".join(x for x in (loc.get("city"), loc.get("street")) if x)
        print(f"  ID {p['id']}   {p['name']}   {where or '（住所の登録なし）'}")

    if found:
        print("\n岐阜市・金園町 のものを選び、その ID を")
        print("GitHub の Secrets に META_PLACE_ID として登録してください。")
    else:
        print("見つかりませんでした。手で調べる方法もあります:\n")
        print("  1. Facebook で「MUSIC CAFE SAKURA」を検索し、お店の場所のページを開く")
        print("  2. そのページの「基本データ」→ 下のほうに出る「ページID」を控える")
        print("  3. その数字を META_PLACE_ID として登録する\n")
        print("※ 位置情報なしでも投稿はできます。空のままでも止まりません。")


if __name__ == "__main__":
    main()
