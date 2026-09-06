#!/usr/bin/env python3
"""予約投稿用に、何週間か先までの告知文をまとめて書き出します。

Meta の自動投稿が使えないあいだ、Business Suite に貼って予約するための道具です。
日付とメンバーの計算は自動なので、書き写す手間も間違いもありません。

  python3 scripts/export_manual.py            次の4回分
  python3 scripts/export_manual.py --weeks 8  次の8回分
  python3 scripts/export_manual.py --from 2026-09-06

出来上がるもの（予約投稿/ の中）:
  2026-09-09（水）.txt   その日の告知文（Instagram用・Facebook用）
  画像/                  貼り付ける画像4枚
  はりつけかた.txt       Business Suite での予約のしかた
"""

import argparse
import datetime as dt
import pathlib
import shutil
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_draft as bd  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "予約投稿"

HOWTO = """Business Suite で予約するとき

1. business.facebook.com を開く
2. 左の「コンテンツ」→「投稿を作成」
3. 投稿先で Facebookページ と Instagram の両方に ✓ を入れる
4. 画像/ の feed-1.jpg と feed-2.jpg を、この順番でアップロード
5. その日の .txt を開き、「── Instagram ──」の下を丸ごとコピーして貼る
   （Facebook にも同じ文でかまいません。DM の案内だけ違います）
6. 位置情報に「MUSIC CAFE SAKURA」を入れる
   ※日本語の「ミュージックカフェさくら」では出てきません
7. ホストの方のアカウントが分かっていれば、タグ付けする
8. 右下の「投稿日時を指定」→ その週の【金曜11:00】にする
9. 「予約する」を押す

ストーリーズは別に作ります。
「ストーリーズを作成」から 画像/story-1.jpg と story-2.jpg を上げます。
ストーリーズには本文も位置情報も付けられません（Meta の仕様です）。

ぜんぶ予約し終えたら、この月はもう何もしなくて大丈夫です。
"""


def when_line(date, today):
    """いつ投稿するかの案内。金曜が過ぎていたら、すぐ出すよう促します。"""
    friday = date - dt.timedelta(days=5)
    if friday < today:
        return f"★ 予約する日時：{friday}（金）は過ぎています → 【今すぐ投稿してください】"
    return f"★ 予約する日時：{friday}（金）11:00"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--weeks", type=int, default=4, help="何回分書き出すか（既定4）")
    ap.add_argument("--from", dest="start", help="この日を起点にする（YYYY-MM-DD）")
    args = ap.parse_args()

    today = dt.date.fromisoformat(args.start) if args.start else dt.date.today()

    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "画像").mkdir(parents=True)

    for name in ("feed-1.jpg", "feed-2.jpg", "story-1.jpg", "story-2.jpg"):
        shutil.copy2(ROOT / "images" / name, OUT / "画像" / name)

    (OUT / "はりつけかた.txt").write_text(HOWTO, encoding="utf-8")

    cursor = today
    for _ in range(args.weeks):
        draft = bd.build(cursor)
        date = dt.date.fromisoformat(draft["開催日"])

        body = [
            f"{date.year}年{date.month}月{date.day}日（水）の生バンドカラオケ",
            f"第{draft['第何週']}水曜　{bd.members_line(draft['メンバー'])}",
            "",
            when_line(date, today),
            "",
            "── Instagram ──", "", draft["captions"]["instagram"], "",
            "── Facebook ──", "", draft["captions"]["facebook"], "",
        ]
        miss = draft["アカウント未登録"]["instagram"]
        if miss:
            body.append(f"※ アカウント未登録のためタグ付けできない方：{'、'.join(miss)}")

        (OUT / f"{date}（水）.txt").write_text("\n".join(body) + "\n", encoding="utf-8")
        print(f"  {date}（水）  第{draft['第何週']}水曜  {bd.members_line(draft['メンバー'])}")

        cursor = date  # 次の水曜へ

    print(f"\n{args.weeks}回分を書き出しました → {OUT.name}/")


if __name__ == "__main__":
    main()
