#!/usr/bin/env python3
"""次回の水曜を求め、その週のホストを引いて、告知文の下書きを組み立てます。

投稿はしません。作るのは drafts/YYYY-MM-DD.json だけです。

  python3 scripts/build_draft.py --show              いまの日付で作って中身を表示
  python3 scripts/build_draft.py --date 2026-09-03   その日に動いた想定で作る
"""

import argparse
import datetime as dt
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
WEEKDAY_JA = "月火水木金土日"
WEDNESDAY = 2  # 月曜が 0


def load(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


def next_wednesday(today):
    """今日より後の、いちばん近い水曜日を返します。

    木曜に動けば6日後、金曜に動けば5日後。どちらも同じ「翌週の水曜」です。
    水曜に動いたときは、当日ではなく1週間後を指します。
    """
    days = (WEDNESDAY - today.weekday()) % 7
    if days == 0:
        days = 7
    return today + dt.timedelta(days=days)


def nth_wednesday(date):
    """その日が、その月の第何水曜かを返します（1〜5）。"""
    return (date.day - 1) // 7 + 1


def hosts_for(date, hosts_table):
    n = nth_wednesday(date)
    key = f"week{n}"
    if key not in hosts_table:
        raise SystemExit(
            f"{date} は第{n}水曜ですが、data/hosts.json に {key} がありません。"
        )
    return n, hosts_table[key]


def format_date(date):
    return f"{date.month}/{date.day}（{WEEKDAY_JA[date.weekday()]}）"


def members_line(members):
    return "／".join(f"{m['name']}（{m['instrument']}）" for m in members)


def mention_line(members, platform):
    key = "ig" if platform == "instagram" else "fb"
    handles = [m[key].lstrip("@") for m in members if m.get(key, "").strip()]
    return " ".join(f"@{h}" for h in handles)


def unregistered(members, platform):
    key = "ig" if platform == "instagram" else "fb"
    return [m["name"] for m in members if not m.get(key, "").strip()]


def render(platform, date, members, cfg):
    shop, ev = cfg["shop"], cfg["event"]

    lines = [
        "毎週水曜日は、完全生演奏の「生バンドカラオケ」！",
        "プロのミュージシャンが、あなたの歌を生演奏でバックアップします。",
        "",
        f"次回は {format_date(date)}",
        "ホストミュージシャン",
        members_line(members),
    ]

    mentions = mention_line(members, platform)
    if mentions:
        lines.append(mentions)

    lines += [
        "",
        f"開場{ev['open']}／{ev['start']}〜{ev['end']}",
        f"入場料 {ev['entry_fee']}／歌唱料 {ev['song_fee']}",
        "",
        f"{ev['repertoire']}のレパートリーをご用意しています。手ぶらでOK。",
        "聴くだけの方も、楽器でのご参加も大歓迎です。",
        "初めてでも安心😊 さくらママもサポートします😉",
        "",
        "私と一緒に、音楽でワクワクしましょう🌸🎶",
        "",
        "🎹🎤 生バンドカラオケの店",
        f"📍 {shop['name']}",
        shop["address"],
    ]

    # 電話番号と「ご予約お待ちしてます。」は、さくらさんのご指示で入れません
    #（2026-09-02）。毎週の定例なので、予約を促す形にはしていません。
    lines += ["", " ".join(cfg["hashtags"][platform])]
    return "\n".join(lines)


def user_tags(members):
    """Instagram のタグ付け位置。写真の中の band が写っているあたりに、横に並べます。

    x は左からの割合、y は上からの割合（0.0〜1.0）です。
    """
    tagged = [m for m in members if m.get("ig", "").strip()]
    return [
        {"username": m["ig"].lstrip("@"), "x": round((i + 1) / (len(tagged) + 1), 3), "y": 0.62}
        for i, m in enumerate(tagged)
    ]


def build(today):
    cfg, hosts_table = load("config.json"), load("hosts.json")
    date = next_wednesday(today)
    week, members = hosts_for(date, hosts_table)

    return {
        "生成日": today.isoformat(),
        "開催日": date.isoformat(),
        "第何週": week,
        "メンバー": members,
        "captions": {
            "instagram": render("instagram", date, members, cfg),
            "facebook": render("facebook", date, members, cfg),
        },
        "user_tags": user_tags(members),
        "アカウント未登録": {
            "instagram": unregistered(members, "instagram"),
            "facebook": unregistered(members, "facebook"),
        },
    }


def show(draft):
    d = dt.date.fromisoformat(draft["開催日"])
    print(f"開催日　　: {format_date(d)}  （第{draft['第何週']}水曜）")
    print(f"メンバー　: {members_line(draft['メンバー'])}")
    tags = draft["user_tags"]
    print(f"タグ付け　: {', '.join('@' + t['username'] for t in tags) if tags else '（なし）'}")
    miss = draft["アカウント未登録"]["instagram"]
    if miss:
        print(f"未登録　　: {'、'.join(miss)}　← data/hosts.json の ig 欄が空です")
    for name, key in (("Instagram", "instagram"), ("Facebook", "facebook")):
        print(f"\n─── {name} ───\n{draft['captions'][key]}")


def main():
    ap = argparse.ArgumentParser(description="告知文の下書きを作ります（投稿はしません）")
    ap.add_argument("--date", help="この日に動いた想定にする（YYYY-MM-DD）")
    ap.add_argument("--show", action="store_true", help="中身を画面に出す")
    ap.add_argument("--out", default=None, help="書き出し先（既定 drafts/開催日.json）")
    ap.add_argument("--path-only", action="store_true",
                    help="書き出さず、下書きファイルの場所だけを出す（金曜の投稿で使います）")
    args = ap.parse_args()

    today = dt.date.fromisoformat(args.date) if args.date else dt.date.today()
    draft = build(today)

    out = pathlib.Path(args.out) if args.out else ROOT / "drafts" / f"{draft['開催日']}.json"

    if args.path_only:
        print(out.relative_to(ROOT))
        return

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(draft, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.show:
        show(draft)
    print(f"\n書き出しました: {out.relative_to(ROOT)}", file=sys.stderr)

    # GitHub Actions から、次の手順にファイルの場所を渡します
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a", encoding="utf-8") as f:
            f.write(f"draft={out.relative_to(ROOT)}\n")


if __name__ == "__main__":
    main()
