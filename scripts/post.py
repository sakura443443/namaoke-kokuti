#!/usr/bin/env python3
"""下書きを、Instagram と Facebook に投稿します。

  python3 scripts/post.py --draft drafts/2026-09-09.json --dry-run
      1回も投稿せず、何をどこへ出すかだけ表示します。

  python3 scripts/post.py --draft drafts/2026-09-09.json --only story
      ストーリーズだけ投稿します。24時間で消えるので、最初の試しに向いています。

  python3 scripts/post.py --draft drafts/2026-09-09.json
      ぜんぶ投稿します。

必要な環境変数（GitHub の Secrets に入れます）:
  META_PAGE_TOKEN  長期ページアクセストークン
  META_PAGE_ID     Facebook ページのID
  IG_USER_ID       Instagram のビジネスアカウントID
  META_PLACE_ID    「ミュージックカフェSAKURA」の場所ID（Instagram・Facebook 共通）
"""

import argparse
import datetime as dt
import json
import os
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import meta_api  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Instagram は画像をあちらのサーバーが取りに行くため、
# 「取り込み終わったか」を待つ必要があります。
POLL_INTERVAL = 4
POLL_LIMIT = 30  # 4秒 × 30 = 最大2分


class Poster:
    def __init__(self, cfg, draft, env, dry_run=False):
        self.cfg = cfg
        self.draft = draft
        self.env = env
        self.dry_run = dry_run
        self.results = []

    # ── 共通の道具 ────────────────────────────────────────────

    def image_urls(self, kind):
        base = self.cfg["image_base_url"].rstrip("/")
        return [f"{base}/{name}" for name in self.cfg["images"][kind]]

    def log(self, msg):
        print(msg, flush=True)

    def record(self, step, ok, detail):
        self.results.append({"step": step, "ok": ok, "detail": detail})
        self.log(f"  {'✅' if ok else '❌'} {step}: {detail}")

    def graph_post(self, path, params):
        if self.dry_run:
            self.log(f"  [下書き確認] POST {path}")
            for k, v in params.items():
                v = str(v)
                # 本文は省略しません。ここを読んで文面を確かめてもらうためです。
                if k not in ("caption", "message") and len(v) > 200:
                    v = v[:200] + " …"
                self.log(f"      {k} = {v}")
            return {"id": f"DRYRUN-{path.replace('/', '-')}"}
        return meta_api.post(path, params, self.env["token"])

    def wait_container(self, container_id):
        """Instagram が画像を取り込み終わるまで待ちます。"""
        if self.dry_run:
            return
        for _ in range(POLL_LIMIT):
            res = meta_api.get(container_id, {"fields": "status_code,status"}, self.env["token"])
            code = res.get("status_code")
            if code == "FINISHED":
                return
            if code == "ERROR":
                raise meta_api.GraphError(
                    container_id, {"error": {"message": res.get("status", "取り込みに失敗しました")}}
                )
            time.sleep(POLL_INTERVAL)
        raise meta_api.GraphError(container_id, {"error": {"message": "取り込みが2分で終わりませんでした"}})

    # ── Instagram ────────────────────────────────────────────

    def instagram_feed(self):
        ig = self.env["ig_user_id"]
        caption = self.draft["captions"]["instagram"]
        tags = self.draft.get("user_tags") or []

        def build(with_tags):
            children = []
            for url in self.image_urls("feed"):
                params = {"image_url": url, "is_carousel_item": "true"}
                if with_tags and tags:
                    params["user_tags"] = json.dumps(tags, ensure_ascii=False)
                child = self.graph_post(f"{ig}/media", params)["id"]
                self.wait_container(child)
                children.append(child)

            parent_params = {
                "media_type": "CAROUSEL",
                "children": ",".join(children),
                "caption": caption,
            }
            if self.env.get("place_id"):
                parent_params["location_id"] = self.env["place_id"]
            parent = self.graph_post(f"{ig}/media", parent_params)["id"]
            self.wait_container(parent)
            return self.graph_post(f"{ig}/media_publish", {"creation_id": parent})["id"]

        try:
            post_id = build(with_tags=True)
        except meta_api.GraphError as e:
            if not tags:
                raise
            # タグ付けは、相手が非公開だったりタグを許可していないと投稿ごと失敗します。
            # 本文の @メンション は残るので、タグ無しで投稿し直します。
            self.log(f"  ⚠ タグ付きで失敗したため、タグ無しで投稿し直します（{e.detail}）")
            post_id = build(with_tags=False)
            self.record("Instagram フィード（タグ無しで再投稿）", True, post_id)
            return

        self.record("Instagram フィード", True, post_id)

    def instagram_story(self):
        ig = self.env["ig_user_id"]
        for i, url in enumerate(self.image_urls("story"), 1):
            cid = self.graph_post(f"{ig}/media", {"image_url": url, "media_type": "STORIES"})["id"]
            self.wait_container(cid)
            post_id = self.graph_post(f"{ig}/media_publish", {"creation_id": cid})["id"]
            self.record(f"Instagram ストーリー {i}枚目", True, post_id)

    # ── Facebook ─────────────────────────────────────────────

    def _upload_unpublished(self, url):
        """あとで使うために、公開しない写真としてアップロードします。"""
        return self.graph_post(f"{self.env['page_id']}/photos", {"url": url, "published": "false"})["id"]

    def facebook_feed(self):
        page = self.env["page_id"]
        photo_ids = [self._upload_unpublished(u) for u in self.image_urls("feed")]

        params = {"message": self.draft["captions"]["facebook"]}
        for i, pid in enumerate(photo_ids):
            params[f"attached_media[{i}]"] = json.dumps({"media_fbid": pid})
        if self.env.get("place_id"):
            params["place"] = self.env["place_id"]

        post_id = self.graph_post(f"{page}/feed", params)["id"]
        self.record("Facebook フィード", True, post_id)

    def facebook_story(self):
        page = self.env["page_id"]
        for i, url in enumerate(self.image_urls("story"), 1):
            photo_id = self._upload_unpublished(url)
            res = self.graph_post(f"{page}/photo_stories", {"photo_id": photo_id})
            self.record(f"Facebook ストーリー {i}枚目", True, res.get("post_id") or res.get("id", "投稿しました"))

    # ── 進行 ─────────────────────────────────────────────────

    def run(self, only):
        steps = [
            ("instagram_feed", "Instagram フィード", self.instagram_feed),
            ("instagram_story", "Instagram ストーリー", self.instagram_story),
            ("facebook_feed", "Facebook フィード", self.facebook_feed),
            ("facebook_story", "Facebook ストーリー", self.facebook_story),
        ]
        for key, label, fn in steps:
            if not self.cfg["post_to"].get(key, False):
                self.log(f"— {label}：config.json で off になっています")
                continue
            if only and only not in key:
                continue
            self.log(f"\n— {label}")
            try:
                fn()
            except meta_api.GraphError as e:
                self.record(label, False, e.detail)
        return self.results


def summary(draft, results, dry_run):
    d = dt.date.fromisoformat(draft["開催日"])
    head = "下書き確認（投稿していません）" if dry_run else "投稿結果"
    lines = [f"### {head} — {d.month}/{d.day}（水）の告知", ""]
    for r in results:
        lines.append(f"- {'✅' if r['ok'] else '❌'} {r['step']} … {r['detail']}")
    miss = draft["アカウント未登録"]["instagram"]
    if miss:
        lines += ["", f"> ℹ️ アカウント未登録のためタグ付けを飛ばした方：{'、'.join(miss)}"]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="下書きを Instagram と Facebook に投稿します")
    ap.add_argument("--draft", required=True, help="build_draft.py が作った json")
    ap.add_argument("--dry-run", action="store_true", help="投稿せず、内容だけ表示する")
    ap.add_argument("--only", choices=["feed", "story", "instagram", "facebook"],
                    help="一部だけ投稿する（story は24時間で消えるので試しに向きます）")
    ap.add_argument("--approval", help="承認コメントで本文が差し替えられていたら、そちらを使う")
    args = ap.parse_args()

    cfg = json.loads((ROOT / "data" / "config.json").read_text(encoding="utf-8"))
    draft = json.loads(pathlib.Path(args.draft).read_text(encoding="utf-8"))

    # さくらさんが承認コメントで本文を直していたら、そちらを使います。
    if args.approval and pathlib.Path(args.approval).exists():
        override = json.loads(pathlib.Path(args.approval).read_text(encoding="utf-8")).get("override") or {}
        for platform, text in override.items():
            draft["captions"][platform] = text
            print(f"本文を差し替えました（{platform}）", file=sys.stderr)

    env = {
        "token": os.environ.get("META_PAGE_TOKEN", ""),
        "page_id": os.environ.get("META_PAGE_ID", ""),
        "ig_user_id": os.environ.get("IG_USER_ID", ""),
        "place_id": os.environ.get("META_PLACE_ID", ""),
    }
    if args.dry_run:
        # 表示を読みやすくするための仮の値です。通信はしません。
        env = {k: (v or f"<{k}>") for k, v in env.items()}
    else:
        missing = [k for k in ("token", "page_id", "ig_user_id") if not env[k]]
        if missing:
            raise SystemExit(
                "次の設定が足りません: " + "、".join(missing) +
                "\nセットアップ手順.md の 4 をご覧ください。"
            )
        if not env["place_id"]:
            print("⚠ META_PLACE_ID が空です。位置情報なしで投稿します。", file=sys.stderr)

    if cfg["image_base_url"].startswith("https://raw.githubusercontent.com/YOUR-GITHUB-NAME"):
        msg = "data/config.json の image_base_url が、まだ見本のままです。GitHub の公開URLに書き換えてください。"
        if args.dry_run:
            print(f"⚠ {msg}", file=sys.stderr)
        else:
            raise SystemExit(msg)

    poster = Poster(cfg, draft, env, dry_run=args.dry_run)
    results = poster.run(args.only)

    text = summary(draft, results, args.dry_run)
    print("\n" + text)

    if not args.dry_run:
        log_path = ROOT / "logs" / f"{draft['開催日']}.json"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(
            json.dumps({"投稿日時": dt.datetime.now().isoformat(timespec="seconds"),
                        "開催日": draft["開催日"], "結果": results},
                       ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # GitHub Actions から Issue にそのまま貼れるように書き出します
    out = os.environ.get("SUMMARY_FILE")
    if out:
        pathlib.Path(out).write_text(text + "\n", encoding="utf-8")

    if any(not r["ok"] for r in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
